import csv
import io
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, F, Max, Min, Q
from django.db.models.functions import Trim, TruncDay, TruncMonth, TruncWeek, Upper
from django.utils import timezone

from .dtos import StatusPeca, TipoEmpresa
from .models import Empresa, Equipamento, Funcionario, Tecnico, Triagem

NFF = StatusPeca.FUNCIONAL
DEFEITO = StatusPeca.NAO_FUNCIONAL
REFERENCIA_NFF = (20.0, 50.0)
MIN_AMOSTRA = 5
Z95 = 1.96
MAX_PONTOS_SERIE = 400
LIMITE_DIAS_GRANULARIDADE_DIA = 45
LIMITE_DIAS_GRANULARIDADE_SEMANA = 200
MIN_TRIAGENS_PARA_INSIGHT = 10
MAX_INSIGHTS = 8
FORMATO_DATA_HORA = '%d/%m/%Y %H:%M'
FORMATO_DATA = '%d/%m/%Y'

PRIORIDADE_DOS_INSIGHTS = {'critico': 0, 'atencao': 1, 'info': 2, 'positivo': 3}

COLUNAS_CSV = [
    'Data', 'Ticket', 'NF', 'Cidade', 'UF', 'Técnico', 'Prestadora', 'Cliente', 'PN', 'Modelo', 'SN',
    'Resultado', 'Peça trocada (catálogo)', 'Peça trocada (observação)', 'Defeito do usuário',
    'Diagnóstico do técnico', 'Defeito constatado', 'Diagnóstico divergente', 'Analista do chamado',
    'Analista da triagem',
]


class FiltroInvalido(ValueError):
    pass


