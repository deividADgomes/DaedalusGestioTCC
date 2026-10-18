import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views import View
import re
import unicodedata
from django.db.models import Count, F, Q

from django.core.exceptions import ObjectDoesNotExist
from .models import Equipamento, FotoTriagem, Funcionario, Triagem
from .analytics import FiltroInvalido, exportar_csv, montar_dashboard
from .dtos import CargoFuncionario, EmpresaDTO, EquipamentoDTO, StatusPeca, TipoEmpresa, TecnicoDTO, FuncionarioDTO, TriagemDTO
from .partsurfer import PartSurferError
from .services import LimiteConsultasExcedido, EmpresaService, EquipamentoService, FotoService, FuncionarioService, SolicitacaoSenhaService, TecnicoService, TriagemService

def _normalizar_texto(valor):
    """Minúsculas, sem acentos nem pontuação: base da comparação diagnóstico do técnico x constatação."""
    if not valor:
        return ''
    sem_acento = ''.join(c for c in unicodedata.normalize('NFD', valor) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', sem_acento.lower()).strip()


# ==========================================
# RENDERIZAÇÃO DAS TELAS (FRONT-END)
# ==========================================
def daedalus_principal(request):
    return render(request, 'Daedalus/TelaPrincipal/index.html')

def daedalus_pesquisa(request):
    return render(request, 'Daedalus/Pesquisa/pesquisa.html')

def daedalus_gerenciarEmpresa(request):
    return render(request, 'Daedalus/GerenciarEmpresa/G_empresa.html')

def daedalus_gerenciarTecnico(request):
    return render(request, 'Daedalus/GerenciarTecnico/G_tecnico.html')

def daedalus_gerenciarFuncionario(request):
    return render(request, 'Daedalus/GerenciarFuncionario/G_funcionario.html')

def daedalus_gerenciarMdeloEquipamento(request):
    return render(request, 'Daedalus/GerenciarModeloEquipamento/G_modeloEquipamento.html')

def daedalus_dashboard(request):
    return render(request, 'Daedalus/Dashboard/dashboard.html')

def daedalus_visualizar_triagem(request):
    return render(request, 'Daedalus/Visualizar/visualizar.html')

def daedalus_primeiro_acesso(request):
    return render(request, 'Daedalus/PrimeiroAcesso/primeiro_acesso.html')


# ==========================================
# APIs E REGRAS DE NEGÓCIO
# ==========================================

class EmpresaView(View):
    def get(self, request):
        try:
            tipo_param = request.GET.get('tipo')
            
            if tipo_param:
                empresas_dto = EmpresaService.listar(tipo_filtro=int(tipo_param))
            else:
                empresas_dto = EmpresaService.listar()
            
            dados = [
                {
                    'id': emp.id_empresa,
                    'razao_social': emp.razao_social,
                    'cnpj': emp.cnpj,
                    'tipo': emp.tipo
                }
                for emp in empresas_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
            
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    def post(self, request):
        try:
            body = json.loads(request.body)
            dto_entrada = EmpresaDTO(
                id_empresa=body.get('id'),
                cnpj=body.get('cnpj'),
                razao_social=body.get('razaoSocial'),
                tipo=TipoEmpresa(int(body.get('tipo')))
            )
            dto_saida = EmpresaService.salvar(dto_entrada)

            return JsonResponse({
                'status': 'sucesso', 
                'mensagem': 'Empresa salva com sucesso!',
                'id_gerado': dto_saida.id_empresa
            })
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': f"Dados inválidos: {str(ve)}"}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class TecnicoView(View):
    def get(self, request):
        try:
            tecnicos_dto = TecnicoService.listar()
            dados = [
                {
                    'id': tec.id_tecnico,
                    'nome': tec.nome,
                    'nome_empresa': tec.nome_empresa 
                }
                for tec in tecnicos_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)
        
    def post(self, request):
        try:
            body = json.loads(request.body)
            dto_entrada = TecnicoDTO(
                id_tecnico=body.get('id'),
                nome=body.get('nome'),
                id_empresa=body.get('id_empresa') 
            )
            dto_saida = TecnicoService.salvar(dto_entrada)

            return JsonResponse({'status': 'sucesso', 'mensagem': 'Técnico salvo com sucesso!'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


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
                    'email': func.email,
                    'primeiroAcesso': func.primeiro_acesso 
                }
                for func in funcionarios_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    def post(self, request):
        try:
            body = json.loads(request.body)
            dto_entrada = FuncionarioDTO(
                id_funcionario=body.get('id'),
                nome=body.get('nome'),
                cargo=CargoFuncionario(body.get('cargo')), 
                login=int(body.get('login')),
                senha=body.get('senha'),
                email=body.get('email')
            )

            if request.session.get('funcionario_cargo') == 'Gestor':
                alvo_existente = Funcionario.objects.filter(pk=dto_entrada.id_funcionario).first() if dto_entrada.id_funcionario else None
                cargos_restritos = ('Administrador', 'Gestor')
                if dto_entrada.cargo.value in cargos_restritos or (alvo_existente and alvo_existente.cargo in cargos_restritos):
                    return JsonResponse({'status': 'erro', 'mensagem': 'Gestor não pode criar ou alterar Gestor/Administrador.'}, status=403)

            dto_saida = FuncionarioService.salvar(dto_entrada)

            return JsonResponse({
                'status': 'sucesso', 
                'mensagem': 'Funcionário salvo com sucesso!',
                'id_gerado': dto_saida.id_funcionario
            })
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': f"Dados inválidos: {str(ve)}"}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class EquipamentoView(View):
    def get(self, request):
        try:
            equipamento_dto = EquipamentoService.listar()
            dados = [
                {
                    'id': equipamento.id_equipamento,
                    'pn': equipamento.pn,
                    'modelo': equipamento.modelo,
                    'total_pecas': equipamento.total_pecas
                }
                for equipamento in equipamento_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    def post(self, request):
        try:
            body = json.loads(request.body)
            dto_entrada = EquipamentoDTO(
                id_equipamento=body.get('id'),
                pn=body.get('pn'),
                modelo=body.get('modelo')
            )
            dto_saida = EquipamentoService.salvar(dto_entrada)

            return JsonResponse({
                'status': 'sucesso', 
                'mensagem': 'Equipamento salvo com sucesso!',
                'id_gerado': dto_saida.id_equipamento
            })
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': f"Dados inválidos: {str(ve)}"}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class PecasEquipamentoView(View):
    """Peças vinculadas a um modelo de equipamento (GET lista; POST substitui a lista inteira)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso',
                                 'dados': EquipamentoService.listar_pecas(int(request.GET.get('id_equipamento')))})
        except (TypeError, ValueError):
            return JsonResponse({'status': 'erro', 'mensagem': 'Equipamento inválido.'}, status=400)
        except Equipamento.DoesNotExist:
            return JsonResponse({'status': 'erro', 'mensagem': 'Equipamento não encontrado.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    def post(self, request):
        try:
            body = json.loads(request.body)
            dados = EquipamentoService.salvar_pecas(int(body.get('id_equipamento')), body.get('pecas'))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Peças do modelo salvas!', 'dados': dados})
        except (TypeError, ValueError) as ve:
            return JsonResponse({'status': 'erro', 'mensagem': f"Dados inválidos: {ve}"}, status=400)
        except Equipamento.DoesNotExist:
            return JsonResponse({'status': 'erro', 'mensagem': 'Equipamento não encontrado.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class ConsultarPartSurferView(View):
    """POST: consulta o HP PartSurfer pelo PN do modelo e devolve as peças candidatas. Não grava nada."""
    def post(self, request, id_equipamento):
        try:
            candidatas = EquipamentoService.consultar_partsurfer(id_equipamento)
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': f'O PartSurfer retornou {sum(1 for c in candidatas if not c["somente_local"])} peça(s).',
                'dados': candidatas,
            })
        except Equipamento.DoesNotExist:
            return JsonResponse({'status': 'erro', 'mensagem': 'Equipamento não encontrado.'}, status=404)
        except LimiteConsultasExcedido as le:
            return JsonResponse({'status': 'erro', 'mensagem': str(le)}, status=429)
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': str(ve)}, status=404)
        except PartSurferError as pe:
            return JsonResponse({'status': 'erro', 'mensagem': f'Falha ao consultar o PartSurfer: {pe}'}, status=502)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class FotoTriagemView(View):
    """Fotos de uma triagem: GET lista, POST envia (multipart), DELETE remove."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': FotoService.listar(int(request.GET.get('id_triagem')))})
        except (TypeError, ValueError):
            return JsonResponse({'status': 'erro', 'mensagem': 'Triagem inválida.'}, status=400)

    def post(self, request):
        try:
            arquivo = request.FILES.get('arquivo')
            if arquivo is None:
                raise ValueError("Nenhuma foto enviada.")
            foto = FotoService.adicionar(
                int(request.POST.get('id_triagem')), arquivo, request.POST.get('legenda', ''))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Foto adicionada!', 'dado': foto})
        except Triagem.DoesNotExist:
            return JsonResponse({'status': 'erro', 'mensagem': 'Triagem não encontrada.'}, status=404)
        except (TypeError, ValueError) as ve:
            return JsonResponse({'status': 'erro', 'mensagem': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

    def delete(self, request):
        try:
            FotoService.excluir(int(request.GET.get('id')))
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Foto removida.'})
        except (TypeError, ValueError):
            return JsonResponse({'status': 'erro', 'mensagem': 'Foto inválida.'}, status=400)
        except ObjectDoesNotExist as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=404)


def daedalus_foto_arquivo(request, id_foto):
    """Entrega o arquivo da foto. Passa pelo middleware, então exige login."""
    foto = FotoTriagem.objects.filter(pk=id_foto).first()
    if foto is None:
        raise Http404()
    try:
        resposta = FileResponse(foto.arquivo.open('rb'), content_type='image/jpeg')
    except (FileNotFoundError, OSError):
        raise Http404()
    resposta['X-Content-Type-Options'] = 'nosniff'
    resposta['Cache-Control'] = 'private, max-age=3600'
    return resposta


class TriagemView(View):
    def get(self, request):
        try:
            id_param = request.GET.get('id')
            
            # Lógica para Visualizar UM ticket específico
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
                        'troca': tri.troca, 'id_equipamento': tri.id_equipamento,
                        'id_peca_trocada': tri.id_peca_trocada, 'peca_trocada': tri.peca_trocada,
                        'fotos': FotoService.listar(tri.id_triagem),
                        'defeito_usuario': tri.defeito_usuario,
                        'defeito_tecnico': tri.defeito_tecnico, 'defeito_constatado': tri.defeito_constatado,
                        'testes': tri.testes, 'analise': tri.analise, 'conclusao': tri.conclusao,
                        'nome_cliente': tri.nome_cliente, 'nome_equipamento': tri.nome_equipamento,
                        'nome_tecnico': tri.nome_tecnico,
                        'data_triagem': tri.data_triagem.isoformat() if tri.data_triagem else None,
                        # Para o Front-end não quebrar
                        'nome_analista': tri.nome_analista_triagem,
                        'nome_analista_chamado': tri.nome_analista_chamado 
                    }
                })

            # Lógica para a Pesquisa Geral
            triagens_dto = TriagemService.listar()
            dados = [
                {
                    'id': tri.id_triagem, 'n_ticket': tri.n_ticket, 'sn': tri.sn,
                    'status_peca': tri.status_peca.value if hasattr(tri.status_peca, 'value') else tri.status_peca,
                    'nome_cliente': tri.nome_cliente,
                    'defeito_usuario': tri.defeito_usuario, 'defeito_tecnico': tri.defeito_tecnico,
                    'conclusao': tri.conclusao,
                    'nome_analista': tri.nome_analista_triagem
                }
                for tri in triagens_dto
            ]
            return JsonResponse({'status': 'sucesso', 'dados': dados})
            
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)
        
    def post(self, request):
        try:
            # Pega o ID de quem está logado no sistema
            id_analista_logado = request.session.get('funcionario_id')
            
            if not id_analista_logado:
                return JsonResponse({'status': 'erro', 'mensagem': 'Sessão expirada. Faça login novamente.'}, status=401)

            body = json.loads(request.body)
            
            dto_entrada = TriagemDTO(
                id_triagem=body.get('id') or None, 
                n_ticket=int(body.get('n_ticket')),
                nf=int(body.get('nf')),
                cidade=body.get('cidade'),
                estado=body.get('estado'),
                id_cliente=int(body.get('id_cliente')),
                id_equipamento=int(body.get('id_equipamento')),
                id_tecnico=int(body.get('id_tecnico')),
                id_analista_chamado=int(body.get('id_analista')), # Vem do Formulário
                id_analista_triagem=id_analista_logado, # Vem da Sessão (invisível)
                sn=body.get('sn'),
                status_peca=StatusPeca(int(body.get('status_peca'))),
                troca=body.get('troca'),
                id_peca_trocada=int(body.get('id_peca_trocada')) if body.get('id_peca_trocada') else None,
                defeito_usuario=body.get('defeito_usuario'),
                defeito_tecnico=body.get('defeito_tecnico'),
                defeito_constatado=body.get('defeito_constatado'),
                testes=body.get('testes'),
                analise=body.get('analise'),
                conclusao=body.get('conclusao')
            )

            dto_salvo = TriagemService.salvar(dto_entrada)

            return JsonResponse({'status': 'sucesso', 'mensagem': 'Triagem salva com sucesso!',
                                 'id_gerado': dto_salvo.id_triagem})
            
        except ValueError as ve:
             return JsonResponse({'status': 'erro', 'mensagem': f"Erro de validação: {str(ve)}"}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class ExportarTriagemDocxView(View):
    def get(self, request):
        try:
            id_param = request.GET.get('id')
            buffer, nome_arquivo = TriagemService.gerar_docx(int(id_param))
            
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
            return response
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class DashboardView(View):
    """BI do dashboard: toda a análise é feita em Daedalus/analytics.py (filtros via querystring)."""
    def get(self, request):
        try:
            dados = montar_dashboard(request.GET)
            return JsonResponse({'status': 'sucesso', 'vazio': dados['vazio'], 'dados': dados})
        except FiltroInvalido as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class DashboardExportarView(View):
    """Exporta em CSV as triagens do recorte filtrado (mesmos parâmetros do dashboard)."""
    def get(self, request):
        try:
            conteudo = exportar_csv(request.GET)
            resposta = HttpResponse(conteudo, content_type='text/csv; charset=utf-8')
            resposta['Content-Disposition'] = 'attachment; filename="triagens_daedalus.csv"'
            return resposta
        except FiltroInvalido as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


# ==========================================
# AUTENTICAÇÃO E LOGIN
# ==========================================

class LoginView(View):
    def get(self, request):
        if request.session.get('funcionario_id'):
            return redirect('/principal/')
        return render(request, 'Daedalus/login/login.html')

class LoginAPIView(View):
    def post(self, request):
        try:
            dados = json.loads(request.body)
            login_informado = dados.get('login')
            senha_informada = dados.get('senha')

            if not login_informado or not senha_informada:
                return JsonResponse({'status': 'erro', 'mensagem': 'Credenciais em branco.'}, status=400)

            try:
                login_informado = int(login_informado)
            except (TypeError, ValueError):
                return JsonResponse({'status': 'erro', 'mensagem': 'Matrícula ou senha incorretos.'}, status=401)

            # DELEGA A RESPONSABILIDADE PARA O SERVICE
            funcionario_dto = FuncionarioService.autenticar(login=login_informado, senha=senha_informada)

            if funcionario_dto:
                # O Controller apenas gere a Sessão HTTP
                request.session['funcionario_id'] = funcionario_dto.id_funcionario
                request.session['funcionario_nome'] = funcionario_dto.nome
                request.session['funcionario_cargo'] = funcionario_dto.cargo
                request.session['primeiro_acesso'] = funcionario_dto.primeiro_acesso
                
                return JsonResponse({
                    'status': 'sucesso',
                    'mensagem': 'Login aprovado.',
                    'primeiro_acesso': funcionario_dto.primeiro_acesso
                })
            else:
                return JsonResponse({'status': 'erro', 'mensagem': 'Matrícula ou senha incorretos.'}, status=401)
                
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

class AlterarSenhaView(View):
    """RF13/RF14: o próprio usuário logado troca a senha. Exige a senha atual."""
    def post(self, request):
        try:
            id_logado = request.session.get('funcionario_id')
            if not id_logado:
                return JsonResponse({'status': 'erro', 'mensagem': 'Sessão expirada. Faça login novamente.'}, status=401)

            dados = json.loads(request.body)
            FuncionarioService.alterar_senha(
                id_funcionario=id_logado,
                senha_atual=dados.get('senha_atual'),
                nova_senha=dados.get('nova_senha')
            )
            request.session['primeiro_acesso'] = False
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Senha alterada com sucesso.'})
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class RecuperarSenhaView(View):
    """UC09: o usuário informa matrícula e e-mail na tela de login e o administrador é avisado por e-mail."""
    def post(self, request):
        try:
            dados = json.loads(request.body)
            try:
                login = int(dados.get('login'))
            except (TypeError, ValueError):
                login = None
            if login is not None:
                SolicitacaoSenhaService.registrar(login, dados.get('email'))
            # Resposta sempre igual: não revela se matrícula e e-mail existem
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Se a matrícula e o e-mail estiverem corretos, o administrador foi avisado por e-mail e vai redefinir sua senha.'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


class SolicitacoesSenhaView(View):
    """Lista os pedidos pendentes (acesso restrito a Administrador/Gestor pelo middleware)."""
    def get(self, request):
        return JsonResponse({'status': 'sucesso', 'dados': SolicitacaoSenhaService.listar_pendentes()})


class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('tela_login')