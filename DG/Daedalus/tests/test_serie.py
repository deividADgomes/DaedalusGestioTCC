from datetime import timedelta

from django.utils import timezone

from ..models import ChamadoRFB, Empresa, Equipamento, Tecnico, Triagem
from .test_orcamentos import OrcamentoBase


class SerieBase(OrcamentoBase):
    """Cenário comum (cliente, técnico, equipamento e atalho para criar triagens), reaproveitado por outros testes."""

    def setUp(self):
        super().setUp()
        self.cliente = Empresa.objects.create(cnpj='11222333000181', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-1', modelo='ProBook')

    def triagem(self, sn, ticket, status=2):
        r = self.post_json('/api/triagem/', {
            'n_ticket': ticket, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
            'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
            'id_analista': self.func.id_funcionario, 'sn': sn, 'status_peca': status, 'conclusao': 'Placa com defeito'})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['id']


class SerieTests(SerieBase):
    """Reincidência na triagem e linha do tempo por número de série."""

    def test_aviso_de_reincidencia_lista_triagens_anteriores(self):
        a = self.triagem('SN-9', 1)
        self.triagem('SN-9', 2, status=1)
        self.triagem('OUTRO', 3)
        dados = self.client.get('/api/triagem/por-serie/', {'sn': 'sn-9'}).json()['dados']   # sem diferenciar maiúsculas
        self.assertEqual(sorted(d['n_ticket'] for d in dados), [1, 2])
        sem_a = self.client.get('/api/triagem/por-serie/', {'sn': 'SN-9', 'excluir': a}).json()['dados']
        self.assertEqual([d['n_ticket'] for d in sem_a], [2])           # ao editar, a própria triagem não conta

    def test_serie_vazia_ou_inedita_nao_tem_aviso(self):
        self.assertEqual(self.client.get('/api/triagem/por-serie/', {'sn': ''}).json()['dados'], [])
        self.assertEqual(self.client.get('/api/triagem/por-serie/', {'sn': 'NUNCA'}).json()['dados'], [])

    def test_linha_do_tempo_reune_triagem_laudo_e_chamado(self):
        self.triagem('SN-9', 1)
        self.criar(equip_sn='sn-9')
        ChamadoRFB.objects.create(
            ticket='RFB1', data_abertura=timezone.now() - timedelta(days=2), estado='SP', cidade='Cidade', is_metropolitana=True,
            descricao_defeito='x', modelo_equipamento='ProBook', sn='SN-9', status='andamento')
        ChamadoRFB.objects.create(
            ticket='RFB2', data_abertura=timezone.now(), estado='SP', cidade='Cidade', is_metropolitana=True,
            descricao_defeito='x', modelo_equipamento='ProBook', sn='OUTRO', status='andamento')
        d = self.client.get('/api/serie/', {'sn': 'SN-9'}).json()['dado']
        self.assertEqual(d['resumo'], {'triagem': 1, 'orcamento': 1, 'rfb': 1})
        self.assertEqual({e['tipo'] for e in d['eventos']}, {'triagem', 'orcamento', 'rfb'})
        datas = [e['data'] for e in d['eventos'] if e['data']]
        self.assertEqual(datas, sorted(datas, reverse=True))               # mais recente primeiro

    def test_triagem_antiga_sem_data_vai_para_o_fim(self):
        antiga = self.triagem('SN-9', 1)
        Triagem.objects.filter(pk=antiga).update(criado_em=None)
        self.criar(equip_sn='SN-9')
        eventos = self.client.get('/api/serie/', {'sn': 'SN-9'}).json()['dado']['eventos']
        self.assertEqual([e['tipo'] for e in eventos], ['orcamento', 'triagem'])

    def test_sem_serie_informada_devolve_400(self):
        self.assertEqual(self.client.get('/api/serie/', {'sn': '  '}).status_code, 400)

    def test_serie_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/serie/', {'sn': 'X'}).status_code, 401)
        self.assertEqual(self.client.get('/api/triagem/por-serie/', {'sn': 'X'}).status_code, 401)
