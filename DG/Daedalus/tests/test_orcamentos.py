from datetime import date, timedelta

from django.core import mail
from django.test import override_settings

from ..models import CotacaoPeca, Empresa, Equipamento, ItemOrcamento, Orcamento, Peca, Tecnico, Triagem
from .base import BaseTestCase

EMAIL_ANALISTA = 'func@exemplo.com'   # e-mail padrão de BaseTestCase.criar_funcionario


class OrcamentoBase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.func = self.criar_funcionario(cargo='Analista de Triagem', nome='Ana Analista')
        self.entrar(self.func)
        self.fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor A', tipo=3)
        self.peca = Peca.objects.create(part_number='L1', descricao='Tela 14"')
        CotacaoPeca.objects.create(peca=self.peca, fornecedor=self.fornecedor, valor='300.00', data_cotacao=date.today())

    def dados(self, **extra):
        base = {
            'cliente_nome': 'Prefeitura', 'cliente_uf': 'sp', 'equip_modelo': 'ProBook', 'equip_sn': 'SN1',
            'motivo_problema': 'Não liga', 'analise': 'Placa com defeito', 'disponibilidade': 'disponivel',
            'itens': [{'peca_id': self.peca.id_peca, 'quantidade': 2}],
        }
        base.update(extra)
        return base

    def criar(self, **extra):
        r = self.post_json('/api/orcamentos/', self.dados(**extra))
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['dado']


