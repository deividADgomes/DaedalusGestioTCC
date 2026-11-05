from datetime import date

from django.core.management.base import BaseCommand, CommandError

from Daedalus.services.relatorios import RelatorioService


class Command(BaseCommand):
    help = ("Envia por e-mail o resumo do mês (triagens, orçamentos, RFB e técnicos fora do padrão) aos Administradores e Gestores. "
            "Sem --mes, usa o mês anterior. Agende para o dia 1 (Cron Job do Render: 0 11 1 * *).")

    def add_arguments(self, parser):
        parser.add_argument('--mes', help='Mês no formato AAAA-MM (padrão: o mês anterior).')

    def handle(self, *args, **opcoes):
        if opcoes['mes']:
            try:
                ano, mes = (int(p) for p in opcoes['mes'].split('-'))
                date(ano, mes, 1)
            except ValueError:
                raise CommandError('Use o formato AAAA-MM, por exemplo 2026-10.')
        else:
            hoje = date.today()
            ano, mes = (hoje.year - 1, 12) if hoje.month == 1 else (hoje.year, hoje.month - 1)
        r = RelatorioService.enviar_mensal(ano, mes)
        if r['enviado']:
            self.stdout.write(self.style.SUCCESS(f"Relatório de {r['titulo']} enviado a {r['destinatarios']} destinatário(s)."))
        else:
            self.stdout.write(self.style.WARNING(r['motivo']))
