"""Alerta por e-mail de chamados RFB que ainda não estão agendados e já consumiram boa parte do SLA."""
import logging
from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail

from ..models import AgendamentoChamado, AlertaNaoAgendado, ChamadoRFB
from .bi import INATIVOS, _limite, _pct_sla
from .relatorios import RelatorioService

logger = logging.getLogger(__name__)


class AlertasRFBService:
    @staticmethod
    def limiar() -> float:
        return float(getattr(settings, 'RFB_ALERTA_NAO_AGENDADO_PCT', 75.0))

    @staticmethod
    def nao_agendados_acima_do_limiar(limiar=None) -> list:
        """
        Chamados ativos SEM visita agendada pendente (mesmo critério do filtro "Agendado" da tela de RFB) com
        o SLA consumido no limiar ou acima. Devolve [(chamado, percentual)], do mais atrasado ao menos.
        Usa as horas já gravadas: o comando atualizar_bi as recalcula antes de chamar isto.
        """
        limiar = AlertasRFBService.limiar() if limiar is None else limiar
        agendados = set(AgendamentoChamado.objects.filter(status='pendente', tipo_pausa='agendamento')
                        .values_list('chamado_id', flat=True))
        achados = []
        for c in ChamadoRFB.objects.exclude(status__in=INATIVOS).select_related('analista_responsavel'):
            if c.pk in agendados:
                continue
            pct = _pct_sla(c.horas_consumidas, c.is_metropolitana)
            if pct >= limiar:
                achados.append((c, pct))
        achados.sort(key=lambda x: -x[1])
        return achados

    @staticmethod
    def _destinos(novos: list) -> dict:
        """Agrupa os chamados por e-mail de destino, conforme RFB_ALERTA_NAO_AGENDADO_PARA."""
        modo = getattr(settings, 'RFB_ALERTA_NAO_AGENDADO_PARA', 'gestao')
        gestao = RelatorioService.destinatarios()
        destinos = defaultdict(list)
        for c, pct in novos:
            emails = set()
            if modo != 'analista':           # 'gestao', 'ambos' (ou um valor desconhecido: o padrão é avisar a gestão)
                emails.update(gestao)
            if modo in ('analista', 'ambos'):
                analista = c.analista_responsavel
                if analista and analista.email:
                    emails.add(analista.email)
                else:
                    emails.update(gestao)      # sem analista com e-mail, o aviso não pode se perder
            for e in emails:
                destinos[e].append((c, pct))
        return destinos

    @staticmethod
    def enviar() -> dict:
        resultado = {'enviados': 0, 'chamados': 0, 'ignorado': None}
        if not getattr(settings, 'EMAIL_ENABLED', False):
            resultado['ignorado'] = 'E-mail não configurado (defina EMAIL_HOST).'
            return resultado
        ja_avisados = set(AlertaNaoAgendado.objects.values_list('chamado_id', flat=True))
        novos = [(c, pct) for c, pct in AlertasRFBService.nao_agendados_acima_do_limiar() if c.pk not in ja_avisados]
        if not novos:
            return resultado
        destinos = AlertasRFBService._destinos(novos)
        if not destinos:
            resultado['ignorado'] = 'Nenhum destinatário com e-mail (cadastre o e-mail de um Gestor ou defina ADMIN_EMAIL).'
            return resultado

        limiar = AlertasRFBService.limiar()
        link = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        avisados = defaultdict(set)         # chamado -> e-mails que receberam de fato
        for email, itens in destinos.items():
            itens.sort(key=lambda x: -x[1])
            linhas = []
            for c, pct in itens:
                analista = c.analista_responsavel.nome if c.analista_responsavel else 'sem analista'
                limite = _limite(c.is_metropolitana)
                linhas.append(f"- Ticket {c.ticket} ({c.cidade}/{c.estado}, {c.modelo_equipamento}): {pct:.0f}% do SLA "
                              f"({c.horas_consumidas:.0f}h de {limite:.0f}h) | analista: {analista}")
            corpo = (f"Chamados do RFB que ainda NÃO estão agendados e já consumiram {limiar:.0f}% ou mais do SLA:\n\n"
                     + "\n".join(linhas)
                     + "\n\nAgende estes chamados o quanto antes para não estourar o prazo."
                     + (f"\nAcompanhe em {link}/gerenciar-chamados-rfb/" if link else ""))
            try:
                send_mail(f"[Daedalus] {len(itens)} chamado(s) RFB sem agendamento com {limiar:.0f}% do SLA consumido",
                          corpo, None, [email])
            except Exception:
                logger.exception("Falha ao enviar o alerta de chamados não agendados para %s", email)
                continue
            resultado['enviados'] += 1
            for c, _ in itens:
                avisados[c].add(email)

        # Só marca como avisado quem realmente saiu; o que falhou tenta de novo na próxima rodada.
        for c, emails in avisados.items():
            AlertaNaoAgendado.objects.update_or_create(chamado=c, defaults={'destinatario': ', '.join(sorted(emails))[:500]})
        resultado['chamados'] = len(avisados)
        return resultado
