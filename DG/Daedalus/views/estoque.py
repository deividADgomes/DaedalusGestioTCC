from django.http import JsonResponse
from django.views import View

from ..models import Peca
from ..services.estoque import EstoqueService
from .utils import erro_interno, ler_json, resposta_erro


class EstoqueView(View):
    """GET ?q=&situacao=(todos|abaixo|sem_saldo): peças controladas, com o resumo geral."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', **EstoqueService.listar(request.GET.get('q'), request.GET.get('situacao') or 'todos')})
        except Exception as e:
            return erro_interno(e)


class EstoqueCatalogoView(View):
    """GET ?q=: busca peças do catálogo (para uma nova entrada)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': EstoqueService.catalogo(request.GET.get('q'))})
        except Exception as e:
            return erro_interno(e)


class EstoqueMovimentarView(View):
    """POST {id_peca, tipo: entrada|saida|contagem, quantidade, custo?, motivo?}."""
    def post(self, request):
        try:
            d = ler_json(request)
            dado = EstoqueService.movimentar(
                int(d.get('id_peca') or 0), d.get('tipo'), d.get('quantidade'), d.get('custo'), d.get('motivo'),
                request.session.get('funcionario_id'))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Movimento registrado.', 'dado': dado})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class EstoqueConfigView(View):
    """POST {id_peca, minimo, local}: define o estoque mínimo e o local da peça."""
    def post(self, request):
        try:
            d = ler_json(request)
            dado = EstoqueService.configurar(int(d.get('id_peca') or 0), d.get('minimo'), d.get('local'))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Dados do estoque salvos.', 'dado': dado})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class EstoqueHistoricoView(View):
    """GET: movimentos de uma peça, do mais recente ao mais antigo."""
    def get(self, request, id_peca):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': EstoqueService.historico(id_peca)})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except Exception as e:
            return erro_interno(e)