def normalizar_texto(valor):
    if not valor:
        return ''
    sem_acento = ''.join(c for c in unicodedata.normalize('NFD', valor) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', sem_acento.lower()).strip()


def _resumir_texto(valor, limite=60):
    texto = ' '.join((valor or '').split())
    return texto if len(texto) <= limite else texto[:limite - 1] + '…'


def _pct(parte, total):
    return round(100.0 * parte / total, 1) if total else 0.0


def intervalo_wilson(sucessos, total, z=Z95):
    if total <= 0:
        return 0.0, 0.0
    proporcao = sucessos / total
    denominador = 1 + z * z / total
    centro = (proporcao + z * z / (2 * total)) / denominador
    margem = z * math.sqrt(proporcao * (1 - proporcao) / total + z * z / (4 * total * total)) / denominador
    return max(0.0, centro - margem), min(1.0, centro + margem)


def classificar(proporcao, proporcao_media, total):
    if total < MIN_AMOSTRA:
        return 'insuficiente', None
    if proporcao_media <= 0 or proporcao_media >= 1:
        return 'normal', 0.0

    sigma = math.sqrt(proporcao_media * (1 - proporcao_media) / total)
    z = (proporcao - proporcao_media) / sigma
    if z >= 3:
        return 'critico', round(z, 2)
    if z >= 2:
        return 'atencao', round(z, 2)
    if z <= -2:
        return 'destaque', round(z, 2)
    return 'normal', round(z, 2)


def _comparar_diagnostico(diagnostico, constatado):
    a, b = normalizar_texto(diagnostico), normalizar_texto(constatado)
    if not a or not b:
        return False, False
    return True, a != b


def _diverge(diagnostico, constatado):
    return _comparar_diagnostico(diagnostico, constatado)[1]


def _converter_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        raise FiltroInvalido('Datas inválidas. Use o formato AAAA-MM-DD.')


def _converter_inteiro(valor):
    if valor in (None, ''):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise FiltroInvalido('Filtro inválido.')


class Filtros:
    def __init__(self, params):
        self.inicio = _converter_data(params.get('inicio'))
        self.fim = _converter_data(params.get('fim'))
        if self.inicio and self.fim and self.inicio > self.fim:
            raise FiltroInvalido('A data inicial não pode ser maior que a final.')

        self.tecnico = _converter_inteiro(params.get('tecnico'))
        self.prestadora = _converter_inteiro(params.get('prestadora'))
        self.cliente = _converter_inteiro(params.get('cliente'))
        self.equipamento = _converter_inteiro(params.get('equipamento'))
        self.analista = _converter_inteiro(params.get('analista'))
        self.estado = (params.get('estado') or '').strip().upper()[:2] or None
        self.comparar = params.get('comparar', '1') != '0'

    def queryset(self, inicio=None, fim=None):
        triagens = Triagem.objects.all()
        if inicio:
            triagens = triagens.filter(data_triagem__date__gte=inicio)
        if fim:
            triagens = triagens.filter(data_triagem__date__lte=fim)
        if self.tecnico:
            triagens = triagens.filter(tecnico_id=self.tecnico)
        if self.prestadora:
            triagens = triagens.filter(tecnico__empresa_id=self.prestadora)
        if self.cliente:
            triagens = triagens.filter(cliente_id=self.cliente)
        if self.equipamento:
            triagens = triagens.filter(equipamento_id=self.equipamento)
        if self.analista:
            triagens = triagens.filter(analista_triagem_id=self.analista)
        if self.estado:
            triagens = triagens.filter(estado__iexact=self.estado)
        return triagens

    def periodo_anterior(self):
        if not (self.comparar and self.inicio and self.fim):
            return None
        dias = (self.fim - self.inicio).days + 1
        fim_anterior = self.inicio - timedelta(days=1)
        return fim_anterior - timedelta(days=dias - 1), fim_anterior

    def como_dict(self):
        return {
            'inicio': self.inicio.isoformat() if self.inicio else None,
            'fim': self.fim.isoformat() if self.fim else None,
            'tecnico': self.tecnico,
            'prestadora': self.prestadora,
            'cliente': self.cliente,
            'equipamento': self.equipamento,
            'analista': self.analista,
            'estado': self.estado,
            'comparar': self.comparar,
        }


def _contagens_nff():
    return {'total': Count('id_triagem'), 'nff': Count('id_triagem', filter=Q(status=NFF))}


def _indicadores_do_grupo(nff, total, proporcao_media):
    inferior, superior = intervalo_wilson(nff, total)
    status, z = classificar(nff / total if total else 0, proporcao_media, total)
    return {
        'total': total,
        'nff': nff,
        'acertos': total - nff,
        'taxa_nff': _pct(nff, total),
        'ic_inf': round(100 * inferior, 1),
        'ic_sup': round(100 * superior, 1),
        'z': z,
        'status': status,
    }


def _agregar(triagens):
    base = triagens.aggregate(
        total=Count('id_triagem'),
        nff=Count('id_triagem', filter=Q(status=NFF)),
        defeitos=Count('id_triagem', filter=Q(status=DEFEITO)),
    )

    comparaveis = divergentes = 0
    if base['total']:
        for diagnostico, constatado in triagens.values_list('defeito_tecnico', 'defeito_constatado'):
            comparavel, diverge = _comparar_diagnostico(diagnostico, constatado)
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


def _granularidade(inicio, fim):
    dias = (fim - inicio).days + 1
    if dias <= LIMITE_DIAS_GRANULARIDADE_DIA:
        return 'dia'
    if dias <= LIMITE_DIAS_GRANULARIDADE_SEMANA:
        return 'semana'
    return 'mes'


def _inicio_do_periodo(data, granularidade):
    if granularidade == 'dia':
        return data
    if granularidade == 'semana':
        return data - timedelta(days=data.weekday())
    return data.replace(day=1)


def _proximo_periodo(data, granularidade):
    if granularidade == 'dia':
        return data + timedelta(days=1)
    if granularidade == 'semana':
        return data + timedelta(days=7)
    return (data.replace(day=28) + timedelta(days=4)).replace(day=1)


def _rotulo_do_periodo(data, granularidade):
    return data.strftime('%m/%Y') if granularidade == 'mes' else data.strftime('%d/%m')


def _serie_temporal(triagens, inicio, fim):
    granularidade = _granularidade(inicio, fim)
    truncar = {'dia': TruncDay, 'semana': TruncWeek, 'mes': TruncMonth}[granularidade]
    linhas = (
        triagens.annotate(periodo=truncar('data_triagem'))
        .values('periodo')
        .annotate(**_contagens_nff())
        .order_by('periodo')
    )

    por_periodo = {}
    for linha in linhas:
        periodo = linha['periodo']
        periodo = periodo.date() if isinstance(periodo, datetime) else periodo
        por_periodo[periodo] = linha

    pontos = []
    atual = _inicio_do_periodo(inicio, granularidade)
    for _ in range(MAX_PONTOS_SERIE):
        if atual > fim:
            break
        linha = por_periodo.get(atual)
        total = linha['total'] if linha else 0
        nff = linha['nff'] if linha else 0
        pontos.append({
            'rotulo': _rotulo_do_periodo(atual, granularidade),
            'inicio': atual.isoformat(),
            'total': total,
            'nff': nff,
            'taxa_nff': _pct(nff, total) if total else None,
        })
        atual = _proximo_periodo(atual, granularidade)
    return {'granularidade': granularidade, 'pontos': pontos}


def _tecnicos(triagens, proporcao_media):
    linhas = (
        triagens.values('tecnico_id', 'tecnico__nome', 'tecnico__empresa__razao_social')
        .annotate(**_contagens_nff())
        .order_by('-total')
    )

    divergencias = Counter()
    for id_tecnico, diagnostico, constatado in triagens.values_list(
        'tecnico_id', 'defeito_tecnico', 'defeito_constatado'
    ):
        if _diverge(diagnostico, constatado):
            divergencias[id_tecnico] += 1

    resultado = []
    for linha in linhas:
        indicadores = _indicadores_do_grupo(linha['nff'], linha['total'], proporcao_media)
        resultado.append({
            **indicadores,
            'id': linha['tecnico_id'],
            'nome': linha['tecnico__nome'],
            'prestadora': linha['tecnico__empresa__razao_social'],
            'taxa_acerto': _pct(indicadores['acertos'], indicadores['total']),
            'divergencias': divergencias.get(linha['tecnico_id'], 0),
        })
    return resultado


def _por_dimensao(triagens, campo_id, campo_nome, proporcao_media, limite=10):
    linhas = (
        triagens.values(ident=F(campo_id), nome=F(campo_nome))
        .annotate(**_contagens_nff())
        .order_by('-total')[:limite]
    )
    return [
        {
            **_indicadores_do_grupo(linha['nff'], linha['total'], proporcao_media),
            'id': linha['ident'],
            'nome': linha['nome'],
        }
        for linha in linhas
    ]


def _modelos(triagens, limite=30):
    linhas = (
        triagens.values(ident=F('equipamento_id'), pn=F('equipamento__pn'), modelo=F('equipamento__modelo'))
        .annotate(**_contagens_nff())
        .order_by('-total')[:limite]
    )
    return [
        {
            'id': linha['ident'],
            'pn': linha['pn'],
            'modelo': linha['modelo'],
            'total': linha['total'],
            'nff': linha['nff'],
            'taxa_nff': _pct(linha['nff'], linha['total']),
        }
        for linha in linhas
    ]


def _pecas(triagens, limite=10):
    com_peca = triagens.filter(peca_trocada__isnull=False)
    linhas = (
        com_peca.values(
            ident=F('peca_trocada_id'),
            pn=F('peca_trocada__part_number'),
            descricao=F('peca_trocada__descricao'),
        )
        .annotate(trocas=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF)))
        .order_by('-trocas', 'pn')[:limite]
    )
    itens = [
        {
            'id': linha['ident'],
            'part_number': linha['pn'],
            'descricao': linha['descricao'],
            'trocas': linha['trocas'],
            'nff': linha['nff'],
            'taxa_nff': _pct(linha['nff'], linha['trocas']),
        }
        for linha in linhas
    ]
    total_com_peca = com_peca.count()
    return {'itens': itens, 'com_peca': total_com_peca, 'sem_peca': triagens.count() - total_com_peca}


