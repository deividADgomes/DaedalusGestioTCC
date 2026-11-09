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

    def corpo(self):
        return {'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
                'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
                'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2}

    def salvar(self, **extra):
        dados = {'n_ticket': 100, 'nf': 1, 'cidade': 'Sorocaba', 'estado': 'SP', 'id_cliente': self.cliente.id_empresa,
                 'id_equipamento': self.equip.id_equipamento, 'id_tecnico': self.tecnico.id_tecnico,
                 'id_analista': self.func.id_funcionario, 'sn': 'SN1', 'status_peca': 2}
        dados.update(extra)
        r = self.post_json('/api/triagem/', dados)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['id']

    MOTIVO = 'Não era a peça com defeito'

    def test_grava_sim_nao_e_nao_informado(self):
        casos = ((True, True), (False, False), ('sim', True), ('nao', False), ('não', False), (None, None), ('talvez', None))
        for enviado, esperado in casos:
            id_t = self.salvar(troca_indevida=enviado, motivo_troca_indevida=self.MOTIVO)
            self.assertIs(Triagem.objects.get(pk=id_t).troca_indevida, esperado, enviado)
        id_t = self.salvar()                                   # campo omitido (cliente antigo da API): não informado
        self.assertIsNone(Triagem.objects.get(pk=id_t).troca_indevida)

    def test_consulta_devolve_o_valor_e_o_motivo(self):
        id_t = self.salvar(troca_indevida=True, motivo_troca_indevida=self.MOTIVO, justificativa_troca_indevida='Era o cabo')
        d = self.client.get('/api/triagem/', {'id': id_t}).json()['dado']
        self.assertEqual((d['troca_indevida'], d['motivo_troca_indevida'], d['justificativa_troca_indevida']), (True, self.MOTIVO, 'Era o cabo'))

    def test_alterar_o_campo_entra_no_historico(self):
        id_t = self.salvar(troca_indevida=False)
        self.salvar(id=id_t, troca_indevida=True, motivo_troca_indevida='Resolvido com software')
        mudou = {a['campo']: (a['de'], a['para']) for a in TriagemHistorico.objects.get().alteracoes}
        self.assertEqual(mudou['Troca indevida'], ('Não', 'Sim'))
        self.assertEqual(mudou['Motivo da troca indevida'], ('—', 'Resolvido com software'))

    def test_triagem_antiga_sem_informacao_aparece_como_travessao_no_historico(self):
        id_t = self.salvar()
        self.salvar(id=id_t, troca_indevida=True, motivo_troca_indevida=self.MOTIVO)
        alteracao = TriagemHistorico.objects.get().alteracoes[0]
        self.assertEqual((alteracao['campo'], alteracao['de'], alteracao['para']), ('Troca indevida', '—', 'Sim'))

    def test_salvar_igual_nao_gera_historico(self):
        id_t = self.salvar(troca_indevida=True, motivo_troca_indevida=self.MOTIVO)
        self.salvar(id=id_t, troca_indevida=True, motivo_troca_indevida=self.MOTIVO)
        self.assertEqual(TriagemHistorico.objects.count(), 0)

    # ---------------------------------------------------------------- motivo da troca indevida
    def test_troca_indevida_exige_um_motivo_da_lista(self):
        for extra in ({}, {'motivo_troca_indevida': ''}, {'motivo_troca_indevida': 'Porque sim'}):
            r = self.post_json('/api/triagem/', {**self.corpo(), 'troca_indevida': True, **extra})
            self.assertEqual(r.status_code, 400, extra)
            self.assertIn('motivo da troca indevida', r.json()['mensagem'])
        self.assertEqual(Triagem.objects.count(), 0)

    def test_todos_os_motivos_da_lista_sao_aceitos(self):
        opcoes = self.client.get('/api/triagem/opcoes/').json()['dados']
        self.assertEqual(opcoes['motivo_outro'], 'Outro')
        for motivo in opcoes['motivos_troca_indevida']:
            id_t = self.salvar(troca_indevida=True, motivo_troca_indevida=motivo, justificativa_troca_indevida='Detalhe do caso')
            self.assertEqual(Triagem.objects.get(pk=id_t).motivo_troca_indevida, motivo)
        self.assertEqual(set(opcoes['motivos_troca_indevida']), {'Avaria constatada (orçamento)', 'Não era a peça com defeito', 'Resolvido com software', 'Outro'})

    def test_motivo_outro_exige_a_explicacao(self):
        r = self.post_json('/api/triagem/', {**self.corpo(), 'troca_indevida': True, 'motivo_troca_indevida': 'Outro', 'justificativa_troca_indevida': ' x '})
        self.assertEqual(r.status_code, 400)
        self.assertIn('Descreva', r.json()['mensagem'])
        id_t = self.salvar(troca_indevida=True, motivo_troca_indevida='Outro', justificativa_troca_indevida='  Cabo   de vídeo com defeito  ')
        self.assertEqual(Triagem.objects.get(pk=id_t).justificativa_troca_indevida, 'Cabo de vídeo com defeito')

    def test_para_os_demais_motivos_a_explicacao_e_opcional(self):
        id_t = self.salvar(troca_indevida=True, motivo_troca_indevida='Resolvido com software')
        t = Triagem.objects.get(pk=id_t)
        self.assertEqual((t.motivo_troca_indevida, t.justificativa_troca_indevida), ('Resolvido com software', ''))

    def test_troca_nao_indevida_ou_nao_informada_nao_guarda_motivo(self):
        for valor in (False, None):
            id_t = self.salvar(troca_indevida=valor, motivo_troca_indevida=self.MOTIVO, justificativa_troca_indevida='ignorado')
            t = Triagem.objects.get(pk=id_t)
            self.assertEqual((t.motivo_troca_indevida, t.justificativa_troca_indevida), ('', ''))

    def test_mudar_de_sim_para_nao_apaga_o_motivo_e_registra_no_historico(self):
        id_t = self.salvar(troca_indevida=True, motivo_troca_indevida=self.MOTIVO, justificativa_troca_indevida='Era o cabo')
        self.salvar(id=id_t, troca_indevida=False)
        t = Triagem.objects.get(pk=id_t)
        self.assertEqual((t.motivo_troca_indevida, t.justificativa_troca_indevida), ('', ''))
        mudou = {a['campo']: (a['de'], a['para']) for a in TriagemHistorico.objects.get().alteracoes}
        self.assertEqual(mudou['Motivo da troca indevida'], (self.MOTIVO, '—'))
        self.assertEqual(mudou['Justificativa da troca indevida'], ('Era o cabo', '—'))

    def test_opcoes_exigem_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/triagem/opcoes/').status_code, 401)


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


    def test_ranking_dos_motivos_das_trocas_indevidas(self):
        for motivo, qtd in (('Não era a peça com defeito', 3), ('Resolvido com software', 1), ('', 1)):
            for _ in range(qtd):
                t = self.triagem(status=2)
                Triagem.objects.filter(pk=t.pk).update(troca_indevida=True, motivo_troca_indevida=motivo)
        t = self.triagem(status=2)
        Triagem.objects.filter(pk=t.pk).update(troca_indevida=False)                  # troca correta: fora do ranking
        motivos = self.dados('qualidade')['troca_indevida']['motivos']
        self.assertEqual([(m['nome'], m['quantidade']) for m in motivos],
                         [('Não era a peça com defeito', 3), ('(sem motivo informado)', 1), ('Resolvido com software', 1)])
        self.assertEqual(motivos[0]['pct'], 60.0)

    def test_sem_trocas_indevidas_o_ranking_fica_vazio(self):
        self.marcar(2, False)
        self.assertEqual(self.dados('qualidade')['troca_indevida']['motivos'], [])
