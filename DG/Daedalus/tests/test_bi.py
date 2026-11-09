from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from ..models import (AgendamentoChamado, AlertaSLAEnviado, ChamadoRFB, CotacaoPeca, Empresa, Equipamento, Insight,
                      ItemOrcamento, Orcamento, OrcamentoHistorico, Peca, SnapshotSLA, Tecnico, Triagem)
from ..services.bi import BIService
from .base import BaseTestCase

CALCULO = 'Daedalus.services.chamado_rfb.ChamadoRFBService.calcular_consumo_sla'


class BIBase(BaseTestCase):
    """Fixtures do BI. O cálculo de SLA (que consulta feriados na internet) é trocado pelo valor já gravado."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch(CALCULO, side_effect=lambda chamado: chamado.horas_consumidas)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.func = self.criar_funcionario(cargo='Gestor', nome='Gina Gestora', email='gina@exemplo.com')
        self.entrar(self.func)
        self.cliente = Empresa.objects.create(cnpj='03619767000191', razao_social='Cliente A', tipo=2)
        self.tecnico = Tecnico.objects.create(empresa=self.cliente, nome='Téc')
        self.equip = Equipamento.objects.create(pn='PN-BI', modelo='ProBook', tipo='Notebook', marca='HP')
        self._n = 0

    def dados(self, caminho, **params):
        r = self.client.get(f'/api/bi/{caminho}/', params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['dados']

    def kpis(self, **params):
        return {k['chave']: k for k in self.dados('executivo', **params)['kpis']}

    def chamado(self, horas, ticket=None, metropolitana=True, status='andamento', dias_aberto=1, uf='SP', analista=None, concluido_ha=None):
        self._n += 1
        return ChamadoRFB.objects.create(
            ticket=ticket or f'T{self._n}', data_abertura=timezone.now() - timedelta(days=dias_aberto), estado=uf, cidade='Cidade',
            is_metropolitana=metropolitana, descricao_defeito='x', modelo_equipamento='ProBook', sn=f'S{self._n}',
            horas_consumidas=horas, status=status, analista_responsavel=analista,
            data_conclusao=timezone.now() - timedelta(days=concluido_ha) if concluido_ha is not None else None,
        )

    def triagem(self, sn=None, status=1, dias=1, defeito=None, troca=None, uf='SP', equip=None):
        self._n += 1
        return Triagem.objects.create(
            n_ticket=self._n, nf=1, cidade='Cidade', estado=uf, tecnico=self.tecnico, cliente=self.cliente,
            equipamento=equip or self.equip, analista_chamado=self.func, analista_triagem=self.func,
            sn=sn or f'SN{self._n}', status=status, defeito_constatado=defeito, troca=troca,
            criado_em=timezone.now() - timedelta(days=dias) if dias is not None else None,
        )

    def laudo(self, status='emitido', base='100', qtd=1, dias=1, cliente='Cliente A', uf='SP', validade_em=10, pn='PN1'):
        self._n += 1
        hoje = timezone.localdate()
        orc = Orcamento.objects.create(
            numero=f'T-{self._n}', status=status, cliente_nome=cliente, cliente_uf=uf, equip_modelo='ProBook',
            data_emissao=hoje - timedelta(days=dias), validade_ate=hoje + timedelta(days=validade_em), analista=self.func,
            equipamento=self.equip,
        )
        ItemOrcamento.objects.create(orcamento=orc, nome='Peça', part_number=pn, quantidade=qtd, valor_base=Decimal(base),
                                     valor_unitario=Decimal(base) * Decimal('1.3'), adicional=Decimal('0'))
        return orc


class FiltrosEAcessoTests(BIBase):
    def test_exige_login(self):
        self.client.get('/logout/')
        self.assertEqual(self.client.get('/api/bi/executivo/').status_code, 401)

    def test_periodo_invalido_e_recusado(self):
        for params in ({'inicio': '2026-10-10', 'fim': '2026-10-01'}, {'inicio': 'ontem'}, {'inicio': '2020-01-01', 'fim': '2026-01-01'}):
            self.assertEqual(self.client.get('/api/bi/executivo/', params).status_code, 400, params)

    def test_lista_de_opcoes_dos_filtros(self):
        self.chamado(10, uf='MG')
        self.triagem(uf='SP')
        d = self.dados('filtros')
        self.assertEqual(d['ufs'], ['MG', 'SP'])
        self.assertTrue(any(a['nome'] == 'Gina Gestora' for a in d['analistas']))
        self.assertEqual(d['modelos'][0]['modelo'], 'ProBook')
        self.assertEqual(d['clientes'][0]['cliente__razao_social'], 'Cliente A')

    def test_filtro_de_periodo_conta_so_as_triagens_datadas_dentro_dele(self):
        self.triagem(dias=1)
        self.triagem(dias=60)
        self.triagem(dias=None)                      # histórico, sem data
        self.assertEqual(self.kpis()['triagens']['atual'], 1)
        self.assertEqual(self.kpis(historico='1')['triagens']['atual'], 2)
        self.assertEqual(self.dados('executivo')['historico_sem_data'], 1)

    def test_comparacao_com_o_periodo_anterior(self):
        self.triagem(dias=1)
        self.triagem(dias=2)
        self.triagem(dias=35)                         # cai no período anterior (30 dias antes)
        k = self.kpis()['triagens']
        self.assertEqual((k['atual'], k['anterior'], k['variacao_pct'], k['tendencia']), (2.0, 1.0, 100.0, 'up'))

    def test_comparar_com_o_mesmo_periodo_do_ano_anterior(self):
        periodo = {'inicio': '2026-01-01', 'fim': '2026-06-30'}
        recente, ano_passado = self.triagem(dias=1), self.triagem(dias=1)
        Triagem.objects.filter(pk=recente.pk).update(criado_em=timezone.make_aware(datetime(2026, 3, 10, 12, 0)))
        Triagem.objects.filter(pk=ano_passado.pk).update(criado_em=timezone.make_aware(datetime(2025, 3, 10, 12, 0)))

        d = self.dados('executivo', comparar='ano', **periodo)
        self.assertEqual((d['periodo']['anterior_inicio'], d['periodo']['anterior_fim'], d['periodo']['comparar']), ('2025-01-01', '2025-06-30', 'ano'))
        k = {x['chave']: x for x in d['kpis']}['triagens']
        self.assertEqual((k['atual'], k['anterior']), (1.0, 1.0))

        padrao = self.dados('executivo', **periodo)
        self.assertEqual((padrao['periodo']['anterior_fim'], padrao['periodo']['comparar']), ('2025-12-31', 'anterior'))   # período imediatamente anterior
        k = {x['chave']: x for x in padrao['kpis']}['triagens']
        self.assertEqual(k['anterior'], 0.0)                 # a triagem de 2025-03 fica fora do "período anterior"

    def test_comparativo_de_ano_bissexto(self):
        d = self.dados('executivo', comparar='ano', inicio='2028-02-01', fim='2028-02-29')['periodo']
        self.assertEqual((d['anterior_inicio'], d['anterior_fim']), ('2027-02-01', '2027-02-28'))

    def test_periodo_anual_e_aceito(self):
        d = self.dados('executivo', inicio='2025-10-16', fim='2026-10-15')['periodo']
        self.assertEqual(d['dias'], 365)

    def test_pagina_do_dashboard_abre_com_o_painel(self):
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('id="painel-bi"', html)
        self.assertIn('echarts', html)


class IndicadoresExecutivosTests(BIBase):
    def test_kpis_comerciais(self):
        self.laudo('aprovado', qtd=2)                 # valor 260, custo 200
        self.laudo('recusado')                        # valor 130, custo 100
        self.laudo('emitido')                         # valor 130, custo 100
        self.laudo('rascunho')                        # não conta
        k = self.kpis()
        self.assertEqual(k['valor_aprovado']['atual'], 260.0)
        self.assertEqual(k['taxa_aprovacao']['atual'], 50.0)
        self.assertEqual(k['ticket_medio']['atual'], 173.33)
        self.assertEqual(k['margem']['atual'], 23.1)

    def test_margem_ignora_laudos_de_valor_cheio(self):
        self.laudo('emitido')                               # valor 130, custo 100 -> 23,1%
        cheio = self.laudo('emitido', base='1000')          # valor 1.300
        Orcamento.objects.filter(pk=cheio.pk).update(aplicar_regra=False)
        k = self.kpis()
        self.assertEqual(k['margem']['atual'], 23.1)         # só o laudo com a regra entra na margem
        self.assertEqual(k['ticket_medio']['atual'], 715.0)  # mas os dois contam no ticket médio

    def test_sla_dos_concluidos_e_tempo_medio_de_resolucao(self):
        self.chamado(50, status='concluido', concluido_ha=2)                          # 50 h <= 72: dentro
        self.chamado(100, status='concluido', concluido_ha=2)                         # 100 h > 72: fora
        self.chamado(100, status='concluido', concluido_ha=2, metropolitana=False)    # 100 h <= 120: dentro
        k = self.kpis()
        self.assertEqual((k['sla']['atual'], k['sla']['n'], k['sla']['meta']), (66.7, 3, 95.0))
        self.assertEqual(k['mttr']['atual'], 83.3)
        self.assertTrue(k['mttr']['menor_melhor'])

    def test_variacao_boa_ou_ruim_depende_do_indicador(self):
        for _ in range(3):
            self.chamado(10)                           # backlog atual = 3
        SnapshotSLA.objects.create(data=timezone.localdate() - timedelta(days=40), ativos=1)
        backlog = self.kpis()['backlog']
        self.assertEqual((backlog['atual'], backlog['anterior']), (3.0, 1.0))
        self.assertFalse(backlog['bom'])               # backlog subiu: ruim (menor é melhor)


class OperacaoTests(BIBase):
    def setUp(self):
        super().setUp()
        for ticket, horas in (('A', 30), ('B', 50), ('C', 60), ('D', 80)):        # 41,7% / 69,4% / 83,3% / 111,1% do limite de 72 h
            self.chamado(horas, ticket=ticket)

    def test_faixas_de_sla_e_chamados_criticos(self):
        d = self.dados('operacao')
        self.assertEqual(d['total_ativos'], 4)
        self.assertEqual(d['faixas'], {'ate_60': 1, 'faixa_60_80': 1, 'faixa_80_100': 1, 'acima_100': 1})
        self.assertEqual([c['ticket'] for c in d['criticos']], ['D', 'C', 'B'])
        self.assertEqual(d['criticos'][0]['pct'], 111.1)
        self.assertEqual(d['aging']['24_48h'], 4)

    def test_retrato_diario_e_gravado_uma_vez_por_dia(self):
        self.dados('operacao')
        self.dados('operacao', uf='SP')
        s = SnapshotSLA.objects.get()
        self.assertEqual((s.data, s.ativos, s.ate_60, s.acima_100), (timezone.localdate(), 4, 1, 1))
        self.assertEqual(s.por_uf['SP'], {'ativos': 4, 'estourados': 1})

    def test_filtros_de_uf_e_analista(self):
        self.chamado(10, ticket='MG1', uf='MG', analista=self.func)
        self.assertEqual(self.dados('operacao', uf='MG')['total_ativos'], 1)
        self.assertEqual(self.dados('operacao', analista=self.func.id_funcionario)['total_ativos'], 1)
        self.assertEqual(self.dados('operacao')['total_ativos'], 5)

    def test_vazao_semanal_e_agendamentos(self):
        c = self.chamado(10, ticket='V1', status='concluido', dias_aberto=3, concluido_ha=1)
        agora = timezone.now()
        AgendamentoChamado.objects.create(chamado=c, status='realizado', data_registro_pausa=agora)
        AgendamentoChamado.objects.create(chamado=c, status='frustrado', data_registro_pausa=agora)
        AgendamentoChamado.objects.create(chamado=c, status='frustrado', tipo_pausa='sem_resposta', data_registro_pausa=agora)
        d = self.dados('operacao')
        self.assertTrue(sum(s['abertos'] for s in d['vazao']) >= 5)
        self.assertTrue(sum(s['concluidos'] for s in d['vazao']) >= 1)
        self.assertEqual(d['agendamentos']['taxa_frustrados'], 66.7)
        self.assertEqual(d['agendamentos']['sem_resposta'], 1)


class QualidadeTests(BIBase):
    def test_pareto_agrupa_variacoes_do_texto_e_fecha_em_100(self):
        self.triagem(status=2, defeito='Tela quebrada')
        self.triagem(status=2, defeito='tela  QUEBRADA!')
        self.triagem(status=2, defeito='Bateria')
        self.triagem(status=2, defeito=None)
        p = self.dados('qualidade')['pareto']
        self.assertEqual((p[0]['nome'], p[0]['qtd']), ('Tela quebrada', 2))
        self.assertEqual(p[-1]['acumulado'], 100.0)

    def test_taxa_de_defeito_por_modelo_e_aviso_de_poucos_dados(self):
        for _ in range(3):
            self.triagem(status=2)
        self.triagem(status=1)
        d = self.dados('qualidade')
        self.assertEqual((d['total'], d['defeitos']), (4, 3))
        self.assertEqual(d['por_modelo'][0]['taxa'], 75.0)
        self.assertTrue(d['por_modelo'][0]['poucos_dados'])

    def test_reincidencia_por_numero_de_serie(self):
        self.triagem(sn='REP1', dias=40)
        self.triagem(sn='REP1', dias=2)
        self.triagem(sn='UNICO')
        r = self.dados('qualidade')['reincidencia']
        self.assertEqual((r['total'], r['lista'][0]['sn'], r['lista'][0]['n']), (1, 'REP1', 2))

    def test_pecas_trocadas_por_modelo(self):
        self.triagem(troca='Tela'); self.triagem(troca='tela'); self.triagem(troca='Bateria')
        pecas = self.dados('qualidade')['pecas_trocadas']
        self.assertEqual((pecas[0]['peca'], pecas[0]['qtd'], pecas[0]['modelo']), ('Tela', 2, 'ProBook'))


class ComercialTests(BIBase):
    def test_funil_e_valores(self):
        self.triagem(); self.triagem()
        self.laudo('aprovado'); self.laudo('emitido'); self.laudo('rascunho'); self.laudo('cancelado')
        d = self.dados('comercial')
        self.assertEqual({e['etapa']: e['valor'] for e in d['funil']},
                         {'Triagens': 2, 'Laudos criados': 3, 'Laudos emitidos': 2, 'Aprovados': 1})
        self.assertEqual(d['pipeline'], {'qtd': 1, 'valor': 130.0})
        self.assertEqual(d['top_clientes'][0]['nome'], 'Cliente A')

    def test_laudos_a_vencer_em_ate_3_dias(self):
        self.laudo('emitido', validade_em=2)
        self.laudo('emitido', validade_em=10)
        self.laudo('aprovado', validade_em=1)       # já decidido: não conta
        a_vencer = self.dados('comercial')['a_vencer']
        self.assertEqual(len(a_vencer), 1)
        self.assertEqual(a_vencer[0]['valor'], 130.0)

    def test_tempo_ate_a_decisao_vem_do_historico_de_status(self):
        orc = self.laudo('aprovado')
        agora = timezone.now()
        for para, ha in (('Emitido', 5), ('Aprovado', 3)):
            h = OrcamentoHistorico.objects.create(orcamento=orc, motivo='Mudança de status',
                                                  alteracoes=[{'campo': 'Status', 'de': 'x', 'para': para}])
            OrcamentoHistorico.objects.filter(pk=h.pk).update(criado_em=agora - timedelta(days=ha))
        self.assertEqual(self.dados('comercial')['tempo_decisao'], {'media_dias': 2.0, 'n': 1})


class PecasTests(BIBase):
    def setUp(self):
        super().setUp()
        self.fornecedor = Empresa.objects.create(cnpj='11222333000181', razao_social='Fornecedor X', tipo=3)

    def peca(self, pn, **cotacoes):
        peca = Peca.objects.create(part_number=pn, descricao=f'Peça {pn}')
        self.equip.pecas.add(peca)
        return peca

    def cotar(self, peca, valor, dias):
        return CotacaoPeca.objects.create(peca=peca, fornecedor=self.fornecedor, valor=Decimal(valor),
                                          data_cotacao=timezone.localdate() - timedelta(days=dias))

    def test_cotacoes_velhas_e_pecas_sem_cotacao(self):
        self.cotar(self.peca('VELHA'), '50', 60)
        self.peca('SEMCOT')
        self.cotar(self.peca('NOVA'), '70', 2)
        d = self.dados('pecas')
        self.assertEqual([c['pn'] for c in d['cotacoes_velhas']], ['VELHA'])
        self.assertGreaterEqual(d['cotacoes_velhas'][0]['dias'], 60)
        self.assertEqual([p['part_number'] for p in d['sem_cotacao']], ['SEMCOT'])

    def test_variacao_de_preco_e_melhor_fornecedor(self):
        peca = self.peca('VAR')
        self.cotar(peca, '100', 10)
        self.cotar(peca, '120', 1)
        self.laudo('emitido', pn='VAR')
        d = self.dados('pecas')
        self.assertEqual((d['variacoes'][0]['pn'], d['variacoes'][0]['variacao_pct']), ('VAR', 20.0))
        self.assertEqual(d['top_orcadas'][0]['pn'], 'VAR')
        self.assertEqual((d['melhor_fornecedor'][0]['fornecedor'], d['melhor_fornecedor'][0]['valor']), ('Fornecedor X', 120.0))

    def test_itens_de_laudo_sem_cotacao_sao_contados(self):
        orc = self.laudo('emitido', pn='SC')
        ItemOrcamento.objects.filter(orcamento=orc).update(peca=self.peca('SC'))
        self.assertEqual(self.dados('pecas')['itens_sem_cotacao_em_laudos'], 1)


class InsightsEAlertasTests(BIBase):
    def test_insight_de_sla_nao_se_repete_no_mesmo_dia_e_pode_ser_marcado_como_lido(self):
        self.chamado(100, ticket='X1')                     # 138% do limite: estourado
        call_command('atualizar_bi')
        call_command('atualizar_bi')
        insights = Insight.objects.filter(tipo='sla')
        self.assertEqual(insights.count(), 1)
        self.assertEqual(insights.get().severidade, 'critico')

        lista = self.client.get('/api/bi/insights/', {'nao_lidos': 1}).json()['dados']
        self.assertEqual(len(lista), 1)
        r = self.post_json(f"/api/bi/insights/{lista[0]['id']}/lido/", {'lido': True})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get('/api/bi/insights/', {'nao_lidos': 1}).json()['dados'], [])

    def test_insight_de_laudo_a_vencer(self):
        self.laudo('emitido', validade_em=1)
        BIService.gerar_insights()
        self.assertTrue(Insight.objects.filter(tipo='laudo_vencendo').exists())

    def test_atualizar_agora_so_para_gestao(self):
        self.assertEqual(self.post_json('/api/bi/atualizar/').status_code, 200)
        self.client.get('/logout/')
        self.entrar(self.criar_funcionario(cargo='Analista de Triagem', login=71))
        self.assertEqual(self.post_json('/api/bi/atualizar/').status_code, 403)

    @override_settings(EMAIL_ENABLED=False)
    def test_sem_configuracao_de_email_nada_e_enviado(self):
        self.chamado(100, analista=self.func)
        resultado = BIService.enviar_alertas_sla()
        self.assertTrue(resultado['ignorado'])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AlertaSLAEnviado.objects.exists())

    @override_settings(EMAIL_ENABLED=True, SITE_URL='https://exemplo.com')
    def test_email_de_sla_agrupa_por_analista_e_nao_repete(self):
        a = self.chamado(47, ticket='A60', analista=self.func)     # 65,3%: faixa 60
        self.chamado(61.2, ticket='B80', analista=self.func)       # 85%: faixa 80
        self.chamado(10, ticket='OK', analista=self.func)          # abaixo de 60%: não avisa

        resultado = BIService.enviar_alertas_sla()
        self.assertEqual((resultado['enviados'], resultado['chamados']), (1, 2))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['gina@exemplo.com'])
        self.assertIn('A60', mail.outbox[0].body)
        self.assertIn('https://exemplo.com/gerenciar-chamados-rfb/', mail.outbox[0].body)
        self.assertEqual(AlertaSLAEnviado.objects.count(), 2)

        BIService.enviar_alertas_sla()                              # nada novo
        self.assertEqual(len(mail.outbox), 1)

        ChamadoRFB.objects.filter(pk=a.pk).update(horas_consumidas=79.2)   # 110%: cruzou a faixa 100
        BIService.enviar_alertas_sla()
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('A60', mail.outbox[1].body)
        self.assertNotIn('B80', mail.outbox[1].body)

    @override_settings(EMAIL_ENABLED=True)
    def test_analista_sem_email_nao_recebe(self):
        sem_email = self.criar_funcionario(cargo='Funcionário', login=72, email='')
        self.chamado(100, analista=sem_email)
        self.assertEqual(BIService.enviar_alertas_sla()['enviados'], 0)


class NFFeCartaDeControleTests(BIBase):
    """NFF (peça trocada que a bancada achou funcional), carta de controle por técnico e diagnósticos contrariados."""

    def tecnico_novo(self, nome):
        return Tecnico.objects.create(empresa=self.cliente, nome=nome)

    def triagem_de(self, tecnico, status, diag=None, const=None):
        t = self.triagem(status=status)
        Triagem.objects.filter(pk=t.pk).update(tecnico=tecnico, defeito_tecnico=diag, defeito_constatado=const)
        return t

    def qualidade(self):
        return self.dados('qualidade')

    def test_nff_da_taxa_e_intervalo(self):
        for _ in range(3):
            self.triagem(status=1)
        for _ in range(7):
            self.triagem(status=2)
        nff = self.qualidade()['nff']
        self.assertEqual(nff['funcionais'], 3)
        self.assertEqual(nff['taxa']['atual'], 30.0)
        self.assertAlmostEqual(nff['ic_inf'], 10.8, places=1)
        self.assertAlmostEqual(nff['ic_sup'], 60.3, places=1)
        self.assertEqual(nff['referencia'], [20.0, 50.0])

    def test_sem_triagens_nao_quebra(self):
        d = self.qualidade()
        self.assertIsNone(d['nff']['ic_inf'])
        self.assertEqual(d['controle_tecnicos'], [])
        self.assertEqual(d['funil']['pontos'], [])
        self.assertEqual(d['diagnosticos']['itens'], [])

    def test_tecnico_com_nff_muito_acima_da_media_fica_critico(self):
        ruim, bom = self.tecnico_novo('Ruim'), self.tecnico_novo('Bom')
        for _ in range(10):
            self.triagem_de(ruim, status=1)            # 100% de NFF
        for _ in range(40):
            self.triagem_de(bom, status=2)             # 0% de NFF
        por_nome = {t['nome']: t for t in self.qualidade()['controle_tecnicos']}
        self.assertEqual(por_nome['Ruim']['status'], 'critico')
        self.assertEqual(por_nome['Bom']['status'], 'destaque')
        self.assertEqual(por_nome['Ruim']['taxa_nff'], 100.0)

    def test_tecnico_com_poucas_triagens_nao_e_classificado(self):
        novo = self.tecnico_novo('Novato')
        for _ in range(3):
            self.triagem_de(novo, status=1)
        for _ in range(20):
            self.triagem_de(self.tecnico, status=2)
        d = self.qualidade()
        por_nome = {t['nome']: t for t in d['controle_tecnicos']}
        self.assertEqual(por_nome['Novato']['status'], 'insuficiente')
        self.assertNotIn('Novato', [p['nome'] for p in d['funil']['pontos']])   # fora do funnel plot

    def test_funil_tem_limites_quando_ha_tecnico_com_volume(self):
        for _ in range(12):
            self.triagem(status=1)
        for _ in range(12):
            self.triagem(status=2)
        funil = self.qualidade()['funil']
        self.assertEqual(funil['p_medio'], 50.0)
        self.assertGreater(len(funil['limites']), 1)
        self.assertEqual(len(funil['pontos']), 1)

    def test_diagnosticos_contrariados(self):
        self.triagem_de(self.tecnico, 2, diag='Placa-mãe', const='Memória')
        self.triagem_de(self.tecnico, 2, diag='placa mae', const='memoria')    # mesma divergência, grafia diferente
        self.triagem_de(self.tecnico, 2, diag='Tela quebrada', const='TELA  quebrada!')   # igual: não conta
        self.triagem_de(self.tecnico, 1, diag='Bateria', const=None)           # sem constatado: não comparável
        dg = self.qualidade()['diagnosticos']
        self.assertEqual(dg['comparaveis'], 3)
        self.assertEqual(dg['divergentes'], 2)
        self.assertEqual(len(dg['itens']), 1)
        self.assertEqual(dg['itens'][0]['qtd'], 2)
        self.assertEqual(dg['itens'][0]['pct'], 100.0)
        self.assertEqual(self.qualidade()['controle_tecnicos'][0]['divergencias'], 2)

    def test_ranking_de_pecas_agrupa_pelo_part_number_quando_ha_vinculo(self):
        peca = Peca.objects.create(part_number='L1', descricao='Tela')
        self.equip.pecas.add(peca)
        for texto in ('L1 - Tela', 'L1 - Tela'):
            t = self.triagem(status=2, troca=texto)
            Triagem.objects.filter(pk=t.pk).update(peca_trocada=peca)
        self.triagem(status=2, troca='tela')                                    # texto livre antigo: grupo à parte
        itens = {p['peca']: p['qtd'] for p in self.qualidade()['pecas_trocadas']}
        self.assertEqual(itens['L1 - Tela'], 2)
        self.assertEqual(itens['tela'], 1)


class FiltroPorTecnicoTests(BIBase):
    def test_filtro_restringe_as_triagens_ao_tecnico(self):
        outro = Tecnico.objects.create(empresa=self.cliente, nome='Outro Técnico')
        for _ in range(3):
            self.triagem(status=2)
        for _ in range(2):
            t = self.triagem(status=2)
            Triagem.objects.filter(pk=t.pk).update(tecnico=outro)
        self.assertEqual(self.dados('qualidade')['total'], 5)
        r = self.client.get('/api/bi/qualidade/', {'tecnico': outro.id_tecnico})
        self.assertEqual(r.json()['dados']['total'], 2)

    def test_opcoes_de_filtro_listam_so_tecnicos_com_triagem(self):
        sem_triagem = Tecnico.objects.create(empresa=self.cliente, nome='Sem triagem')
        self.triagem(status=2)
        nomes = [t['nome'] for t in self.client.get('/api/bi/filtros/').json()['dados']['tecnicos']]
        self.assertIn(self.tecnico.nome, nomes)
        self.assertNotIn(sem_triagem.nome, nomes)