class PrecificacaoTests(OrcamentoBase):
    """Regra: valor da peça x 1,3; só a 1ª peça soma ainda 300 + 100."""

    def test_primeira_peca_recebe_margem_e_adicionais(self):
        a = self.criar(itens=[{'peca_id': self.peca.id_peca, 'quantidade': 1}])
        item = a['itens'][0]
        self.assertEqual(item['valor_base'], 300.0)
        self.assertEqual(item['valor_unitario'], 390.0)     # 300 x 1,3
        self.assertEqual(item['adicional'], 400.0)          # 300 + 100
        self.assertEqual(item['subtotal'], 790.0)
        self.assertEqual(a['valor_total'], 790.0)

    def test_demais_pecas_so_recebem_a_margem(self):
        outra = Peca.objects.create(part_number='L2', descricao='Bateria')
        CotacaoPeca.objects.create(peca=outra, fornecedor=self.fornecedor, valor='100.00', data_cotacao=date.today())
        a = self.criar(itens=[{'peca_id': self.peca.id_peca, 'quantidade': 1}, {'peca_id': outra.id_peca, 'quantidade': 1}])
        self.assertEqual(a['itens'][0]['subtotal'], 790.0)
        self.assertEqual(a['itens'][1]['valor_unitario'], 130.0)
        self.assertEqual(a['itens'][1]['adicional'], 0.0)
        self.assertEqual(a['itens'][1]['subtotal'], 130.0)
        self.assertEqual(a['valor_total'], 920.0)

    def test_adicional_conta_uma_vez_mesmo_com_varias_unidades(self):
        a = self.criar(itens=[{'peca_id': self.peca.id_peca, 'quantidade': 2}])
        self.assertEqual(a['valor_total'], 1180.0)          # 390 x 2 + 400 (e não + 800)

    def test_ordem_da_lista_define_qual_e_a_primeira(self):
        outra = Peca.objects.create(part_number='L2', descricao='Bateria')
        CotacaoPeca.objects.create(peca=outra, fornecedor=self.fornecedor, valor='100.00', data_cotacao=date.today())
        a = self.criar(itens=[{'peca_id': outra.id_peca}, {'peca_id': self.peca.id_peca}])
        self.assertEqual(a['itens'][0]['adicional'], 400.0)
        self.assertEqual(a['itens'][0]['subtotal'], 530.0)  # 130 + 400
        self.assertEqual(a['itens'][1]['adicional'], 0.0)

    def test_valor_informado_a_mao_tambem_recebe_margem(self):
        sem = Peca.objects.create(part_number='SEM', descricao='Sem cotação')
        r = self.post_json('/api/orcamentos/', self.dados(itens=[{'peca_id': sem.id_peca, 'valor_base': '45,90'}]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['valor_total'], 459.67)   # 45,90 x 1,3 = 59,67 + 400

    def test_o_servidor_ignora_valor_calculado_enviado_pela_tela(self):
        a = self.criar(itens=[{'peca_id': self.peca.id_peca, 'quantidade': 1, 'valor_unitario': 1, 'adicional': 0}])
        self.assertEqual(a['valor_total'], 790.0)

    def test_valor_nao_muda_quando_surge_cotacao_nova(self):
        a = self.criar()
        CotacaoPeca.objects.create(peca=self.peca, fornecedor=self.fornecedor, valor='999.00', data_cotacao=date.today())
        self.assertEqual(self.client.get(f"/api/orcamentos/{a['id']}/").json()['dado']['valor_total'], 1180.0)


    def test_a_regra_e_aplicada_por_padrao(self):
        self.assertTrue(self.criar()['aplicar_regra'])

    def test_sem_a_regra_o_valor_digitado_e_o_valor_cheio(self):
        a = self.criar(aplicar_regra=False, itens=[
            {'peca_id': self.peca.id_peca, 'valor_base': '1000', 'quantidade': 1},
            {'nome': 'Fonte', 'descricao': 'Fonte 65W', 'valor_base': '200'}])
        self.assertFalse(a['aplicar_regra'])
        self.assertEqual([(i['valor_unitario'], i['adicional']) for i in a['itens']], [(1000.0, 0.0), (200.0, 0.0)])
        self.assertEqual(a['valor_total'], 1200.0)

    def test_sem_a_regra_sem_valor_digitado_usa_a_cotacao_como_valor_cheio(self):
        a = self.criar(aplicar_regra=False, itens=[{'peca_id': self.peca.id_peca, 'quantidade': 2}])
        self.assertEqual(a['valor_total'], 600.0)            # 300 x 2, sem margem e sem adicional

    def test_aceita_a_regra_enviada_como_texto(self):
        self.assertFalse(self.criar(aplicar_regra='false')['aplicar_regra'])
        self.assertTrue(self.criar(aplicar_regra='true')['aplicar_regra'])

    def test_alterar_a_regra_de_laudo_emitido_fica_no_historico_e_recalcula(self):
        a = self.criar()
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], aplicar_regra=False, motivo_alteracao='Cliente com preço fechado'))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['valor_total'], 600.0)
        historico = self.client.get(f"/api/orcamentos/{a['id']}/historico/").json()['dados']
        mudancas = [alt for h in historico for alt in h['alteracoes'] if alt['campo'] == 'Regra de preço']
        self.assertEqual(mudancas, [{'campo': 'Regra de preço', 'de': 'Aplicada', 'para': 'Não aplicada (valor cheio)'}])

    def test_word_valor_na_mesma_linha_da_etiqueta_e_com_a_formatacao_dela(self):
        from io import BytesIO
        from docx import Document
        a = self.criar(cliente_email='maria@exemplo.com', motivo_problema='Display trincado', analise='Mediante informações do usuário.')
        r = self.client.get(f"/api/orcamentos/{a['id']}/docx/")
        pars = [p for t in Document(BytesIO(r.content)).tables for row in t.rows for c in row.cells for p in c.paragraphs]
        textos = [p.text for p in pars]
        self.assertTrue(any(t == 'Motivo/Problema do Equipamento: Display trincado' for t in textos), textos)
        self.assertTrue(any(t == 'Análise: Mediante informações do usuário.' for t in textos))
        email = next(p for p in pars if p.text == 'E-MAIL: maria@exemplo.com')
        self.assertIsNone(email.runs[-1].font.name)          # herda a fonte da etiqueta, sem forçar outra
        self.assertFalse(email.runs[-1].bold)
        data = next(p for p in pars if p.text.startswith('DATA:'))
        self.assertNotIn('\t', data.text)                    # sem o TAB que empurrava a data para longe


