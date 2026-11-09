from django.core.cache import cache
from django.http import JsonResponse
from django.views import View

from ..models import Insight, Peca
from ..services.bi import BIService, Filtros
from .utils import erro_interno, ler_json, resposta_erro

CACHE_SEGUNDOS = 60


class _BIBase(View):
    """GET com os filtros comuns do dashboard (período, UF, analista, modelo, cliente). Cache curto por filtro."""
    calcular = None

    def get(self, request):
        try:
            chave = f"bi:{self.__class__.__name__}:{request.GET.urlencode()}"
            dados = cache.get(chave)
            if dados is None:
                dados = type(self).calcular(Filtros(request.GET))
                cache.set(chave, dados, CACHE_SEGUNDOS)
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class BIExecutivoView(_BIBase):
    calcular = staticmethod(BIService.executivo)


class BIOperacaoView(_BIBase):
    calcular = staticmethod(BIService.operacao)


class BIChamadosAnalistaView(View):
    """GET ?id_analista=&situacao=(ativos|atendidos|cancelados|todos) + filtros do dashboard: lista os chamados de um analista."""
    def get(self, request):
        try:
            id_analista = int(request.GET.get('id_analista') or 0)
            dados = BIService.chamados_do_analista(Filtros(request.GET), id_analista, request.GET.get('situacao') or 'todos')
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class BIPecaRegioesView(View):
    """GET ?id_peca= (ou ?pn=) + filtros do dashboard: em que regiões uma peça foi usada no período."""
    def get(self, request):
        try:
            id_peca = int(request.GET.get('id_peca') or 0)
            pn = ' '.join((request.GET.get('pn') or '').split())
            if not id_peca and pn:
                peca = Peca.objects.filter(part_number__iexact=pn).first()
                if peca is None:
                    return resposta_erro(f'Nenhuma peça cadastrada com o PN {pn}.', 404)
                id_peca = peca.id_peca
            if not id_peca:
                return resposta_erro('Informe o PN da peça.', 400)
            return JsonResponse({'status': 'sucesso', 'dados': BIService.regioes_da_peca(Filtros(request.GET), id_peca)})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except ValueError:
            return resposta_erro('Peça inválida.', 400)
        except Exception as e:
            return erro_interno(e)


class BIQualidadeView(_BIBase):
    calcular = staticmethod(BIService.qualidade)


class BIComercialView(_BIBase):
    calcular = staticmethod(BIService.comercial)


class BIPecasView(_BIBase):
    calcular = staticmethod(BIService.pecas)


class BIFiltrosView(View):
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': BIService.opcoes_filtros()})
        except Exception as e:
            return erro_interno(e)


class BIInsightsView(View):
    def get(self, request):
        try:
            nao_lidos = request.GET.get('nao_lidos') == '1'
            return JsonResponse({'status': 'sucesso', 'dados': BIService.listar_insights(apenas_nao_lidos=nao_lidos)})
        except Exception as e:
            return erro_interno(e)


class BIInsightLidoView(View):
    """POST {"lido": true|false}"""
    def post(self, request, id_insight):
        try:
            BIService.marcar_insight(id_insight, bool(ler_json(request).get('lido', True)))
            return JsonResponse({'status': 'sucesso'})
        except Insight.DoesNotExist:
            return resposta_erro('Insight não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class BIAtualizarView(View):
    """POST: recalcula SLA, retrato do dia e insights agora (Gestor/Administrador)."""
    def post(self, request):
        try:
            BIService.atualizar_se_necessario(forcar=True)
            cache.clear()   # as respostas em cache ficam velhas depois de atualizar
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Indicadores atualizados.'})
        except Exception as e:
            return erro_interno(e)
