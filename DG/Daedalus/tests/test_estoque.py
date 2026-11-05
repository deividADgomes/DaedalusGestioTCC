from decimal import Decimal

from ..models import EstoquePeca, MovimentoEstoque, Peca
from .base import BaseTestCase


class EstoqueBase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=41, nome='Gil Gestor', email='gil@exemplo.com')
        self.entrar(self.gestor)
        self.tela = Peca.objects.create(part_number='L1-TELA', descricao='Tela 14 HD')
        self.bateria = Peca.objects.create(part_number='B1', descricao='Bateria')

    def mover(self, peca, tipo, quantidade, **extra):
        return self.post_json('/api/estoque/movimentar/', {'id_peca': peca.id_peca, 'tipo': tipo, 'quantidade': quantidade, **extra})

    def saldo(self, peca):
        return EstoquePeca.objects.get(peca=peca).saldo


class MovimentacaoTests(EstoqueBase):
    def test_entrada_cria_o_controle_e_soma_ao_saldo(self):
        r = self.mover(self.tela, 'entrada', 10, custo='100,00', motivo='NF 123')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.saldo(self.tela), 10)
        m = MovimentoEstoque.objects.get()
        self.assertEqual((m.tipo, m.quantidade, m.saldo_apos, m.funcionario_nome), ('entrada', 10, 10, 'Gil Gestor'))
        self.assertEqual(m.custo_unitario, Decimal('100.00'))

    def test_custo_medio_ponderado_nas_entradas(self):
        self.mover(self.tela, 'entrada', 10, custo='100,00')
        self.mover(self.tela, 'entrada', 10, custo='200,00')
        self.assertEqual(EstoquePeca.objects.get(peca=self.tela).custo_medio, Decimal('150.00'))
        self.mover(self.tela, 'entrada', 20, custo='300,00')       # (20*150 + 20*300) / 40
        self.assertEqual(EstoquePeca.objects.get(peca=self.tela).custo_medio, Decimal('225.00'))

    def test_entrada_sem_custo_nao_mexe_no_custo_medio(self):
        self.mover(self.tela, 'entrada', 5, custo='80,00')
        self.mover(self.tela, 'entrada', 5)
        e = EstoquePeca.objects.get(peca=self.tela)
        self.assertEqual((e.saldo, e.custo_medio), (10, Decimal('80.00')))

    def test_saida_exige_motivo_e_desconta(self):
        self.mover(self.tela, 'entrada', 5)
        self.assertEqual(self.mover(self.tela, 'saida', 2).status_code, 400)
        r = self.mover(self.tela, 'saida', 2, motivo='Ticket 987')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.saldo(self.tela), 3)
        self.assertEqual(MovimentoEstoque.objects.first().quantidade, -2)

    def test_saida_maior_que_o_saldo_e_recusada_sem_alterar_nada(self):
        self.mover(self.tela, 'entrada', 3)
        r = self.mover(self.tela, 'saida', 4, motivo='x')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Saldo insuficiente', r.json()['mensagem'])
        self.assertEqual((self.saldo(self.tela), MovimentoEstoque.objects.count()), (3, 1))

    def test_saida_de_peca_nunca_controlada_e_recusada(self):
        self.assertEqual(self.mover(self.bateria, 'saida', 1, motivo='x').status_code, 400)

    def test_contagem_ajusta_o_saldo_e_registra_a_diferenca(self):
        self.mover(self.tela, 'entrada', 10)
        r = self.mover(self.tela, 'contagem', 7, motivo='Inventário de outubro')
        self.assertEqual(r.status_code, 200, r.content)
        m = MovimentoEstoque.objects.first()
        self.assertEqual((self.saldo(self.tela), m.tipo, m.quantidade, m.saldo_apos), (7, 'contagem', -3, 7))

    def test_contagem_pode_zerar_e_exige_motivo_e_diferenca(self):
        self.mover(self.tela, 'entrada', 4)
        self.assertEqual(self.mover(self.tela, 'contagem', 4, motivo='igual').status_code, 400)
        self.assertEqual(self.mover(self.tela, 'contagem', 1).status_code, 400)
        self.assertEqual(self.mover(self.tela, 'contagem', 0, motivo='Zerado').status_code, 200)
        self.assertEqual(self.saldo(self.tela), 0)

    def test_quantidades_invalidas(self):
        for q in (0, -1, 'abc', '', 1.5, 10_000_000):
            self.assertEqual(self.mover(self.tela, 'entrada', q).status_code, 400, q)

    def test_tipo_invalido_e_peca_inexistente(self):
        self.assertEqual(self.mover(self.tela, 'roubo', 1).status_code, 400)
        r = self.post_json('/api/estoque/movimentar/', {'id_peca': 99999, 'tipo': 'entrada', 'quantidade': 1})
        self.assertEqual(r.status_code, 404)

    def test_o_saldo_sempre_bate_com_a_soma_dos_movimentos(self):
        self.mover(self.tela, 'entrada', 10)
        self.mover(self.tela, 'saida', 3, motivo='a')
        self.mover(self.tela, 'contagem', 5, motivo='b')
        self.mover(self.tela, 'entrada', 2)
        total = sum(m.quantidade for m in MovimentoEstoque.objects.filter(peca=self.tela))
        self.assertEqual(total, self.saldo(self.tela))