def _pareto_defeitos(triagens, limite=10):
    confirmados = triagens.filter(status=DEFEITO)
    contagem, exemplos = Counter(), defaultdict(Counter)
    for texto in confirmados.values_list('defeito_constatado', flat=True):
        chave = normalizar_texto(texto)
        if not chave:
            continue
        contagem[chave] += 1
        exemplos[chave][_resumir_texto(texto)] += 1

    total = sum(contagem.values())
    itens, acumulado = [], 0
    for chave, quantidade in contagem.most_common(limite):
        acumulado += quantidade
        itens.append({
            'rotulo': exemplos[chave].most_common(1)[0][0],
            'qtd': quantidade,
            'acumulado_pct': round(100.0 * acumulado / total, 1),
        })
    return {'itens': itens, 'total': total, 'sem_registro': confirmados.count() - total}


def _transicoes(triagens, limite=8):
    pares, rotulos = Counter(), {}
    comparaveis = divergentes = 0
    for diagnostico, constatado in triagens.values_list('defeito_tecnico', 'defeito_constatado'):
        comparavel, diverge = _comparar_diagnostico(diagnostico, constatado)
        comparaveis += comparavel
        if diverge:
            chave = (normalizar_texto(diagnostico), normalizar_texto(constatado))
            pares[chave] += 1
            rotulos[chave] = (_resumir_texto(diagnostico, 50), _resumir_texto(constatado, 50))
            divergentes += 1

    itens = [
        {
            'diagnostico': rotulos[chave][0],
            'constatado': rotulos[chave][1],
            'qtd': quantidade,
            'pct': _pct(quantidade, divergentes),
        }
        for chave, quantidade in pares.most_common(limite)
    ]
    return {
        'itens': itens,
        'divergentes': divergentes,
        'comparaveis': comparaveis,
        'pct_div': _pct(divergentes, comparaveis),
    }