class OrcamentoTests(OrcamentoBase):
    def test_cria_com_numero_sequencial(self):
        a = self.criar()
        b = self.criar()
        self.assertTrue(a['numero'].endswith('-0001'))
        self.assertTrue(b['numero'].endswith('-0002'))
        self.assertEqual(a['cliente_uf'], 'SP')
        self.assertEqual(a['status'], 'rascunho')

    def test_analista_e_email_sao_sempre_os_do_usuario(self):
        a = self.criar(analista_nome='Outra Pessoa', analista_email='outra@exemplo.com')
        self.assertEqual(a['analista_nome'], 'Ana Analista')
        self.assertEqual(a['analista_email'], EMAIL_ANALISTA)

    def test_validade_e_de_15_dias_contando_a_emissao_como_dia_1(self):
        a = self.criar(data_emissao='2020-01-01', validade_ate='2030-12-31')   # valores da tela são ignorados
        hoje = date.today()
        self.assertEqual(a['data_emissao'], hoje.isoformat())
        # Dia 1 = emissão, dia 15 = emissão + 14.
        self.assertEqual(a['validade_ate'], (hoje + timedelta(days=14)).isoformat())

    def test_peca_sem_cotacao_exige_valor_informado(self):
        sem = Peca.objects.create(part_number='SEM', descricao='Sem cotação')
        r = self.post_json('/api/orcamentos/', self.dados(itens=[{'peca_id': sem.id_peca}]))
        self.assertEqual(r.status_code, 400)

    def test_item_avulso_sem_peca_do_catalogo(self):
        r = self.post_json('/api/orcamentos/', self.dados(itens=[
            {'nome': 'Fonte', 'descricao': 'Fonte 65W', 'valor_base': '120'}]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['valor_total'], 556.0)    # 120 x 1,3 = 156 + 400

    def test_campos_obrigatorios(self):
        self.assertEqual(self.post_json('/api/orcamentos/', self.dados(cliente_nome='')).status_code, 400)
        self.assertEqual(self.post_json('/api/orcamentos/', self.dados(equip_modelo='')).status_code, 400)
        self.assertEqual(self.post_json('/api/orcamentos/', self.dados(disponibilidade='talvez')).status_code, 400)
        self.assertEqual(self.post_json('/api/orcamentos/', self.dados(itens=[{'peca_id': self.peca.id_peca, 'quantidade': 0}])).status_code, 400)

    def test_edita_rascunho_e_troca_os_itens(self):
        a = self.criar()
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], itens=[{'peca_id': self.peca.id_peca, 'quantidade': 1}]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['valor_total'], 790.0)
        self.assertEqual(Orcamento.objects.count(), 1)

    def test_ciclo_de_status(self):
        a = self.criar()
        url = f"/api/orcamentos/{a['id']}/status/"
        self.assertEqual(self.post_json(url, {'status': 'aprovado'}).status_code, 400)   # rascunho não aprova direto
        self.assertEqual(self.post_json(url, {'status': 'emitido'}).status_code, 200)
        self.assertEqual(self.post_json(url, {'status': 'aprovado'}).status_code, 200)
        self.assertEqual(self.post_json(url, {'status': 'emitido'}).status_code, 400)

    def test_emitir_exige_motivo_e_analise(self):
        a = self.criar(motivo_problema='', analise='')
        r = self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('motivo', r.json()['mensagem'])

    def test_emitir_fixa_analista_e_a_validade_de_15_dias_com_emissao_como_dia_1(self):
        a = self.criar()
        r = self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual(d['analista_email'], EMAIL_ANALISTA)
        self.assertEqual(d['validade_ate'], (date.fromisoformat(d['data_emissao']) + timedelta(days=14)).isoformat())

    def test_emitir_exige_email_cadastrado_no_usuario(self):
        self.client.get('/logout/')
        sem_email = self.criar_funcionario(cargo='Analista de Triagem', login=55, nome='Sem Email', email='')
        self.entrar(sem_email)
        a = self.criar()
        r = self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('e-mail', r.json()['mensagem'])
        self.assertEqual(Orcamento.objects.get().status, 'rascunho')

    def emitir(self):
        a = self.criar()
        r = self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['dado']

    def test_alterar_laudo_emitido_exige_motivo(self):
        a = self.emitir()
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Outro'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('motivo', r.json()['mensagem'])
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Outro', motivo_alteracao='abc'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Orcamento.objects.get().cliente_nome, 'Prefeitura')

    def test_alterar_emitido_mantem_status_numero_datas_e_analista(self):
        a = self.emitir()
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Prefeitura Municipal',
                                                           motivo_alteracao='Correção do nome do cliente'))
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual(d['cliente_nome'], 'Prefeitura Municipal')
        for campo in ('status', 'numero', 'data_emissao', 'validade_ate', 'analista_nome', 'analista_email'):
            self.assertEqual(d[campo], a[campo], campo)

    def test_alteracao_fica_registrada_no_historico(self):
        a = self.emitir()
        self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Prefeitura Municipal',
                                                      motivo_alteracao='Correção do nome do cliente'))
        historico = self.client.get(f"/api/orcamentos/{a['id']}/historico/").json()['dados']
        entrada = next(h for h in historico if h['motivo'] == 'Correção do nome do cliente')
        self.assertEqual(entrada['usuario'], 'Ana Analista')
        self.assertEqual(entrada['alteracoes'], [{'campo': 'Cliente', 'de': 'Prefeitura', 'para': 'Prefeitura Municipal'}])
        # a emissão também aparece (mudança de status)
        self.assertTrue(any(h['motivo'] == 'Mudança de status' for h in historico))

    def test_alterar_pecas_recalcula_o_preco_e_registra_o_total(self):
        a = self.emitir()                                     # 2 unidades: R$ 1.180,00
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], itens=[{'peca_id': self.peca.id_peca, 'quantidade': 1}],
                                                           motivo_alteracao='Cliente reduziu a quantidade'))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['valor_total'], 790.0)
        historico = self.client.get(f"/api/orcamentos/{a['id']}/historico/").json()['dados']
        campos = [alt['campo'] for h in historico for alt in h['alteracoes']]
        self.assertIn('Valor total', campos)
        self.assertIn('Peças do orçamento', campos)

    def test_alteracao_sem_mudanca_e_recusada(self):
        a = self.emitir()
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], motivo_alteracao='Só conferindo'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Nenhuma alteração', r.json()['mensagem'])

    def test_laudo_cancelado_nao_pode_ser_alterado(self):
        a = self.emitir()
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'cancelado'})
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Outro', motivo_alteracao='Tentativa'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('cancelados', r.json()['mensagem'])

    def test_laudo_aprovado_so_gestao_altera(self):
        a = self.emitir()
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'aprovado'})
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Outro', motivo_alteracao='Correção'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Gestor', r.json()['mensagem'])
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Gestor', login=88, nome='Chefe'))
        r = self.post_json('/api/orcamentos/', self.dados(id=a['id'], cliente_nome='Outro', motivo_alteracao='Correção autorizada'))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['status'], 'aprovado')
        self.assertEqual(r.json()['dado']['analista_nome'], 'Ana Analista')   # o analista original continua

    def test_dado_informa_se_o_laudo_pode_ser_alterado(self):
        a = self.criar()
        self.assertFalse(a['alteravel'])      # rascunho edita direto
        self.assertTrue(self.emitir()['alteravel'])

    def test_so_rascunho_pode_ser_excluido(self):
        a = self.criar()
        b = self.criar()
        self.post_json(f"/api/orcamentos/{b['id']}/status/", {'status': 'emitido'})
        self.assertEqual(self.client.delete(f"/api/orcamentos/{a['id']}/").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/orcamentos/{b['id']}/").status_code, 400)

    def test_funcionario_comum_nao_cria_orcamento(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Funcionário', login=99))
        self.assertEqual(self.post_json('/api/orcamentos/', self.dados()).status_code, 403)
        self.assertEqual(self.client.get('/api/orcamentos/').status_code, 200)

    def test_baixa_o_laudo_em_word(self):
        a = self.criar()
        r = self.client.get(f"/api/orcamentos/{a['id']}/docx/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('wordprocessingml', r['Content-Type'])
        self.assertTrue(r.content.startswith(b'PK'))   # arquivo .docx é um zip
        self.assertIn(a['numero'], r['Content-Disposition'])

    def test_usuario_escolhe_o_nome_do_arquivo(self):
        a = self.criar()
        r = self.client.get(f"/api/orcamentos/{a['id']}/docx/", {'nome': 'Laudo Prefeitura Out'})
        self.assertIn('Laudo Prefeitura Out.docx', r['Content-Disposition'])

    def test_nome_do_arquivo_perigoso_e_limpo(self):
        a = self.criar()
        r = self.client.get(f"/api/orcamentos/{a['id']}/docx/", {'nome': '../../etc/passwd'})
        self.assertIn('etcpasswd.docx', r['Content-Disposition'])
        self.assertNotIn('..', r['Content-Disposition'])

    def test_pagina_de_emissao_abre_com_a_configuracao_de_precos(self):
        r = self.client.get('/orcamentos/emissao/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('precificacao-data', r.content.decode())


class PesquisaEEstatisticasTests(OrcamentoBase):
    def test_pesquisa_por_texto_status_e_periodo(self):
        a = self.criar(cliente_nome='Prefeitura de Sorocaba', ticket='555')
        b = self.criar(cliente_nome='Escola Estadual')
        self.post_json(f"/api/orcamentos/{b['id']}/status/", {'status': 'emitido'})
        Orcamento.objects.filter(pk=b['id']).update(data_emissao=date(2026, 1, 10))

        def ids(**params):
            dados = self.client.get('/api/orcamentos/', params).json()['dados']
            return {d['id'] for d in dados}

        self.assertEqual(ids(q='sorocaba'), {a['id']})
        self.assertEqual(ids(q='555'), {a['id']})
        self.assertEqual(ids(status='emitido'), {b['id']})
        self.assertEqual(ids(de='2026-06-01'), {a['id']})
        self.assertEqual(ids(), {a['id'], b['id']})

    def test_pesquisa_retorna_valor_total(self):
        self.criar()
        linha = self.client.get('/api/orcamentos/').json()['dados'][0]
        self.assertEqual(linha['valor_total'], 1180.0)

    def test_estatisticas(self):
        ids = [self.criar()['id'] for _ in range(3)]
        for i in ids:
            self.post_json(f'/api/orcamentos/{i}/status/', {'status': 'emitido'})
        self.post_json(f'/api/orcamentos/{ids[0]}/status/', {'status': 'aprovado'})
        self.post_json(f'/api/orcamentos/{ids[1]}/status/', {'status': 'recusado'})
        rascunho = self.criar()   # não conta nos valores

        e = self.client.get('/api/orcamentos/estatisticas/').json()['dado']
        self.assertEqual(e['total'], 4)
        self.assertEqual(e['por_status']['aprovado'], 1)
        self.assertEqual(e['por_status']['rascunho'], 1)
        self.assertEqual(e['valor_emitido'], 3540.0)       # 3 laudos x 1.180
        self.assertEqual(e['valor_aprovado'], 1180.0)
        self.assertEqual(e['ticket_medio'], 1180.0)
        self.assertEqual(e['taxa_aprovacao'], 50.0)
        self.assertEqual(e['pecas_mais_orcadas'][0]['nome'], 'L1')
        self.assertEqual(e['pecas_mais_orcadas'][0]['quantidade'], 6)
        self.assertEqual(len(e['por_mes']), 1)
        self.assertEqual(rascunho['status'], 'rascunho')

    def test_estatisticas_sem_dados(self):
        e = self.client.get('/api/orcamentos/estatisticas/').json()['dado']
        self.assertEqual(e['total'], 0)
        self.assertIsNone(e['taxa_aprovacao'])
        self.assertEqual(e['ticket_medio'], 0.0)

    def test_pre_preenchimento_a_partir_da_triagem(self):
        empresa = Empresa.objects.create(cnpj='11222333000181', razao_social='Cliente X', tipo=2)
        tecnico = Tecnico.objects.create(empresa=empresa, nome='Téc')
        equip = Equipamento.objects.create(pn='PN9', modelo='EliteBook', tipo='Notebook', marca='HP')
        Triagem.objects.create(
            n_ticket=4321, nf=1, cidade='Sorocaba', estado='SP', tecnico=tecnico, cliente=empresa, equipamento=equip,
            analista_chamado=self.func, analista_triagem=self.func, sn='SN77', status=2,
            defeito_usuario='Tela quebrada', analise='Painel trincado',
        )
        r = self.client.get('/api/orcamentos/pre-preenchimento/', {'ticket': 4321})
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual((d['cliente_nome'], d['equip_modelo'], d['equip_sn']), ('Cliente X', 'EliteBook', 'SN77'))
        self.assertEqual((d['equip_tipo'], d['equip_marca']), ('Notebook', 'HP'))
        self.assertEqual(d['motivo_problema'], 'Tela quebrada')
        self.assertEqual(self.client.get('/api/orcamentos/pre-preenchimento/', {'ticket': 1}).status_code, 404)
        self.assertEqual(self.client.get('/api/orcamentos/pre-preenchimento/', {'ticket': 'abc'}).status_code, 400)


class PendentesDeDecisaoTests(OrcamentoBase):
    """Laudos emitidos com a validade vencida entram na lista de "aguardando resposta do cliente"."""

    def emitido(self, validade_ate, status='emitido'):
        a = self.criar()
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        Orcamento.objects.filter(pk=a['id']).update(validade_ate=validade_ate, status=status)
        return a['id']

    def pendentes(self):
        r = self.client.get('/api/orcamentos/pendentes-decisao/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_validade_vencida_aparece_como_pendente(self):
        id_orc = self.emitido(date.today() - timedelta(days=3))
        r = self.pendentes()
        self.assertEqual(r['total'], 1)
        self.assertEqual(r['dados'][0]['id'], id_orc)
        self.assertEqual(r['dados'][0]['dias_vencido'], 3)

    def test_no_ultimo_dia_de_validade_ainda_nao_e_pendente(self):
        self.emitido(date.today())
        self.assertEqual(self.pendentes()['total'], 0)

    def test_so_aparece_no_dia_seguinte_ao_ultimo_dia_de_validade(self):
        self.emitido(date.today() - timedelta(days=1))
        self.assertEqual(self.pendentes()['total'], 1)

    def test_dentro_da_validade_nao_e_pendente(self):
        self.emitido(date.today() + timedelta(days=5))
        self.assertEqual(self.pendentes()['total'], 0)

    def test_aprovado_recusado_e_cancelado_nao_sao_pendentes(self):
        for status in ('aprovado', 'recusado', 'cancelado', 'rascunho'):
            self.emitido(date.today() - timedelta(days=10), status=status)
        self.assertEqual(self.pendentes()['total'], 0)

    def test_responder_tira_o_laudo_da_lista(self):
        id_orc = self.emitido(date.today() - timedelta(days=2))
        r = self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'aprovado'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.pendentes()['total'], 0)
        self.assertEqual(Orcamento.objects.get(pk=id_orc).status, 'aprovado')

    def test_pendentes_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/orcamentos/pendentes-decisao/').status_code, 401)


class MotivoDaRecusaTests(OrcamentoBase):
    def emitir(self):
        a = self.criar()
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        return a['id']

    def test_recusar_com_motivo_grava_e_registra_no_historico(self):
        id_orc = self.emitir()
        r = self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'recusado', 'motivo_recusa': '  Preço   alto '})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['dado']['motivo_recusa'], 'Preço alto')
        historico = self.client.get(f'/api/orcamentos/{id_orc}/historico/').json()['dados'][0]
        self.assertIn('Motivo da recusa', [a['campo'] for a in historico['alteracoes']])

    def test_recusar_sem_motivo_continua_funcionando(self):
        id_orc = self.emitir()
        self.assertEqual(self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'recusado'}).status_code, 200)
        self.assertEqual(Orcamento.objects.get(pk=id_orc).motivo_recusa, '')

    def test_voltar_a_emitido_apaga_o_motivo(self):
        id_orc = self.emitir()
        self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'recusado', 'motivo_recusa': 'Prazo'})
        self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'emitido'})
        self.assertEqual(Orcamento.objects.get(pk=id_orc).motivo_recusa, '')

    def test_motivo_so_vale_para_recusado(self):
        id_orc = self.emitir()
        self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'aprovado', 'motivo_recusa': 'Preço'})
        self.assertEqual(Orcamento.objects.get(pk=id_orc).motivo_recusa, '')

    def test_estatisticas_agrupam_os_motivos(self):
        for motivo in ('Preço', 'Preço', 'Prazo', ''):
            id_orc = self.emitir()
            self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'recusado', 'motivo_recusa': motivo})
        dados = self.client.get('/api/orcamentos/estatisticas/').json()['dado']
        motivos = {m['nome']: m['quantidade'] for m in dados['motivos_recusa']}
        self.assertEqual(motivos, {'Preço': 2, 'Prazo': 1, '(não informado)': 1})


