from django.http import HttpResponse, JsonResponse
from django.views import View

from ..models import SaidaPecas
from ..services.saidas import SaidaService
from .utils import erro_interno, ler_json, resposta_erro


def _nao_encontrada():
    return resposta_erro('Saída não encontrada.', 404)


class SaidasView(View):
    """GET ?status=&q=: lista de saídas. POST: grava (cria ou altera) o rascunho."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': SaidaService.listar(request.GET.get('status') or '', request.GET.get('q') or ''),
                                 'config': SaidaService.config()})
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            dado = SaidaService.salvar(ler_json(request), request.session.get('funcionario_id'))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Saída salva.', 'dado': dado})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SaidaDetalheView(View):
    def get(self, request, id_saida):
        try:
            return JsonResponse({'status': 'sucesso', 'dado': SaidaService.obter(id_saida)})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except Exception as e:
            return erro_interno(e)


class SaidaEnviarView(View):
    """POST {enviar_email?, destinatarios?, mensagem?}: envia a lista ao fiscal e dá a baixa dos itens que saem do estoque."""
    def post(self, request, id_saida):
        try:
            d = ler_json(request)
            dado = SaidaService.enviar(id_saida, request.session.get('funcionario_id'), bool(d.get('enviar_email')),
                                       d.get('destinatarios') or '', d.get('mensagem') or '')
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Saída enviada ao fiscal.', 'dado': dado})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SaidaNotaView(View):
    """POST {numero_nf}: a mesma nota para todas as linhas que ainda não têm NF."""
    def post(self, request, id_saida):
        try:
            d = ler_json(request)
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Nota registrada.', 'dado': SaidaService.registrar_nota(id_saida, d.get('numero_nf'))})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SaidaRetornoView(View):
    """POST {linhas: [{id, numero_nf?, rastreio?, observacao?}], nf_geral?}: NF e rastreio por linha, depois do envio ao fiscal."""
    def post(self, request, id_saida):
        try:
            d = ler_json(request)
            dado = SaidaService.registrar_retorno(id_saida, d.get('linhas') if isinstance(d.get('linhas'), list) else [], d.get('nf_geral') or '')
            return JsonResponse({'status': 'sucesso', 'mensagem': 'NF e rastreio salvos.', 'dado': dado})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SaidaCancelarView(View):
    """POST {motivo?}: cancela; se já foi enviada, as peças voltam ao estoque."""
    def post(self, request, id_saida):
        try:
            d = ler_json(request)
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Saída cancelada.', 'dado': SaidaService.cancelar(id_saida, d.get('motivo'), request.session.get('funcionario_id'))})
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SaidaCsvView(View):
    """GET: a lista em CSV (separador ponto e vírgula, abre direto no Excel)."""
    def get(self, request, id_saida):
        try:
            conteudo, nome = SaidaService.csv_da_saida(id_saida)
            resposta = HttpResponse(conteudo, content_type='text/csv; charset=utf-8')
            resposta['Content-Disposition'] = f'attachment; filename="{nome}"'
            return resposta
        except SaidaPecas.DoesNotExist:
            return _nao_encontrada()
        except Exception as e:
            return erro_interno(e)
