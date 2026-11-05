from datetime import date, timedelta

from django.core.management.base import BaseCommand

from Daedalus.services.relatorios import RelatorioService


class Command(BaseCommand):
    help = ("Avisa por e-mail os Administradores e Gestores quando algum técnico tem taxa de NFF fora do padrão nos últimos dias. "
            "Só envia se houver alguém fora do padrão. Agende toda segunda (Cron Job do Render: 0 11 * * 1).")

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30, help='Janela analisada, em dias (padrão: 30).')

    def handle(self, *args, **opcoes):
        fim = date.today()
        r = RelatorioService.alertar_tecnicos(fim - timedelta(days=max(opcoes['dias'], 1) - 1), fim)
        if r['enviado']:
            self.stdout.write(self.style.SUCCESS(f"Alerta enviado: {r['tecnicos']} técnico(s), {r['destinatarios']} destinatário(s)."))
        else:
            self.stdout.write(self.style.WARNING(r['motivo']))
