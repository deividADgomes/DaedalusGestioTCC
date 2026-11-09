from ..models import Empresa, Equipamento, Peca, Tecnico, Triagem, TriagemHistorico
from .base import BaseTestCase


class CampoCtTests(BaseTestCase):
    """System board = PN terminado em -601. O CT é o número de série dessa placa."""

    def setUp(self):
        super().setUp()
        self.func = self.criar_funcionario(cargo='Analista de Triagem', login=81, nome='Ana Autora')
        self.entrar(self.func)
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='640 G9')
        self.system = Peca.objects.create(part_number='N07915-601', descricao='System I7')
        self.chamada_system = Peca.objects.create(part_number='X1', descricao='System board')      # "System" só no texto: não é -601
        self.tela = Peca.objects.create(part_number='L1', descricao='Tela 14 HD')
        self.equip.pecas.add(self.system, self.chamada_system, self.tela)

    def salvar(self, **extra):
        dados = {'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
                 'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
                 'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2}
        dados.update(extra)
        return self.post_json('/api/triagem/', dados)

    def test_pn_terminado_em_601_e_system_board_e_exige_o_ct(self):
        r = self.salvar(id_peca_trocada=self.system.id_peca)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Informe o CT', r.json()['mensagem'])
        self.assertEqual(Triagem.objects.count(), 0)

    def test_o_ct_e_o_numero_de_serie_e_nao_precisa_terminar_em_601(self):
        r = self.salvar(id_peca_trocada=self.system.id_peca, ct=' ct 5CD1234xyz ')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Triagem.objects.get().ct, 'CT5CD1234XYZ')                  # sem espaços, em maiúsculas

    def test_so_o_pn_identifica_a_system_board_nao_o_nome_da_peca(self):
        r = self.salvar(id_peca_trocada=self.chamada_system.id_peca)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Triagem.objects.get().ct, '')

    def test_peca_comum_nao_pede_ct_e_ignora_um_ct_enviado(self):
        r = self.salvar(id_peca_trocada=self.tela.id_peca, ct='ABC123')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Triagem.objects.get().ct, '')

    def test_sem_peca_trocada_nao_pede_ct(self):
        self.assertEqual(self.salvar().status_code, 200)

    def test_pn_601_digitado_em_outra_peca_tambem_exige_o_ct(self):
        self.assertEqual(self.salvar(troca='Placa N11111-601 do cliente').status_code, 400)
        self.assertEqual(self.salvar(troca='N11111-601', ct='SERIE9').status_code, 200)
        self.assertEqual(self.salvar(troca='Placa System do cliente').status_code, 200)            # sem PN -601, não é identificada
        self.assertEqual(self.salvar(troca='N11111-6010').status_code, 200)                       # -6010 não é -601

    def test_ct_aparece_na_consulta_e_no_historico(self):
        id_t = self.salvar(id_peca_trocada=self.system.id_peca, ct='SERIE1').json()['id']
        self.assertEqual(self.client.get('/api/triagem/', {'id': id_t}).json()['dado']['ct'], 'SERIE1')
        self.salvar(id=id_t, id_peca_trocada=self.system.id_peca, ct='SERIE2')
        mudou = {a['campo']: (a['de'], a['para']) for a in TriagemHistorico.objects.get().alteracoes}
        self.assertEqual(mudou['CT'], ('SERIE1', 'SERIE2'))

    def test_trocar_para_peca_comum_limpa_o_ct_gravado(self):
        id_t = self.salvar(id_peca_trocada=self.system.id_peca, ct='SERIE1').json()['id']
        self.salvar(id=id_t, id_peca_trocada=self.tela.id_peca)
        self.assertEqual(Triagem.objects.get().ct, '')