def _reincidencia(triagens, total, limite=8):
    grupos = (
        triagens.exclude(sn='')
        .annotate(sn_normalizado=Upper(Trim('sn')))
        .values('sn_normalizado')
        .annotate(vezes=Count('id_triagem'), ultima=Max('data_triagem'), modelo=Max('equipamento__modelo'))
        .filter(vezes__gt=1)
        .order_by('-vezes', '-ultima')
    )
    series = list(grupos)
    total_triagens = sum(grupo['vezes'] for grupo in series)
    return {
        'series': len(series),
        'triagens': total_triagens,
        'pct': _pct(total_triagens, total),
        'itens': [
            {
                'sn': grupo['sn_normalizado'],
                'vezes': grupo['vezes'],
                'modelo': grupo['modelo'],
                'ultima': timezone.localtime(grupo['ultima']).strftime(FORMATO_DATA),
            }
            for grupo in series[:limite]
        ],
    }


def _recentes(triagens, limite=15):
    recentes = (
        triagens.select_related('tecnico', 'cliente', 'equipamento')
        .order_by('-data_triagem', '-id_triagem')[:limite]
    )
    return [
        {
            'id': triagem.id_triagem,
            'data': timezone.localtime(triagem.data_triagem).strftime(FORMATO_DATA_HORA),
            'ticket': triagem.n_ticket,
            'sn': triagem.sn,
            'tecnico': triagem.tecnico.nome,
            'cliente': triagem.cliente.razao_social,
            'modelo': triagem.equipamento.modelo,
            'status': triagem.status,
            'divergente': _diverge(triagem.defeito_tecnico, triagem.defeito_constatado),
        }
        for triagem in recentes
    ]


def _id_e_nome(consulta, campo_id, campo_nome):
    return [{'id': linha[campo_id], 'nome': linha[campo_nome]} for linha in consulta.values(campo_id, campo_nome)]