@override_settings(EMAIL_ENABLED=True)
class EnvioDoLaudoPorEmailTests(OrcamentoBase):
    def emitido(self, **dados):
        a = self.criar(**dados)
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        return a['id']

    def enviar(self, id_orc, **corpo):
        return self.post_json(f'/api/orcamentos/{id_orc}/enviar-email/', corpo)

    def test_envia_o_word_para_o_email_do_cliente_do_laudo(self):
        id_orc = self.emitido(cliente_email='maria@exemplo.com')
        r = self.enviar(id_orc)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['maria@exemplo.com'])
        self.assertEqual(len(msg.attachments), 1)
        self.assertTrue(msg.attachments[0][0].endswith('.docx'))
        self.assertIn('Orçamento', msg.subject)

    def test_destinatario_e_mensagem_podem_ser_trocados(self):
        id_orc = self.emitido(cliente_email='maria@exemplo.com')
        self.enviar(id_orc, destinatario='outra@exemplo.com', mensagem='Olá, segue o laudo combinado.')
        self.assertEqual(mail.outbox[0].to, ['outra@exemplo.com'])
        self.assertIn('Olá, segue o laudo combinado.', mail.outbox[0].body)

    def test_o_envio_fica_no_historico_do_laudo(self):
        id_orc = self.emitido(cliente_email='maria@exemplo.com')
        self.enviar(id_orc)
        historico = self.client.get(f'/api/orcamentos/{id_orc}/historico/').json()['dados'][0]
        self.assertEqual(historico['alteracoes'][0]['campo'], 'E-mail do laudo')
        self.assertEqual(historico['alteracoes'][0]['para'], 'maria@exemplo.com')

    def test_rascunho_nao_pode_ser_enviado(self):
        a = self.criar(cliente_email='maria@exemplo.com')
        r = self.enviar(a['id'])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_invalido_ou_ausente_e_recusado(self):
        id_orc = self.emitido(cliente_email='')
        self.assertEqual(self.enviar(id_orc).status_code, 400)
        self.assertEqual(self.enviar(id_orc, destinatario='isso-nao-e-email').status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_laudo_inexistente_devolve_404(self):
        self.assertEqual(self.enviar(99999, destinatario='a@b.com').status_code, 404)

    @override_settings(EMAIL_ENABLED=False)
    def test_sem_servidor_de_email_configurado_avisa_em_vez_de_fingir(self):
        id_orc = self.emitido(cliente_email='maria@exemplo.com')
        r = self.enviar(id_orc)
        self.assertEqual(r.status_code, 400)
        self.assertIn('não está configurado', r.json()['mensagem'])
        self.assertEqual(len(mail.outbox), 0)

    def test_exige_login(self):
        id_orc = self.emitido(cliente_email='maria@exemplo.com')
        self.client.get('/logout/')
        self.assertEqual(self.enviar(id_orc).status_code, 401)


class AvisosDeCotacaoNoRascunhoTests(OrcamentoBase):
    def setUp(self):
        super().setUp()
        self.fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor', tipo=3)
        self.peca_l1 = Peca.objects.create(part_number='L1', descricao='Tela')

    def avisos(self, id_orc):
        # O laudo de teste já traz um item com a peça padrão (cotada hoje); aqui interessam só os avisos da peça L1 e do item manual.
        todos = self.client.get(f'/api/orcamentos/{id_orc}/').json()['dado']['avisos_cotacao']
        return [a for a in todos if a.startswith('L1')]

    def com_item(self, **item):
        a = self.criar()
        ItemOrcamento.objects.create(orcamento_id=a['id'], peca=self.peca_l1, nome='Tela', part_number='L1', valor_base=100, valor_unitario=120, **item)
        return a['id']

    def test_peca_sem_cotacao_gera_aviso(self):
        avisos = self.avisos(self.com_item())
        self.assertEqual(len(avisos), 1)
        self.assertIn('sem cotação vinculada', avisos[0])

    def test_cotacao_antiga_gera_aviso_e_recente_nao(self):
        antiga = CotacaoPeca.objects.create(peca=self.peca_l1, fornecedor=self.fornecedor, valor='100.00', data_cotacao=date.today() - timedelta(days=120))
        recente = CotacaoPeca.objects.create(peca=self.peca_l1, fornecedor=self.fornecedor, valor='100.00', data_cotacao=date.today() - timedelta(days=5))
        self.assertIn('120 dias', self.avisos(self.com_item(cotacao=antiga))[0])
        self.assertEqual(self.avisos(self.com_item(cotacao=recente)), [])

    def test_item_digitado_sem_peca_nao_gera_aviso(self):
        a = self.criar()
        ItemOrcamento.objects.create(orcamento_id=a['id'], nome='Mão de obra', valor_base=50, valor_unitario=50)
        todos = self.client.get(f"/api/orcamentos/{a['id']}/").json()['dado']['avisos_cotacao']
        self.assertEqual([x for x in todos if 'Mão de obra' in x], [])

    def test_depois_de_emitido_nao_ha_mais_aviso(self):
        id_orc = self.com_item()
        self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'emitido'})
        self.assertEqual(self.client.get(f'/api/orcamentos/{id_orc}/').json()['dado']['avisos_cotacao'], [])