class ListagemEConfigTests(EstoqueBase):
    def configurar(self, peca, minimo, local=''):
        return self.post_json('/api/estoque/config/', {'id_peca': peca.id_peca, 'minimo': minimo, 'local': local})

    def lista(self, **params):
        return self.client.get('/api/estoque/', params).json()

    def test_so_aparecem_pecas_com_controle_e_o_resumo_soma_o_valor(self):
        self.mover(self.tela, 'entrada', 10, custo='50,00')
        d = self.lista()
        self.assertEqual([i['part_number'] for i in d['dados']], ['L1-TELA'])
        self.assertEqual((d['resumo']['itens'], d['resumo']['valor_total']), (1, 500.0))

    def test_minimo_e_local_podem_ser_definidos_antes_de_qualquer_entrada(self):
        r = self.configurar(self.bateria, 5, '  Prateleira   B2 ')
        self.assertEqual(r.status_code, 200, r.content)
        item = self.lista()['dados'][0]
        self.assertEqual((item['minimo'], item['local'], item['saldo']), (5, 'Prateleira B2', 0))

    def test_filtros_abaixo_do_minimo_e_sem_saldo(self):
        self.mover(self.tela, 'entrada', 2)
        self.configurar(self.tela, 5)                    # 2 < 5: abaixo
        self.mover(self.bateria, 'entrada', 10)
        self.configurar(self.bateria, 5)                 # 10 >= 5: ok
        abaixo = [i['part_number'] for i in self.lista(situacao='abaixo')['dados']]
        self.assertEqual(abaixo, ['L1-TELA'])
        self.assertEqual(self.lista()['resumo']['abaixo_minimo'], 1)
        self.mover(self.tela, 'saida', 2, motivo='x')
        self.assertEqual([i['part_number'] for i in self.lista(situacao='sem_saldo')['dados']], ['L1-TELA'])
        self.assertEqual(self.lista(situacao='sem_saldo')['dados'][0]['situacao'], 'sem_saldo')

    def test_peca_sem_minimo_nunca_gera_alerta(self):
        self.mover(self.tela, 'entrada', 1)
        self.assertEqual(self.lista(situacao='abaixo')['dados'], [])
        self.assertEqual(self.lista()['dados'][0]['situacao'], 'ok')

    def test_busca_por_pn_descricao_e_local(self):
        self.mover(self.tela, 'entrada', 1)
        self.configurar(self.tela, 0, 'Armário 3')
        self.mover(self.bateria, 'entrada', 1)
        for termo, esperado in (('l1', 1), ('bateria', 1), ('armário', 1), ('zzz', 0)):
            self.assertEqual(len(self.lista(q=termo)['dados']), esperado, termo)

    def test_minimo_invalido_e_recusado(self):
        for valor in (-1, 'abc'):
            self.assertEqual(self.configurar(self.tela, valor).status_code, 400, valor)
        self.assertEqual(self.configurar(self.tela, 1, 'x' * 101).status_code, 400)

    def test_catalogo_busca_e_marca_as_pecas_ja_controladas(self):
        self.mover(self.tela, 'entrada', 1)
        achados = {p['part_number']: p['controlada'] for p in self.client.get('/api/estoque/catalogo/', {'q': 'l1'}).json()['dados']}
        self.assertEqual(achados, {'L1-TELA': True})
        self.assertEqual(self.client.get('/api/estoque/catalogo/', {'q': 'b'}).json()['dados'], [])    # menos de 2 letras

    def test_historico_traz_do_mais_recente_ao_mais_antigo(self):
        self.mover(self.tela, 'entrada', 5)
        self.mover(self.tela, 'saida', 1, motivo='Ticket 1')
        dados = self.client.get(f'/api/estoque/{self.tela.id_peca}/movimentos/').json()['dados']
        self.assertEqual([m['quantidade'] for m in dados], [-1, 5])
        self.assertEqual(dados[0]['motivo'], 'Ticket 1')
        self.assertEqual(self.client.get('/api/estoque/99999/movimentos/').status_code, 404)

    def test_o_sino_avisa_pecas_abaixo_do_minimo(self):
        self.mover(self.tela, 'entrada', 1)
        self.configurar(self.tela, 3)
        itens = {i['tipo']: i for i in self.client.get('/api/avisos/').json()['dado']['itens']}
        self.assertEqual(itens['estoque']['quantidade'], 1)


class PermissoesDoEstoqueTests(EstoqueBase):
    def test_funcionario_consulta_mas_nao_movimenta(self):
        self.mover(self.tela, 'entrada', 5)
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Funcionário', login=42, nome='Maria', email='m@exemplo.com'))
        self.assertEqual(self.client.get('/api/estoque/').status_code, 200)
        self.assertEqual(self.client.get('/estoque/').status_code, 200)
        self.assertEqual(self.mover(self.tela, 'saida', 1, motivo='x').status_code, 403)
        self.assertEqual(self.post_json('/api/estoque/config/', {'id_peca': self.tela.id_peca, 'minimo': 1}).status_code, 403)
        self.assertEqual(self.saldo(self.tela), 5)

    def test_analista_de_triagem_pode_movimentar(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Analista de Triagem', login=43, nome='Ana', email='a@exemplo.com'))
        self.assertEqual(self.mover(self.tela, 'entrada', 2).status_code, 200)
        self.assertEqual(MovimentoEstoque.objects.get().funcionario_nome, 'Ana')

    def test_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/estoque/').status_code, 401)
        self.assertEqual(self.mover(self.tela, 'entrada', 1).status_code, 401)
