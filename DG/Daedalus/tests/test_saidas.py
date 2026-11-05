from datetime import date
from unittest import mock

from django.core import mail
from django.test import override_settings

from ..models import AuditoriaLog, EstoquePeca, ItemSaida, MovimentoEstoque, Peca, SaidaPecas
from ..services.estoque import EstoqueService
from .base import BaseTestCase


def linha(pn='L1-TELA', **extra):
    """Uma linha no formato da planilha da operação."""
    dados = {'ticket': '8058339', 'cliente': 'TRT1', 'equipamento': '640 G9', 'descricao': 'System I7', 'quantidade': 1, 'part_number': pn,
             'destinatario': 'Ativaar', 'telefone': '5521995772830', 'cidade': 'Rio de Janeiro', 'estado': 'rj', 'data_solicitacao': '11/3/2026',
             'origem': 'auto'}
    dados.update(extra)
    return dados


class SaidasBase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=51, nome='Gil Gestor', email='gil@exemplo.com')
        self.entrar(self.gestor)
        self.tela = Peca.objects.create(part_number='L1-TELA', descricao='Tela 14 HD')
        self.bateria = Peca.objects.create(part_number='B1', descricao='Bateria')
        EstoqueService.movimentar(self.tela.id_peca, 'entrada', 10, custo='100,00')
        EstoqueService.movimentar(self.bateria.id_peca, 'entrada', 2)

    def criar(self, itens=None, **extra):
        r = self.post_json('/api/saidas/', {'observacao': '', 'itens': itens if itens is not None else [linha(quantidade=3)], **extra})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['dado']

    def enviar(self, id_saida, **corpo):
        return self.post_json(f'/api/saidas/{id_saida}/enviar/', corpo)

    def retorno(self, id_saida, **corpo):
        return self.post_json(f'/api/saidas/{id_saida}/retorno/', corpo)

    def saldo(self, peca):
        return EstoquePeca.objects.get(peca=peca).saldo


class RascunhoTests(SaidasBase):
    def test_cria_lista_com_numero_sequencial_e_os_campos_da_planilha(self):
        a, b = self.criar(), self.criar()
        ano = date.today().year
        self.assertEqual((a['numero'], b['numero']), (f'SAI-{ano}-0001', f'SAI-{ano}-0002'))
        i = a['itens'][0]
        self.assertEqual((i['ticket'], i['cliente'], i['equipamento'], i['part_number'], i['destinatario'], i['telefone']),
                         ('8058339', 'TRT1', '640 G9', 'L1-TELA', 'Ativaar', '5521995772830'))
        self.assertEqual((i['cidade'], i['estado'], i['data_solicitacao']), ('Rio de Janeiro', 'RJ', '2026-03-11'))   # UF em maiúsculas e data dd/m/aaaa
        self.assertEqual((i['numero_nf'], i['rastreio']), ('', ''))

    def test_cada_linha_pode_ter_ticket_e_destino_diferentes(self):
        d = self.criar([linha('L1-TELA', ticket='1', destinatario='Ativaar'), linha('B1', ticket='2', destinatario='Outra Empresa', cidade='Sorocaba', estado='SP')])
        self.assertEqual(sorted(d['tickets']), ['1', '2'])
        self.assertEqual(d['destinatarios'], ['Ativaar', 'Outra Empresa'])

    def test_origem_automatica_catalogo_e_nosso_estoque_o_resto_e_externo(self):
        d = self.criar([linha('L1-TELA'), linha('N07915-601', descricao='System I7')])
        self.assertEqual([(i['part_number'], i['origem']) for i in d['itens']], [('L1-TELA', 'estoque'), ('N07915-601', 'externa')])

    def test_item_marcado_como_nosso_estoque_precisa_estar_no_catalogo(self):
        r = self.post_json('/api/saidas/', {'itens': [linha('NAOEXISTE', origem='estoque')]})
        self.assertEqual(r.status_code, 400)
        self.assertIn('Não sai do nosso estoque', r.json()['mensagem'])

    def test_pn_e_normalizado_e_descricao_vem_do_catalogo_quando_falta(self):
        d = self.criar([linha(' l1-tela ', descricao='')])
        self.assertEqual((d['itens'][0]['part_number'], d['itens'][0]['descricao']), ('L1-TELA', 'Tela 14 HD'))

    def test_validacoes_apontam_a_linha_com_problema(self):
        casos = [
            ([], 'ao menos uma peça'), ([linha(destinatario='')], 'destinatário'), ([linha(cidade='')], 'cidade'),
            ([linha(estado='')], 'UF'), ([linha(estado='RIO')], 'UF'), ([linha(quantidade=0)], 'quantidade'),
            ([linha(quantidade='x')], 'quantidade'), ([linha(pn_ruim := '')], 'PN'), ([linha(origem='roubo')], 'origem'),
            ([linha(data_solicitacao='ontem')], 'Data inválida'),
        ]
        for itens, trecho in casos:
            r = self.post_json('/api/saidas/', {'itens': itens})
            self.assertEqual(r.status_code, 400, itens)
            self.assertIn(trecho, r.json()['mensagem'], itens)
        r = self.post_json('/api/saidas/', {'itens': [linha(), linha('B1', destinatario='')]})
        self.assertIn('Linha 2 (B1)', r.json()['mensagem'])
        self.assertEqual(SaidaPecas.objects.count(), 0)

    def test_editar_rascunho_troca_as_linhas_e_mantem_o_numero(self):
        d = self.criar()
        novo = self.post_json('/api/saidas/', {'id': d['id'], 'observacao': 'Urgente', 'itens': [linha('B1', ticket='99')]}).json()['dado']
        self.assertEqual(([i['part_number'] for i in novo['itens']], novo['observacao'], novo['numero']), (['B1'], 'Urgente', d['numero']))

    def test_aviso_soma_as_linhas_do_mesmo_pn_contra_o_saldo(self):
        d = self.criar([linha('B1', ticket='1'), linha('B1', ticket='2'), linha('B1', ticket='3')])    # 3 pedidos, saldo 2
        self.assertIn('B1: pedido 3, saldo em estoque 2', d['avisos'][0])

    def test_rascunho_nao_mexe_no_estoque(self):
        self.criar()
        self.assertEqual((self.saldo(self.tela), MovimentoEstoque.objects.count()), (10, 2))


