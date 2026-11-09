"""
Camada de BI (indicadores, comparações, insights e alertas do dashboard).

As telas só LEEM daqui. O recálculo do SLA dos chamados ativos acontece no máximo a cada
`BI_CONFIG['refresh_minutos']` (ou pelo comando `atualizar_bi`), e não a cada clique.
"""
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import mean, pstdev
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Count, DecimalField, F, Max, Q, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone as django_timezone

from ..models import (AgendamentoChamado, AlertaSLAEnviado, ChamadoRFB, CotacaoPeca, Equipamento, Funcionario,
                      Insight, ItemOrcamento, Orcamento, OrcamentoHistorico, Peca, SnapshotSLA, Tecnico, Triagem)
from .chamado_rfb import ChamadoRFBService
from .estatistica import (MIN_AMOSTRA, NFF, REFERENCIA_NFF, classificar, comparar_diagnostico, intervalo_wilson,
                         limites_controle, limpar, normalizar_texto, pct)

logger = logging.getLogger(__name__)

DEC = DecimalField(max_digits=16, decimal_places=2)
ENVIADOS = ('emitido', 'aprovado', 'recusado')       # laudos que chegaram ao cliente
INATIVOS = ('concluido', 'cancelado')                # chamados que não contam no backlog
CHAVE_ULTIMA_ATUALIZACAO = 'bi:ultima_atualizacao'
CHAVE_TRAVA = 'bi:atualizando'


def _cfg() -> dict:
    base = {'meta_sla': 95.0, 'limiares': (60.0, 80.0, 100.0), 'refresh_minutos': 10, 'cotacao_velha_dias': 30,
            'modelo_min_n': 20, 'modelo_fator': 2.0}
    base.update(getattr(settings, 'BI_CONFIG', {}))
    return base


def _limite(metropolitana: bool) -> float:
    return 72.0 if metropolitana else 120.0


def _pct_sla(horas: float, metropolitana: bool) -> float:
    return round((horas or 0.0) / _limite(metropolitana) * 100.0, 1)


def _int(valor) -> Optional[int]:
    try:
        return int(valor) if valor not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _data(texto) -> Optional[date]:
    if not texto:
        return None
    try:
        return datetime.strptime(str(texto)[:10], '%Y-%m-%d').date()
    except ValueError:
        raise ValueError("Data inválida. Use o formato AAAA-MM-DD.")


def _brl(valor) -> str:
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def _normalizar(texto) -> str:
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', t)).strip()


def _ranking(textos, topo: int = 8) -> list:
    """Conta textos livres agrupando variações ("Tela", "tela ", "TELA!") e devolve o rótulo mais comum."""
    contagem, rotulos = Counter(), defaultdict(Counter)
    for texto in textos:
        chave = _normalizar(texto)
        if chave:
            contagem[chave] += 1
            rotulos[chave][str(texto).strip()] += 1
    return [{'nome': rotulos[c].most_common(1)[0][0], 'qtd': n} for c, n in contagem.most_common(topo)]


def _comparar(atual, anterior, menor_melhor: bool = False) -> dict:
    """Valor atual x anterior, com diferença, variação percentual e se a mudança é boa ou ruim."""
    if atual is None:
        return {'atual': None, 'anterior': anterior, 'diferenca': None, 'variacao_pct': None, 'tendencia': 'flat', 'bom': None}
    a = float(atual)
    if anterior is None:
        return {'atual': round(a, 2), 'anterior': None, 'diferenca': None, 'variacao_pct': None, 'tendencia': 'flat', 'bom': None}
    b = float(anterior)
    dif = round(a - b, 2)
    if dif == 0:
        tendencia, bom = 'flat', None
    else:
        tendencia = 'up' if a > b else 'down'
        bom = (a < b) if menor_melhor else (a > b)
    return {'atual': round(a, 2), 'anterior': round(b, 2), 'diferenca': dif,
            'variacao_pct': round((a - b) / b * 100, 1) if b else None, 'tendencia': tendencia, 'bom': bom}


def _um_ano_antes(dia: date) -> date:
    try:
        return dia.replace(year=dia.year - 1)
    except ValueError:                       # 29 de fevereiro
        return dia.replace(year=dia.year - 1, day=28)


class Filtros:
    """Filtros comuns do dashboard, lidos da querystring."""

    def __init__(self, params):
        hoje = django_timezone.localdate()
        self.fim = _data(params.get('fim')) or hoje
        self.inicio = _data(params.get('inicio')) or (self.fim - timedelta(days=29))
        if self.inicio > self.fim:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        self.dias = (self.fim - self.inicio).days + 1
        if self.dias > 800:
            raise ValueError("O período máximo é de cerca de 2 anos.")
        self.comparar = 'ano' if str(params.get('comparar') or '') == 'ano' else 'anterior'
        if self.comparar == 'ano':           # mesmo período do ano passado (bom para semestre e ano)
            self.ant_inicio, self.ant_fim = _um_ano_antes(self.inicio), _um_ano_antes(self.fim)
        else:                                 # período imediatamente anterior, do mesmo tamanho
            self.ant_fim = self.inicio - timedelta(days=1)
            self.ant_inicio = self.ant_fim - timedelta(days=self.dias - 1)
        self.uf = (params.get('uf') or '').strip().upper()[:2]
        self.analista = _int(params.get('analista'))
        self.modelo = _int(params.get('modelo'))
        self.cliente = _int(params.get('cliente'))
        self.tecnico = _int(params.get('tecnico'))
        self.historico = str(params.get('historico') or '').lower() in ('1', 'true', 'on')

    def periodo(self, anterior: bool = False):
        return (self.ant_inicio, self.ant_fim) if anterior else (self.inicio, self.fim)

    def descrever(self) -> dict:
        return {'inicio': self.inicio.isoformat(), 'fim': self.fim.isoformat(), 'dias': self.dias, 'comparar': self.comparar,
                'anterior_inicio': self.ant_inicio.isoformat(), 'anterior_fim': self.ant_fim.isoformat()}


