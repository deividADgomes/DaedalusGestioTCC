from datetime import date

from ..models import AuditoriaLog, Empresa, Equipamento, Peca
from .base import BaseTestCase


class AuditoriaTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.gestor = self.criar_funcionario(cargo='Gestor', login=21, nome='Gil Gestor', email='gil@exemplo.com')
        self.analista = self.criar_funcionario(cargo='Analista de Triagem', login=22, nome='Ana Analista', email='ana@exemplo.com')
        self.entrar(self.gestor)

    def test_gravar_cadastro_gera_registro_com_quem_e_o_que(self):
        r = self.post_json('/api/empresa/', {'razao_social': 'Cliente Novo', 'cnpj': '03619767000191', 'tipo': 2})
        self.assertEqual(r.status_code, 200, r.content)
        log = AuditoriaLog.objects.get()
        self.assertEqual((log.funcionario_nome, log.acao, log.entidade), ('Gil Gestor', 'gravou', 'Empresa'))
        self.assertIn('razao_social=Cliente Novo', log.descricao)
        self.assertEqual(log.funcionario_id, self.gestor.id_funcionario)

    def test_senha_nunca_vai_para_o_log(self):
        self.post_json('/api/funcionario/', {'nome': 'Novo', 'cargo': 'Funcionário', 'login': 555, 'email': 'n@e.com', 'senha': 'Segredo#2026x'})
        texto = ' '.join(f"{l.descricao} {l.acao} {l.entidade}" for l in AuditoriaLog.objects.all())
        self.assertNotIn('Segredo', texto)
        self.assertIn('senha redefinida', texto)
        self.assertNotIn('n@e.com', texto)

    def test_gravar_e_excluir_cotacao_registra_as_duas_acoes(self):
        peca = Peca.objects.create(part_number='L1', descricao='Tela')
        fornecedor = Empresa.objects.create(cnpj='03619767000191', razao_social='Fornecedor', tipo=3)
        r = self.post_json(f'/api/pecas/{peca.id_peca}/cotacoes/', {'fornecedor_id': fornecedor.id_empresa, 'valor': '100,00', 'data_cotacao': date.today().isoformat()})
        self.assertEqual(r.status_code, 200, r.content)
        id_cotacao = r.json()['dado']['id']
        self.assertLess(self.client.delete(f'/api/cotacoes/{id_cotacao}/').status_code, 300)
        acoes = list(AuditoriaLog.objects.order_by('id_log').values_list('acao', 'entidade', 'entidade_id'))
        self.assertEqual(acoes, [('gravou', 'Cotação', peca.id_peca), ('excluiu', 'Cotação', id_cotacao)])

    def test_importacao_e_lista_de_pecas_sao_registradas(self):
        equip = Equipamento.objects.create(pn='ABC123', modelo='X')
        self.post_json('/api/modelo-equipamento/importar-pecas/', {'texto': 'ABC123;L1;Tela'})
        self.post_json(f'/api/modelo-equipamento/{equip.id_equipamento}/pecas/', {'pecas': [{'part_number': 'L1', 'descricao': 'Tela'}]})
        acoes = list(AuditoriaLog.objects.order_by('id_log').values_list('acao', 'descricao'))
        self.assertEqual(acoes[0][0], 'importou')
        self.assertIn('1 peça(s) na lista', acoes[1][1])
        self.assertEqual(AuditoriaLog.objects.order_by('-id_log')[0].entidade_id, equip.id_equipamento)

    def test_leituras_e_requisicoes_com_erro_nao_geram_registro(self):
        self.client.get('/api/empresa/')
        self.post_json('/api/empresa/', {'razao_social': '', 'cnpj': 'invalido', 'tipo': 2})     # recusada pela validação
        self.assertEqual(AuditoriaLog.objects.count(), 0)

    def test_consulta_ao_partsurfer_nao_e_gravacao(self):
        equip = Equipamento.objects.create(pn='ABC123', modelo='X')
        self.post_json(f'/api/modelo-equipamento/{equip.id_equipamento}/partsurfer/', {})
        self.assertEqual(AuditoriaLog.objects.count(), 0)

    def test_so_a_gestao_ve_a_auditoria(self):
        self.assertEqual(self.client.get('/api/auditoria/').status_code, 200)
        self.assertEqual(self.client.get('/auditoria/').status_code, 200)
        self.client.get('/logout/')
        self.entrar(self.analista)
        self.assertEqual(self.client.get('/api/auditoria/').status_code, 403)
        self.assertEqual(self.client.get('/auditoria/').status_code, 403)

    def test_busca_filtra_por_usuario(self):
        self.post_json('/api/empresa/', {'razao_social': 'Cliente Novo', 'cnpj': '03619767000191', 'tipo': 2})
        achados = self.client.get('/api/auditoria/', {'q': 'gil'}).json()['dados']
        self.assertEqual(len(achados), 1)
        self.assertEqual(self.client.get('/api/auditoria/', {'q': 'zzz'}).json()['dados'], [])