class EnvioAoFiscalTests(SaidasBase):
    def test_envio_da_baixa_so_nas_linhas_do_nosso_estoque_com_ticket_e_destino_no_motivo(self):
        d = self.criar([linha('L1-TELA', quantidade=3), linha('B1', quantidade=1, ticket='777', destinatario='Outra'), linha('FORA-1', quantidade=4)])
        r = self.enviar(d['id'])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((self.saldo(self.tela), self.saldo(self.bateria)), (7, 1))
        movimentos = MovimentoEstoque.objects.filter(referencia=d['numero'])
        self.assertEqual(sorted(m.quantidade for m in movimentos), [-3, -1])
        motivos = ' '.join(m.motivo for m in movimentos)
        self.assertIn('ticket 8058339 para Ativaar', motivos)
        self.assertIn('ticket 777 para Outra', motivos)
        self.assertEqual(SaidaPecas.objects.get().status, 'enviada')

    def test_saldo_insuficiente_recusa_e_nao_baixa_nada(self):
        d = self.criar([linha('L1-TELA', quantidade=3), linha('B1', quantidade=5)])
        r = self.enviar(d['id'])
        self.assertEqual(r.status_code, 400)
        self.assertIn('B1: Saldo insuficiente', r.json()['mensagem'])
        self.assertEqual((self.saldo(self.tela), self.saldo(self.bateria), SaidaPecas.objects.get().status), (10, 2, 'rascunho'))

    def test_varias_linhas_do_mesmo_pn_somam_contra_o_saldo(self):
        d = self.criar([linha('B1', ticket='1'), linha('B1', ticket='2'), linha('B1', ticket='3')])
        self.assertEqual(self.enviar(d['id']).status_code, 400)
        self.assertEqual(self.saldo(self.bateria), 2)

    def test_nao_envia_duas_vezes_nem_edita_as_linhas_depois_de_enviada(self):
        d = self.criar()
        self.enviar(d['id'])
        self.assertEqual(self.enviar(d['id']).status_code, 400)
        self.assertEqual(self.post_json('/api/saidas/', {'id': d['id'], 'itens': [linha()]}).status_code, 400)
        self.assertEqual(self.saldo(self.tela), 7)

    @override_settings(EMAIL_ENABLED=True, FISCAL_EMAIL='fiscal@exemplo.com')
    def test_email_leva_as_linhas_no_corpo_e_o_csv_no_formato_da_planilha(self):
        d = self.criar([linha('L1-TELA', quantidade=3), linha('FORA-1', ticket='555', destinatario='Ativaar Ltda')], observacao='Urgente')
        r = self.enviar(d['id'], enviar_email=True, destinatarios='fiscal@exemplo.com', mensagem='Obrigado!')
        self.assertEqual(r.status_code, 200, r.content)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['fiscal@exemplo.com'])
        self.assertIn(d['numero'], msg.subject)
        for trecho in ('8058339', 'TRT1', '640 G9', 'L1-TELA', 'FORA-1', 'Ativaar Ltda', 'Rio de Janeiro/RJ', '11/03/2026',
                       'Urgente', 'Obrigado!', 'fora do nosso estoque', '(5521995772830)'):
            self.assertIn(trecho, msg.body)
        nome, conteudo, _ = msg.attachments[0]
        self.assertEqual(nome, f"{d['numero']}.csv")
        primeira = conteudo.decode('utf-8-sig').split('\r\n')[0] if isinstance(conteudo, bytes) else conteudo.lstrip('\ufeff').split('\r\n')[0]
        self.assertEqual(primeira, 'Ticket;Cliente;Equip.;Peça;QTDE;PN;Dest.;Número;Cidade;Estado;Dia Solic.;NF;RASTREIO;Observação')
        self.assertEqual(SaidaPecas.objects.get().emails_fiscal, 'fiscal@exemplo.com')

    @override_settings(EMAIL_ENABLED=True, FISCAL_EMAIL='fiscal@exemplo.com')
    def test_sem_informar_o_email_usa_o_fiscal_padrao(self):
        d = self.criar()
        self.enviar(d['id'], enviar_email=True)
        self.assertEqual(mail.outbox[0].to, ['fiscal@exemplo.com'])

    @override_settings(EMAIL_ENABLED=True, FISCAL_EMAIL='')
    def test_email_sem_destinatario_ou_invalido_e_recusado(self):
        d = self.criar()
        self.assertEqual(self.enviar(d['id'], enviar_email=True).status_code, 400)
        self.assertEqual(self.enviar(d['id'], enviar_email=True, destinatarios='nao-e-email').status_code, 400)
        self.assertEqual((SaidaPecas.objects.get().status, self.saldo(self.tela)), ('rascunho', 10))

    @override_settings(EMAIL_ENABLED=False)
    def test_email_pedido_sem_servidor_configurado_nao_finge_e_nao_baixa(self):
        d = self.criar()
        r = self.enviar(d['id'], enviar_email=True, destinatarios='fiscal@exemplo.com')
        self.assertEqual(r.status_code, 400)
        self.assertIn('não está configurado', r.json()['mensagem'])
        self.assertEqual((SaidaPecas.objects.get().status, self.saldo(self.tela)), ('rascunho', 10))

    @override_settings(EMAIL_ENABLED=True)
    def test_falha_no_envio_do_email_desfaz_tudo(self):
        d = self.criar()
        with mock.patch('Daedalus.services.saidas.EmailMessage.send', side_effect=OSError('smtp fora do ar')):
            r = self.enviar(d['id'], enviar_email=True, destinatarios='fiscal@exemplo.com')
        self.assertEqual(r.status_code, 400)
        self.assertEqual((SaidaPecas.objects.get().status, self.saldo(self.tela), SaidaPecas.objects.get().emails_fiscal), ('rascunho', 10, ''))
        self.assertEqual(MovimentoEstoque.objects.filter(tipo='saida').count(), 0)

    def test_enviar_sem_email_so_registra_o_envio(self):
        d = self.criar()
        self.assertEqual(self.enviar(d['id']).status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class NfRastreioECancelamentoTests(SaidasBase):
    def enviada(self, itens=None):
        d = self.criar(itens or [linha('L1-TELA', ticket='1'), linha('B1', ticket='2'), linha('FORA-1', ticket='3')])
        self.enviar(d['id'])
        return SaidaPecas.objects.get(pk=d['id'])

    def test_nf_e_rastreio_so_depois_de_enviada(self):
        d = self.criar()
        r = self.retorno(d['id'], linhas=[{'id': d['itens'][0]['id'], 'numero_nf': '1'}])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post_json(f"/api/saidas/{d['id']}/nota/", {'numero_nf': '1'}).status_code, 400)

    def test_nf_e_rastreio_linha_a_linha_e_status_automatico(self):
        saida = self.enviada()
        ids = list(saida.itens.values_list('id_item', flat=True))
        r = self.retorno(saida.pk, linhas=[{'id': ids[0], 'numero_nf': 'NF-1', 'rastreio': 'BR123'}, {'id': ids[1], 'numero_nf': 'NF-2'}])
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()['dado']
        self.assertEqual((d['status'], d['com_nf'], d['total_itens']), ('enviada', 2, 3))         # falta uma linha
        self.assertEqual([(i['numero_nf'], i['rastreio']) for i in d['itens']], [('NF-1', 'BR123'), ('NF-2', ''), ('', '')])
        r = self.retorno(saida.pk, linhas=[{'id': ids[2], 'numero_nf': 'NF-3', 'observacao': 'Entregue'}])
        self.assertEqual((r.json()['dado']['status'], r.json()['dado']['com_nf']), ('nota_emitida', 3))
        self.assertEqual(ItemSaida.objects.get(pk=ids[2]).observacao, 'Entregue')

    def test_mesma_nf_para_as_linhas_que_ainda_nao_tem(self):
        saida = self.enviada()
        primeira = saida.itens.first()
        self.retorno(saida.pk, linhas=[{'id': primeira.id_item, 'numero_nf': 'NF-ORIGINAL'}])
        r = self.post_json(f'/api/saidas/{saida.pk}/nota/', {'numero_nf': 'NF-GERAL'})
        self.assertEqual(r.status_code, 200, r.content)
        notas = list(saida.itens.values_list('numero_nf', flat=True))
        self.assertEqual(notas, ['NF-ORIGINAL', 'NF-GERAL', 'NF-GERAL'])                          # não sobrescreve a que já existia
        self.assertEqual(SaidaPecas.objects.get().status, 'nota_emitida')

    def test_apagar_uma_nf_volta_a_lista_para_enviada(self):
        saida = self.enviada([linha()])
        item = saida.itens.get()
        self.retorno(saida.pk, linhas=[{'id': item.id_item, 'numero_nf': 'NF-1'}])
        self.assertEqual(SaidaPecas.objects.get().status, 'nota_emitida')
        self.retorno(saida.pk, linhas=[{'id': item.id_item, 'numero_nf': ''}])
        self.assertEqual(SaidaPecas.objects.get().status, 'enviada')

    def test_retorno_nao_altera_os_dados_do_pedido(self):
        saida = self.enviada([linha()])
        item = saida.itens.get()
        self.retorno(saida.pk, linhas=[{'id': item.id_item, 'numero_nf': 'NF-1', 'destinatario': 'Hacker', 'quantidade': 99, 'part_number': 'X'}])
        item.refresh_from_db()
        self.assertEqual((item.destinatario, item.quantidade, item.part_number), ('Ativaar', 1, 'L1-TELA'))

    def test_retorno_invalido(self):
        saida = self.enviada([linha()])
        self.assertEqual(self.retorno(saida.pk).status_code, 400)                                  # nada informado
        self.assertEqual(self.retorno(saida.pk, linhas=[{'id': 99999, 'numero_nf': '1'}]).status_code, 400)
        outra = self.enviada([linha('B1')])
        self.assertEqual(self.retorno(saida.pk, linhas=[{'id': outra.itens.get().id_item, 'numero_nf': '1'}]).status_code, 400)   # linha de outra lista

    def test_cancelar_rascunho_nao_precisa_de_motivo_nem_mexe_no_estoque(self):
        d = self.criar()
        self.assertEqual(self.post_json(f"/api/saidas/{d['id']}/cancelar/", {}).status_code, 200)
        self.assertEqual((SaidaPecas.objects.get().status, self.saldo(self.tela)), ('cancelada', 10))

    def test_cancelar_enviada_exige_motivo_e_devolve_so_o_que_saiu_do_estoque(self):
        d = self.criar([linha('L1-TELA', quantidade=3), linha('FORA-1', quantidade=2)])
        self.enviar(d['id'])
        url = f"/api/saidas/{d['id']}/cancelar/"
        self.assertEqual(self.post_json(url, {}).status_code, 400)
        self.assertEqual(self.saldo(self.tela), 7)
        self.assertEqual(self.post_json(url, {'motivo': 'Pedido duplicado'}).status_code, 200)
        self.assertEqual(self.saldo(self.tela), 10)
        estorno = MovimentoEstoque.objects.filter(referencia=d['numero'], tipo='entrada').get()
        self.assertEqual((estorno.quantidade, 'Estorno' in estorno.motivo), (3, True))

    def test_nao_cancela_lista_com_nota_emitida_nem_ja_cancelada(self):
        saida = self.enviada([linha()])
        self.post_json(f'/api/saidas/{saida.pk}/nota/', {'numero_nf': '1'})
        self.assertEqual(self.post_json(f'/api/saidas/{saida.pk}/cancelar/', {'motivo': 'x'}).status_code, 400)
        outra = self.criar()
        self.post_json(f"/api/saidas/{outra['id']}/cancelar/", {})
        self.assertEqual(self.post_json(f"/api/saidas/{outra['id']}/cancelar/", {}).status_code, 400)

    def test_lista_inexistente_devolve_404(self):
        for url in ('/api/saidas/99999/', '/api/saidas/99999/csv/'):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        for acao in ('enviar', 'nota', 'retorno', 'cancelar'):
            self.assertEqual(self.post_json(f'/api/saidas/99999/{acao}/', {'numero_nf': '1', 'motivo': 'x', 'linhas': [{'id': 1}]}).status_code, 404, acao)


