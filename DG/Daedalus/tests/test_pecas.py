from datetime import date, timedelta
from unittest import mock

from ..models import CotacaoPeca, Empresa, Equipamento, Peca
from ..partsurfer import PartSurferError
from .base import BaseTestCase

PECAS_HP = [
    {'part_number': 'L1', 'descricao': 'Tela'},
    {'part_number': 'L2', 'descricao': 'Bateria'},
    {'part_number': 'L3', 'descricao': 'Parafuso'},
]
BUSCA = 'Daedalus.services.equipamento.buscar_pecas_por_pn'


class SelecaoDePecasTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.equip = Equipamento.objects.create(pn='ABC123', modelo='Notebook X')
        self.base = f'/api/modelo-equipamento/{self.equip.id_equipamento}'

    @mock.patch(BUSCA)
    def test_consulta_devolve_candidatas_sem_gravar_nada(self, busca):
        busca.return_value = PECAS_HP
        r = self.post_json(f'{self.base}/partsurfer/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['dados']), 3)
        self.assertEqual(Peca.objects.count(), 0)
        self.assertEqual(self.equip.pecas.count(), 0)

    @mock.patch(BUSCA)
    def test_salvar_selecao_grava_so_as_escolhidas(self, busca):
        r = self.post_json(f'{self.base}/pecas/', {'pecas': [
            {'part_number': 'l1', 'descricao': 'Tela'}, {'part_number': 'L2', 'descricao': 'Bateria'},
        ]})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(sorted(Peca.objects.values_list('part_number', flat=True)), ['L1', 'L2'])
        self.assertEqual(self.equip.pecas.count(), 2)

    @mock.patch(BUSCA)
    def test_nova_consulta_marca_as_ja_escolhidas_e_mantem_as_locais(self, busca):
        self.post_json(f'{self.base}/pecas/', {'pecas': [
            {'part_number': 'L1', 'descricao': 'Tela'}, {'part_number': 'MANUAL9', 'descricao': 'Peça avulsa'},
        ]})
        busca.return_value = PECAS_HP
        dados = {c['part_number']: c for c in self.post_json(f'{self.base}/partsurfer/').json()['dados']}
        self.assertTrue(dados['L1']['selecionada'])
        self.assertFalse(dados['L2']['selecionada'])
        self.assertTrue(dados['MANUAL9']['selecionada'])
        self.assertTrue(dados['MANUAL9']['somente_local'])

    @mock.patch(BUSCA)
    def test_desmarcar_remove_so_o_vinculo_e_preserva_a_peca_e_cotacoes(self, busca):
        self.post_json(f'{self.base}/pecas/', {'pecas': [{'part_number': 'L1', 'descricao': 'Tela'}]})
        peca = Peca.objects.get(part_number='L1')
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='F', tipo=3)
        CotacaoPeca.objects.create(peca=peca, fornecedor=fornecedor, valor='10.00', data_cotacao=date.today())
        self.post_json(f'{self.base}/pecas/', {'pecas': []})
        self.assertEqual(self.equip.pecas.count(), 0)
        self.assertEqual(peca.cotacoes.count(), 1)

    @mock.patch(BUSCA)
    def test_segunda_consulta_seguida_e_limitada(self, busca):
        busca.return_value = PECAS_HP
        self.assertEqual(self.post_json(f'{self.base}/partsurfer/').status_code, 200)
        self.assertEqual(self.post_json(f'{self.base}/partsurfer/').status_code, 429)

    @mock.patch(BUSCA)
    def test_falha_do_partsurfer_vira_502_e_resposta_vazia_vira_404(self, busca):
        busca.side_effect = PartSurferError('fora do ar')
        self.assertEqual(self.post_json(f'{self.base}/partsurfer/').status_code, 502)
        from django.core.cache import cache
        cache.clear()
        busca.side_effect = None
        busca.return_value = []
        self.assertEqual(self.post_json(f'{self.base}/partsurfer/').status_code, 404)

    def test_selecao_invalida_e_recusada(self):
        r = self.post_json(f'{self.base}/pecas/', {'pecas': 'nada'})
        self.assertEqual(r.status_code, 400)

    def test_equipamento_inexistente(self):
        self.assertEqual(self.post_json('/api/modelo-equipamento/9999/partsurfer/').status_code, 404)


