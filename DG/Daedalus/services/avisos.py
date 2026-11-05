"""Central de avisos (sino do cabeçalho) e busca global."""
from django.db.models import Q

from ..models import ChamadoRFB, Insight, Orcamento, SaidaPecas, SnapshotSLA, SolicitacaoSenha, Triagem
from .alertas_rfb import AlertasRFBService
from .estoque import EstoqueService
from .orcamento import OrcamentoService

CARGOS_GESTAO = {'Administrador', 'Gestor'}


class AvisosService:
    @staticmethod
    def listar(cargo: str) -> dict:
        itens = []

        if cargo in CARGOS_GESTAO:
            n = SolicitacaoSenha.objects.filter(atendida=False).count()
            if n:
                itens.append({'tipo': 'senha', 'nivel': 'atencao', 'quantidade': n, 'url': '/gerenciar-funcionario/',
                              'texto': f"{n} pedido(s) de redefinição de senha esperando atendimento"})

        n = OrcamentoService.pendentes_decisao()['total']
        if n:
            itens.append({'tipo': 'orcamento', 'nivel': 'atencao', 'quantidade': n, 'url': '/orcamentos/pesquisa/',
                          'texto': f"{n} orçamento(s) com a validade vencida aguardando a resposta do cliente"})

        n = len(AlertasRFBService.nao_agendados_acima_do_limiar())
        if n:
            itens.append({'tipo': 'rfb_agendamento', 'nivel': 'atencao', 'quantidade': n, 'url': '/gerenciar-chamados-rfb/',
                          'texto': f"{n} chamado(s) RFB sem agendamento com {AlertasRFBService.limiar():.0f}% ou mais do SLA consumido"})

        n = EstoqueService.abaixo_do_minimo()
        if n:
            itens.append({'tipo': 'estoque', 'nivel': 'atencao', 'quantidade': n, 'url': '/estoque/?situacao=abaixo',
                          'texto': f"{n} peça(s) abaixo do estoque mínimo"})

        n = SaidaPecas.objects.filter(status='enviada').count()
        if n:
            itens.append({'tipo': 'saidas', 'nivel': 'info', 'quantidade': n, 'url': '/saidas/?status=enviada',
                          'texto': f"{n} saída(s) de peças enviada(s) ao fiscal aguardando o número da nota"})

        # Último retrato do SLA (atualizado pelo painel de BI), sem recalcular nada aqui.
        snap = SnapshotSLA.objects.order_by('-data').first()
        if snap and snap.acima_100:
            itens.append({'tipo': 'sla', 'nivel': 'critico', 'quantidade': snap.acima_100, 'url': '/gerenciar-chamados-rfb/',
                          'texto': f"{snap.acima_100} chamado(s) RFB com o SLA estourado"})
        if snap and snap.faixa_80_100:
            itens.append({'tipo': 'sla', 'nivel': 'atencao', 'quantidade': snap.faixa_80_100, 'url': '/gerenciar-chamados-rfb/',
                          'texto': f"{snap.faixa_80_100} chamado(s) RFB perto de estourar o SLA (80% a 100%)"})

        n = Insight.objects.filter(lido=False, severidade='critico').count()
        if n:
            itens.append({'tipo': 'insight', 'nivel': 'critico', 'quantidade': n, 'url': '/dashboard/?aba=insights',
                          'texto': f"{n} alerta(s) crítico(s) do dashboard sem leitura"})

        ordem = {'critico': 0, 'atencao': 1, 'info': 2}
        itens.sort(key=lambda i: ordem.get(i['nivel'], 3))
        return {'itens': itens, 'total': sum(i['quantidade'] for i in itens)}


class BuscaService:
    LIMITE = 5

    @staticmethod
    def buscar(termo: str) -> list:
        termo = (termo or '').strip()
        if len(termo) < 2:
            return []
        resultados = []

        # Existe algum registro com esse número de série? Então oferece a linha do tempo completa.
        if (Triagem.objects.filter(sn__iexact=termo).exists() or Orcamento.objects.filter(equip_sn__iexact=termo).exists()
                or ChamadoRFB.objects.filter(sn__iexact=termo).exists()):
            resultados.append({'tipo': 'serie', 'titulo': f"Linha do tempo do número de série {termo}",
                               'detalhe': 'Triagens, laudos e chamados RFB do mesmo equipamento', 'url': f"/serie/?sn={termo}"})

        filtro_triagem = Q(sn__icontains=termo) | Q(cliente__razao_social__icontains=termo)
        if termo.isdigit() and len(termo) <= 9:      # cabe no campo inteiro do banco
            filtro_triagem |= Q(n_ticket=int(termo)) | Q(nf=int(termo))
        for t in Triagem.objects.filter(filtro_triagem).select_related('equipamento', 'cliente').order_by('-criado_em', '-id_triagem')[:BuscaService.LIMITE]:
            resultados.append({'tipo': 'triagem', 'titulo': f"Triagem do ticket {t.n_ticket}",
                               'detalhe': f"{t.equipamento.modelo} · SN {t.sn} · {t.cliente.razao_social}", 'url': f"/visualizar/?id={t.id_triagem}"})

        filtro_orc = (Q(numero__icontains=termo) | Q(ticket__icontains=termo) | Q(equip_sn__icontains=termo)
                      | Q(cliente_nome__icontains=termo))
        for o in Orcamento.objects.filter(filtro_orc).order_by('-data_emissao', '-id_orcamento')[:BuscaService.LIMITE]:
            resultados.append({'tipo': 'orcamento', 'titulo': f"Laudo {o.numero} ({o.get_status_display()})",
                               'detalhe': f"{o.cliente_nome} · {o.equip_modelo}", 'url': f"/orcamentos/emissao/?id={o.id_orcamento}"})

        for c in ChamadoRFB.objects.filter(Q(ticket__icontains=termo) | Q(sn__icontains=termo)).order_by('-data_abertura')[:BuscaService.LIMITE]:
            resultados.append({'tipo': 'rfb', 'titulo': f"Chamado RFB {c.ticket} ({c.get_status_display()})",
                               'detalhe': f"{c.modelo_equipamento} · SN {c.sn}", 'url': '/gerenciar-chamados-rfb/'})
        return resultados
