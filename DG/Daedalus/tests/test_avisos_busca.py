from datetime import date, timedelta

from ..models import Insight, Orcamento, SnapshotSLA, SolicitacaoSenha
from .test_serie import SerieBase


class AvisosEBuscaTests(SerieBase):
    """Reaproveita o cenário de SerieBase (cliente, técnico, equipamento, laudos e triagens)."""

    def vencer(self, id_orc):
        self.post_json(f'/api/orcamentos/{id_orc}/status/', {'status': 'emitido'})
        Orcamento.objects.filter(pk=id_orc).update(validade_ate=date.today() - timedelta(days=2))

    def avisos(self):
        r = self.client.get('/api/avisos/')
        self.assertEqual(r.status_code, 200, r.content)
        return {i['tipo'] + ':' + i['nivel']: i for i in r.json()['dado']['itens']}, r.json()['dado']['total']

    def test_sem_pendencias_o_sino_fica_vazio(self):
        itens, total = self.avisos()
        self.assertEqual((itens, total), ({}, 0))

    def test_orcamento_vencido_aparece_para_todos(self):
        self.vencer(self.criar()['id'])
        itens, total = self.avisos()
        self.assertEqual(itens['orcamento:atencao']['quantidade'], 1)
        self.assertEqual(total, 1)

    def test_pedido_de_senha_so_aparece_para_a_gestao(self):
        usuario = self.criar_funcionario(cargo='Funcionário', login=77, nome='Maria', email='m@e.com')
        SolicitacaoSenha.objects.create(funcionario=usuario)
        self.assertNotIn('senha:atencao', self.avisos()[0])              # analista não vê
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Gestor', login=78, nome='Gil', email='g@e.com'))
        self.assertEqual(self.avisos()[0]['senha:atencao']['quantidade'], 1)

    def test_sla_estourado_e_alerta_critico_entram_no_sino(self):
        SnapshotSLA.objects.create(data=date.today(), ativos=5, acima_100=2, faixa_80_100=1)
        Insight.objects.create(tipo='teste', severidade='critico', titulo='Algo grave', texto='x')
        Insight.objects.create(tipo='teste', severidade='info', titulo='Informativo', texto='x')
        itens, total = self.avisos()
        self.assertEqual(itens['sla:critico']['quantidade'], 2)
        self.assertEqual(itens['sla:atencao']['quantidade'], 1)
        self.assertEqual(itens['insight:critico']['quantidade'], 1)       # o informativo não conta
        self.assertEqual(total, 4)

    def test_itens_criticos_vem_primeiro(self):
        self.vencer(self.criar()['id'])
        SnapshotSLA.objects.create(data=date.today(), ativos=1, acima_100=1)
        niveis = [i['nivel'] for i in self.client.get('/api/avisos/').json()['dado']['itens']]
        self.assertEqual(niveis, sorted(niveis, key=lambda n: {'critico': 0, 'atencao': 1}.get(n, 2)))

    def test_busca_acha_triagem_por_ticket_e_serie(self):
        self.triagem('SN-ABC', 4321)
        por_ticket = self.client.get('/api/busca/', {'q': '4321'}).json()['dados']
        self.assertEqual(por_ticket[0]['tipo'], 'triagem')
        por_serie = self.client.get('/api/busca/', {'q': 'sn-abc'}).json()['dados']
        self.assertEqual(por_serie[0]['tipo'], 'serie')                  # a linha do tempo vem primeiro
        self.assertIn('/serie/?sn=', por_serie[0]['url'])
        self.assertIn('triagem', [r['tipo'] for r in por_serie])

    def test_busca_acha_laudo_pelo_numero_e_pelo_cliente(self):
        a = self.criar(cliente_nome='Prefeitura de Itu')
        self.assertEqual(self.client.get('/api/busca/', {'q': a['numero']}).json()['dados'][0]['tipo'], 'orcamento')
        self.assertEqual(self.client.get('/api/busca/', {'q': 'Itu'}).json()['dados'][0]['tipo'], 'orcamento')

    def test_busca_curta_ou_numero_gigante_nao_quebra(self):
        self.assertEqual(self.client.get('/api/busca/', {'q': 'a'}).json()['dados'], [])
        self.assertEqual(self.client.get('/api/busca/', {'q': '9' * 40}).status_code, 200)

    def test_avisos_busca_e_ping_exigem_login(self):
        self.client.get('/logout/')
        for url in ('/api/avisos/', '/api/busca/?q=ab', '/api/sessao/ping/'):
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_ping_renova_a_sessao(self):
        self.assertEqual(self.client.get('/api/sessao/ping/').json()['status'], 'sucesso')