def _opcoes():
    empresas = Empresa.objects
    estados = Triagem.objects.values_list('estado', flat=True).distinct()
    analistas = Funcionario.objects.filter(triagens_efetuadas__isnull=False).distinct().order_by('nome')
    return {
        'tecnicos': _id_e_nome(Tecnico.objects.order_by('nome'), 'id_tecnico', 'nome'),
        'prestadoras': _id_e_nome(
            empresas.filter(tipo=TipoEmpresa.PRESTADORA).order_by('razao_social'), 'id_empresa', 'razao_social'
        ),
        'clientes': _id_e_nome(
            empresas.filter(tipo=TipoEmpresa.CLIENTE).order_by('razao_social'), 'id_empresa', 'razao_social'
        ),
        'estados': sorted({estado.upper() for estado in estados if estado}),
        'equipamentos': [
            {'id': linha['id_equipamento'], 'nome': f"{linha['modelo']} ({linha['pn']})"}
            for linha in Equipamento.objects.order_by('modelo').values('id_equipamento', 'modelo', 'pn')
        ],
        'analistas': _id_e_nome(analistas, 'id_funcionario', 'nome'),
    }


@dataclass
class Analise:
    resumo: dict
    anterior: dict
    tecnicos: list
    dimensoes: dict
    modelos: list
    transicoes: dict
    reincidencia: dict
    serie: dict
    sem_constatado_pct: float


def _insight(nivel, titulo, texto, filtro=None):
    return {'nivel': nivel, 'titulo': titulo, 'texto': texto, 'filtro': filtro}


def _insight_nff_global(analise):
    total, taxa = analise.resumo['total'], analise.resumo['taxa_nff']
    ref_min, ref_max = REFERENCIA_NFF
    if total < MIN_TRIAGENS_PARA_INSIGHT:
        return []

    if taxa > ref_max:
        return [_insight(
            'critico', 'NFF acima da faixa de referência',
            f"{taxa}% das peças trocadas estavam funcionais. A literatura de eletrônicos reporta {ref_min:.0f}% a {ref_max:.0f}%.",
        )]
    if taxa > ref_min:
        return [_insight(
            'atencao', 'NFF dentro da faixa, mas alto',
            f"{taxa}% das peças trocadas estavam funcionais (referência da literatura: {ref_min:.0f}% a {ref_max:.0f}%).",
        )]
    return [_insight(
        'positivo', 'NFF abaixo da faixa de referência',
        f"Apenas {taxa}% das peças trocadas estavam funcionais, abaixo dos {ref_min:.0f}% da literatura.",
    )]


def _insights_variacao(analise):
    atual, anterior = analise.resumo, analise.anterior
    if not (anterior and anterior['total'] >= MIN_TRIAGENS_PARA_INSIGHT and atual['total'] >= MIN_TRIAGENS_PARA_INSIGHT):
        return []

    insights = []
    taxa, taxa_anterior = atual['taxa_nff'], anterior['taxa_nff']
    delta = round(taxa - taxa_anterior, 1)
    texto_taxa = f"A taxa foi de {taxa_anterior}% para {taxa}% ({delta:+.1f} p.p.) em relação ao período anterior."
    if delta >= 5:
        insights.append(_insight('critico' if delta >= 10 else 'atencao', 'NFF subiu no período', texto_taxa))
    elif delta <= -5:
        insights.append(_insight('positivo', 'NFF caiu no período', texto_taxa))

    if abs(atual['total'] - anterior['total']) / anterior['total'] >= 0.3:
        variacao = round(100.0 * (atual['total'] - anterior['total']) / anterior['total'])
        insights.append(_insight(
            'info', 'Volume de triagens mudou',
            f"{atual['total']} triagens contra {anterior['total']} no período anterior ({variacao:+d}%).",
        ))
    return insights


