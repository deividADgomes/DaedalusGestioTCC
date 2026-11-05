from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from ..models import AgendamentoChamado, AlertaNaoAgendado, ChamadoRFB
from ..services.alertas_rfb import AlertasRFBService
from .base import BaseTestCase


@override_settings(EMAIL_ENABLED=True, RFB_ALERTA_NAO_AGENDADO_PCT=75.0, RFB_ALERTA_NAO_AGENDADO_PARA='gestao')
class AlertaChamadoNaoAgendadoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=31, nome='Gil Gestor', email='gil@exemplo.com')
        self.analista = self.criar_funcionario(cargo='Analista de Triagem', login=32, nome='Ana Analista', email='ana@exemplo.com')
        self.n = 0

    def chamado(self, horas, metropolitana=True, status='aberto', analista=None):
        self.n += 1
        return ChamadoRFB.objects.create(
            ticket=f'RFB{self.n}', data_abertura=timezone.now() - timedelta(hours=horas), estado='SP', cidade='Sorocaba',
            is_metropolitana=metropolitana, descricao_defeito='x', modelo_equipamento='ProBook', sn=f'SN{self.n}',
            status=status, horas_consumidas=horas, analista_responsavel=analista)

    def agendar(self, chamado, tipo='agendamento', status='pendente'):
        return AgendamentoChamado.objects.create(
            chamado=chamado, tipo_pausa=tipo, status=status, data_agendamento=timezone.now() + timedelta(days=1))

    def test_dispara_exatamente_em_75_por_cento_do_sla(self):
        self.chamado(54)                       # 54h de 72h (metropolitana) = 75%
        self.chamado(53)                       # 73,6%: ainda não
        r = AlertasRFBService.enviar()
        self.assertEqual((r['enviados'], r['chamados']), (1, 1))
        self.assertIn('RFB1', mail.outbox[0].body)
        self.assertNotIn('RFB2', mail.outbox[0].body)
        self.assertIn('75%', mail.outbox[0].body)

    def test_interior_usa_o_limite_de_120_horas(self):
        self.chamado(90, metropolitana=False)  # 90h de 120h = 75%
        self.chamado(80, metropolitana=False)  # 66%
        self.assertEqual(AlertasRFBService.enviar()['chamados'], 1)

    def test_chamado_com_visita_agendada_pendente_nao_alerta(self):
        self.agendar(self.chamado(60))
        r = AlertasRFBService.enviar()
        self.assertEqual((r['enviados'], len(mail.outbox)), (0, 0))

    def test_agendamento_realizado_ou_frustrado_ou_sem_resposta_continua_sem_agendamento(self):
        self.agendar(self.chamado(60), status='realizado')
        self.agendar(self.chamado(60), status='frustrado')
        self.agendar(self.chamado(60), tipo='sem_resposta')
        self.assertEqual(AlertasRFBService.enviar()['chamados'], 3)

    def test_chamado_concluido_ou_cancelado_nao_alerta(self):
        self.chamado(70, status='concluido')
        self.chamado(70, status='cancelado')
        self.assertEqual(AlertasRFBService.enviar()['chamados'], 0)

    def test_cada_chamado_e_avisado_uma_unica_vez(self):
        self.chamado(60)
        AlertasRFBService.enviar()
        AlertasRFBService.enviar()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(AlertaNaoAgendado.objects.count(), 1)

    def test_chamado_novo_que_cruza_depois_e_avisado_sozinho(self):
        self.chamado(60)
        AlertasRFBService.enviar()
        self.chamado(70)
        AlertasRFBService.enviar()
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotIn('RFB1', mail.outbox[1].body)

    def test_varios_chamados_vao_num_unico_email_do_mais_atrasado_ao_menos(self):
        self.chamado(55)
        self.chamado(70)
        AlertasRFBService.enviar()
        self.assertEqual(len(mail.outbox), 1)
        corpo = mail.outbox[0].body
        self.assertLess(corpo.index('RFB2'), corpo.index('RFB1'))

    def test_por_padrao_vai_para_a_gestao_nao_para_o_analista(self):
        self.chamado(60, analista=self.analista)
        AlertasRFBService.enviar()
        self.assertEqual(mail.outbox[0].to, ['gil@exemplo.com'])

    @override_settings(RFB_ALERTA_NAO_AGENDADO_PARA='analista')
    def test_modo_analista_envia_direto_para_o_responsavel(self):
        self.chamado(60, analista=self.analista)
        AlertasRFBService.enviar()
        self.assertEqual([m.to for m in mail.outbox], [['ana@exemplo.com']])

    @override_settings(RFB_ALERTA_NAO_AGENDADO_PARA='analista')
    def test_modo_analista_sem_responsavel_cai_para_a_gestao(self):
        self.chamado(60, analista=None)
        AlertasRFBService.enviar()
        self.assertEqual([m.to for m in mail.outbox], [['gil@exemplo.com']])

    @override_settings(RFB_ALERTA_NAO_AGENDADO_PARA='ambos')
    def test_modo_ambos_avisa_os_dois(self):
        self.chamado(60, analista=self.analista)
        AlertasRFBService.enviar()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['ana@exemplo.com', 'gil@exemplo.com'])
        self.assertEqual(AlertaNaoAgendado.objects.count(), 1)

    def test_sem_destinatario_nao_marca_como_avisado(self):
        from ..models import Funcionario
        Funcionario.objects.update(email='')
        self.chamado(60)
        r = AlertasRFBService.enviar()
        self.assertIn('Nenhum destinatário', r['ignorado'])
        self.assertEqual(AlertaNaoAgendado.objects.count(), 0)

    @override_settings(EMAIL_ENABLED=False)
    def test_sem_servidor_de_email_nao_envia_nem_marca(self):
        self.chamado(60)
        r = AlertasRFBService.enviar()
        self.assertIn('E-mail não configurado', r['ignorado'])
        self.assertEqual((len(mail.outbox), AlertaNaoAgendado.objects.count()), (0, 0))

    @override_settings(RFB_ALERTA_NAO_AGENDADO_PCT=50.0)
    def test_o_percentual_e_configuravel(self):
        self.chamado(40)                       # 55%
        self.assertEqual(AlertasRFBService.enviar()['chamados'], 1)

    def test_o_sino_conta_os_chamados_sem_agendamento(self):
        self.entrar(self.gestor)
        self.chamado(60)
        self.agendar(self.chamado(60))
        itens = {i['tipo']: i for i in self.client.get('/api/avisos/').json()['dado']['itens']}
        self.assertEqual(itens['rfb_agendamento']['quantidade'], 1)
