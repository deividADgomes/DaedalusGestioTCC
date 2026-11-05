from ..models import Empresa, Equipamento, Peca, Tecnico, Triagem
from ..services.bi import BIService
from .base import BaseTestCase


class PecaTrocadaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.func = self.criar_funcionario(cargo='Analista de Triagem', nome='Ana Analista')
        self.entrar(self.func)
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='ProBook')
        self.outro_equip = Equipamento.objects.create(pn='PN-2', modelo='EliteBook')
        self.tela = Peca.objects.create(part_number='L1', descricao='Tela  14"\nHD')
        self.bateria = Peca.objects.create(part_number='B1', descricao='Bateria')
        self.equip.pecas.add(self.tela)
        self.outro_equip.pecas.add(self.bateria)

    def salvar(self, **extra):
        dados = {
            'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
            'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
            'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2,
        }
        dados.update(extra)
        return self.post_json('/api/triagem/', dados)

    def test_peca_do_modelo_grava_o_vinculo_e_o_texto(self):
        r = self.salvar(id_peca_trocada=self.tela.id_peca, troca='ignorado')
        self.assertEqual(r.status_code, 200, r.content)
        t = Triagem.objects.get()
        self.assertEqual(t.peca_trocada_id, self.tela.id_peca)
        self.assertEqual(t.troca, 'L1 - Tela 14" HD')       # espaços e quebras de linha são normalizados

    def test_peca_de_outro_modelo_e_recusada(self):
        r = self.salvar(id_peca_trocada=self.bateria.id_peca)
        self.assertEqual(r.status_code, 400)
        self.assertIn('cadastradas para este modelo', r.json()['mensagem'])
        self.assertEqual(Triagem.objects.count(), 0)

    def test_peca_inexistente_e_recusada(self):
        self.assertEqual(self.salvar(id_peca_trocada=99999).status_code, 400)

    def test_sem_peca_o_texto_livre_continua_valendo(self):
        r = self.salvar(troca='  Placa-mãe usada ')
        self.assertEqual(r.status_code, 200, r.content)
        t = Triagem.objects.get()
        self.assertIsNone(t.peca_trocada_id)
        self.assertEqual(t.troca, 'Placa-mãe usada')

    def test_sem_nada_a_troca_fica_vazia(self):
        self.salvar(troca='')
        t = Triagem.objects.get()
        self.assertIsNone(t.peca_trocada_id)
        self.assertIsNone(t.troca)

    def test_consulta_devolve_o_id_da_peca(self):
        self.salvar(id_peca_trocada=self.tela.id_peca)
        t = Triagem.objects.get()
        r = self.client.get('/api/triagem/', {'id': t.id_triagem}).json()['dado']
        self.assertEqual(r['id_peca_trocada'], self.tela.id_peca)

    def test_apagar_a_peca_do_catalogo_nao_apaga_a_triagem(self):
        self.salvar(id_peca_trocada=self.tela.id_peca)
        self.tela.delete()
        t = Triagem.objects.get()
        self.assertIsNone(t.peca_trocada_id)
        self.assertEqual(t.troca, 'L1 - Tela 14" HD')         # o texto da época permanece no laudo