def _insights_tecnicos(analise):
    taxa = analise.resumo['taxa_nff']
    tecnicos = analise.tecnicos
    insights = []

    criticos = sorted((t for t in tecnicos if t['status'] == 'critico'), key=lambda t: -t['z'])
    em_atencao = sorted((t for t in tecnicos if t['status'] == 'atencao'), key=lambda t: -t['z'])
    pior = (criticos or em_atencao or [None])[0]
    if pior:
        outros = len(criticos) + len(em_atencao) - 1
        extra = f" Mais {outros} técnico(s) também fora do padrão." if outros > 0 else ''
        insights.append(_insight(
            'critico' if criticos else 'atencao',
            f"{pior['nome']} fora do limite de controle",
            f"{pior['taxa_nff']}% de NFF em {pior['total']} triagens, contra {taxa}% da média (z = {pior['z']}).{extra}",
            {'tecnico': pior['id']},
        ))

    destaques = sorted(
        (t for t in tecnicos if t['status'] == 'destaque' and t['total'] >= MIN_TRIAGENS_PARA_INSIGHT),
        key=lambda t: t['z'],
    )
    if destaques:
        melhor = destaques[0]
        insights.append(_insight(
            'positivo',
            f"{melhor['nome']} se destaca",
            f"{melhor['taxa_nff']}% de NFF em {melhor['total']} triagens, bem abaixo da média de {taxa}%.",
            {'tecnico': melhor['id']},
        ))
    return insights


def _insight_modelo_concentrado(analise):
    nff_total = analise.resumo['nff']
    if nff_total < 5 or not analise.modelos:
        return []

    topo = max(analise.modelos, key=lambda modelo: modelo['nff'])
    participacao = _pct(topo['nff'], nff_total)
    if participacao < 25 or topo['nff'] < 3:
        return []
    return [_insight(
        'atencao',
        f"{topo['modelo']} concentra o NFF",
        f"{participacao}% de todas as peças funcionais trocadas são deste modelo ({topo['nff']} de {nff_total}).",
        {'equipamento': topo['id']},
    )]


def _insights_dimensoes(analise):
    taxa = analise.resumo['taxa_nff']
    insights = []
    for chave, rotulo in (('prestadora', 'Prestadora'), ('cliente', 'Cliente')):
        grupo = analise.dimensoes.get(chave, [])
        if len(grupo) < 2:
            continue
        fora_do_padrao = [item for item in grupo if item['status'] in ('critico', 'atencao')]
        if fora_do_padrao:
            pior = max(fora_do_padrao, key=lambda item: item['z'])
            insights.append(_insight(
                'atencao',
                f"{rotulo} {pior['nome']} acima do padrão",
                f"{pior['taxa_nff']}% de NFF em {pior['total']} triagens (média {taxa}%).",
                {chave: pior['id']},
            ))
    return insights


def _insights_diagnostico(analise):
    transicoes = analise.transicoes
    if transicoes['comparaveis'] < MIN_TRIAGENS_PARA_INSIGHT:
        return []

    insights = []
    if transicoes['pct_div'] >= 30:
        insights.append(_insight(
            'atencao', 'Diagnóstico de campo diverge da bancada',
            f"{transicoes['pct_div']}% dos diagnósticos comparáveis não coincidem com o defeito constatado.",
        ))
    if transicoes['itens'] and transicoes['itens'][0]['pct'] >= 15:
        mais_trocado = transicoes['itens'][0]
        insights.append(_insight(
            'info', 'Diagnóstico mais trocado',
            f"“{mais_trocado['diagnostico']}” foi apontado em campo onde a bancada constatou "
            f"“{mais_trocado['constatado']}” ({mais_trocado['qtd']} casos).",
        ))
    return insights


def _insight_reincidencia(analise):
    reincidencia = analise.reincidencia
    if not reincidencia['series']:
        return []
    return [_insight(
        'atencao' if reincidencia['pct'] >= 10 else 'info',
        'Equipamentos voltando',
        f"{reincidencia['series']} série(s) passaram pela triagem mais de uma vez, "
        f"somando {reincidencia['triagens']} triagens ({reincidencia['pct']}%).",
    )]


