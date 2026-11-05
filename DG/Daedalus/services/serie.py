"""Tudo o que já aconteceu com um número de série: triagens, laudos (orçamentos) e chamados RFB."""
from django.db.models import Q
from django.utils import timezone as django_timezone

from ..models import ChamadoRFB, Orcamento, Triagem


def _iso(valor):
    if valor is None:
        return None
    return django_timezone.localtime(valor).isoformat() if hasattr(valor, 'hour') else valor.isoformat()


def _limpar_sn(sn) -> str:
    return (sn or '').strip()


class SerieService:
    @staticmethod
    def triagens_da_serie(sn: str, excluir=None) -> list:
        """Triagens anteriores do mesmo número de série (aviso de reincidência na tela de triagem)."""
        sn = _limpar_sn(sn)
        if not sn:
            return []
        qs = Triagem.objects.filter(sn__iexact=sn).select_related('equipamento', 'cliente')
        if excluir:
            qs = qs.exclude(pk=excluir)
        return [
            {'id': t.id_triagem, 'n_ticket': t.n_ticket, 'criado_em': _iso(t.criado_em),
             'modelo': t.equipamento.modelo, 'cliente': t.cliente.razao_social,
             'status': 'Funcional' if t.status == 1 else 'Defeito', 'conclusao': (t.conclusao or '')[:120]}
            for t in qs.order_by('-criado_em', '-id_triagem')[:20]
        ]

    @staticmethod
    def linha_do_tempo(sn: str) -> dict:
        sn = _limpar_sn(sn)
        if not sn:
            raise ValueError("Informe o número de série.")
        eventos = []

        triagens = Triagem.objects.filter(sn__iexact=sn).select_related('equipamento', 'cliente')
        for t in triagens:
            eventos.append({
                'tipo': 'triagem', 'data': _iso(t.criado_em), 'titulo': f"Triagem do ticket {t.n_ticket}",
                'detalhe': f"{t.equipamento.modelo} · {t.cliente.razao_social}",
                'status': 'Funcional (NFF)' if t.status == 1 else 'Defeito confirmado',
                'texto': (t.conclusao or '')[:200], 'url': f"/visualizar/?id={t.id_triagem}"})

        orcamentos = Orcamento.objects.filter(Q(equip_sn__iexact=sn) | Q(triagem__sn__iexact=sn)).distinct()
        for o in orcamentos:
            eventos.append({
                'tipo': 'orcamento', 'data': _iso(o.data_emissao) or _iso(o.criado_em), 'titulo': f"Laudo {o.numero}",
                'detalhe': o.cliente_nome, 'status': o.get_status_display(), 'texto': '',
                'url': f"/orcamentos/emissao/?id={o.id_orcamento}"})

        for c in ChamadoRFB.objects.filter(sn__iexact=sn):
            eventos.append({
                'tipo': 'rfb', 'data': _iso(c.data_abertura), 'titulo': f"Chamado RFB {c.ticket}",
                'detalhe': c.modelo_equipamento, 'status': c.get_status_display(), 'texto': '',
                'url': '/gerenciar-chamados-rfb/'})

        # Mais recente primeiro; o que não tem data (triagens antigas) vai para o fim.
        eventos.sort(key=lambda e: (e['data'] is None, '' if e['data'] is None else e['data']), reverse=False)
        com_data = sorted([e for e in eventos if e['data']], key=lambda e: e['data'], reverse=True)
        sem_data = [e for e in eventos if not e['data']]
        eventos = com_data + sem_data
        contagem = {tipo: sum(1 for e in eventos if e['tipo'] == tipo) for tipo in ('triagem', 'orcamento', 'rfb')}
        return {'sn': sn, 'eventos': eventos, 'resumo': contagem}
