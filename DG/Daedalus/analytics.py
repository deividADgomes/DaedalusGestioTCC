"""
Motor analítico do dashboard (BI) do Daedalus Gestio.

Indicador central: NFF (No Fault Found), a peça que o técnico de campo trocou por
"defeituosa" e que a bancada constatou FUNCIONAL (Triagem.status == 1).

Técnicas aplicadas:
- carta de controle p / funnel plot (limites de 2 e 3 sigma por volume) para achar técnicos fora do padrão;
- intervalo de confiança de Wilson (95%) nas taxas, para não punir quem tem poucas triagens;
- comparação automática com o período anterior de mesmo tamanho;
- Pareto dos defeitos, matriz de diagnósticos trocados, reincidência por número de série;
- insights gerados por regras, com ação de filtro (drill-down).
"""
import csv
import io
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Count, F, Max, Min, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, Trim, Upper
from django.utils import timezone

from .models import Empresa, Equipamento, Funcionario, Tecnico, Triagem

NFF = 1          # status 1: peça funcional (No Fault Found)
DEFEITO = 2      # status 2: defeito confirmado na bancada
REFERENCIA_NFF = (20.0, 50.0)   # faixa de NFF reportada na literatura de eletrônicos (%)
MIN_AMOSTRA = 5                 # abaixo disso o técnico não é classificado
Z95 = 1.96


class FiltroInvalido(ValueError):
    pass


