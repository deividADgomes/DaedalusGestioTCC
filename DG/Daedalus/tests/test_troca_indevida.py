from ..models import Empresa, Equipamento, Tecnico, Triagem, TriagemHistorico
from .base import BaseTestCase
from .test_bi import BIBase


class TrocaIndevidaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.func = self.criar_funcionario(cargo='Analista de Triagem', login=61, nome='Ana Autora')
        self.entrar(self.func)
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='ProBook')

    def salvar(self, **extra):
        dados = {'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
                 'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
                 'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2}
        dados.update(extra)
        r = self.post_json('/api/triagem/', dados)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['id']

    def test_grava_sim_nao_e_nao_informado(self):
        for enviado, esperado in ((True, True), (False, False), ('sim', True), ('nao', False), ('não', False), (None, None), ('talvez', None)):
            id_t = self.salvar(troca_indevida=enviado)
            self.assertIs(Triagem.objects.get(pk=id_t).troca_indevida, esperado, enviado)
        id_t = self.salvar()                                   # campo omitido (cliente antigo da API): não informado
        self.assertIsNone(Triagem.objects.get(pk=id_t).troca_indevida)

    def test_consulta_devolve_o_valor(self):
        id_t = self.salvar(troca_indevida=True)
        self.assertIs(self.client.get('/api/triagem/', {'id': id_t}).json()['dado']['troca_indevida'], True)

    def test_alterar_o_campo_entra_no_historico(self):
        id_t = self.salvar(troca_indevida=False)
        self.salvar(id=id_t, troca_indevida=True)
        alteracao = TriagemHistorico.objects.get().alteracoes[0]
        self.assertEqual((alteracao['campo'], alteracao['de'], alteracao['para']), ('Troca indevida', 'Não', 'Sim'))

    def test_triagem_antiga_sem_informacao_aparece_como_travessao_no_historico(self):
        id_t = self.salvar()
        self.salvar(id=id_t, troca_indevida=True)
        alteracao = TriagemHistorico.objects.get().alteracoes[0]
        self.assertEqual((alteracao['de'], alteracao['para']), ('—', 'Sim'))

    def test_salvar_igual_nao_gera_historico(self):
        id_t = self.salvar(troca_indevida=True)
        self.salvar(id=id_t, troca_indevida=True)
        self.assertEqual(TriagemHistorico.objects.count(), 0)


class TrocaIndevidaNoBITests(BIBase):
    def marcar(self, qtd, valor):
        for _ in range(qtd):
            t = self.triagem(status=2)
            Triagem.objects.filter(pk=t.pk).update(troca_indevida=valor)

    def test_taxa_considera_so_triagens_com_a_informacao_preenchida(self):
        self.marcar(2, True)
        self.marcar(6, False)
        self.marcar(10, None)                                  # antigas: não entram na conta
        d = self.dados('qualidade')['troca_indevida']
        self.assertEqual((d['indevidas'], d['informadas'], d['taxa']['atual']), (2, 8, 25.0))

    def test_sem_nenhuma_informacao_a_taxa_fica_vazia(self):
        self.marcar(3, None)
        d = self.dados('qualidade')['troca_indevida']
        self.assertEqual((d['informadas'], d['taxa']['atual']), (0, None))
