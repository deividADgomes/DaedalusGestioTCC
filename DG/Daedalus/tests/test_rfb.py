import importlib
from unittest import mock

from django.apps import apps
from django.utils import timezone

from ..models import ChamadoRFB, Equipamento, Peca
from ..services.chamado_rfb import ChamadoRFBService
from .base import BaseTestCase

IBGE = 'Daedalus.services.chamado_rfb.consultar_ibge_metropolitana'


class RFBBase(BaseTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch(IBGE, return_value=False)      # a consulta ao IBGE usa a internet
        patcher.start()
        self.addCleanup(patcher.stop)
        self.func = self.criar_funcionario(cargo='Gestor', nome='Gina', email='gina@exemplo.com')
        self.entrar(self.func)
        self.eq = Equipamento.objects.create(pn='RFB-1', modelo='HP EliteBook 640 G10', rfb=True)
        self.fora = Equipamento.objects.create(pn='OUT-1', modelo='Modelo Antigo', rfb=False)
        self.p1 = Peca.objects.create(part_number='P-TELA', descricao='Tela')
        self.p2 = Peca.objects.create(part_number='P-BAT', descricao='Bateria')
        self.eq.pecas.add(self.p1, self.p2)
        self.outra = Peca.objects.create(part_number='P-OUTRA', descricao='De outro modelo')
        self.fora.pecas.add(self.outra)
        self._n = 0

    def novo(self, **extra):
        dados = {'ticket': 'T100', 'sn': 'SN1', 'cidade': 'Sorocaba', 'estado': 'SP', 'data_abertura': timezone.now().isoformat(),
                 'descricao_defeito': 'Não liga', 'equipamento_id': self.eq.id_equipamento}
        dados.update(extra)
        return self.post_json('/api/chamados-rfb/', dados)

    def chamado(self, equipamento='padrao', **kw):
        self._n += 1
        eq = self.eq if equipamento == 'padrao' else equipamento
        return ChamadoRFB.objects.create(
            ticket=kw.pop('ticket', f'C{self._n}'), data_abertura=timezone.now(), estado='SP', cidade='Sorocaba',
            descricao_defeito='x', modelo_equipamento=eq.modelo if eq else 'Sem cadastro', sn=f'S{self._n}', equipamento=eq,
            status=kw.pop('status', 'andamento'), **kw)

    def encerrar(self, chamado, **extra):
        dados = {'id': chamado.id_chamado, 'status': 'concluido', 'data_conclusao': timezone.now().isoformat()}
        dados.update(extra)
        return self.post_json('/api/chamados-rfb/', dados)


class ModelosDoRFBTests(RFBBase):
    def test_lista_so_os_modelos_do_rfb_e_com_todos_traz_a_marca(self):
        lista = self.client.get('/api/rfb/modelos/').json()['dados']
        self.assertEqual([m['modelo'] for m in lista], ['HP EliteBook 640 G10'])
        todos = {m['modelo']: m['rfb'] for m in self.client.get('/api/rfb/modelos/', {'todos': 1}).json()['dados']}
        self.assertEqual(todos, {'HP EliteBook 640 G10': True, 'Modelo Antigo': False})

    def test_retirar_do_rfb_so_esconde_e_nao_apaga(self):
        antigo = self.chamado()
        r = self.post_json('/api/rfb/modelos/', {'id': self.eq.id_equipamento, 'rfb': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get('/api/rfb/modelos/').json()['dados'], [])
        self.assertTrue(Equipamento.objects.filter(pk=self.eq.pk).exists())          # continua no banco
        antigo.refresh_from_db()
        self.assertEqual(antigo.equipamento, self.eq)                                  # chamados antigos seguem ligados
        self.assertEqual(self.eq.pecas.count(), 2)                                     # e as peças também

    def test_adicionar_modelo_ao_rfb(self):
        self.post_json('/api/rfb/modelos/', {'id': self.fora.id_equipamento, 'rfb': True})
        nomes = [m['modelo'] for m in self.client.get('/api/rfb/modelos/').json()['dados']]
        self.assertEqual(nomes, ['HP EliteBook 640 G10', 'Modelo Antigo'])

    def test_modelo_inexistente_e_dado_invalido(self):
        self.assertEqual(self.post_json('/api/rfb/modelos/', {'id': 9999, 'rfb': True}).status_code, 404)
        self.assertEqual(self.post_json('/api/rfb/modelos/', {'rfb': True}).status_code, 400)

    def test_so_gestao_altera_a_lista(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Analista de Triagem', login=61))
        self.assertEqual(self.post_json('/api/rfb/modelos/', {'id': self.eq.id_equipamento, 'rfb': False}).status_code, 403)
        self.assertEqual(self.client.get('/api/rfb/modelos/').status_code, 200)


class NovoChamadoTests(RFBBase):
    def test_novo_chamado_usa_o_modelo_do_banco(self):
        self.assertEqual(self.novo().status_code, 200)
        c = ChamadoRFB.objects.get()
        self.assertEqual((c.equipamento, c.modelo_equipamento), (self.eq, 'HP EliteBook 640 G10'))

    def test_modelo_fora_do_rfb_e_recusado(self):
        r = self.novo(equipamento_id=self.fora.id_equipamento)
        self.assertEqual(r.status_code, 400)
        self.assertIn('não está habilitado', r.json()['mensagem'])

    def test_sem_modelo_e_recusado(self):
        dados = {'ticket': 'T9', 'sn': 'S9', 'cidade': 'X', 'estado': 'SP', 'data_abertura': timezone.now().isoformat(), 'descricao_defeito': 'x'}
        r = self.post_json('/api/chamados-rfb/', dados)
        self.assertEqual(r.status_code, 400)
        self.assertIn('modelo', r.json()['mensagem'])

    def test_texto_antigo_do_modelo_ainda_funciona(self):
        r = self.novo(equipamento_id=None, modelo_equipamento='hp  elitebook 640 g10')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ChamadoRFB.objects.get().equipamento, self.eq)

    def test_chamado_antigo_pode_manter_o_modelo_que_saiu_do_rfb(self):
        c = self.chamado(equipamento=self.fora)
        r = self.post_json('/api/chamados-rfb/', {'id': c.id_chamado, 'equipamento_id': self.fora.id_equipamento, 'observacao': 'ok'})
        self.assertEqual(r.status_code, 200, r.content)
        # mas não dá para trocar para outro modelo que também não é do RFB
        outro = Equipamento.objects.create(pn='OUT-2', modelo='Outro Antigo', rfb=False)
        r = self.post_json('/api/chamados-rfb/', {'id': c.id_chamado, 'equipamento_id': outro.id_equipamento})
        self.assertEqual(r.status_code, 400)


class EncerramentoComPecasPadronizadasTests(RFBBase):
    def test_encerra_com_pecas_do_modelo(self):
        c = self.chamado()
        r = self.encerrar(c, pecas_utilizadas_ids=[self.p1.id_peca, self.p2.id_peca])
        self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db()
        self.assertEqual(c.status, 'concluido')
        self.assertEqual(c.pecas_utilizadas.count(), 2)
        self.assertIn('P-TELA (Tela)', c.peca_utilizada)
        self.assertIn('P-BAT (Bateria)', c.peca_utilizada)

    def test_exige_escolher_as_pecas_ou_marcar_nenhuma(self):
        c = self.chamado()
        for extra in ({}, {'pecas_utilizadas_ids': []}):
            r = self.encerrar(c, **extra)
            self.assertEqual(r.status_code, 400, extra)
        c.refresh_from_db()
        self.assertEqual(c.status, 'andamento')            # nada foi gravado

    def test_nenhuma_peca_utilizada(self):
        c = self.chamado()
        self.assertEqual(self.encerrar(c, sem_peca=True).status_code, 200)
        c.refresh_from_db()
        self.assertEqual((c.peca_utilizada, c.pecas_utilizadas.count()), ('Nenhuma peça utilizada', 0))

    def test_peca_de_outro_modelo_e_recusada(self):
        c = self.chamado()
        r = self.encerrar(c, pecas_utilizadas_ids=[self.outra.id_peca])
        self.assertEqual(r.status_code, 400)
        self.assertIn('não pertencem', r.json()['mensagem'])

    def test_nao_aceita_peca_e_nenhuma_ao_mesmo_tempo(self):
        c = self.chamado()
        self.assertEqual(self.encerrar(c, sem_peca=True, pecas_utilizadas_ids=[self.p1.id_peca]).status_code, 400)

    def test_texto_livre_nao_substitui_a_escolha(self):
        c = self.chamado()
        self.assertEqual(self.encerrar(c, peca_utilizada='qualquer texto digitado').status_code, 400)

    def test_chamado_sem_modelo_cadastrado_nao_encerra(self):
        c = self.chamado(equipamento=None)
        r = self.encerrar(c, sem_peca=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn('modelo cadastrado', r.json()['mensagem'])

    def test_encerrar_informando_o_modelo_na_mesma_hora(self):
        c = self.chamado(equipamento=None)
        r = self.encerrar(c, equipamento_id=self.eq.id_equipamento, pecas_utilizadas_ids=[self.p1.id_peca])
        self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db()
        self.assertEqual(c.equipamento, self.eq)

    def test_editar_chamado_ja_concluido_nao_pede_as_pecas_de_novo(self):
        c = self.chamado()
        self.encerrar(c, sem_peca=True)
        r = self.post_json('/api/chamados-rfb/', {'id': c.id_chamado, 'status': 'concluido', 'observacao': 'revisado'})
        self.assertEqual(r.status_code, 200, r.content)

    def test_ranking_de_pecas_junta_as_padronizadas_e_o_texto_antigo(self):
        novo = self.chamado(status='concluido', peca_utilizada='P-TELA (Tela)')
        novo.pecas_utilizadas.add(self.p1)
        self.chamado(status='concluido', peca_utilizada='Tela quebrada')       # texto livre de antes
        self.chamado(status='concluido', peca_utilizada='Nenhuma peça utilizada')
        ranking = ChamadoRFBService._top_pecas(ChamadoRFB.objects.all(), ['', 'Nenhuma peça utilizada', None])
        self.assertEqual({r['peca_utilizada']: r['total'] for r in ranking}, {'P-TELA': 1, 'Tela quebrada': 1})


class MigracaoDosModelosDoRFBTests(BaseTestCase):
    def rodar(self):
        modulo = importlib.import_module('Daedalus.migrations.0019_vincular_modelos_rfb')
        modulo.migrar(apps, None)

    def chamado(self, modelo):
        return ChamadoRFB.objects.create(ticket=f'M-{modelo}', data_abertura=timezone.now(), estado='SP', cidade='X',
                                         descricao_defeito='x', modelo_equipamento=modelo, sn='S')

    def test_marca_liga_e_cria_os_modelos_que_faltam(self):
        existente = Equipamento.objects.create(pn='EB1', modelo='EliteBook 640 G10')       # cadastrado sem o "HP"
        c = self.chamado('HP EliteBook 640 G10')
        self.rodar()
        existente.refresh_from_db(); c.refresh_from_db()
        self.assertTrue(existente.rfb)
        self.assertEqual(c.equipamento, existente)
        provisorios = Equipamento.objects.filter(pn__startswith='PENDENTE-RFB-')
        self.assertEqual(provisorios.count(), 4)                                             # os outros 4 modelos
        self.assertTrue(all(p.rfb for p in provisorios))

    def test_rodar_de_novo_nao_duplica(self):
        self.chamado('Monitor AOC 24P1U')
        self.rodar()
        self.rodar()
        self.assertEqual(Equipamento.objects.count(), 5)

    def test_banco_sem_chamados_nao_cria_nada(self):
        self.rodar()
        self.assertEqual(Equipamento.objects.count(), 0)


class SemIntervencaoTecnicaTests(RFBBase):
    """Chamado resolvido sem ir a campo: sem técnico, sem peças, mas com a explicação de como foi resolvido."""

    def setUp(self):
        super().setUp()
        self.tecnico = self.criar_funcionario(cargo='Funcionário', login=77, nome='Téc Campo', email='tec@exemplo.com')

    def test_encerra_sem_tecnico_nem_pecas_e_marca_o_chamado(self):
        c = self.chamado()
        r = self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Orientado por telefone: reinicialização do firmware.')
        self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db()
        self.assertEqual(c.status, 'concluido')
        self.assertTrue(c.sem_intervencao_tecnica)
        self.assertIsNone(c.tecnico_atendimento_id)
        self.assertEqual(c.pecas_utilizadas.count(), 0)
        self.assertEqual(c.peca_utilizada, 'Nenhuma peça utilizada')

    def test_nao_exige_modelo_cadastrado_nem_lista_de_pecas(self):
        c = self.chamado(equipamento=None)                   # chamado antigo, sem modelo cadastrado
        r = self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Cliente resolveu sozinho.')
        self.assertEqual(r.status_code, 200, r.content)

    def test_sem_explicacao_da_resolucao_e_recusado(self):
        c = self.chamado()
        r = self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='   ')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Descreva como o chamado foi resolvido', r.json()['mensagem'])
        c.refresh_from_db()
        self.assertEqual(c.status, 'andamento')

    def test_o_tecnico_enviado_e_ignorado(self):
        c = self.chamado()
        self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Remoto.', tecnico_atendimento_id=self.tecnico.id_funcionario)
        c.refresh_from_db()
        self.assertIsNone(c.tecnico_atendimento_id)

    def test_encerramento_normal_continua_exigindo_pecas(self):
        c = self.chamado()
        self.assertEqual(self.encerrar(c).status_code, 400)
        c.refresh_from_db()
        self.assertFalse(c.sem_intervencao_tecnica)

    def test_encerramento_normal_nao_marca_sem_intervencao(self):
        c = self.chamado()
        self.encerrar(c, sem_peca=True, tecnico_atendimento_id=self.tecnico.id_funcionario)
        c.refresh_from_db()
        self.assertFalse(c.sem_intervencao_tecnica)
        self.assertEqual(c.tecnico_atendimento_id, self.tecnico.id_funcionario)

    def test_reabrir_o_chamado_apaga_a_marcacao(self):
        c = self.chamado()
        self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Remoto.')
        r = self.post_json('/api/chamados-rfb/', {'id': c.id_chamado, 'status': 'andamento'})
        self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db()
        self.assertFalse(c.sem_intervencao_tecnica)

    def test_a_lista_e_o_dashboard_informam_a_marcacao(self):
        c = self.chamado()
        self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Remoto.')
        self.encerrar(self.chamado(), sem_peca=True)
        r = ChamadoRFBService.listar_para_api(status_filter='todos')
        itens = {i['ticket']: i for i in r['dados']}
        self.assertTrue(itens[c.ticket]['sem_intervencao_tecnica'])
        self.assertEqual((r['dashboard']['concluidos'], r['dashboard']['concluidos_sem_intervencao']), (2, 1))

    def test_editar_um_chamado_ja_encerrado_mantem_a_marcacao(self):
        c = self.chamado()
        self.encerrar(c, sem_intervencao_tecnica=True, resolucao_caso='Remoto.')
        self.post_json('/api/chamados-rfb/', {'id': c.id_chamado, 'observacao': 'revisado'})
        c.refresh_from_db()
        self.assertTrue(c.sem_intervencao_tecnica)
