from datetime import date, timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from ..models import Peca, Triagem
from ..services.manutencao import ManutencaoService
from .test_bi import BIBase


class VincularPecasTrocadasTests(BIBase):
    def setUp(self):
        super().setUp()
        self.tela = Peca.objects.create(part_number='L1-TELA', descricao='Tela 14 HD')
        self.bateria = Peca.objects.create(part_number='B1', descricao='Bateria')
        self.equip.pecas.add(self.tela, self.bateria)

    def com_troca(self, texto):
        return self.triagem(status=2, troca=texto)

    def test_simulacao_nao_altera_nada(self):
        t = self.com_troca('trocada a L1-TELA do cliente')
        r = ManutencaoService.vincular_pecas_trocadas(aplicar=False)
        self.assertEqual(r['vinculadas'], 1)
        self.assertIsNone(Triagem.objects.get(pk=t.pk).peca_trocada_id)

    def test_aplicar_vincula_pelo_part_number_inteiro(self):
        t = self.com_troca('Troca da l1-tela')
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=StringIO())
        t.refresh_from_db()
        self.assertEqual(t.peca_trocada_id, self.tela.id_peca)
        self.assertEqual(t.troca, 'Troca da l1-tela')                  # o texto original fica como estava

    def test_vincula_quando_a_descricao_e_igual_ao_texto(self):
        t = self.com_troca('  BATERIA ')
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=StringIO())
        t.refresh_from_db()
        self.assertEqual(t.peca_trocada_id, self.bateria.id_peca)

    def test_pn_dentro_de_outra_palavra_nao_vale(self):
        t = self.com_troca('B100 trocada')                              # "B1" aparece, mas não como palavra inteira
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=StringIO())
        t.refresh_from_db()
        self.assertIsNone(t.peca_trocada_id)

    def test_duas_pecas_possiveis_e_ambiguo_e_nao_vincula(self):
        t = self.com_troca('L1-TELA e B1 trocadas')
        saida = StringIO()
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=saida)
        t.refresh_from_db()
        self.assertIsNone(t.peca_trocada_id)
        self.assertIn('ambíguas (mais de uma peça serve): 1', saida.getvalue())

    def test_peca_de_outro_modelo_nao_e_considerada(self):
        outra = Peca.objects.create(part_number='ZZ9', descricao='Outra')
        t = self.com_troca('ZZ9')
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=StringIO())
        t.refresh_from_db()
        self.assertIsNone(t.peca_trocada_id)
        self.assertEqual(outra.part_number, 'ZZ9')

    def test_quem_ja_tem_vinculo_nao_e_tocado(self):
        t = self.com_troca('B1')
        Triagem.objects.filter(pk=t.pk).update(peca_trocada=self.tela)
        call_command('vincular_pecas_trocadas', '--aplicar', stdout=StringIO())
        t.refresh_from_db()
        self.assertEqual(t.peca_trocada_id, self.tela.id_peca)


class RelatoriosPorEmailTests(BIBase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=2001, nome='Gil Gestor', email='gil@exemplo.com')

    def triagens_do_mes_passado(self, tecnico, qtd, status):
        primeiro = date.today().replace(day=1)
        for _ in range(qtd):
            t = self.triagem(status=status)
            data = timezone.now().replace(year=(primeiro - timedelta(days=1)).year, month=(primeiro - timedelta(days=1)).month, day=15)
            Triagem.objects.filter(pk=t.pk).update(tecnico=tecnico, criado_em=data)

    def test_relatorio_mensal_e_enviado_a_gestao_com_os_numeros_do_mes(self):
        self.triagens_do_mes_passado(self.tecnico, 4, 2)
        saida = StringIO()
        call_command('enviar_relatorio_mensal', stdout=saida)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('gil@exemplo.com', mail.outbox[0].to)
        self.assertIn('Triagens: 4', mail.outbox[0].body)
        self.assertIn('Relatório mensal', mail.outbox[0].subject)

    def test_mes_informado_invalido_da_erro(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('enviar_relatorio_mensal', '--mes', '2026-13', stdout=StringIO())

    def test_sem_destinatario_nao_envia_e_avisa(self):
        from ..models import Funcionario
        Funcionario.objects.filter(cargo__in=['Gestor', 'Administrador']).update(email='')
        saida = StringIO()
        call_command('enviar_relatorio_mensal', stdout=saida)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('Nenhum Administrador ou Gestor', saida.getvalue())

    def test_alerta_de_tecnicos_so_envia_se_houver_alguem_fora_do_padrao(self):
        saida = StringIO()
        call_command('alertar_tecnicos', stdout=saida)
        self.assertEqual(len(mail.outbox), 0)

    def test_alerta_de_tecnicos_avisa_quem_esta_fora_do_limite(self):
        from ..models import Tecnico
        ruim = Tecnico.objects.create(empresa=self.cliente, nome='Técnico Ruim')
        for _ in range(10):
            t = self.triagem(status=1)                                   # 100% NFF
            Triagem.objects.filter(pk=t.pk).update(tecnico=ruim)
        for _ in range(40):
            self.triagem(status=2)                                       # o resto não tem NFF
        call_command('alertar_tecnicos', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Técnico Ruim', mail.outbox[0].body)
