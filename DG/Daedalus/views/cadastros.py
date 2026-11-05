from django.http import JsonResponse
from django.views import View

from ..dtos import CargoFuncionario, EmpresaDTO, EquipamentoDTO, FuncionarioDTO, TecnicoDTO, TipoEmpresa
from ..models import CotacaoPeca, Equipamento, Peca
from ..partsurfer import PartSurferError
from ..services import (CotacaoService, EmpresaService, EquipamentoService, FuncionarioService,
                        LimiteConsultasExcedido, TecnicoService)
from .utils import erro_interno, ler_json, resposta_erro


class EmpresaView(View):
    def get(self, request):
        try:
            tipo_param = request.GET.get('tipo')
            if tipo_param:
                empresas_dto = EmpresaService.listar(tipo_filtro=int(tipo_param))
            else:
                empresas_dto = EmpresaService.listar()

            dados = [
                {'id': emp.id_empresa, 'razao_social': emp.razao_social, 'cnpj': emp.cnpj, 'tipo': emp.tipo}
                for emp in empresas_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except ValueError:
            return resposta_erro('Filtro de tipo inválido.', 400)
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            body = ler_json(request)
            dto_entrada = EmpresaDTO(
                id_empresa=body.get('id'),
                cnpj=body.get('cnpj'),
                razao_social=body.get('razaoSocial'),
                tipo=TipoEmpresa(int(body.get('tipo'))),
            )
            dto_saida = EmpresaService.salvar(dto_entrada)
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': 'Empresa salva com sucesso!',
                'id_gerado': dto_saida.id_empresa,
            })
        except (ValueError, TypeError) as ve:
            return resposta_erro(f"Dados inválidos: {ve}", 400)
        except Exception as e:
            return erro_interno(e)


class TecnicoView(View):
    def get(self, request):
        try:
            tecnicos_dto = TecnicoService.listar()
            dados = [
                {'id': tec.id_tecnico, 'nome': tec.nome, 'nome_empresa': tec.nome_empresa}
                for tec in tecnicos_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            body = ler_json(request)
            if not (body.get('nome') or '').strip() or not body.get('id_empresa'):
                return resposta_erro('Informe o nome e a empresa do técnico.', 400)
            TecnicoService.salvar(TecnicoDTO(
                id_tecnico=body.get('id'),
                nome=body.get('nome').strip(),
                id_empresa=body.get('id_empresa'),
            ))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Técnico salvo com sucesso!'})
        except ValueError as ve:
            return resposta_erro(f"Dados inválidos: {ve}", 400)
        except Exception as e:
            return erro_interno(e)


class FuncionarioView(View):
    def get(self, request):
        try:
            funcionarios_dto = FuncionarioService.listar()
            dados = [
                {
                    'id': func.id_funcionario,
                    'nome': func.nome,
                    'cargo': func.cargo.value if hasattr(func.cargo, 'value') else str(func.cargo),
                    'login': func.login,
                    'primeiroAcesso': func.primeiro_acesso,
                    'email': func.email,
                }
                for func in funcionarios_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            body = ler_json(request)
            cargo_novo = CargoFuncionario(body.get('cargo')).value
            cargo_logado = getattr(request, 'funcionario_cargo', '')

            # Gestor administra apenas os cargos abaixo do dele; só o Administrador cria Gestores/Administradores.
            if cargo_logado != CargoFuncionario.ADMINISTRADOR.value:
                if cargo_novo in (CargoFuncionario.ADMINISTRADOR.value, CargoFuncionario.GESTOR.value):
                    return resposta_erro('Você não tem privilégios para criar ou editar cargos de Gestor ou Administrador.', 403)
                if body.get('id'):
                    atual = FuncionarioService.obter(body.get('id'))
                    if atual and atual.cargo in (CargoFuncionario.ADMINISTRADOR.value, CargoFuncionario.GESTOR.value):
                        return resposta_erro('Você não tem privilégios para alterar este funcionário.', 403)

            dto_saida = FuncionarioService.salvar(FuncionarioDTO(
                id_funcionario=body.get('id'),
                nome=body.get('nome'),
                cargo=cargo_novo,
                login=int(body.get('login')),
                senha=body.get('senha'),
                email=body.get('email'),
            ))
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': 'Funcionário salvo com sucesso!',
                'id_gerado': dto_saida.id_funcionario,
            })
        except (ValueError, TypeError) as ve:
            return resposta_erro(f"Dados inválidos: {ve}", 400)
        except Exception as e:
            return erro_interno(e)


class EquipamentoView(View):
    def get(self, request):
        try:
            equipamento_dto = EquipamentoService.listar(request.GET.get('q') or '')
            dados = [
                {
                    'id': equipamento.id_equipamento,
                    'pn': equipamento.pn,
                    'modelo': equipamento.modelo,
                    'tipo': equipamento.tipo,
                    'marca': equipamento.marca,
                    'rfb': equipamento.rfb,
                    'total_pecas': equipamento.total_pecas,
                    'pecas_sincronizadas_em': equipamento.pecas_sincronizadas_em,
                }
                for equipamento in equipamento_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return erro_interno(e)

    def post(self, request):
        try:
            body = ler_json(request)
            dto_saida = EquipamentoService.salvar(EquipamentoDTO(
                id_equipamento=body.get('id'),
                pn=body.get('pn'),
                modelo=body.get('modelo'),
                tipo=body.get('tipo'),
                marca=body.get('marca'),
            ))
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': 'Equipamento salvo com sucesso!',
                'id_gerado': dto_saida.id_equipamento,
            })
        except ValueError as ve:
            return resposta_erro(f"Dados inválidos: {ve}", 400)
        except Exception as e:
            return erro_interno(e)