class SelecaoComEquipamentoCompletoTests(BaseTestCase):
    """A tela de peças grava a lista inteira de uma vez; a marcação de equipamento completo vai junto (e é opcional)."""

    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.equip = Equipamento.objects.create(pn='ABC123', modelo='Notebook X')
        self.url = f'/api/modelo-equipamento/{self.equip.id_equipamento}/pecas/'

    def test_peca_nova_pode_ser_criada_como_equipamento_completo(self):
        r = self.post_json(self.url, {'pecas': [
            {'part_number': 'abc123', 'descricao': 'Equipamento completo', 'equipamento_completo': True},
            {'part_number': 'L1', 'descricao': 'Tela', 'equipamento_completo': False},
        ]})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(Peca.objects.get(part_number='ABC123').equipamento_completo)
        self.assertFalse(Peca.objects.get(part_number='L1').equipamento_completo)

    def test_sem_o_campo_a_marcacao_existente_e_mantida(self):
        Peca.objects.create(part_number='ABC123', descricao='Máquina', equipamento_completo=True)
        self.post_json(self.url, {'pecas': [{'part_number': 'ABC123', 'descricao': 'Máquina inteira'}]})
        peca = Peca.objects.get(part_number='ABC123')
        self.assertTrue(peca.equipamento_completo)
        self.assertEqual(peca.descricao, 'Máquina inteira')

    def test_o_campo_pode_desmarcar_uma_peca_existente(self):
        Peca.objects.create(part_number='L1', descricao='Tela', equipamento_completo=True)
        self.post_json(self.url, {'pecas': [{'part_number': 'L1', 'descricao': 'Tela', 'equipamento_completo': False}]})
        self.assertFalse(Peca.objects.get(part_number='L1').equipamento_completo)

    def test_salvar_a_lista_mantem_as_cotacoes_das_pecas(self):
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor A', tipo=3)
        peca = Peca.objects.create(part_number='L1', descricao='Tela')
        CotacaoPeca.objects.create(peca=peca, fornecedor=fornecedor, valor='300.00', data_cotacao=date.today())
        self.equip.pecas.add(peca)
        self.post_json(self.url, {'pecas': [{'part_number': 'L1', 'descricao': 'Tela', 'equipamento_completo': False}]})
        self.assertEqual(peca.cotacoes.count(), 1)
        dados = self.client.get(self.url).json()['dados']
        self.assertEqual(dados[0]['cotacao_atual']['valor'], 300.0)


class CotacoesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.peca = Peca.objects.create(part_number='L1', descricao='Tela')
        self.fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor A', tipo=3)
        self.cliente = Empresa.objects.create(cnpj='11222333000181', razao_social='Cliente', tipo=2)
        self.url = f'/api/pecas/{self.peca.id_peca}/cotacoes/'

    def dados(self, **extra):
        base = {'fornecedor_id': self.fornecedor.id_empresa, 'valor': '1.234,56',
                'data_cotacao': date.today().isoformat(), 'observacao': 'à vista'}
        base.update(extra)
        return base

    def test_registra_cotacao_com_fornecedor_valor_e_data(self):
        r = self.post_json(self.url, self.dados())
        self.assertEqual(r.status_code, 200, r.content)
        c = CotacaoPeca.objects.get()
        self.assertEqual(str(c.valor), '1234.56')
        self.assertEqual(c.fornecedor, self.fornecedor)
        self.assertIsNotNone(c.criado_por)

    def test_so_aceita_empresa_do_tipo_fornecedor(self):
        r = self.post_json(self.url, self.dados(fornecedor_id=self.cliente.id_empresa))
        self.assertEqual(r.status_code, 400)

    def test_valor_e_data_invalidos(self):
        for extra in ({'valor': '-5'}, {'valor': 'abc'}, {'valor': '0'},
                      {'data_cotacao': (date.today() + timedelta(days=2)).isoformat()},
                      {'data_cotacao': '31/12/2026'}):
            self.assertEqual(self.post_json(self.url, self.dados(**extra)).status_code, 400, extra)
        self.assertFalse(CotacaoPeca.objects.exists())

    def test_valor_atual_e_a_cotacao_de_data_mais_recente(self):
        self.post_json(self.url, self.dados(valor='100', data_cotacao=(date.today() - timedelta(days=10)).isoformat()))
        self.post_json(self.url, self.dados(valor='80', data_cotacao=date.today().isoformat()))
        self.post_json(self.url, self.dados(valor='50', data_cotacao=(date.today() - timedelta(days=30)).isoformat()))
        self.assertEqual(float(self.peca.cotacao_atual().valor), 80.0)
        historico = self.client.get(self.url).json()['cotacoes']
        self.assertEqual([c['valor'] for c in historico], [80.0, 100.0, 50.0])

    def test_cotacao_aparece_na_lista_de_pecas_do_equipamento(self):
        equip = Equipamento.objects.create(pn='P1', modelo='M')
        equip.pecas.add(self.peca)
        self.post_json(self.url, self.dados(valor='99.90'))
        dados = self.client.get(f'/api/modelo-equipamento/{equip.id_equipamento}/pecas/').json()['dados']
        self.assertEqual(dados[0]['cotacao_atual']['valor'], 99.9)
        self.assertEqual(dados[0]['cotacao_atual']['fornecedor'], 'Fornecedor A')

    def test_so_gestao_exclui_cotacao(self):
        self.post_json(self.url, self.dados())
        c = CotacaoPeca.objects.get()
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Analista de Triagem', login=77))
        self.assertEqual(self.client.delete(f'/api/cotacoes/{c.id_cotacao}/').status_code, 403)
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Gestor', login=78))
        self.assertEqual(self.client.delete(f'/api/cotacoes/{c.id_cotacao}/').status_code, 200)


class CatalogoCompartilhadoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())

    def test_peca_compartilhada_entre_equipamentos_e_total_na_listagem(self):
        a = Equipamento.objects.create(pn='A1', modelo='A')
        b = Equipamento.objects.create(pn='B1', modelo='B')
        item = {'pecas': [{'part_number': 'COMUM', 'descricao': 'Peça comum'}]}
        self.post_json(f'/api/modelo-equipamento/{a.id_equipamento}/pecas/', item)
        self.post_json(f'/api/modelo-equipamento/{b.id_equipamento}/pecas/', item)
        self.assertEqual(Peca.objects.count(), 1)
        dados = {d['pn']: d for d in self.client.get('/api/modelo-equipamento/').json()['dados']}
        self.assertEqual(dados['A1']['total_pecas'], 1)
        self.assertEqual(dados['B1']['total_pecas'], 1)

    def test_cotacao_e_universal_para_modelos_com_o_mesmo_pn(self):
        a = Equipamento.objects.create(pn='A2', modelo='Modelo A')
        b = Equipamento.objects.create(pn='B2', modelo='Modelo B')
        item = {'pecas': [{'part_number': 'comum-1', 'descricao': 'Peça comum'}]}   # minúsculas: vira o mesmo PN
        self.post_json(f'/api/modelo-equipamento/{a.id_equipamento}/pecas/', item)
        self.post_json(f'/api/modelo-equipamento/{b.id_equipamento}/pecas/', {'pecas': [{'part_number': 'COMUM-1 '}]})
        self.assertEqual(Peca.objects.count(), 1)

        peca = Peca.objects.get()
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor', tipo=3)
        r = self.post_json(f'/api/pecas/{peca.id_peca}/cotacoes/',
                           {'fornecedor_id': fornecedor.id_empresa, 'valor': '250,00', 'data_cotacao': date.today().isoformat()})
        self.assertEqual(r.status_code, 200, r.content)

        for equip in (a, b):
            dados = self.client.get(f'/api/modelo-equipamento/{equip.id_equipamento}/pecas/').json()['dados']
            self.assertEqual(dados[0]['cotacao_atual']['valor'], 250.0)
        modelos = self.client.get(f'/api/pecas/{peca.id_peca}/cotacoes/').json()['modelos']
        self.assertEqual(sorted(m['modelo'] for m in modelos), ['Modelo A', 'Modelo B'])