class CopiaDeLaudoTests(OrcamentoBase):
    """Começar um laudo novo a partir de um já existente."""

    def copiar(self, **params):
        return self.client.get('/api/orcamentos/copiar/', params)

    def emitido(self, **dados):
        a = self.criar(**dados)
        self.post_json(f"/api/orcamentos/{a['id']}/status/", {'status': 'emitido'})
        return a

    def test_copia_traz_os_dados_do_laudo_sem_numero_status_nem_datas(self):
        a = self.emitido(cliente_nome='Prefeitura de Itu', cliente_email='itu@exemplo.com', motivo_problema='Display trincado',
                         analise='Troca do display', prazo_estimado='5 dias úteis')
        r = self.copiar(numero=a['numero'])
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual((d['cliente_nome'], d['cliente_email'], d['motivo_problema'], d['analise'], d['prazo_estimado']),
                         ('Prefeitura de Itu', 'itu@exemplo.com', 'Display trincado', 'Troca do display', '5 dias úteis'))
        for campo in ('id', 'numero', 'status', 'data_emissao', 'validade_ate', 'analista_nome', 'analista_email', 'motivo_recusa', 'valor_total'):
            self.assertNotIn(campo, d, campo)
        self.assertEqual(d['origem']['numero'], a['numero'])
        self.assertEqual(len(d['itens']), 1)
        self.assertEqual(d['itens'][0]['peca_id'], self.peca.id_peca)

    def test_copia_o_ticket_o_equipamento_e_a_regra_de_preco(self):
        a = self.emitido(ticket='7788', equip_modelo='EliteBook', equip_sn='SN-ORIGINAL', aplicar_regra=False)
        d = self.copiar(numero=a['numero']).json()['dado']
        self.assertEqual((d['ticket'], d['equip_modelo'], d['equip_sn'], d['aplicar_regra']), ('7788', 'EliteBook', 'SN-ORIGINAL', False))

    def test_qualquer_status_pode_ser_copiado(self):
        rascunho = self.criar()
        recusado = self.emitido()
        self.post_json(f"/api/orcamentos/{recusado['id']}/status/", {'status': 'recusado', 'motivo_recusa': 'Preço'})
        cancelado = self.emitido()
        self.post_json(f"/api/orcamentos/{cancelado['id']}/status/", {'status': 'cancelado'})
        for a in (rascunho, recusado, cancelado):
            self.assertEqual(self.copiar(numero=a['numero']).status_code, 200, a['numero'])
        self.assertNotIn('motivo_recusa', self.copiar(numero=recusado['numero']).json()['dado'])      # a recusa não vai para a cópia

    def test_numero_sem_diferenciar_maiusculas_ou_so_o_final(self):
        a = self.emitido()
        self.assertEqual(self.copiar(numero=a['numero'].lower()).status_code, 200)
        final = a['numero'].split('ORC-', 1)[1]                   # ex.: 2026-0001
        self.assertEqual(self.copiar(numero=final).json()['dado']['origem']['numero'], a['numero'])

    def test_numero_inexistente_ou_vazio(self):
        self.emitido()
        self.assertEqual(self.copiar(numero='9999-9999').status_code, 404)
        self.assertEqual(self.copiar(numero='   ').status_code, 400)
        self.assertEqual(self.copiar().status_code, 400)

    def test_final_do_numero_que_casa_com_mais_de_um_laudo_e_recusado(self):
        a, b = self.emitido(), self.emitido()
        Orcamento.objects.filter(pk=b['id']).update(numero=a['numero'].replace('ORC-', 'OUT-'))   # dois números com o mesmo final
        r = self.copiar(numero=a['numero'].split('-', 1)[1])
        self.assertEqual(r.status_code, 400)
        self.assertIn('Mais de um laudo', r.json()['mensagem'])

    def test_por_padrao_mantem_os_valores_e_com_a_opcao_usa_a_cotacao_mais_recente(self):
        a = self.emitido()
        antigo = self.copiar(numero=a['numero']).json()['dado']['itens'][0]
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor Novo', tipo=3)
        nova = CotacaoPeca.objects.create(peca=self.peca, fornecedor=fornecedor, valor='999.00', data_cotacao=date.today())
        sem_atualizar = self.copiar(numero=a['numero']).json()['dado']
        self.assertEqual((sem_atualizar['itens'][0]['valor_base'], sem_atualizar['mudancas_preco']), (antigo['valor_base'], []))
        atualizado = self.copiar(numero=a['numero'], atualizar_valores=1).json()['dado']
        self.assertEqual((atualizado['itens'][0]['valor_base'], atualizado['itens'][0]['cotacao_id']), (999.0, nova.id_cotacao))
        self.assertIn('999,00', atualizado['mudancas_preco'][0])

    def test_salvar_a_copia_cria_um_laudo_novo_e_nao_mexe_no_original(self):
        a = self.emitido(cliente_nome='Cliente Original')
        d = self.copiar(numero=a['numero']).json()['dado']
        d['cliente_nome'] = 'Cliente Corrigido'
        itens = [{'peca_id': i['peca_id'], 'cotacao_id': i['cotacao_id'], 'quantidade': i['quantidade'], 'valor_base': i['valor_base']} for i in d['itens']]
        r = self.post_json('/api/orcamentos/', self.dados(cliente_nome=d['cliente_nome'], equip_modelo=d['equip_modelo'], equip_sn=d['equip_sn'], itens=itens))
        self.assertEqual(r.status_code, 200, r.content)
        novo = r.json()['dado']
        self.assertNotEqual(novo['numero'], a['numero'])
        self.assertEqual((novo['status'], novo['cliente_nome']), ('rascunho', 'Cliente Corrigido'))
        original = Orcamento.objects.get(pk=a['id'])
        self.assertEqual((original.cliente_nome, original.status), ('Cliente Original', 'emitido'))

    def test_por_id_e_exige_login(self):
        a = self.emitido()
        self.assertEqual(self.copiar(id=a['id']).json()['dado']['origem']['numero'], a['numero'])
        self.client.get('/logout/')
        self.assertEqual(self.copiar(numero=a['numero']).status_code, 401)