# ==========================================
# PEÇAS DO EQUIPAMENTO (PartSurfer + seleção) E COTAÇÕES
# ==========================================
class ImportarPecasView(View):
    """POST {"texto": "..."}: importa peças de vários modelos de uma vez (planilha colada ou arquivo CSV lido pela tela)."""
    def post(self, request):
        try:
            resultado = EquipamentoService.importar_pecas(ler_json(request).get('texto'))
            return JsonResponse({'status': 'sucesso', 'dado': resultado})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class PecasEquipamentoView(View):
    """
    GET  -> peças já escolhidas para o equipamento, com a cotação mais recente de cada uma.
    POST -> salva a seleção feita pelo usuário: {"pecas": [{"part_number": "...", "descricao": "..."}]}
    """
    def get(self, request, id_equipamento):
        try:
            pecas = EquipamentoService.listar_pecas(id_equipamento)
            return JsonResponse({'status': 'sucesso', 'dados': pecas})
        except Equipamento.DoesNotExist:
            return resposta_erro('Equipamento não encontrado.', 404)
        except Exception as e:
            return erro_interno(e)

    def post(self, request, id_equipamento):
        try:
            body = ler_json(request)
            pecas = EquipamentoService.salvar_selecao(id_equipamento, body.get('pecas'))
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': f'{len(pecas)} peça(s) salva(s) para este modelo.',
                'dados': pecas,
            })
        except Equipamento.DoesNotExist:
            return resposta_erro('Equipamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class ConsultarPartSurferView(View):
    """POST: consulta o HP PartSurfer pelo PN e devolve as peças candidatas. Não grava nada."""
    def post(self, request, id_equipamento):
        try:
            candidatas = EquipamentoService.consultar_partsurfer(id_equipamento)
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': f'O PartSurfer retornou {sum(1 for c in candidatas if not c["somente_local"])} peça(s).',
                'dados': candidatas,
            })
        except Equipamento.DoesNotExist:
            return resposta_erro('Equipamento não encontrado.', 404)
        except LimiteConsultasExcedido as le:
            return resposta_erro(str(le), 429)
        except ValueError as ve:
            # PartSurfer respondeu, mas sem peças para esse PN
            return resposta_erro(str(ve), 404)
        except PartSurferError as pe:
            return resposta_erro(f'Falha ao consultar o PartSurfer: {pe}', 502)
        except Exception as e:
            return erro_interno(e)


class CotacoesPecaView(View):
    """
    GET  -> histórico de cotações da peça.
    POST -> lança uma cotação: {"fornecedor_id", "valor", "data_cotacao" (AAAA-MM-DD), "observacao"}
    """
    def get(self, request, id_peca):
        try:
            return JsonResponse({'status': 'sucesso', **CotacaoService.listar(id_peca)})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except Exception as e:
            return erro_interno(e)

    def post(self, request, id_peca):
        try:
            cotacao = CotacaoService.criar(id_peca, ler_json(request), request.session.get('funcionario_id'))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Cotação registrada!', 'dado': cotacao})
        except Peca.DoesNotExist:
            return resposta_erro('Peça não encontrada.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class CotacaoDetalheView(View):
    def delete(self, request, id_cotacao):
        try:
            CotacaoService.excluir(id_cotacao)
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Cotação excluída.'})
        except CotacaoPeca.DoesNotExist:
            return resposta_erro('Cotação não encontrada.', 404)
        except Exception as e:
            return erro_interno(e)


class PecaManualView(View):
    """POST {part_number, descricao, equipamento_completo?}: adiciona uma peça ao modelo sem usar o PartSurfer."""
    def post(self, request, id_equipamento):
        try:
            pecas = EquipamentoService.adicionar_peca_manual(id_equipamento, ler_json(request))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Peça adicionada ao modelo.', 'dados': pecas})
        except Equipamento.DoesNotExist:
            return resposta_erro('Equipamento não encontrado.', 404)
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class PecaRemoverView(View):
    """POST {id_peca}: tira a peça do modelo (não apaga a peça nem as cotações)."""
    def post(self, request, id_equipamento):
        try:
            pecas = EquipamentoService.remover_peca(id_equipamento, int(ler_json(request).get('id_peca')))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Peça retirada do modelo.', 'dados': pecas})
        except (Equipamento.DoesNotExist, Peca.DoesNotExist) as e:
            return resposta_erro(str(e) or 'Não encontrado.', 404)
        except (TypeError, ValueError):
            return resposta_erro('Dados inválidos.', 400)
        except Exception as e:
            return erro_interno(e)