def _insight_qualidade_do_registro(analise):
    if analise.resumo['total'] < MIN_TRIAGENS_PARA_INSIGHT or analise.sem_constatado_pct < 20:
        return []
    return [_insight(
        'info', 'Registros incompletos limitam a análise',
        f"{analise.sem_constatado_pct}% das triagens estão sem defeito constatado, "
        "o que reduz a precisão do cruzamento com o campo.",
    )]


def _insight_tendencia_de_alta(analise):
    periodos_validos = [ponto for ponto in analise.serie['pontos'] if ponto['total'] >= 3]
    if len(periodos_validos) < 3:
        return []

    a, b, c = (ponto['taxa_nff'] for ponto in periodos_validos[-3:])
    if not a < b < c:
        return []
    return [_insight('atencao', 'NFF em alta contínua', f"A taxa subiu nos 3 últimos períodos: {a}%, {b}% e {c}%.")]


REGRAS_DE_INSIGHT = (
    _insight_nff_global,
    _insights_variacao,
    _insights_tecnicos,
    _insight_modelo_concentrado,
    _insights_dimensoes,
    _insights_diagnostico,
    _insight_reincidencia,
    _insight_qualidade_do_registro,
    _insight_tendencia_de_alta,
)


def _insights(analise):
    insights = [insight for regra in REGRAS_DE_INSIGHT for insight in regra(analise)]
    insights.sort(key=lambda insight: PRIORIDADE_DOS_INSIGHTS[insight['nivel']])
    return insights[:MAX_INSIGHTS]


def _montar_kpis(resumo, anterior, tecnicos, reincidencia):
    return {
        'triagens': _kpi(resumo['total'], anterior['total'] if anterior else None),
        'taxa_nff': _kpi(resumo['taxa_nff'], anterior['taxa_nff'] if anterior else None),
        'divergencia': _kpi(
            resumo['pct_div'],
            anterior['pct_div'] if anterior and anterior['comparaveis'] else None,
        ),
        'defeitos': resumo['defeitos'],
        'nff': resumo['nff'],
        'comparaveis': resumo['comparaveis'],
        'divergentes': resumo['divergentes'],
        'reincidencia': {
            'series': reincidencia['series'],
            'triagens': reincidencia['triagens'],
            'pct': reincidencia['pct'],
        },
        'tecnicos_alerta': {
            'criticos': sum(1 for t in tecnicos if t['status'] == 'critico'),
            'atencao': sum(1 for t in tecnicos if t['status'] == 'atencao'),
            'avaliados': sum(1 for t in tecnicos if t['status'] != 'insuficiente'),
        },
    }


def _montar_meta(serie, inicio, fim, periodo_anterior, proporcao_media):
    return {
        'granularidade': serie['granularidade'],
        'inicio': inicio.isoformat(),
        'fim': fim.isoformat(),
        'anterior': (
            {'inicio': periodo_anterior[0].isoformat(), 'fim': periodo_anterior[1].isoformat()}
            if periodo_anterior else None
        ),
        'referencia_nff': {'min': REFERENCIA_NFF[0], 'max': REFERENCIA_NFF[1]},
        'p_medio': round(100 * proporcao_media, 1),
        'min_amostra': MIN_AMOSTRA,
    }