class BIService:
    # ------------------------------------------------------------------ atualização
    @staticmethod
    def atualizar_sla_ativos() -> int:
        """Recalcula e grava o consumo de SLA dos chamados ativos. Devolve quantos mudaram."""
        mudaram = 0
        for chamado in ChamadoRFB.objects.prefetch_related('agendamentos').exclude(status__in=INATIVOS):
            consumo = ChamadoRFBService.calcular_consumo_sla(chamado)
            if chamado.horas_consumidas != consumo:
                chamado.horas_consumidas = consumo
                chamado.save(update_fields=['horas_consumidas'])
                mudaram += 1
        return mudaram

    @staticmethod
    def registrar_snapshot(dia=None) -> SnapshotSLA:
        dia = dia or django_timezone.localdate()
        faixas = {'ate_60': 0, 'faixa_60_80': 0, 'faixa_80_100': 0, 'acima_100': 0}
        por_uf = defaultdict(lambda: {'ativos': 0, 'estourados': 0})
        ativos = list(ChamadoRFB.objects.exclude(status__in=INATIVOS).values('estado', 'is_metropolitana', 'horas_consumidas'))
        for c in ativos:
            pct = _pct_sla(c['horas_consumidas'], c['is_metropolitana'])
            chave = 'ate_60' if pct <= 60 else 'faixa_60_80' if pct <= 80 else 'faixa_80_100' if pct <= 100 else 'acima_100'
            faixas[chave] += 1
            por_uf[c['estado']]['ativos'] += 1
            if pct > 100:
                por_uf[c['estado']]['estourados'] += 1
        snapshot, _ = SnapshotSLA.objects.update_or_create(data=dia, defaults={
            'ativos': len(ativos), **faixas, 'por_uf': dict(por_uf),
            'abertos_dia': ChamadoRFB.objects.filter(data_abertura__date=dia).count(),
            'concluidos_dia': ChamadoRFB.objects.filter(data_conclusao__date=dia).count(),
        })
        return snapshot

    @staticmethod
    def atualizar_se_necessario(forcar: bool = False) -> bool:
        """
        Atualiza SLA, snapshot do dia e insights, no máximo a cada `refresh_minutos`.
        A trava no cache evita que várias pessoas disparem o cálculo ao mesmo tempo.
        """
        if not forcar and cache.get(CHAVE_ULTIMA_ATUALIZACAO):
            return False
        if not cache.add(CHAVE_TRAVA, 1, 300):
            return False
        try:
            BIService.atualizar_sla_ativos()
            BIService.registrar_snapshot()
            try:
                BIService.gerar_insights()
            except Exception:
                logger.exception("Falha ao gerar insights (o painel segue funcionando)")
            cache.set(CHAVE_ULTIMA_ATUALIZACAO, django_timezone.now().isoformat(), _cfg()['refresh_minutos'] * 60)
        finally:
            cache.delete(CHAVE_TRAVA)
        return True

    # ------------------------------------------------------------------ consultas base
    @staticmethod
    def _triagens(f: Filtros, anterior: bool = False, com_periodo: bool = True):
        qs = Triagem.objects.all()
        if f.uf:
            qs = qs.filter(estado=f.uf)
        if f.analista:
            qs = qs.filter(analista_triagem_id=f.analista)
        if f.modelo:
            qs = qs.filter(equipamento_id=f.modelo)
        if f.cliente:
            qs = qs.filter(cliente_id=f.cliente)
        if f.tecnico:
            qs = qs.filter(tecnico_id=f.tecnico)
        if not com_periodo:
            return qs
        ini, fim = f.periodo(anterior)
        filtro = Q(criado_em__date__gte=ini, criado_em__date__lte=fim)
        if f.historico and not anterior:
            filtro |= Q(criado_em__isnull=True)     # triagens antigas, sem data
        return qs.filter(filtro)

    @staticmethod
    def _chamados(f: Filtros):
        qs = ChamadoRFB.objects.all()
        if f.uf:
            qs = qs.filter(estado=f.uf)
        if f.analista:
            qs = qs.filter(analista_responsavel_id=f.analista)
        if f.modelo:
            nome = Equipamento.objects.filter(pk=f.modelo).values_list('modelo', flat=True).first()
            qs = qs.filter(Q(equipamento_id=f.modelo) | Q(modelo_equipamento__iexact=nome or '\x00')) if nome else qs.none()
        return qs

    @staticmethod
    def _orcamentos(f: Filtros, anterior: bool = False, com_periodo: bool = True):
        qs = Orcamento.objects.all()
        if f.uf:
            qs = qs.filter(cliente_uf=f.uf)
        if f.analista:
            qs = qs.filter(analista_id=f.analista)
        if f.modelo:
            qs = qs.filter(equipamento_id=f.modelo)
        if f.cliente:
            qs = qs.filter(triagem__cliente_id=f.cliente)
        if f.tecnico:
            qs = qs.filter(triagem__tecnico_id=f.tecnico)
        if not com_periodo:
            return qs
        ini, fim = f.periodo(anterior)
        return qs.filter(data_emissao__gte=ini, data_emissao__lte=fim)

    @staticmethod
    def _soma(orcamentos, o_que: str = 'valor') -> Decimal:
        itens = ItemOrcamento.objects.filter(orcamento__in=orcamentos)
        expr = F('valor_unitario') * F('quantidade') + F('adicional') if o_que == 'valor' else F('valor_base') * F('quantidade')
        return itens.aggregate(t=Sum(expr, output_field=DEC))['t'] or Decimal('0')

    @staticmethod
    def _financeiro(f: Filtros, anterior: bool = False) -> dict:
        enviados = BIService._orcamentos(f, anterior).filter(status__in=ENVIADOS)
        valor = BIService._soma(enviados, 'valor')
        # A margem só faz sentido nos laudos com a regra de preço: nos de valor cheio o custo da peça não é registrado.
        com_regra = enviados.filter(aplicar_regra=True)
        valor_regra = BIService._soma(com_regra, 'valor')
        custo_regra = BIService._soma(com_regra, 'custo')
        qtd = enviados.count()
        aprovados = enviados.filter(status='aprovado')
        n_apr, n_rec = aprovados.count(), enviados.filter(status='recusado').count()
        decididos = n_apr + n_rec
        return {
            'qtd_emitidos': qtd, 'valor_emitido': float(valor), 'valor_aprovado': float(BIService._soma(aprovados, 'valor')),
            'aprovados': n_apr, 'recusados': n_rec, 'decididos': decididos,
            'taxa_aprovacao': round(n_apr * 100 / decididos, 1) if decididos else None,
            'ticket_medio': float(valor / qtd) if qtd else None,
            'margem_pct': round(float((valor_regra - custo_regra) / valor_regra * 100), 1) if valor_regra else None,
        }

    @staticmethod
    def _sla_concluidos(f: Filtros, anterior: bool = False) -> dict:
        ini, fim = f.periodo(anterior)
        qs = (BIService._chamados(f).filter(status='concluido', data_conclusao__date__gte=ini, data_conclusao__date__lte=fim)
              .prefetch_related('agendamentos'))
        total = dentro = 0
        horas = []
        for chamado in qs:
            consumo = ChamadoRFBService.calcular_consumo_sla(chamado)
            horas.append(consumo)
            total += 1
            if consumo <= _limite(chamado.is_metropolitana):
                dentro += 1
        return {'total': total, 'dentro': dentro, 'pct': round(dentro * 100 / total, 1) if total else None,
                'mttr': round(mean(horas), 1) if horas else None}

    # ------------------------------------------------------------------ visão executiva
    @staticmethod
    def executivo(f: Filtros) -> dict:
        BIService.atualizar_se_necessario()
        fin, fin_ant = BIService._financeiro(f), BIService._financeiro(f, True)
        sla, sla_ant = BIService._sla_concluidos(f), BIService._sla_concluidos(f, True)
        tri, tri_ant = BIService._triagens(f), BIService._triagens(f, True)
        n_tri, n_tri_ant = tri.count(), tri_ant.count()
        taxa_func = round(tri.filter(status=1).count() * 100 / n_tri, 1) if n_tri else None
        taxa_func_ant = round(tri_ant.filter(status=1).count() * 100 / n_tri_ant, 1) if n_tri_ant else None

        backlog = BIService._chamados(f).exclude(status__in=INATIVOS).count()
        referencia = f.ant_fim if f.comparar == 'ano' else f.inicio
        snap = SnapshotSLA.objects.filter(data__lte=referencia).order_by('-data').first()
        meta = _cfg()['meta_sla']

        def kpi(chave, rotulo, unidade, atual, anterior, menor_melhor=False, n=None, meta_valor=None, dica=''):
            return {'chave': chave, 'rotulo': rotulo, 'unidade': unidade, 'menor_melhor': menor_melhor,
                    'n': n, 'meta': meta_valor, 'dica': dica, **_comparar(atual, anterior, menor_melhor)}

        return {
            'periodo': f.descrever(), 'meta_sla': meta,
            'kpis': [
                kpi('sla', 'Dentro do SLA', 'pct', sla['pct'], sla_ant['pct'], n=sla['total'], meta_valor=meta,
                    dica='Chamados concluídos no período que respeitaram o limite (72 h metropolitana, 120 h demais)'),
                kpi('backlog', 'Backlog (chamados ativos)', 'num', backlog, snap.ativos if snap else None, menor_melhor=True,
                    dica='Comparado com o retrato diário mais próximo do fim do período de comparação'),
                kpi('valor_aprovado', 'Valor aprovado', 'moeda', fin['valor_aprovado'], fin_ant['valor_aprovado'], n=fin['aprovados']),
                kpi('taxa_aprovacao', 'Taxa de aprovação', 'pct', fin['taxa_aprovacao'], fin_ant['taxa_aprovacao'], n=fin['decididos'],
                    dica='Aprovados ÷ (aprovados + recusados)'),
                kpi('ticket_medio', 'Ticket médio', 'moeda', fin['ticket_medio'], fin_ant['ticket_medio'], n=fin['qtd_emitidos']),
                kpi('margem', 'Margem bruta', 'pct', fin['margem_pct'], fin_ant['margem_pct'], n=fin['qtd_emitidos'],
                    dica='(valor dos laudos − custo das peças) ÷ valor dos laudos'),
                kpi('triagens', 'Triagens no período', 'num', n_tri, n_tri_ant, n=n_tri),
                kpi('taxa_funcional', 'Equipamentos funcionais', 'pct', taxa_func, taxa_func_ant, n=n_tri,
                    dica='Triagens sem defeito constatado ÷ total'),
                kpi('mttr', 'Tempo médio de resolução', 'horas', sla['mttr'], sla_ant['mttr'], menor_melhor=True, n=sla['total'],
                    dica='Horas de SLA (descontadas as pausas) dos concluídos no período'),
            ],
            'historico_sem_data': Triagem.objects.filter(criado_em__isnull=True).count(),
            'insights': BIService.listar_insights(limite=5, apenas_nao_lidos=True),
        }

    # ------------------------------------------------------------------ operação e SLA
    @staticmethod
    def operacao(f: Filtros) -> dict:
        BIService.atualizar_se_necessario()
        agora = django_timezone.now()
        ativos = list(BIService._chamados(f).exclude(status__in=INATIVOS).values(
            'id_chamado', 'ticket', 'estado', 'cidade', 'is_metropolitana', 'horas_consumidas', 'data_abertura',
            'modelo_equipamento', 'analista_responsavel__nome'))
        faixas = {'ate_60': 0, 'faixa_60_80': 0, 'faixa_80_100': 0, 'acima_100': 0}
        aging = {'ate_24h': 0, '24_48h': 0, '48_72h': 0, '72_120h': 0, 'acima_120h': 0}
        por_uf = defaultdict(lambda: {'ativos': 0, 'criticos': 0, 'estourados': 0})
        por_analista = defaultdict(lambda: {'ativos': 0, 'soma_pct': 0.0, 'estourados': 0})
        criticos = []
        for c in ativos:
            pct = _pct_sla(c['horas_consumidas'], c['is_metropolitana'])
            faixas['ate_60' if pct <= 60 else 'faixa_60_80' if pct <= 80 else 'faixa_80_100' if pct <= 100 else 'acima_100'] += 1
            horas = (agora - c['data_abertura']).total_seconds() / 3600
            aging['ate_24h' if horas < 24 else '24_48h' if horas < 48 else '48_72h' if horas < 72 else '72_120h' if horas < 120 else 'acima_120h'] += 1
            u = por_uf[c['estado']]
            u['ativos'] += 1
            u['criticos'] += pct >= 80
            u['estourados'] += pct > 100
            nome = c['analista_responsavel__nome'] or 'Sem analista'
            a = por_analista[nome]
            a['ativos'] += 1
            a['soma_pct'] += pct
            a['estourados'] += pct > 100
            if pct >= 60:
                criticos.append({'id': c['id_chamado'], 'ticket': c['ticket'], 'uf': c['estado'], 'cidade': c['cidade'],
                                 'modelo': c['modelo_equipamento'], 'pct': pct, 'analista': nome,
                                 'horas_abertas': round(horas, 1)})
        criticos.sort(key=lambda x: -x['pct'])

        base = BIService._chamados(f)
        ini, fim = f.periodo()
        semanas = defaultdict(lambda: {'abertos': 0, 'concluidos': 0})
        for linha in (base.filter(data_abertura__date__gte=ini, data_abertura__date__lte=fim)
                      .annotate(sem=TruncWeek('data_abertura')).values('sem').annotate(n=Count('id_chamado'))):
            semanas[str(linha['sem'])[:10]]['abertos'] = linha['n']
        for linha in (base.filter(status='concluido', data_conclusao__date__gte=ini, data_conclusao__date__lte=fim)
                      .annotate(sem=TruncWeek('data_conclusao')).values('sem').annotate(n=Count('id_chamado'))):
            semanas[str(linha['sem'])[:10]]['concluidos'] = linha['n']

        agend = {l['status']: l['n'] for l in AgendamentoChamado.objects.filter(
            chamado__in=base, data_registro_pausa__date__gte=ini, data_registro_pausa__date__lte=fim
        ).values('status').annotate(n=Count('id_agendamento'))}
        decididos = agend.get('realizado', 0) + agend.get('frustrado', 0)

        tendencia = []
        for s in SnapshotSLA.objects.filter(data__gte=ini, data__lte=fim):
            tendencia.append({'data': s.data.isoformat(), 'ativos': s.ativos, 'estourados': s.acima_100,
                              'pct_no_prazo': round((s.ativos - s.acima_100) * 100 / s.ativos, 1) if s.ativos else None})

        concluidos, concluidos_ant = BIService._sla_concluidos(f), BIService._sla_concluidos(f, True)
        return {
            'periodo': f.descrever(), 'meta_sla': _cfg()['meta_sla'], 'total_ativos': len(ativos),
            'faixas': faixas, 'aging': aging,
            'por_uf': sorted(({'uf': k, **v} for k, v in por_uf.items()), key=lambda x: (-x['estourados'], -x['criticos'], -x['ativos'])),
            'por_analista': sorted(({'nome': k, 'ativos': v['ativos'], 'estourados': v['estourados'],
                                     'pct_medio': round(v['soma_pct'] / v['ativos'], 1)} for k, v in por_analista.items()),
                                   key=lambda x: -x['ativos']),
            'criticos': criticos[:15],
            'vazao': [{'semana': k, **v} for k, v in sorted(semanas.items())],
            'agendamentos': {'pendente': agend.get('pendente', 0), 'realizado': agend.get('realizado', 0),
                             'frustrado': agend.get('frustrado', 0),
                             'taxa_frustrados': round(agend.get('frustrado', 0) * 100 / decididos, 1) if decididos else None,
                             'sem_resposta': AgendamentoChamado.objects.filter(
                                 chamado__in=base, tipo_pausa='sem_resposta',
                                 data_registro_pausa__date__gte=ini, data_registro_pausa__date__lte=fim).count()},
            'tendencia': tendencia,
            'concluidos': {**concluidos, 'comparacao_pct': _comparar(concluidos['pct'], concluidos_ant['pct']),
                           'comparacao_mttr': _comparar(concluidos['mttr'], concluidos_ant['mttr'], True)},
        }

    # ------------------------------------------------------------------ qualidade
    @staticmethod
    def _controle_tecnicos(tri, funcionais: int, total: int) -> dict:
        """
        NFF por técnico com intervalo de Wilson e carta de controle p (funnel plot), e a matriz de diagnósticos
        do técnico de campo que a bancada contradisse. Uma passada só pelas triagens do recorte.
        """
        p_medio = funcionais / total if total else 0.0

        divergencias, pares, rotulos, comparaveis, divergentes = Counter(), Counter(), {}, 0, 0
        for tec_id, diag, const in tri.values_list('tecnico_id', 'defeito_tecnico', 'defeito_constatado'):
            comparavel, diverge = comparar_diagnostico(diag, const)
            comparaveis += comparavel
            if diverge:
                divergentes += 1
                divergencias[tec_id] += 1
                chave = (normalizar_texto(diag), normalizar_texto(const))
                pares[chave] += 1
                rotulos[chave] = (limpar(diag, 50), limpar(const, 50))

        linhas = (tri.values('tecnico_id', 'tecnico__nome', 'tecnico__empresa__razao_social')
                  .annotate(total=Count('id_triagem'), nff=Count('id_triagem', filter=Q(status=NFF))).order_by('-total'))
        tecnicos, funil, maior_n = [], [], 0
        for l in linhas:
            n, k = l['total'], l['nff']
            inf, sup = intervalo_wilson(k, n)
            status, z = classificar(k / n if n else 0.0, p_medio, n)
            tecnicos.append({
                'id': l['tecnico_id'], 'nome': l['tecnico__nome'], 'prestadora': l['tecnico__empresa__razao_social'],
                'total': n, 'nff': k, 'taxa_nff': pct(k, n), 'ic_inf': round(100 * inf, 1), 'ic_sup': round(100 * sup, 1),
                'divergencias': divergencias.get(l['tecnico_id'], 0), 'z': z, 'status': status,
            })
            if n >= MIN_AMOSTRA:
                maior_n = max(maior_n, n)
                funil.append({'nome': l['tecnico__nome'], 'n': n, 'taxa': pct(k, n), 'status': status})

        # Curvas dos limites de 2 e 3 sigma (no máximo ~40 pontos, do menor ao maior volume).
        limites = []
        if funil and 0 < p_medio < 1:
            passo = max(1, (maior_n - MIN_AMOSTRA) // 40)
            limites = [limites_controle(p_medio, n) for n in range(MIN_AMOSTRA, maior_n + passo, passo)]

        itens = [{'diagnostico': rotulos[c][0], 'constatado': rotulos[c][1], 'qtd': q, 'pct': pct(q, divergentes)}
                 for c, q in pares.most_common(8)]
        return {
            'tecnicos': tecnicos,
            'funil': {'p_medio': round(100 * p_medio, 1), 'pontos': funil, 'limites': limites, 'min_amostra': MIN_AMOSTRA},
            'diagnosticos': {'itens': itens, 'divergentes': divergentes, 'comparaveis': comparaveis,
                             'pct_div': pct(divergentes, comparaveis)},
        }

    @staticmethod
    def qualidade(f: Filtros) -> dict:
        tri = BIService._triagens(f)
        total = tri.count()
        defeitos = tri.filter(status=2).count()
        tri_ant = BIService._triagens(f, True)
        total_ant = tri_ant.count()
        taxa = round(defeitos * 100 / total, 1) if total else None
        taxa_ant = round(tri_ant.filter(status=2).count() * 100 / total_ant, 1) if total_ant else None

        modelos = []
        for m in (tri.values(modelo=F('equipamento__modelo'), id_modelo=F('equipamento_id')).annotate(
                total=Count('id_triagem'), defeitos=Count('id_triagem', filter=Q(status=2))).order_by('-defeitos', '-total')[:15]):
            t = round(m['defeitos'] * 100 / m['total'], 1)
            modelos.append({**m, 'taxa': t, 'fator': round(t / taxa, 1) if taxa else None, 'poucos_dados': m['total'] < 5})

        defeitos_rank = _ranking(tri.values_list('defeito_constatado', flat=True), topo=8)
        total_def = sum(d['qtd'] for d in _ranking(tri.values_list('defeito_constatado', flat=True), topo=10_000))
        acumulado, pareto = 0, []
        for d in defeitos_rank:
            acumulado += d['qtd']
            pareto.append({**d, 'pct': round(d['qtd'] * 100 / total_def, 1), 'acumulado': round(acumulado * 100 / total_def, 1)})
        if total_def > acumulado:
            pareto.append({'nome': 'Outros', 'qtd': total_def - acumulado, 'pct': round((total_def - acumulado) * 100 / total_def, 1), 'acumulado': 100.0})

        pecas = Counter()
        rotulo = {}
        for troca, modelo, pn_peca in (tri.exclude(troca__isnull=True).exclude(troca='')
                                       .values_list('troca', 'equipamento__modelo', 'peca_trocada__part_number')):
            # Peça escolhida do cadastro agrupa pelo part number; texto livre (triagens antigas) agrupa pelo texto normalizado.
            chave = (f"pn:{pn_peca}" if pn_peca else _normalizar(troca), modelo)
            if chave[0]:
                pecas[chave] += 1
                rotulo.setdefault(chave, str(troca).strip())
        pecas_trocadas = [{'peca': rotulo[c], 'modelo': c[1], 'qtd': n} for c, n in pecas.most_common(10)]

        reincidentes = (BIService._triagens(f, com_periodo=False).values('sn')
                        .annotate(n=Count('id_triagem'), modelo=Max('equipamento__modelo')).filter(n__gte=2).order_by('-n', 'sn'))

        volume = []
        for v in (tri.filter(criado_em__isnull=False).annotate(sem=TruncWeek('criado_em')).values('sem')
                  .annotate(total=Count('id_triagem'), defeitos=Count('id_triagem', filter=Q(status=2))).order_by('sem')):
            volume.append({'semana': str(v['sem'])[:10], 'total': v['total'], 'defeitos': v['defeitos']})

        def ranking_pessoas(campo):
            return list(tri.values(nome=F(campo)).annotate(total=Count('id_triagem'), defeitos=Count('id_triagem', filter=Q(status=2))).order_by('-total')[:10])

        funcionais = tri.filter(status=NFF).count()
        funcionais_ant = tri_ant.filter(status=NFF).count()
        taxa_nff = round(funcionais * 100 / total, 1) if total else None
        taxa_nff_ant = round(funcionais_ant * 100 / total_ant, 1) if total_ant else None
        ic_inf, ic_sup = intervalo_wilson(funcionais, total)
        nff = {'taxa': _comparar(taxa_nff, taxa_nff_ant, True), 'funcionais': funcionais, 'amostra': total,
               'ic_inf': round(100 * ic_inf, 1) if total else None, 'ic_sup': round(100 * ic_sup, 1) if total else None,
               'referencia': list(REFERENCIA_NFF)}
        informadas, informadas_ant = tri.exclude(troca_indevida__isnull=True).count(), tri_ant.exclude(troca_indevida__isnull=True).count()
        indevidas, indevidas_ant = tri.filter(troca_indevida=True).count(), tri_ant.filter(troca_indevida=True).count()
        troca_indevida = {
            'taxa': _comparar(round(indevidas * 100 / informadas, 1) if informadas else None,
                              round(indevidas_ant * 100 / informadas_ant, 1) if informadas_ant else None, True),
            'indevidas': indevidas, 'informadas': informadas}
        controle = BIService._controle_tecnicos(tri, funcionais, total)

        return {
            'periodo': f.descrever(), 'total': total, 'defeitos': defeitos, 'funcionais': total - defeitos,
            'nff': nff, 'troca_indevida': troca_indevida, 'controle_tecnicos': controle['tecnicos'], 'funil': controle['funil'],
            'diagnosticos': controle['diagnosticos'],
            'taxa_defeito': _comparar(taxa, taxa_ant, True), 'por_modelo': modelos, 'pareto': pareto,
            'pecas_trocadas': pecas_trocadas, 'reincidencia': {'total': reincidentes.count(), 'lista': list(reincidentes[:10])},
            'volume_semanal': volume, 'por_tecnico': ranking_pessoas('tecnico__nome'),
            'por_analista': ranking_pessoas('analista_triagem__nome'),
            'historico_sem_data': Triagem.objects.filter(criado_em__isnull=True).count(),
        }

    # ------------------------------------------------------------------ comercial
    @staticmethod
    def comercial(f: Filtros) -> dict:
        orcs = BIService._orcamentos(f)
        fin, fin_ant = BIService._financeiro(f), BIService._financeiro(f, True)
        enviados = orcs.filter(status__in=ENVIADOS)
        hoje = django_timezone.localdate()
        valor_expr = F('itens__valor_unitario') * F('itens__quantidade') + F('itens__adicional')

        funil = [
            {'etapa': 'Triagens', 'valor': BIService._triagens(f).count()},
            {'etapa': 'Laudos criados', 'valor': orcs.exclude(status='cancelado').count()},
            {'etapa': 'Laudos emitidos', 'valor': enviados.count()},
            {'etapa': 'Aprovados', 'valor': orcs.filter(status='aprovado').count()},
        ]
        abertos = BIService._orcamentos(f, com_periodo=False).filter(status='emitido')
        a_vencer = list(abertos.filter(validade_ate__gte=hoje, validade_ate__lte=hoje + timedelta(days=3))
                        .annotate(valor=Sum(valor_expr, output_field=DEC)).order_by('validade_ate')
                        .values('id_orcamento', 'numero', 'cliente_nome', 'validade_ate', 'valor')[:10])
        for item in a_vencer:
            item['id'] = item.pop('id_orcamento')
            item['valor'] = float(item['valor'] or 0)
            item['validade_ate'] = item['validade_ate'].isoformat()

        emitido_em, decidido_em = {}, {}
        historico = (OrcamentoHistorico.objects.filter(orcamento__in=enviados, motivo='Mudança de status')
                     .order_by('criado_em').values('orcamento_id', 'criado_em', 'alteracoes'))
        for h in historico:
            para = (h['alteracoes'] or [{}])[0].get('para')
            if para == 'Emitido':
                emitido_em.setdefault(h['orcamento_id'], h['criado_em'])
            elif para in ('Aprovado', 'Recusado'):
                decidido_em[h['orcamento_id']] = h['criado_em']
        dias = [(decidido_em[i] - emitido_em[i]).total_seconds() / 86400 for i in decidido_em if i in emitido_em]

        def agrupar(campo, topo=8):
            return [{'nome': l[campo] or '—', 'valor': float(l['valor'] or 0), 'n': l['n']} for l in
                    enviados.values(campo).annotate(valor=Sum(valor_expr, output_field=DEC), n=Count('id_orcamento', distinct=True)).order_by('-valor')[:topo]]

        semanal = [{'semana': str(l['sem'])[:10], 'valor': float(l['valor'] or 0), 'n': l['n']} for l in
                   enviados.annotate(sem=TruncWeek('data_emissao')).values('sem')
                   .annotate(valor=Sum(valor_expr, output_field=DEC), n=Count('id_orcamento', distinct=True)).order_by('sem')]
        return {
            'periodo': f.descrever(), 'funil': funil,
            'por_status': {l['status']: l['n'] for l in orcs.values('status').annotate(n=Count('id_orcamento'))},
            'financeiro': {k: _comparar(fin[k], fin_ant[k], False) for k in ('valor_emitido', 'valor_aprovado', 'taxa_aprovacao', 'ticket_medio', 'margem_pct')},
            'amostras': {'emitidos': fin['qtd_emitidos'], 'decididos': fin['decididos']},
            'pipeline': {'qtd': abertos.count(), 'valor': float(BIService._soma(abertos, 'valor'))},
            'a_vencer': a_vencer,
            'tempo_decisao': {'media_dias': round(mean(dias), 1) if dias else None, 'n': len(dias)},
            'top_clientes': agrupar('cliente_nome'), 'por_uf': agrupar('cliente_uf'), 'valor_semanal': semanal,
        }

    # ------------------------------------------------------------------ peças e custos
    @staticmethod
    def pecas(f: Filtros) -> dict:
        hoje = django_timezone.localdate()
        limite_velha = hoje - timedelta(days=_cfg()['cotacao_velha_dias'])
        enviados = BIService._orcamentos(f).filter(status__in=ENVIADOS)
        itens = ItemOrcamento.objects.filter(orcamento__in=enviados)
        top = [{'pn': l['part_number'] or l['nome'] or '—', 'qtd': l['qtd'] or 0, 'valor': float(l['valor'] or 0)} for l in
               itens.values('part_number', 'nome').annotate(
                   qtd=Sum('quantidade'), valor=Sum(F('valor_unitario') * F('quantidade') + F('adicional'), output_field=DEC)).order_by('-qtd')[:10]]

        vinculadas = Peca.objects.filter(equipamentos__isnull=False).distinct().annotate(ultima=Max('cotacoes__data_cotacao'))
        sem_cotacao = list(vinculadas.filter(ultima__isnull=True).order_by('part_number').values('part_number', 'descricao')[:15])
        velhas = [{'pn': l['part_number'], 'descricao': l['descricao'], 'ultima': l['ultima'].isoformat(),
                   'dias': (hoje - l['ultima']).days} for l in
                  vinculadas.filter(ultima__lt=limite_velha).order_by('ultima').values('part_number', 'descricao', 'ultima')[:15]]

        variacoes, ultimas = [], {}
        desde = hoje - timedelta(days=365)
        cotacoes = (CotacaoPeca.objects.filter(data_cotacao__gte=desde).select_related('peca', 'fornecedor')
                    .order_by('peca_id', '-data_cotacao', '-id_cotacao'))
        por_peca = defaultdict(list)
        for c in cotacoes:
            por_peca[c.peca_id].append(c)
        for lista in por_peca.values():
            if len(lista) >= 2 and lista[1].valor:
                atual, anterior = lista[0], lista[1]
                variacoes.append({'pn': atual.peca.part_number, 'de': float(anterior.valor), 'para': float(atual.valor),
                                  'variacao_pct': round(float((atual.valor - anterior.valor) / anterior.valor * 100), 1),
                                  'data': atual.data_cotacao.isoformat()})
            melhor = {}
            for c in lista:
                melhor.setdefault(c.fornecedor_id, c)        # cotação mais recente de cada fornecedor
            escolhida = min(melhor.values(), key=lambda c: c.valor)
            ultimas[lista[0].peca.part_number] = {'fornecedor': escolhida.fornecedor.razao_social, 'valor': float(escolhida.valor),
                                                  'fornecedores': len(melhor)}
        variacoes.sort(key=lambda v: -abs(v['variacao_pct']))

        recentes = CotacaoPeca.objects.filter(data_cotacao__gte=hoje - timedelta(days=90))
        total_rec = recentes.count()
        concentracao = [{'nome': l['fornecedor__razao_social'], 'qtd': l['n'], 'pct': round(l['n'] * 100 / total_rec, 1)}
                        for l in recentes.values('fornecedor__razao_social').annotate(n=Count('id_cotacao')).order_by('-n')[:8]] if total_rec else []
        return {
            'periodo': f.descrever(), 'top_orcadas': top,
            'melhor_fornecedor': [{'pn': t['pn'], **ultimas[t['pn']]} for t in top if t['pn'] in ultimas],
            'sem_cotacao': sem_cotacao, 'cotacoes_velhas': velhas, 'dias_cotacao_velha': _cfg()['cotacao_velha_dias'],
            'variacoes': variacoes[:10], 'concentracao': concentracao,
            'itens_sem_cotacao_em_laudos': itens.filter(peca__isnull=False, cotacao__isnull=True).count(),
        }

    # ------------------------------------------------------------------ filtros (listas para os seletores)
    @staticmethod
    def opcoes_filtros() -> dict:
        ufs = sorted(set(ChamadoRFB.objects.values_list('estado', flat=True)) | set(Triagem.objects.values_list('estado', flat=True)))
        return {
            'ufs': [u for u in ufs if u],
            'analistas': list(Funcionario.objects.order_by('nome').values('id_funcionario', 'nome')),
            'modelos': list(Equipamento.objects.order_by('modelo').values('id_equipamento', 'modelo')),
            'tecnicos': list(Tecnico.objects.filter(triagem__isnull=False).distinct().order_by('nome').values('id_tecnico', 'nome')),
            'clientes': list(Triagem.objects.filter(cliente__tipo=2).values('cliente_id', 'cliente__razao_social').distinct().order_by('cliente__razao_social')),
        }

    # ------------------------------------------------------------------ insights
    @staticmethod
    def listar_insights(limite: int = 30, apenas_nao_lidos: bool = False) -> list:
        qs = Insight.objects.all()
        if apenas_nao_lidos:
            qs = qs.filter(lido=False)
        ordem = {'critico': 0, 'atencao': 1, 'info': 2}
        itens = sorted(qs[:200], key=lambda i: (i.lido, ordem.get(i.severidade, 3)))
        return [{'id': i.id_insight, 'tipo': i.tipo, 'severidade': i.severidade, 'titulo': i.titulo, 'texto': i.texto,
                 'link': i.link, 'lido': i.lido, 'criado_em': django_timezone.localtime(i.criado_em).isoformat()}
                for i in itens[:limite]]

    @staticmethod
    def marcar_insight(id_insight: int, lido: bool = True) -> None:
        if Insight.objects.filter(pk=id_insight).update(lido=lido) == 0:
            raise Insight.DoesNotExist("Insight não encontrado.")

    @staticmethod
    def _registrar(tipo, severidade, titulo, texto, link, chave):
        Insight.objects.update_or_create(chave=chave, defaults={
            'tipo': tipo, 'severidade': severidade, 'titulo': titulo[:200], 'texto': texto[:500], 'link': link})

    @staticmethod
    def gerar_insights() -> int:
        """Regras simples e explicáveis. A chave inclui a data, então o mesmo aviso não se repete no dia."""
        cfg, hoje = _cfg(), django_timezone.localdate()
        dia = hoje.isoformat()
        gerados = 0

        faixas = {'100': 0, '80': 0, '60': 0}
        for c in ChamadoRFB.objects.exclude(status__in=INATIVOS).values('is_metropolitana', 'horas_consumidas'):
            pct = _pct_sla(c['horas_consumidas'], c['is_metropolitana'])
            if pct > 100:
                faixas['100'] += 1
            elif pct >= 80:
                faixas['80'] += 1
            elif pct >= 60:
                faixas['60'] += 1
        textos = {'100': ('critico', 'chamado(s) estouraram o SLA'), '80': ('critico', 'chamado(s) passaram de 80% do SLA'),
                  '60': ('atencao', 'chamado(s) passaram de 60% do SLA')}
        for faixa, n in faixas.items():
            if n:
                sev, rotulo = textos[faixa]
                BIService._registrar('sla', sev, f"{n} {rotulo}", 'Veja a lista de chamados críticos na visão Operação e SLA.',
                                     '/gerenciar-chamados-rfb/', f"sla{faixa}:{dia}")
                gerados += 1

        a_vencer = Orcamento.objects.filter(status='emitido', validade_ate__gte=hoje, validade_ate__lte=hoje + timedelta(days=3))
        if a_vencer.exists():
            BIService._registrar('laudo_vencendo', 'atencao', f"{a_vencer.count()} laudo(s) vencem em até 3 dias",
                                 f"Somam {_brl(BIService._soma(a_vencer, 'valor'))}. Vale cobrar uma resposta do cliente.",
                                 '/orcamentos/pesquisa/', f"vencendo:{dia}")
            gerados += 1

        limite_velha = hoje - timedelta(days=cfg['cotacao_velha_dias'])
        n_velhas = Peca.objects.filter(equipamentos__isnull=False).distinct().annotate(u=Max('cotacoes__data_cotacao')).filter(u__lt=limite_velha).count()
        if n_velhas:
            BIService._registrar('cotacao_velha', 'info', f"{n_velhas} peça(s) com cotação de mais de {cfg['cotacao_velha_dias']} dias",
                                 'Os laudos novos usarão preços possivelmente desatualizados.', '/gerenciar-modelo-equipamento/', f"cotvelha:{dia}")
            gerados += 1

        desde = hoje - timedelta(days=90)
        recentes = Triagem.objects.filter(criado_em__date__gte=desde)
        total = recentes.count()
        if total >= cfg['modelo_min_n']:
            media = recentes.filter(status=2).count() / total
            for m in (recentes.values(modelo=F('equipamento__modelo')).annotate(
                    n=Count('id_triagem'), d=Count('id_triagem', filter=Q(status=2))).filter(n__gte=cfg['modelo_min_n'])):
                taxa = m['d'] / m['n']
                if media and taxa >= cfg['modelo_fator'] * media:
                    BIService._registrar('modelo', 'atencao', f"{m['modelo']} falha {taxa / media:.1f}× a média",
                                         f"{m['d']} defeitos em {m['n']} triagens nos últimos 90 dias (média geral {media * 100:.0f}%).",
                                         '/dashboard/', f"modelo:{m['modelo']}:{dia}"[:120])
                    gerados += 1

        reinc = Triagem.objects.values('sn').annotate(n=Count('id_triagem')).filter(n__gte=3).count()
        if reinc:
            BIService._registrar('reincidencia', 'atencao', f"{reinc} equipamento(s) com 3 ou mais triagens",
                                 'Mesmo número de série voltando repetidamente: vale investigar a causa.', '/dashboard/', f"reinc:{dia}")
            gerados += 1

        f = Filtros({'inicio': (hoje - timedelta(days=29)).isoformat(), 'fim': dia})
        atual, anterior = BIService._financeiro(f), BIService._financeiro(f, True)
        if (atual['taxa_aprovacao'] is not None and anterior['taxa_aprovacao'] is not None
                and atual['decididos'] >= 10 and anterior['decididos'] >= 10
                and anterior['taxa_aprovacao'] - atual['taxa_aprovacao'] >= 10):
            BIService._registrar('aprovacao', 'atencao',
                                 f"Aprovação caiu de {anterior['taxa_aprovacao']:.0f}% para {atual['taxa_aprovacao']:.0f}%",
                                 'Comparação dos últimos 30 dias com os 30 anteriores.', '/orcamentos/estatisticas/', f"aprovacao:{dia}")
            gerados += 1

        semanas = [v['n'] for v in Triagem.objects.filter(criado_em__date__gte=hoje - timedelta(days=70))
                   .annotate(sem=TruncWeek('criado_em')).values('sem').annotate(n=Count('id_triagem')).order_by('sem')]
        if len(semanas) >= 9:
            historico, ultima = semanas[-9:-1], semanas[-1]
            if mean(historico) > 0 and ultima > mean(historico) + 2 * pstdev(historico):
                BIService._registrar('pico', 'info', 'Volume de triagens acima do normal nesta semana',
                                     f"{ultima} triagens contra média de {mean(historico):.0f} nas 8 semanas anteriores.", '/dashboard/', f"pico:{dia}")
                gerados += 1
        return gerados

    # ------------------------------------------------------------------ e-mail de SLA
    @staticmethod
    def enviar_alertas_sla() -> dict:
        """
        Um e-mail por analista (com o e-mail cadastrado) listando os chamados que cruzaram 60%, 80% ou 100%.
        Cada chamado/faixa só é avisado uma vez. Sem EMAIL_HOST configurado, nada é enviado.
        """
        resultado = {'enviados': 0, 'chamados': 0, 'ignorado': None}
        if not getattr(settings, 'EMAIL_ENABLED', False):
            resultado['ignorado'] = 'E-mail não configurado (defina EMAIL_HOST).'
            return resultado
        pendentes = defaultdict(list)
        for c in (ChamadoRFB.objects.exclude(status__in=INATIVOS).select_related('analista_responsavel')
                  .exclude(analista_responsavel__isnull=True)):
            email = c.analista_responsavel.email
            if not email:
                continue
            pct = _pct_sla(c.horas_consumidas, c.is_metropolitana)
            faixa = 100 if pct > 100 else 80 if pct >= 80 else 60 if pct >= 60 else 0
            if faixa and not AlertaSLAEnviado.objects.filter(chamado=c, faixa__gte=faixa).exists():
                pendentes[email].append((c, pct, faixa))
        base_url = getattr(settings, 'SITE_URL', '').rstrip('/')
        for email, itens in pendentes.items():
            itens.sort(key=lambda x: -x[1])
            linhas = [f"- Ticket {c.ticket} ({c.cidade}/{c.estado}, {c.modelo_equipamento}): {pct:.0f}% do SLA" for c, pct, _ in itens]
            corpo = ("Chamados do RFB que passaram de um limite de SLA:\n\n" + "\n".join(linhas) +
                     f"\n\nAcompanhe em {base_url}/gerenciar-chamados-rfb/\n")
            send_mail(f"[Daedalus] {len(itens)} chamado(s) do RFB precisam de atenção", corpo, None, [email])
            for c, _, faixa in itens:
                AlertaSLAEnviado.objects.update_or_create(chamado=c, faixa=faixa, defaults={'destinatario': email})
            resultado['enviados'] += 1
            resultado['chamados'] += len(itens)
        return resultado
