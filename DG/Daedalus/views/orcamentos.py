from django.http import HttpResponse, JsonResponse
from django.views import View

from ..models import Orcamento, Triagem
from ..services import OrcamentoService
from ..services.laudo_docx import content_disposition, gerar_laudo_docx, nome_de_arquivo_seguro
from ..services.laudo_email import LaudoEmailService
from .utils import erro_interno, ler_json, resposta_erro

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class OrcamentosView(View):
    """
    GET  ?q=&status=&de=&ate=&page=  -> pesquisa de laudos/orçamentos
    POST                             -> cria (sem "id") ou edita um rascunho (com "id")
    """
    def get(self, request):
        try:
            resultado = OrcamentoService.pesquisar(
                q=request.GET.get('q', ''),
                status=request.GET.get('status', 'todos'),
                de=request.GET.get('de', ''),
                ate=request.GET.get('ate', ''),
                pagina=int(request.GET.get('page', 1)),
            )
            return JsonResponse({'status': 'sucesso', **resultado})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            dado = OrcamentoService.salvar(ler_json(request), request.session.get('funcionario_id'),
                                           getattr(request, 'funcionario_cargo', ''))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Laudo salvo com sucesso!', 'dado': dado})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentosPendentesView(View):
    """GET: laudos emitidos com a validade vencida que ainda esperam a resposta do cliente (aprovado ou não)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', **OrcamentoService.pendentes_decisao()})
        except Exception as e:
            return erro_interno(e)


class OrcamentoDetalheView(View):
    def get(self, request, id_orcamento):
        try:
            return JsonResponse({'status': 'sucesso', 'dado': OrcamentoService.obter(id_orcamento)})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except Exception as e:
            return erro_interno(e)

    def delete(self, request, id_orcamento):
        try:
            OrcamentoService.excluir_rascunho(id_orcamento)
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Rascunho excluído.'})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentoStatusView(View):
    """POST {"status": "emitido|aprovado|recusado|cancelado"}"""
    def post(self, request, id_orcamento):
        try:
            corpo = ler_json(request)
            novo = (corpo.get('status') or '').strip()
            dado = OrcamentoService.alterar_status(id_orcamento, novo, request.session.get('funcionario_id'), corpo.get('motivo_recusa') or '')
            return JsonResponse({'status': 'sucesso', 'mensagem': f"Status alterado para {dado['status_nome']}.", 'dado': dado})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentoDocxView(View):
    """GET: baixa o laudo/orçamento preenchido no modelo Word."""
    def get(self, request, id_orcamento):
        try:
            orc = Orcamento.objects.prefetch_related('itens').get(pk=id_orcamento)
            arquivo, nome = gerar_laudo_docx(orc)
            # O usuário pode escolher o nome do arquivo (?nome=...). Só letras, números e _-. são aceitos.
            escolhido = nome_de_arquivo_seguro(request.GET.get('nome', ''))
            if escolhido:
                nome = escolhido + '.docx'
            resposta = HttpResponse(arquivo.getvalue(), content_type=DOCX_MIME)
            resposta['Content-Disposition'] = content_disposition(nome)
            return resposta
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except FileNotFoundError as fe:
            return resposta_erro(str(fe), 500)
        except Exception as e:
            return erro_interno(e)


class OrcamentoEmailView(View):
    """POST {destinatario?, mensagem?}: envia o laudo em Word por e-mail (o destinatário padrão é o e-mail do cliente do laudo)."""
    def post(self, request, id_orcamento):
        try:
            corpo = ler_json(request)
            r = LaudoEmailService.enviar(id_orcamento, corpo.get('destinatario'), corpo.get('mensagem'), request.session.get('funcionario_id'))
            return JsonResponse({'status': 'sucesso', 'mensagem': f"Laudo enviado para {r['destinatario']}."})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentoPrePreenchimentoView(View):
    """GET ?ticket=123 -> dados da triagem para começar o laudo."""
    def get(self, request):
        try:
            dado = OrcamentoService.pre_preencher_por_ticket(request.GET.get('ticket'))
            return JsonResponse({'status': 'sucesso', 'dado': dado})
        except Triagem.DoesNotExist as de:
            return resposta_erro(str(de), 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentoEstatisticasView(View):
    def get(self, request):
        try:
            dados = OrcamentoService.estatisticas(request.GET.get('de', ''), request.GET.get('ate', ''))
            return JsonResponse({'status': 'sucesso', 'dado': dados})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class OrcamentoHistoricoView(View):
    """GET: histórico de alterações e mudanças de status do laudo."""
    def get(self, request, id_orcamento):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': OrcamentoService.historico(id_orcamento)})
        except Orcamento.DoesNotExist:
            return resposta_erro('Orçamento não encontrado.', 404)
        except Exception as e:
            return erro_interno(e)