def montar_dashboard(params):
    filtros = Filtros(params)
    triagens = filtros.queryset(filtros.inicio, filtros.fim)
    resumo = _agregar(triagens)

    if resumo['total'] == 0:
        return {'vazio': True, 'filtros': filtros.como_dict(), 'opcoes': _opcoes()}

    limites = triagens.aggregate(primeira=Min('data_triagem'), ultima=Max('data_triagem'))
    inicio = filtros.inicio or timezone.localtime(limites['primeira']).date()
    fim = filtros.fim or timezone.localtime(limites['ultima']).date()

    periodo_anterior = filtros.periodo_anterior()
    anterior = _agregar(filtros.queryset(*periodo_anterior)) if periodo_anterior else None
    anterior = anterior if anterior and anterior['total'] else None

    proporcao_media = resumo['nff'] / resumo['total']
    serie = _serie_temporal(triagens, inicio, fim)
    tecnicos = _tecnicos(triagens, proporcao_media)
    dimensoes = {
        'cliente': _por_dimensao(
            triagens.filter(cliente__tipo=TipoEmpresa.CLIENTE), 'cliente_id', 'cliente__razao_social', proporcao_media
        ),
        'prestadora': _por_dimensao(
            triagens, 'tecnico__empresa_id', 'tecnico__empresa__razao_social', proporcao_media
        ),
        'estado': _por_dimensao(triagens, 'estado', 'estado', proporcao_media),
        'analista': _por_dimensao(triagens, 'analista_triagem_id', 'analista_triagem__nome', proporcao_media),
    }
    modelos = _modelos(triagens)
    transicoes = _transicoes(triagens)
    reincidencia = _reincidencia(triagens, resumo['total'])
    sem_constatado = triagens.filter(Q(defeito_constatado__isnull=True) | Q(defeito_constatado__exact='')).count()

    analise = Analise(
        resumo=resumo,
        anterior=anterior,
        tecnicos=tecnicos,
        dimensoes=dimensoes,
        modelos=modelos,
        transicoes=transicoes,
        reincidencia=reincidencia,
        serie=serie,
        sem_constatado_pct=_pct(sem_constatado, resumo['total']),
    )

    return {
        'vazio': False,
        'filtros': filtros.como_dict(),
        'meta': _montar_meta(serie, inicio, fim, periodo_anterior, proporcao_media),
        'kpis': _montar_kpis(resumo, anterior, tecnicos, reincidencia),
        'serie': serie,
        'tecnicos': tecnicos,
        'dimensoes': dimensoes,
        'modelos': modelos,
        'pareto_defeitos': _pareto_defeitos(triagens),
        'pecas': _pecas(triagens),
        'transicoes': transicoes,
        'reincidencia': reincidencia,
        'recentes': _recentes(triagens),
        'insights': _insights(analise),
        'opcoes': _opcoes(),
    }


def _neutralizar_formula(valor):
    texto = '' if valor is None else str(valor).replace('\r', ' ').replace('\n', ' ')
    return "'" + texto if texto[:1] in ('=', '+', '-', '@') else texto


def _linha_csv(triagem):
    resultado = 'Peça funcional (NFF)' if triagem.status == NFF else 'Defeito confirmado'
    divergente = 'Sim' if _diverge(triagem.defeito_tecnico, triagem.defeito_constatado) else 'Não'
    return [
        timezone.localtime(triagem.data_triagem).strftime(FORMATO_DATA_HORA),
        triagem.n_ticket,
        triagem.nf,
        triagem.cidade,
        triagem.estado,
        triagem.tecnico.nome,
        triagem.tecnico.empresa.razao_social,
        triagem.cliente.razao_social,
        triagem.equipamento.pn,
        triagem.equipamento.modelo,
        triagem.sn,
        resultado,
        triagem.peca_trocada.part_number if triagem.peca_trocada_id else '',
        triagem.troca,
        triagem.defeito_usuario,
        triagem.defeito_tecnico,
        triagem.defeito_constatado,
        divergente,
        triagem.analista_chamado.nome,
        triagem.analista_triagem.nome,
    ]


def exportar_csv(params):
    filtros = Filtros(params)
    triagens = (
        filtros.queryset(filtros.inicio, filtros.fim)
        .select_related(
            'tecnico__empresa', 'cliente', 'equipamento', 'analista_chamado', 'analista_triagem', 'peca_trocada'
        )
        .order_by('-data_triagem', '-id_triagem')
    )

    saida = io.StringIO()
    saida.write('\ufeff')
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow(COLUNAS_CSV)
    for triagem in triagens.iterator():
        escritor.writerow([_neutralizar_formula(celula) for celula in _linha_csv(triagem)])
    return saida.getvalue()
