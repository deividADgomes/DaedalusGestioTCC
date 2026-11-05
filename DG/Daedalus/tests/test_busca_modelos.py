from ..models import Equipamento, Peca
from .base import BaseTestCase


class PesquisaDeModelosEPecasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.g9 = Equipamento.objects.create(pn='ABC123', modelo='ProBook 640 G9', tipo='Notebook', marca='HP')
        self.g8 = Equipamento.objects.create(pn='XYZ789', modelo='EliteBook 840 G8', tipo='Notebook', marca='HP')
        self.mon = Equipamento.objects.create(pn='MON001', modelo='Monitor E24', tipo='Monitor', marca='Dell')
        tela, bateria = Peca.objects.create(part_number='L1-TELA', descricao='Tela 14 HD'), Peca.objects.create(part_number='B1', descricao='Bateria longa')
        self.g9.pecas.add(tela, bateria)
        self.g8.pecas.add(bateria)

    def buscar(self, q=None):
        params = {} if q is None else {'q': q}
        return sorted(e['modelo'] for e in self.client.get('/api/modelo-equipamento/', params).json()['dados'])

    def test_sem_busca_traz_todos(self):
        self.assertEqual(len(self.buscar()), 3)
        self.assertEqual(len(self.buscar('')), 3)

    def test_busca_por_modelo_pn_tipo_e_marca(self):
        self.assertEqual(self.buscar('640'), ['ProBook 640 G9'])
        self.assertEqual(self.buscar('xyz'), ['EliteBook 840 G8'])
        self.assertEqual(self.buscar('monitor'), ['Monitor E24'])
        self.assertEqual(self.buscar('dell'), ['Monitor E24'])
        self.assertEqual(len(self.buscar('hp')), 2)

    def test_busca_por_peca_vinculada_pelo_pn_ou_descricao(self):
        self.assertEqual(self.buscar('L1-TELA'), ['ProBook 640 G9'])
        self.assertEqual(self.buscar('b1'), ['EliteBook 840 G8', 'ProBook 640 G9'])
        self.assertEqual(self.buscar('longa'), ['EliteBook 840 G8', 'ProBook 640 G9'])

    def test_total_de_pecas_nao_e_afetado_pela_busca_por_peca(self):
        dados = {e['modelo']: e['total_pecas'] for e in self.client.get('/api/modelo-equipamento/', {'q': 'L1-TELA'}).json()['dados']}
        self.assertEqual(dados, {'ProBook 640 G9': 2})                 # tem 2 peças, mesmo achado por uma delas

    def test_nao_repete_modelo_quando_varias_pecas_casam(self):
        # "l" casa as duas peças do G9 (L1-TELA e "Bateria longa"): o modelo aparece uma única vez
        modelos = [e['modelo'] for e in self.client.get('/api/modelo-equipamento/', {'q': 'l'}).json()['dados']]
        self.assertEqual(modelos.count('ProBook 640 G9'), 1)

    def test_sem_resultado(self):
        self.assertEqual(self.buscar('naoexiste'), [])