# ------------------------------------------------------------------
# Utilidades estatísticas e de texto
# ------------------------------------------------------------------
def normalizar_texto(valor):
    """Minúsculas, sem acentos nem pontuação: base da comparação diagnóstico x constatação."""
    if not valor:
        return ''
    sem_acento = ''.join(c for c in unicodedata.normalize('NFD', valor) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', sem_acento.lower()).strip()


def _limpar(valor, limite=60):
    texto = ' '.join((valor or '').split())
    return texto if len(texto) <= limite else texto[:limite - 1] + '…'


def _pct(k, n):
    return round(100.0 * k / n, 1) if n else 0.0


def intervalo_wilson(k, n, z=Z95):
    """Intervalo de confiança de Wilson para uma proporção (retorna fração entre 0 e 1)."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - margem), min(1.0, centro + margem)


def classificar(p, p_medio, n):
    """
    Carta de controle p: compara a taxa do grupo com a média usando limites de sigma que
    dependem do volume (n). Retorna (status, z).
    status: critico (z >= 3), atencao (z >= 2), destaque (z <= -2), normal ou insuficiente.
    """
    if n < MIN_AMOSTRA:
        return 'insuficiente', None
    if p_medio <= 0 or p_medio >= 1:
        return 'normal', 0.0
    sigma = math.sqrt(p_medio * (1 - p_medio) / n)
    z = (p - p_medio) / sigma
    if z >= 3:
        return 'critico', round(z, 2)
    if z >= 2:
        return 'atencao', round(z, 2)
    if z <= -2:
        return 'destaque', round(z, 2)
    return 'normal', round(z, 2)


def _comparar_diagnostico(diag, const):
    """Retorna (comparavel, diverge)."""
    a, b = normalizar_texto(diag), normalizar_texto(const)
    if not a or not b:
        return False, False
    return True, a != b


# ------------------------------------------------------------------
# Filtros
# ------------------------------------------------------------------
def _data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        raise FiltroInvalido('Datas inválidas. Use o formato AAAA-MM-DD.')


def _inteiro(valor):
    if valor in (None, ''):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise FiltroInvalido('Filtro inválido.')


class Filtros:
    def __init__(self, params):
        self.inicio = _data(params.get('inicio'))
        self.fim = _data(params.get('fim'))
        if self.inicio and self.fim and self.inicio > self.fim:
            raise FiltroInvalido('A data inicial não pode ser maior que a final.')
        self.tecnico = _inteiro(params.get('tecnico'))
        self.prestadora = _inteiro(params.get('prestadora'))
        self.cliente = _inteiro(params.get('cliente'))
        self.equipamento = _inteiro(params.get('equipamento'))
        self.analista = _inteiro(params.get('analista'))
        self.estado = (params.get('estado') or '').strip().upper()[:2] or None
        self.comparar = params.get('comparar', '1') != '0'

    def queryset(self, inicio=None, fim=None):
        qs = Triagem.objects.all()
        if inicio:
            qs = qs.filter(data_triagem__date__gte=inicio)
        if fim:
            qs = qs.filter(data_triagem__date__lte=fim)
        if self.tecnico:
            qs = qs.filter(tecnico_id=self.tecnico)
        if self.prestadora:
            qs = qs.filter(tecnico__empresa_id=self.prestadora)
        if self.cliente:
            qs = qs.filter(cliente_id=self.cliente)
        if self.equipamento:
            qs = qs.filter(equipamento_id=self.equipamento)
        if self.analista:
            qs = qs.filter(analista_triagem_id=self.analista)
        if self.estado:
            qs = qs.filter(estado__iexact=self.estado)
        return qs

    def periodo_anterior(self):
        """Período imediatamente anterior, com o mesmo número de dias."""
        if not (self.comparar and self.inicio and self.fim):
            return None
        dias = (self.fim - self.inicio).days + 1
        fim_ant = self.inicio - timedelta(days=1)
        return fim_ant - timedelta(days=dias - 1), fim_ant

    def como_dict(self):
        return {
            'inicio': self.inicio.isoformat() if self.inicio else None,
            'fim': self.fim.isoformat() if self.fim else None,
            'tecnico': self.tecnico, 'prestadora': self.prestadora, 'cliente': self.cliente,
            'equipamento': self.equipamento, 'analista': self.analista, 'estado': self.estado,
            'comparar': self.comparar,
        }


# ------------------------------------------------------------------
# Blocos de cálculo
# ------------------------------------------------------------------
def _agregar(qs):
    """Totais, NFF e divergência de diagnóstico de um recorte."""
    base = qs.aggregate(
        total=Count('id_triagem'),
        nff=Count('id_triagem', filter=Q(status=NFF)),
        defeitos=Count('id_triagem', filter=Q(status=DEFEITO)),
    )
    comparaveis = divergentes = 0
    if base['total']:
        for diag, const in qs.values_list('defeito_tecnico', 'defeito_constatado'):
            comparavel, diverge = _comparar_diagnostico(diag, const)
            comparaveis += comparavel
            divergentes += diverge
    base.update({
        'taxa_nff': _pct(base['nff'], base['total']),
        'comparaveis': comparaveis,
        'divergentes': divergentes,
        'pct_div': _pct(divergentes, comparaveis),
    })
    return base


def _kpi(atual, anterior):
    kpi = {'valor': atual, 'anterior': anterior, 'delta': None, 'delta_pct': None}
    if anterior is not None:
        kpi['delta'] = round(atual - anterior, 1)
        kpi['delta_pct'] = round(100.0 * (atual - anterior) / anterior, 1) if anterior else None
    return kpi


def _granularidade(ini, fim):
    dias = (fim - ini).days + 1
    if dias <= 45:
        return 'dia'
    if dias <= 200:
        return 'semana'
    return 'mes'


def _inicio_bucket(d, gran):
    if gran == 'dia':
        return d
    if gran == 'semana':
        return d - timedelta(days=d.weekday())
    return d.replace(day=1)


def _proximo_bucket(d, gran):
    if gran == 'dia':
        return d + timedelta(days=1)
    if gran == 'semana':
        return d + timedelta(days=7)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _rotulo(d, gran):
    return d.strftime('%m/%Y') if gran == 'mes' else d.strftime('%d/%m')


def _serie_temporal(qs, ini, fim):
    gran = _granularidade(ini, fim)
    trunc = {'dia': TruncDay, 'semana': TruncWeek, 'mes': TruncMonth}[gran]
    linhas = (qs.annotate(periodo=trunc('data_triagem')).values('periodo')
                .annotate(total=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
                .order_by('periodo'))
    por_bucket = {}
    for linha in linhas:
        p = linha['periodo']
        p = p.date() if isinstance(p, datetime) else p
        por_bucket[p] = linha

    pontos = []
    atual = _inicio_bucket(ini, gran)
    for _ in range(400):
        if atual > fim:
            break
        linha = por_bucket.get(atual)
        total = linha['total'] if linha else 0
        nff = linha['nff'] if linha else 0
        pontos.append({
            'rotulo': _rotulo(atual, gran), 'inicio': atual.isoformat(),
            'total': total, 'nff': nff, 'taxa_nff': _pct(nff, total) if total else None,
        })
        atual = _proximo_bucket(atual, gran)
    return {'granularidade': gran, 'pontos': pontos}


def _tecnicos(qs, p_medio):
    linhas = (qs.values('tecnico_id', 'tecnico__nome', 'tecnico__empresa__razao_social')
                .annotate(total=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
                .order_by('-total'))
    divergencias = Counter()
    for tec_id, diag, const in qs.values_list('tecnico_id', 'defeito_tecnico', 'defeito_constatado'):
        if _comparar_diagnostico(diag, const)[1]:
            divergencias[tec_id] += 1

    resultado = []
    for l in linhas:
        n, k = l['total'], l['nff']
        p = k / n if n else 0
        inf, sup = intervalo_wilson(k, n)
        status, z = classificar(p, p_medio, n)
        resultado.append({
            'id': l['tecnico_id'], 'nome': l['tecnico__nome'],
            'prestadora': l['tecnico__empresa__razao_social'],
            'total': n, 'nff': k, 'acertos': n - k,
            'taxa_nff': _pct(k, n), 'taxa_acerto': _pct(n - k, n),
            'ic_inf': round(100 * inf, 1), 'ic_sup': round(100 * sup, 1),
            'divergencias': divergencias.get(l['tecnico_id'], 0),
            'z': z, 'status': status,
        })
    return resultado


def _por_dimensao(qs, id_expr, nome_expr, p_medio, limite=10):
    linhas = (qs.values(ident=F(id_expr), nome=F(nome_expr))
                .annotate(total=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
                .order_by('-total')[:limite])
    itens = []
    for l in linhas:
        n, k = l['total'], l['nff']
        inf, sup = intervalo_wilson(k, n)
        status, z = classificar(k / n if n else 0, p_medio, n)
        itens.append({
            'id': l['ident'], 'nome': l['nome'], 'total': n, 'nff': k, 'acertos': n - k,
            'taxa_nff': _pct(k, n), 'ic_inf': round(100 * inf, 1), 'ic_sup': round(100 * sup, 1),
            'z': z, 'status': status,
        })
    return itens


def _modelos(qs, limite=30):
    linhas = (qs.values(ident=F('equipamento_id'), pn=F('equipamento__pn'), modelo=F('equipamento__modelo'))
                .annotate(total=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
                .order_by('-total')[:limite])
    return [{'id': l['ident'], 'pn': l['pn'], 'modelo': l['modelo'], 'total': l['total'],
             'nff': l['nff'], 'taxa_nff': _pct(l['nff'], l['total'])} for l in linhas]


def _pecas(qs, limite=10):
    """Peças do catálogo mais trocadas, com a parcela que a bancada achou funcional (troca desnecessária)."""
    base = qs.filter(peca_trocada__isnull=False)
    linhas = (base.values(ident=F('peca_trocada_id'), pn=F('peca_trocada__part_number'), descricao=F('peca_trocada__descricao'))
                  .annotate(trocas=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
                  .order_by('-trocas', 'pn')[:limite])
    itens = [{'id': l['ident'], 'part_number': l['pn'], 'descricao': l['descricao'], 'trocas': l['trocas'],
              'nff': l['nff'], 'taxa_nff': _pct(l['nff'], l['trocas'])} for l in linhas]
    total = qs.count()
    com_peca = base.count()
    return {'itens': itens, 'com_peca': com_peca, 'sem_peca': total - com_peca}


def _pareto_defeitos(qs):
    confirmados = qs.filter(status=DEFEITO)
    contagem, exemplos = Counter(), defaultdict(Counter)
    for texto in confirmados.values_list('defeito_constatado', flat=True):
        chave = normalizar_texto(texto)
        if not chave:
            continue
        contagem[chave] += 1
        exemplos[chave][_limpar(texto)] += 1

    total = sum(contagem.values())
    itens, acumulado = [], 0
    for chave, qtd in contagem.most_common(10):
        acumulado += qtd
        itens.append({
            'rotulo': exemplos[chave].most_common(1)[0][0], 'qtd': qtd,
            'acumulado_pct': round(100.0 * acumulado / total, 1),
        })
    return {'itens': itens, 'total': total, 'sem_registro': confirmados.count() - total}


def _transicoes(qs):
    """Diagnósticos do técnico que a bancada contradisse, do mais frequente ao menos."""
    pares, rotulos, comparaveis, divergentes = Counter(), {}, 0, 0
    for diag, const in qs.values_list('defeito_tecnico', 'defeito_constatado'):
        comparavel, diverge = _comparar_diagnostico(diag, const)
        comparaveis += comparavel
        if diverge:
            chave = (normalizar_texto(diag), normalizar_texto(const))
            pares[chave] += 1
            rotulos[chave] = (_limpar(diag, 50), _limpar(const, 50))
            divergentes += 1
    itens = [{'diagnostico': rotulos[c][0], 'constatado': rotulos[c][1], 'qtd': q,
              'pct': _pct(q, divergentes)} for c, q in pares.most_common(8)]
    return {'itens': itens, 'divergentes': divergentes, 'comparaveis': comparaveis,
            'pct_div': _pct(divergentes, comparaveis)}


def _reincidencia(qs, total):
    grupos = (qs.exclude(sn='').annotate(sn_n=Upper(Trim('sn'))).values('sn_n')
                .annotate(vezes=Count('id_triagem'), ultima=Max('data_triagem'), modelo=Max('equipamento__modelo'))
                .filter(vezes__gt=1).order_by('-vezes', '-ultima'))
    lista = list(grupos)
    triagens = sum(g['vezes'] for g in lista)
    return {
        'series': len(lista), 'triagens': triagens, 'pct': _pct(triagens, total),
        'itens': [{'sn': g['sn_n'], 'vezes': g['vezes'], 'modelo': g['modelo'],
                   'ultima': timezone.localtime(g['ultima']).strftime('%d/%m/%Y')} for g in lista[:8]],
    }


def _recentes(qs, limite=15):
    itens = []
    for t in qs.select_related('tecnico', 'cliente', 'equipamento').order_by('-data_triagem', '-id_triagem')[:limite]:
        itens.append({
            'id': t.id_triagem, 'data': timezone.localtime(t.data_triagem).strftime('%d/%m/%Y %H:%M'),
            'ticket': t.n_ticket, 'sn': t.sn, 'tecnico': t.tecnico.nome, 'cliente': t.cliente.razao_social,
            'modelo': t.equipamento.modelo, 'status': t.status,
            'divergente': _comparar_diagnostico(t.defeito_tecnico, t.defeito_constatado)[1],
        })
    return itens


def _opcoes():
    return {
        'tecnicos': [{'id': t['id_tecnico'], 'nome': t['nome']} for t in Tecnico.objects.order_by('nome').values('id_tecnico', 'nome')],
        'prestadoras': [{'id': e['id_empresa'], 'nome': e['razao_social']} for e in Empresa.objects.filter(tipo=1).order_by('razao_social').values('id_empresa', 'razao_social')],
        'clientes': [{'id': e['id_empresa'], 'nome': e['razao_social']} for e in Empresa.objects.filter(tipo=2).order_by('razao_social').values('id_empresa', 'razao_social')],
        'estados': sorted({(e or '').upper() for e in Triagem.objects.values_list('estado', flat=True).distinct() if e}),
        'equipamentos': [{'id': e['id_equipamento'], 'nome': f"{e['modelo']} ({e['pn']})"} for e in Equipamento.objects.order_by('modelo').values('id_equipamento', 'modelo', 'pn')],
        'analistas': [{'id': f['id_funcionario'], 'nome': f['nome']} for f in Funcionario.objects.filter(triagens_efetuadas__isnull=False).distinct().order_by('nome').values('id_funcionario', 'nome')],
    }


# ------------------------------------------------------------------
# Insights automáticos (regras)
# ------------------------------------------------------------------
_PRIORIDADE = {'critico': 0, 'atencao': 1, 'info': 2, 'positivo': 3}


def _insights(res, ant, tecnicos, dimensoes, modelos, transicoes, reinc, serie, sem_constatado_pct):
    itens = []

    def add(nivel, titulo, texto, filtro=None):
        itens.append({'nivel': nivel, 'titulo': titulo, 'texto': texto, 'filtro': filtro})

    total, taxa = res['total'], res['taxa_nff']
    ref_min, ref_max = REFERENCIA_NFF

    # 1. NFF global frente à faixa de referência
    if total >= 10:
        if taxa > ref_max:
            add('critico', 'NFF acima da faixa de referência',
                f"{taxa}% das peças trocadas estavam funcionais. A literatura de eletrônicos reporta {ref_min:.0f}% a {ref_max:.0f}%.")
        elif taxa > ref_min:
            add('atencao', 'NFF dentro da faixa, mas alto',
                f"{taxa}% das peças trocadas estavam funcionais (referência da literatura: {ref_min:.0f}% a {ref_max:.0f}%).")
        else:
            add('positivo', 'NFF abaixo da faixa de referência',
                f"Apenas {taxa}% das peças trocadas estavam funcionais, abaixo dos {ref_min:.0f}% da literatura.")

    # 2. Variação contra o período anterior
    if ant and ant['total'] >= 10 and total >= 10:
        delta = round(taxa - ant['taxa_nff'], 1)
        if delta >= 5:
            add('critico' if delta >= 10 else 'atencao', 'NFF subiu no período',
                f"A taxa foi de {ant['taxa_nff']}% para {taxa}% ({delta:+.1f} p.p.) em relação ao período anterior.")
        elif delta <= -5:
            add('positivo', 'NFF caiu no período',
                f"A taxa foi de {ant['taxa_nff']}% para {taxa}% ({delta:+.1f} p.p.) em relação ao período anterior.")
        if ant['total'] and abs(total - ant['total']) / ant['total'] >= 0.3:
            variacao = round(100.0 * (total - ant['total']) / ant['total'])
            add('info', 'Volume de triagens mudou',
                f"{total} triagens contra {ant['total']} no período anterior ({variacao:+d}%).")

    # 3. Técnicos fora do limite de controle
    criticos = sorted([t for t in tecnicos if t['status'] == 'critico'], key=lambda t: -t['z'])
    atencao = sorted([t for t in tecnicos if t['status'] == 'atencao'], key=lambda t: -t['z'])
    pior = (criticos or atencao or [None])[0]
    if pior:
        outros = len(criticos) + len(atencao) - 1
        extra = f" Mais {outros} técnico(s) também fora do padrão." if outros > 0 else ''
        add('critico' if criticos else 'atencao', f"{pior['nome']} fora do limite de controle",
            f"{pior['taxa_nff']}% de NFF em {pior['total']} triagens, contra {taxa}% da média (z = {pior['z']}).{extra}",
            {'tecnico': pior['id']})
    destaque = sorted([t for t in tecnicos if t['status'] == 'destaque' and t['total'] >= 10], key=lambda t: t['z'])
    if destaque:
        melhor = destaque[0]
        add('positivo', f"{melhor['nome']} se destaca",
            f"{melhor['taxa_nff']}% de NFF em {melhor['total']} triagens, bem abaixo da média de {taxa}%.",
            {'tecnico': melhor['id']})

    # 4. Concentração de NFF por modelo
    nff_total = res['nff']
    if nff_total >= 5 and modelos:
        topo = max(modelos, key=lambda m: m['nff'])
        participacao = _pct(topo['nff'], nff_total)
        if participacao >= 25 and topo['nff'] >= 3:
            add('atencao', f"{topo['modelo']} concentra o NFF",
                f"{participacao}% de todas as peças funcionais trocadas são deste modelo ({topo['nff']} de {nff_total}).",
                {'equipamento': topo['id']})

    # 5. Prestadoras e clientes fora do padrão
    for chave, rotulo in (('prestadora', 'Prestadora'), ('cliente', 'Cliente')):
        grupo = dimensoes.get(chave, [])
        if len(grupo) < 2:
            continue
        ruins = [g for g in grupo if g['status'] in ('critico', 'atencao')]
        if ruins:
            g = max(ruins, key=lambda x: x['z'])
            add('atencao', f"{rotulo} {g['nome']} acima do padrão",
                f"{g['taxa_nff']}% de NFF em {g['total']} triagens (média {taxa}%).", {chave: g['id']})

    # 6. Diagnósticos do campo contradizidos pela bancada
    if transicoes['comparaveis'] >= 10:
        if transicoes['pct_div'] >= 30:
            add('atencao', 'Diagnóstico de campo diverge da bancada',
                f"{transicoes['pct_div']}% dos diagnósticos comparáveis não coincidem com o defeito constatado.")
        if transicoes['itens'] and transicoes['itens'][0]['pct'] >= 15:
            t = transicoes['itens'][0]
            add('info', 'Diagnóstico mais trocado',
                f"“{t['diagnostico']}” foi apontado em campo onde a bancada constatou “{t['constatado']}” ({t['qtd']} casos).")

    # 7. Reincidência por número de série
    if reinc['series']:
        add('atencao' if reinc['pct'] >= 10 else 'info', 'Equipamentos voltando',
            f"{reinc['series']} série(s) passaram pela triagem mais de uma vez, somando {reinc['triagens']} triagens ({reinc['pct']}%).")

    # 8. Qualidade do registro
    if total >= 10 and sem_constatado_pct >= 20:
        add('info', 'Registros incompletos limitam a análise',
            f"{sem_constatado_pct}% das triagens estão sem defeito constatado, o que reduz a precisão do cruzamento com o campo.")

    # 9. Tendência de alta nos últimos 3 períodos
    validos = [p for p in serie['pontos'] if p['total'] >= 3]
    if len(validos) >= 3:
        a, b, c = (p['taxa_nff'] for p in validos[-3:])
        if a < b < c:
            add('atencao', 'NFF em alta contínua', f"A taxa subiu nos 3 últimos períodos: {a}%, {b}% e {c}%.")

    itens.sort(key=lambda i: _PRIORIDADE[i['nivel']])
    return itens[:8]


# ------------------------------------------------------------------
# Entrada principal
# ------------------------------------------------------------------
def montar_dashboard(params):
    f = Filtros(params)
    qs = f.queryset(f.inicio, f.fim)
    res = _agregar(qs)

    if res['total'] == 0:
        return {'vazio': True, 'filtros': f.como_dict(), 'opcoes': _opcoes()}

    limites = qs.aggregate(a=Min('data_triagem'), b=Max('data_triagem'))
    ini_ef = f.inicio or timezone.localtime(limites['a']).date()
    fim_ef = f.fim or timezone.localtime(limites['b']).date()

    anterior = f.periodo_anterior()
    ant = _agregar(f.queryset(*anterior)) if anterior else None
    ant_valido = ant if ant and ant['total'] else None

    p_medio = res['nff'] / res['total']
    serie = _serie_temporal(qs, ini_ef, fim_ef)
    tecnicos = _tecnicos(qs, p_medio)
    dimensoes = {
        'cliente': _por_dimensao(qs.filter(cliente__tipo=2), 'cliente_id', 'cliente__razao_social', p_medio),
        'prestadora': _por_dimensao(qs, 'tecnico__empresa_id', 'tecnico__empresa__razao_social', p_medio),
        'estado': _por_dimensao(qs, 'estado', 'estado', p_medio),
        'analista': _por_dimensao(qs, 'analista_triagem_id', 'analista_triagem__nome', p_medio),
    }
    modelos = _modelos(qs)
    transicoes = _transicoes(qs)
    reinc = _reincidencia(qs, res['total'])
    sem_constatado = qs.filter(Q(defeito_constatado__isnull=True) | Q(defeito_constatado__exact='')).count()
    sem_constatado_pct = _pct(sem_constatado, res['total'])

    return {
        'vazio': False,
        'filtros': f.como_dict(),
        'meta': {
            'granularidade': serie['granularidade'],
            'inicio': ini_ef.isoformat(), 'fim': fim_ef.isoformat(),
            'anterior': {'inicio': anterior[0].isoformat(), 'fim': anterior[1].isoformat()} if anterior else None,
            'referencia_nff': {'min': REFERENCIA_NFF[0], 'max': REFERENCIA_NFF[1]},
            'p_medio': round(100 * p_medio, 1), 'min_amostra': MIN_AMOSTRA,
        },
        'kpis': {
            'triagens': _kpi(res['total'], ant_valido['total'] if ant_valido else None),
            'taxa_nff': _kpi(res['taxa_nff'], ant_valido['taxa_nff'] if ant_valido else None),
            'divergencia': _kpi(res['pct_div'], ant_valido['pct_div'] if ant_valido and ant_valido['comparaveis'] else None),
            'defeitos': res['defeitos'], 'nff': res['nff'],
            'comparaveis': res['comparaveis'], 'divergentes': res['divergentes'],
            'reincidencia': {'series': reinc['series'], 'triagens': reinc['triagens'], 'pct': reinc['pct']},
            'tecnicos_alerta': {
                'criticos': sum(1 for t in tecnicos if t['status'] == 'critico'),
                'atencao': sum(1 for t in tecnicos if t['status'] == 'atencao'),
                'avaliados': sum(1 for t in tecnicos if t['status'] != 'insuficiente'),
            },
        },
        'serie': serie,
        'tecnicos': tecnicos,
        'dimensoes': dimensoes,
        'modelos': modelos,
        'pareto_defeitos': _pareto_defeitos(qs),
        'pecas': _pecas(qs),
        'transicoes': transicoes,
        'reincidencia': reinc,
        'recentes': _recentes(qs),
        'insights': _insights(res, ant_valido, tecnicos, dimensoes, modelos, transicoes, reinc, serie, sem_constatado_pct),
        'opcoes': _opcoes(),
    }


# ------------------------------------------------------------------
# Exportação CSV do recorte filtrado
# ------------------------------------------------------------------
def _csv_seguro(valor):
    """Evita injeção de fórmulas ao abrir no Excel."""
    texto = '' if valor is None else str(valor).replace('\r', ' ').replace('\n', ' ')
    return "'" + texto if texto[:1] in ('=', '+', '-', '@') else texto


def exportar_csv(params):
    f = Filtros(params)
    qs = (f.queryset(f.inicio, f.fim)
           .select_related('tecnico__empresa', 'cliente', 'equipamento', 'analista_chamado', 'analista_triagem', 'peca_trocada')
           .order_by('-data_triagem', '-id_triagem'))
    saida = io.StringIO()
    saida.write('\ufeff')  # BOM para o Excel abrir com acentos corretos
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(['Data', 'Ticket', 'NF', 'Cidade', 'UF', 'Técnico', 'Prestadora', 'Cliente', 'PN', 'Modelo', 'SN',
                       'Resultado', 'Peça trocada (catálogo)', 'Peça trocada (observação)', 'Defeito do usuário', 'Diagnóstico do técnico',
                       'Defeito constatado', 'Diagnóstico divergente', 'Analista do chamado', 'Analista da triagem'])
    for t in qs.iterator():
        escritor.writerow([_csv_seguro(c) for c in [
            timezone.localtime(t.data_triagem).strftime('%d/%m/%Y %H:%M'), t.n_ticket, t.nf, t.cidade, t.estado,
            t.tecnico.nome, t.tecnico.empresa.razao_social, t.cliente.razao_social, t.equipamento.pn, t.equipamento.modelo,
            t.sn, 'Peça funcional (NFF)' if t.status == NFF else 'Defeito confirmado',
            t.peca_trocada.part_number if t.peca_trocada_id else '', t.troca,
            t.defeito_usuario, t.defeito_tecnico, t.defeito_constatado,
            'Sim' if _comparar_diagnostico(t.defeito_tecnico, t.defeito_constatado)[1] else 'Não',
            t.analista_chamado.nome, t.analista_triagem.nome]])
    return saida.getvalue()
