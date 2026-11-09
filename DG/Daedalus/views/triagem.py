from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.views import View

from ..dtos import StatusPeca, TriagemDTO
from ..services import TriagemService
from .utils import erro_interno, ler_json


def _sim_nao(valor):
    """Aceita true/false, 'sim'/'não', 1/0. Qualquer outra coisa (ou vazio) é 'não informado'."""
    if isinstance(valor, bool) or valor is None:
        return valor
    texto = str(valor).strip().lower()
    if texto in ('sim', 's', 'true', '1'):
        return True
    if texto in ('nao', 'não', 'n', 'false', '0'):
        return False
    return None


class TriagemView(View):
    def get(self, request):
        try:
            id_param = request.GET.get('id')
            if id_param:
                tri = TriagemService.buscar_por_id(int(id_param))
                if not tri: 
                    return JsonResponse({'status': 'erro', 'mensagem': 'Não encontrado'}, status=404)
                
                return JsonResponse({
                    'status': 'sucesso', 
                    'dado': { 
                        'id': tri.id_triagem, 'n_ticket': tri.n_ticket, 'nf': tri.nf, 
                        'cidade': tri.cidade, 'estado': tri.estado, 'sn': tri.sn, 
                        'status_peca': tri.status_peca.value if hasattr(tri.status_peca, 'value') else tri.status_peca, 
                        'troca': tri.troca, 'id_peca_trocada': tri.id_peca_trocada, 'troca_indevida': tri.troca_indevida, 'motivo_troca_indevida': tri.motivo_troca_indevida,
                        'justificativa_troca_indevida': tri.justificativa_troca_indevida, 'ct': tri.ct, 'defeito_usuario': tri.defeito_usuario, 
                        'defeito_tecnico': tri.defeito_tecnico, 'defeito_constatado': tri.defeito_constatado, 
                        'testes': tri.testes, 'analise': tri.analise, 'conclusao': tri.conclusao, 
                        'nome_cliente': tri.nome_cliente, 'nome_equipamento': tri.nome_equipamento, 
                        'nome_tecnico': tri.nome_tecnico, 'nome_analista': tri.nome_analista_triagem, 
                        'nome_analista_chamado': tri.nome_analista_chamado,
                        'id_cliente': tri.id_cliente, 'id_equipamento': tri.id_equipamento, 'id_tecnico': tri.id_tecnico,
                        'id_analista_chamado': tri.id_analista_chamado, 'criado_em': tri.criado_em
                    }
                })

            triagens_dto = TriagemService.listar()
            dados = [
                {
                    'id': tri.id_triagem, 'n_ticket': tri.n_ticket, 'sn': tri.sn, 
                    'status_peca': tri.status_peca.value if hasattr(tri.status_peca, 'value') else tri.status_peca, 
                    'nome_cliente': tri.nome_cliente, 'defeito_usuario': tri.defeito_usuario, 
                    'defeito_tecnico': tri.defeito_tecnico, 'conclusao': tri.conclusao, 
                    'nome_analista': tri.nome_analista_triagem
                } 
                for tri in triagens_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return erro_interno(e)
        
    def post(self, request):
        try:
            id_analista_logado = request.session.get('funcionario_id')
            if not id_analista_logado: 
                return JsonResponse({'status': 'erro', 'mensagem': 'Sessão expirada. Faça login novamente.'}, status=401)

            body = ler_json(request)
            if body.get('id') and not TriagemService.pode_editar(
                    int(body['id']), id_analista_logado, getattr(request, 'funcionario_cargo', '')):
                return JsonResponse({'status': 'erro', 'mensagem': 'Só quem fez a triagem, um Gestor ou um Administrador pode alterá-la.'}, status=403)
            dto_entrada = TriagemDTO(
                id_triagem=body.get('id') or None, 
                n_ticket=int(body.get('n_ticket') or 0), 
                nf=int(body.get('nf') or 0), 
                cidade=body.get('cidade'), 
                estado=body.get('estado'), 
                id_cliente=int(body.get('id_cliente') or 0), 
                id_equipamento=int(body.get('id_equipamento') or 0), 
                id_tecnico=int(body.get('id_tecnico') or 0), 
                id_analista_chamado=int(body.get('id_analista') or 0), 
                id_analista_triagem=id_analista_logado, 
                sn=body.get('sn'), 
                status_peca=StatusPeca(int(body.get('status_peca') or 2)), 
                troca=body.get('troca'), 
                id_peca_trocada=int(body.get('id_peca_trocada') or 0) or None,
                troca_indevida=_sim_nao(body.get('troca_indevida')),
                motivo_troca_indevida=body.get('motivo_troca_indevida'),
                justificativa_troca_indevida=body.get('justificativa_troca_indevida'),
                ct=body.get('ct'),
                defeito_usuario=body.get('defeito_usuario'), 
                defeito_tecnico=body.get('defeito_tecnico'), 
                defeito_constatado=body.get('defeito_constatado'), 
                testes=body.get('testes'), 
                analise=body.get('analise'), 
                conclusao=body.get('conclusao')
            )
            salvo = TriagemService.salvar(dto_entrada)
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Triagem salva com sucesso!', 'id': salvo.id_triagem})
        except ObjectDoesNotExist:
            return JsonResponse({'status': 'erro', 'mensagem': 'Registro não encontrado.'}, status=404)
        except ValueError as ve:
             return JsonResponse({'status': 'erro', 'mensagem': f"Erro de validação: {str(ve)}"}, status=400)
        except Exception as e:
            return erro_interno(e)


class TriagemOpcoesView(View):
    """GET: listas usadas pelo formulário da triagem (hoje, os motivos de troca indevida)."""
    def get(self, request):
        return JsonResponse({'status': 'sucesso', 'dados': {'motivos_troca_indevida': TriagemService.MOTIVOS_TROCA_INDEVIDA,
                                                           'motivo_outro': TriagemService.MOTIVO_OUTRO}})


class TriagemHistoricoView(View):
    """GET ?id=: correções feitas numa triagem depois de salva (quem, quando e o que mudou)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': TriagemService.historico(int(request.GET.get('id') or 0))})
        except (ObjectDoesNotExist, ValueError):
            return JsonResponse({'status': 'erro', 'mensagem': 'Triagem não encontrada.'}, status=404)
        except Exception as e:
            return erro_interno(e)


class ExportarTriagemDocxView(View):
    def get(self, request):
        try:
            id_param = request.GET.get('id')
            buffer, nome_arquivo = TriagemService.gerar_docx(int(id_param))
            response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
            return response
        except Exception as e:
            return erro_interno(e)