class ListaCsvEPermissoesTests(SaidasBase):
    def test_csv_tem_exatamente_as_colunas_da_planilha(self):
        d = self.criar([linha('N07915-601', descricao='System I7', ticket='8058339')])
        r = self.client.get(f"/api/saidas/{d['id']}/csv/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'\xef\xbb\xbf'))
        linhas = r.content.decode('utf-8-sig').strip().split('\r\n')
        self.assertEqual(linhas[0], 'Ticket;Cliente;Equip.;Peça;QTDE;PN;Dest.;Número;Cidade;Estado;Dia Solic.;NF;RASTREIO;Observação')
        self.assertEqual(linhas[1], '8058339;TRT1;640 G9;System I7;1;N07915-601;Ativaar;5521995772830;Rio de Janeiro;RJ;11/03/2026;;;')

    def test_lista_filtra_por_status_e_busca_por_ticket_pn_destinatario_nf_e_rastreio(self):
        a = self.criar([linha('B1', ticket='4001', cliente='Cliente Alfa', destinatario='Dest Alfa')])
        self.criar([linha('L1-TELA', ticket='4002', cliente='Cliente Beta', destinatario='Dest Beta')])
        self.enviar(a['id'])
        self.retorno(a['id'], linhas=[{'id': a['itens'][0]['id'], 'numero_nf': 'NF-777', 'rastreio': 'BR999XYZ'}])
        achar = lambda **p: [s['numero'] for s in self.client.get('/api/saidas/', p).json()['dados']]
        self.assertEqual(len(achar()), 2)
        self.assertEqual(achar(status='nota_emitida'), [a['numero']])
        for termo in ('4001', 'b1', 'alfa', 'nf-777', 'br999'):
            self.assertEqual(achar(q=termo), [a['numero']], termo)
        self.assertEqual(len(achar(q='4002')), 1)

    def test_funcionario_consulta_mas_nao_cria_envia_nem_registra_nf(self):
        d = self.criar()
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Funcionário', login=52, nome='Maria', email='m@exemplo.com'))
        self.assertEqual(self.client.get('/api/saidas/').status_code, 200)
        self.assertEqual(self.client.get('/saidas/').status_code, 200)
        self.assertEqual(self.post_json('/api/saidas/', {'itens': [linha()]}).status_code, 403)
        self.assertEqual(self.enviar(d['id']).status_code, 403)
        self.assertEqual(self.retorno(d['id'], linhas=[{'id': 1}]).status_code, 403)
        self.assertEqual(self.saldo(self.tela), 10)

    def test_analista_de_triagem_pode_criar_e_enviar(self):
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Analista de Triagem', login=53, nome='Ana', email='a@exemplo.com'))
        d = self.criar()
        self.assertEqual(self.enviar(d['id']).status_code, 200)
        self.assertEqual(SaidaPecas.objects.get().enviado_por_nome, 'Ana')

    def test_sino_conta_listas_aguardando_nota_e_auditoria_registra(self):
        d = self.criar()
        self.enviar(d['id'])
        itens = {i['tipo']: i for i in self.client.get('/api/avisos/').json()['dado']['itens']}
        self.assertEqual(itens['saidas']['quantidade'], 1)
        log = AuditoriaLog.objects.filter(entidade='Saída de peças').order_by('id_log').first()
        self.assertIn('1 linha(s)', log.descricao)

    def test_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/saidas/').status_code, 401)
        self.assertEqual(self.post_json('/api/saidas/', {'itens': [linha()]}).status_code, 401)