class PecaManualTests(BaseTestCase):
    """Peças cadastradas direto no modelo, sem PartSurfer (inclui o "equipamento completo")."""

    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.equip = Equipamento.objects.create(pn='MODELO-1', modelo='Notebook X')
        self.url = f'/api/modelo-equipamento/{self.equip.id_equipamento}/pecas/adicionar/'

    def adicionar(self, **extra):
        dados = {'part_number': ' abc-123 ', 'descricao': 'Fonte 65W'}
        dados.update(extra)
        return self.post_json(self.url, dados)

    def test_adiciona_peca_sem_consultar_o_partsurfer(self):
        r = self.adicionar()                 # nenhuma chamada ao PartSurfer é simulada: se tentasse, o teste falharia
        self.assertEqual(r.status_code, 200, r.content)
        peca = Peca.objects.get()
        self.assertEqual((peca.part_number, peca.descricao, peca.equipamento_completo), ('ABC-123', 'Fonte 65W', False))
        self.assertEqual(list(self.equip.pecas.all()), [peca])
        self.assertEqual(r.json()['dados'][0]['part_number'], 'ABC-123')

    def test_equipamento_completo(self):
        r = self.adicionar(part_number='MODELO-1', descricao='Equipamento completo — Notebook X', equipamento_completo=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['dados'][0]['equipamento_completo'])
        self.assertTrue(Peca.objects.get().equipamento_completo)

    def test_pn_existente_e_reaproveitado_e_atualizado(self):
        Peca.objects.create(part_number='ABC-123', descricao='Descrição antiga')
        self.adicionar(descricao='Descrição nova')
        self.assertEqual(Peca.objects.count(), 1)
        self.assertEqual(Peca.objects.get().descricao, 'Descrição nova')
        self.assertEqual(self.equip.pecas.count(), 1)

    def test_mesma_peca_manual_em_dois_modelos_e_universal(self):
        outro = Equipamento.objects.create(pn='MODELO-2', modelo='Notebook Y')
        self.adicionar()
        self.post_json(f'/api/modelo-equipamento/{outro.id_equipamento}/pecas/adicionar/', {'part_number': 'abc-123', 'descricao': 'Fonte 65W'})
        self.assertEqual(Peca.objects.count(), 1)

    def test_validacoes(self):
        self.assertEqual(self.adicionar(part_number='').status_code, 400)
        self.assertEqual(self.adicionar(descricao=' ').status_code, 400)
        self.assertEqual(self.adicionar(part_number='X' * 101).status_code, 400)
        self.assertEqual(self.post_json('/api/modelo-equipamento/9999/pecas/adicionar/', {'part_number': 'A', 'descricao': 'b'}).status_code, 404)
        self.assertFalse(Peca.objects.exists())

    def test_retirar_do_modelo_preserva_a_peca_e_as_cotacoes(self):
        self.adicionar()
        peca = Peca.objects.get()
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Forn', tipo=3)
        CotacaoPeca.objects.create(peca=peca, fornecedor=fornecedor, valor='10.00', data_cotacao=date.today())
        r = self.post_json(f'/api/modelo-equipamento/{self.equip.id_equipamento}/pecas/remover/', {'id_peca': peca.id_peca})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.equip.pecas.count(), 0)
        self.assertEqual((Peca.objects.count(), peca.cotacoes.count()), (1, 1))

    def test_retirar_peca_que_nao_e_do_modelo(self):
        solta = Peca.objects.create(part_number='SOLTA', descricao='x')
        r = self.post_json(f'/api/modelo-equipamento/{self.equip.id_equipamento}/pecas/remover/', {'id_peca': solta.id_peca})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.post_json(f'/api/modelo-equipamento/{self.equip.id_equipamento}/pecas/remover/', {}).status_code, 400)

    def test_funcionario_comum_nao_cadastra_peca(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Funcionário', login=81))
        self.assertEqual(self.adicionar().status_code, 403)


class ResumoDePrecosTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.peca = Peca.objects.create(part_number='L1', descricao='Tela')
        self.a = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor A', tipo=3)
        self.b = Empresa.objects.create(cnpj='11222333000181', razao_social='Fornecedor B', tipo=3)

    def cotar(self, fornecedor, valor, dias_atras):
        CotacaoPeca.objects.create(peca=self.peca, fornecedor=fornecedor, valor=valor, data_cotacao=date.today() - timedelta(days=dias_atras))

    def resumo(self):
        return self.client.get(f'/api/pecas/{self.peca.id_peca}/cotacoes/').json()['resumo']

    def test_sem_cotacoes_nao_ha_resumo(self):
        self.assertIsNone(self.resumo())

    def test_melhor_preco_e_ultima_cotacao_de_cada_fornecedor(self):
        self.cotar(self.a, '300.00', 10)
        self.cotar(self.a, '330.00', 1)          # a última de A é a que vale
        self.cotar(self.b, '310.00', 3)
        r = self.resumo()
        self.assertEqual([f['fornecedor'] for f in r['por_fornecedor']], ['Fornecedor B', 'Fornecedor A'])
        self.assertEqual(r['melhor']['valor'], 310.0)

    def test_variacao_compara_com_a_cotacao_anterior_do_mesmo_fornecedor(self):
        self.cotar(self.a, '300.00', 20)
        self.cotar(self.b, '100.00', 10)          # outro fornecedor não entra na conta
        self.cotar(self.a, '330.00', 1)
        self.assertEqual(self.resumo()['variacao_pct'], 10.0)

    def test_primeira_cotacao_do_fornecedor_nao_tem_variacao(self):
        self.cotar(self.a, '300.00', 2)
        self.assertIsNone(self.resumo()['variacao_pct'])

    def test_queda_de_preco_vira_variacao_negativa(self):
        self.cotar(self.a, '400.00', 9)
        self.cotar(self.a, '300.00', 1)
        self.assertEqual(self.resumo()['variacao_pct'], -25.0)


class ImportarPlanilhaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.entrar(self.criar_funcionario())
        self.a = Equipamento.objects.create(pn='ABC123', modelo='Notebook A')
        self.b = Equipamento.objects.create(pn='XYZ789', modelo='Notebook B')
        self.url = '/api/modelo-equipamento/importar-pecas/'

    def importar(self, texto):
        return self.post_json(self.url, {'texto': texto})

    def test_importa_pecas_de_varios_modelos(self):
        r = self.importar('ABC123;L1;Tela 14 HD\nabc123;B1;Bateria\nXYZ789;L1;Tela 14 HD\nXYZ789;M7;Memória 8GB')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual((d['linhas'], d['criadas'], d['vinculadas'], d['erros']), (4, 3, 4, []))
        self.assertEqual(sorted(p.part_number for p in self.a.pecas.all()), ['B1', 'L1'])
        self.assertEqual(sorted(p.part_number for p in self.b.pecas.all()), ['L1', 'M7'])
        self.assertEqual(Peca.objects.filter(part_number='L1').count(), 1)       # a mesma peça serve aos dois modelos

    def test_cabecalho_e_tabulacao_do_excel_sao_aceitos(self):
        r = self.importar('PN do modelo\tPN da peça\tDescrição\nABC123\tl1\tTela')
        self.assertEqual(r.json()['dado']['criadas'], 1)
        self.assertEqual(Peca.objects.get().part_number, 'L1')

    def test_so_acrescenta_e_nunca_remove_vinculos(self):
        existente = Peca.objects.create(part_number='OLD', descricao='Antiga')
        self.a.pecas.add(existente)
        self.importar('ABC123;L1;Tela')
        self.assertEqual(sorted(p.part_number for p in self.a.pecas.all()), ['L1', 'OLD'])

    def test_reimportar_a_mesma_planilha_nao_duplica(self):
        planilha = 'ABC123;L1;Tela'
        self.importar(planilha)
        d = self.importar(planilha).json()['dado']
        self.assertEqual((d['criadas'], d['vinculadas']), (0, 0))
        self.assertEqual(Peca.objects.count(), 1)

    def test_atualiza_descricao_e_marca_equipamento_completo_sem_apagar_cotacao(self):
        peca = Peca.objects.create(part_number='ABC123', descricao='Antiga')
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor', tipo=3)
        CotacaoPeca.objects.create(peca=peca, fornecedor=fornecedor, valor='100.00', data_cotacao=date.today())
        d = self.importar('ABC123;ABC123;Equipamento novo;sim').json()['dado']
        peca.refresh_from_db()
        self.assertEqual((peca.descricao, peca.equipamento_completo, d['atualizadas']), ('Equipamento novo', True, 1))
        self.assertEqual(peca.cotacoes.count(), 1)

    def test_linhas_com_problema_sao_listadas_e_as_outras_entram(self):
        d = self.importar('ABC123;L1;Tela\nNAOEXISTE;L2;Outra\nABC123;;sem pn\nXYZ789;M7;Memória').json()['dado']
        self.assertEqual(d['criadas'], 2)
        self.assertEqual(len(d['erros']), 2)
        self.assertIn('Linha 2', d['erros'][0])
        self.assertIn('NAOEXISTE', d['erros'][0])

    def test_planilha_vazia_ou_gigante_e_recusada(self):
        self.assertEqual(self.importar('   \n ').status_code, 400)
        self.assertEqual(self.importar('\n'.join('ABC123;P%d;x' % i for i in range(2001))).status_code, 400)

    def test_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.importar('ABC123;L1;Tela').status_code, 401)
