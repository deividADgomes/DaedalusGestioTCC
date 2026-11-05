from ..models import Empresa, Equipamento, Tecnico, Triagem, TriagemHistorico
from .base import BaseTestCase


class EdicaoDeTriagemTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.autor = self.criar_funcionario(cargo='Analista de Triagem', login=11, nome='Ana Autora')
        self.colega = self.criar_funcionario(cargo='Analista de Triagem', login=12, nome='Caio Colega')
        self.gestor = self.criar_funcionario(cargo='Gestor', login=13, nome='Gil Gestor')
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='ProBook')
        self.entrar(self.autor)
        self.id_triagem = self.criar_triagem()

    def corpo(self, **extra):
        dados = {
            'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
            'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
            'id_analista': self.autor.id_funcionario, 'sn': 'SN1', 'status_peca': 2, 'conclusao': 'Defeito na placa',
        }
        dados.update(extra)
        return dados

    def criar_triagem(self):
        r = self.post_json('/api/triagem/', self.corpo())
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['id']

    def editar(self, **extra):
        return self.post_json('/api/triagem/', self.corpo(id=self.id_triagem, **extra))

    def trocar_usuario(self, func):
        self.client.get('/logout/')
        self.entrar(func)

    def test_criar_devolve_o_id_e_nao_cria_historico(self):
        self.assertTrue(self.id_triagem)
        self.assertEqual(TriagemHistorico.objects.count(), 0)

    def test_autor_edita_e_o_historico_registra_so_o_que_mudou(self):
        r = self.editar(sn='SN2', conclusao='Defeito na memória', status_peca=1)
        self.assertEqual(r.status_code, 200, r.content)
        t = Triagem.objects.get(pk=self.id_triagem)
        self.assertEqual((t.sn, t.conclusao, t.status), ('SN2', 'Defeito na memória', 1))
        h = TriagemHistorico.objects.get()
        self.assertEqual(h.funcionario_nome, 'Ana Autora')
        mudou = {a['campo']: (a['de'], a['para']) for a in h.alteracoes}
        self.assertEqual(mudou, {
            'Nº de série': ('SN1', 'SN2'),
            'Status da peça': ('Defeito', 'Funcional'),
            'Conclusão': ('Defeito na placa', 'Defeito na memória'),
        })

    def test_salvar_sem_mudar_nada_nao_cria_historico(self):
        self.assertEqual(self.editar().status_code, 200)
        self.assertEqual(TriagemHistorico.objects.count(), 0)

    def test_gestor_edita_mas_o_analista_da_triagem_continua_o_original(self):
        self.trocar_usuario(self.gestor)
        self.assertEqual(self.editar(sn='SN9').status_code, 200)
        t = Triagem.objects.get(pk=self.id_triagem)
        self.assertEqual(t.analista_triagem_id, self.autor.id_funcionario)
        self.assertEqual(TriagemHistorico.objects.get().funcionario_nome, 'Gil Gestor')

    def test_outro_analista_nao_pode_editar(self):
        self.trocar_usuario(self.colega)
        r = self.editar(sn='SN9')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Triagem.objects.get(pk=self.id_triagem).sn, 'SN1')
        self.assertEqual(TriagemHistorico.objects.count(), 0)

    def test_editar_triagem_inexistente_devolve_404_para_a_gestao(self):
        self.trocar_usuario(self.gestor)
        self.assertEqual(self.post_json('/api/triagem/', self.corpo(id=99999)).status_code, 404)

    def test_consulta_traz_os_ids_para_preencher_o_formulario(self):
        d = self.client.get('/api/triagem/', {'id': self.id_triagem}).json()['dado']
        self.assertEqual(d['id_cliente'], self.cliente.id_empresa)
        self.assertEqual(d['id_equipamento'], self.equip.id_equipamento)
        self.assertEqual(d['id_tecnico'], self.tecnico.id_tecnico)
        self.assertEqual(d['id_analista_chamado'], self.autor.id_funcionario)
        self.assertTrue(d['criado_em'])

    def test_endpoint_do_historico_lista_mais_recente_primeiro(self):
        self.editar(sn='SN2')
        self.editar(sn='SN3')
        dados = self.client.get('/api/triagem/historico/', {'id': self.id_triagem}).json()['dados']
        self.assertEqual(len(dados), 2)
        self.assertEqual(dados[0]['alteracoes'][0]['para'], 'SN3')
        self.assertEqual(dados[0]['usuario'], 'Ana Autora')

    def test_historico_de_triagem_inexistente_devolve_404(self):
        self.assertEqual(self.client.get('/api/triagem/historico/', {'id': 99999}).status_code, 404)

    def test_historico_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/triagem/historico/', {'id': self.id_triagem}).status_code, 401)

    def test_apagar_a_triagem_leva_o_historico_junto(self):
        self.editar(sn='SN2')
        Triagem.objects.filter(pk=self.id_triagem).delete()
        self.assertEqual(TriagemHistorico.objects.count(), 0)
