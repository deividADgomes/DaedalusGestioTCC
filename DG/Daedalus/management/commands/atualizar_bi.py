from django.core.management.base import BaseCommand

from Daedalus.services.alertas_rfb import AlertasRFBService
from Daedalus.services.bi import BIService


class Command(BaseCommand):
    help = (
        "Atualiza o BI: recalcula o SLA dos chamados ativos, grava o retrato diário, gera os insights "
        "e (opcionalmente) envia os e-mails de SLA. Para o aviso de chamados sem agendamento chegar a tempo, agende de hora em hora (ex.: Cron Job do Render, 0 * * * *)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--emails', action='store_true', help='Envia os e-mails de alerta de SLA (60%, 80% e 100%) e o de chamados sem agendamento (75%).')

    def handle(self, *args, **opcoes):
        BIService.atualizar_se_necessario(forcar=True)
        self.stdout.write(self.style.SUCCESS('SLA, retrato do dia e insights atualizados.'))
        if opcoes['emails']:
            resultado = BIService.enviar_alertas_sla()
            if resultado['ignorado']:
                self.stdout.write(self.style.WARNING(resultado['ignorado']))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"E-mails enviados: {resultado['enviados']} (chamados avisados: {resultado['chamados']})."))

            # Chamados sem agendamento que chegaram ao limite de SLA (padrão 75%): aviso único por chamado.
            nao_agendados = AlertasRFBService.enviar()
            if nao_agendados['ignorado']:
                self.stdout.write(self.style.WARNING(f"Chamados sem agendamento: {nao_agendados['ignorado']}"))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Chamados sem agendamento: {nao_agendados['enviados']} e-mail(s), {nao_agendados['chamados']} chamado(s) avisado(s)."))
