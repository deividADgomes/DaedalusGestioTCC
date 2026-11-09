from ..models import Empresa, Equipamento, Peca, Tecnico, Triagem, TriagemHistorico
from .base import BaseTestCase


class CampoCtTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.func = self.criar_funcionario(cargo='Analista de Triagem', login=81, nome='Ana Autora')
        self.entrar(self.func)
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='640 G9')
        self.system = Peca.objects.create(part_number='N07915-601', descricao='System I7')
        self.placa_sem_601 = Peca.objects.create(part_number='X1', descricao='System board')       # "System" só na descrição
        self.tela = Peca.objects.create(part_number='L1', descricao='Tela 14 HD')
        self.equip.pecas.add(self.system, self.placa_sem_601, self.tela)

    def salvar(self, **extra):
        dados = {'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
                 'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
                 'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2}
        dados.update(extra)
        return self.post_json('/api/triagem/', dados)

    def test_system_exige_o_ct(self):
        r = self.salvar(id_peca_trocada=self.system.id_peca)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Informe o CT', r.json()['mensagem'])
        self.assertEqual(Triagem.objects.count(), 0)

    def test_system_pela_descricao_tambem_exige(self):
        self.assertEqual(self.salvar(id_peca_trocada=self.placa_sem_601.id_peca).status_code, 400)

    def test_ct_grava_em_maiusculas_e_sem_espacos(self):
        r = self.salvar(id_peca_trocada=self.system.id_peca, ct=' n07915-601 ')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Triagem.objects.get().ct, 'N07915-601')

    def test_ct_precisa_terminar_em_601(self):
        r = self.salvar(id_peca_trocada=self.system.id_peca, ct='N07915-602')
        self.assertEqual(r.status_code, 400)
        self.assertIn('terminado em -601', r.json()['mensagem'])

    def test_peca_que_nao_e_system_nao_pede_ct(self):
        r = self.salvar(id_peca_trocada=self.tela.id_peca)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Triagem.objects.get().ct, '')

    def test_sem_peca_trocada_nao_pede_ct(self):
        self.assertEqual(self.salvar().status_code, 200)

    def test_peca_digitada_que_parece_system_exige_o_ct(self):
        self.assertEqual(self.salvar(troca='Placa System do cliente').status_code, 400)
        self.assertEqual(self.salvar(troca='N11111-601').status_code, 400)
        self.assertEqual(self.salvar(troca='Placa System do cliente', ct='N11111-601').status_code, 200)
        self.assertEqual(self.salvar(troca='Systematic cleaning kit').status_code, 200)             # "system" só como palavra inteira

    def test_ct_aparece_na_consulta_e_no_historico(self):
        id_t = self.salvar(id_peca_trocada=self.system.id_peca, ct='N07915-601').json()['id']
        self.assertEqual(self.client.get('/api/triagem/', {'id': id_t}).json()['dado']['ct'], 'N07915-601')
        self.salvar(id=id_t, id_peca_trocada=self.system.id_peca, ct='N99999-601')
        mudou = {a['campo']: (a['de'], a['para']) for a in TriagemHistorico.objects.get().alteracoes}
        self.assertEqual(mudou['CT'], ('N07915-601', 'N99999-601'))

    def test_trocar_para_peca_comum_limpa_o_ct_gravado(self):
        id_t = self.salvar(id_peca_trocada=self.system.id_peca, ct='N07915-601').json()['id']
        self.salvar(id=id_t, id_peca_trocada=self.tela.id_peca, ct='')
        self.assertEqual(Triagem.objects.get().ct, '')
