from django.core.management.base import BaseCommand

from Daedalus.services.manutencao import ManutencaoService


class Command(BaseCommand):
    help = ("Liga o texto livre antigo de 'peça trocada' das triagens às peças cadastradas no modelo. "
            "Sem --aplicar só simula e mostra o que seria feito.")

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Grava os vínculos (sem esta opção nada é alterado).')

    def handle(self, *args, **opcoes):
        r = ManutencaoService.vincular_pecas_trocadas(aplicar=opcoes['aplicar'])
        self.stdout.write(f"Triagens analisadas: {r['analisadas']}")
        self.stdout.write(f"  com uma correspondência clara: {r['vinculadas']}")
        self.stdout.write(f"  ambíguas (mais de uma peça serve): {r['ambiguas']}")
        self.stdout.write(f"  sem correspondência: {r['sem_correspondencia']}")
        for exemplo in r['exemplos']:
            self.stdout.write(f"    ex.: {exemplo}")
        if opcoes['aplicar']:
            self.stdout.write(self.style.SUCCESS(f"{r['vinculadas']} vínculo(s) gravado(s)."))
        else:
            self.stdout.write(self.style.WARNING('Simulação: nada foi alterado. Rode de novo com --aplicar para gravar.'))
