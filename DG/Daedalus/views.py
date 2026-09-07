import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, F, Q

from .models import Triagem
from .dtos import CargoFuncionario, EmpresaDTO, EquipamentoDTO, StatusPeca, TipoEmpresa, TecnicoDTO, FuncionarioDTO, TriagemDTO
from .services import EmpresaService, EquipamentoService, FuncionarioService, TecnicoService, TriagemService

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


# ==========================================
# APIs E REGRAS DE NEGÓCIO
# ==========================================

@method_decorator(csrf_exempt, name='dispatch')
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


@method_decorator(csrf_exempt, name='dispatch')
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


@method_decorator(csrf_exempt, name='dispatch')
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
                senha=body.get('senha') 
            )
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


@method_decorator(csrf_exempt, name='dispatch')
class EquipamentoView(View):
    def get(self, request):
        try:
            equipamento_dto = EquipamentoService.listar()
            dados = [
                {
                    'id': equipamento.id_equipamento,
                    'pn': equipamento.pn,
                    'modelo': equipamento.modelo
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


@method_decorator(csrf_exempt, name='dispatch')
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
                        'troca': tri.troca, 'defeito_usuario': tri.defeito_usuario,
                        'defeito_tecnico': tri.defeito_tecnico, 'defeito_constatado': tri.defeito_constatado,
                        'testes': tri.testes, 'analise': tri.analise, 'conclusao': tri.conclusao,
                        'nome_cliente': tri.nome_cliente, 'nome_equipamento': tri.nome_equipamento,
                        'nome_tecnico': tri.nome_tecnico,
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
                defeito_usuario=body.get('defeito_usuario'),
                defeito_tecnico=body.get('defeito_tecnico'),
                defeito_constatado=body.get('defeito_constatado'),
                testes=body.get('testes'),
                analise=body.get('analise'),
                conclusao=body.get('conclusao')
            )

            TriagemService.salvar(dto_entrada)

            return JsonResponse({'status': 'sucesso', 'mensagem': 'Triagem salva com sucesso!'})
            
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
    def get(self, request):
        try:
            filtros = Q()
            query = Triagem.objects.filter(filtros)
            total = query.count()

            if total == 0:
                return JsonResponse({'status': 'sucesso', 'vazio': True})

            # 1. Técnicos
            stats_tecnicos = list(query.values(nome=F('tecnico__nome'))
                                 .annotate(sucessos=Count('id_triagem', filter=Q(status=1)),
                                           erros=Count('id_triagem', filter=Q(status=2)),
                                           total=Count('id_triagem')).order_by('-total')[:10])

            # 2. Analistas (Baseado em quem fez a Triagem na bancada)
            stats_analistas = list(query.values(nome=F('analista_triagem__nome'))
                                  .annotate(sucessos=Count('id_triagem', filter=Q(status=1)),
                                            erros=Count('id_triagem', filter=Q(status=2)),
                                            total=Count('id_triagem')).order_by('-total')[:10])

            # 3. Insight Profundo: Apenas Clientes (Tipo 2)
            top_cliente_obj = query.filter(cliente__tipo=2).values('cliente_id', nome=F('cliente__razao_social')).annotate(total=Count('id_triagem')).order_by('-total').first()
            
            detalhe_cliente = {}
            if top_cliente_obj:
                equip_mais_triado = query.filter(cliente_id=top_cliente_obj['cliente_id']).values(modelo=F('equipamento__modelo')).annotate(qtd=Count('id_triagem')).order_by('-qtd').first()
                defeito_comum = "Não relatado"
                if equip_mais_triado:
                    def_obj = query.filter(cliente_id=top_cliente_obj['cliente_id'], equipamento__modelo=equip_mais_triado['modelo']) \
                                   .exclude(defeito_constatado__exact='').exclude(defeito_constatado__isnull=True) \
                                   .values('defeito_constatado').annotate(qtd=Count('id_triagem')).order_by('-qtd').first()
                    if def_obj: defeito_comum = def_obj['defeito_constatado']

                detalhe_cliente = {
                    'nome': top_cliente_obj['nome'],
                    'total': top_cliente_obj['total'],
                    'equipamento_top': equip_mais_triado['modelo'] if equip_mais_triado else "N/A",
                    'defeito_top': defeito_comum
                }

            # 4. Top Clientes (Gráfico Empilhado APENAS CLIENTES tipo=2)
            top_clientes_graf = list(query.filter(cliente__tipo=2).values(nome=F('cliente__razao_social'))
                                     .annotate(sucessos=Count('id_triagem', filter=Q(status=1)),
                                               erros=Count('id_triagem', filter=Q(status=2)),
                                               total=Count('id_triagem')).order_by('-total')[:5])

            # 5. Top Peças Trocadas (Com Modelo)
            top_pecas = list(query.exclude(troca__exact='').exclude(troca__isnull=True)
                                  .values(nome=F('troca'), modelo=F('equipamento__modelo'))
                                  .annotate(total=Count('id_triagem')).order_by('-total')[:5])
                                  
            top_peca_obj = top_pecas[0] if top_pecas else {'nome': 'Nenhuma', 'modelo': '-', 'total': 0}

            dados = {
                'tecnicos': stats_tecnicos,
                'analistas': stats_analistas,
                'top_cliente': detalhe_cliente,
                'clientes_grafico': top_clientes_graf,
                'pecas': top_pecas,
                'top_peca_kpi': top_peca_obj,
                'resumo': {
                    'total': total,
                    'funcionais': query.filter(status=1).count(),
                    'erros': query.filter(status=2).count()
                }
            }

            return JsonResponse({'status': 'sucesso', 'dados': dados})

        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)


# ==========================================
# AUTENTICAÇÃO E LOGIN
# ==========================================

class LoginView(View):
    def get(self, request):
        if request.session.get('funcionario_id'):
            return redirect('/dashboard/') # Altere se a sua home for outra rota
        return render(request, 'Daedalus/Login/login.html')

@method_decorator(csrf_exempt, name='dispatch')
class LoginAPIView(View):
    def post(self, request):
        try:
            dados = json.loads(request.body)
            login_informado = dados.get('login')
            senha_informada = dados.get('senha')

            if not login_informado or not senha_informada:
                return JsonResponse({'status': 'erro', 'mensagem': 'Credenciais em branco.'}, status=400)

            # DELEGA A RESPONSABILIDADE PARA O SERVICE
            funcionario_dto = FuncionarioService.autenticar(login=login_informado, senha=senha_informada)

            if funcionario_dto:
                # O Controller apenas gere a Sessão HTTP
                request.session['funcionario_id'] = funcionario_dto.id_funcionario
                request.session['funcionario_nome'] = funcionario_dto.nome
                request.session['funcionario_cargo'] = funcionario_dto.cargo
                
                return JsonResponse({'status': 'sucesso', 'mensagem': 'Login aprovado.'})
            else:
                return JsonResponse({'status': 'erro', 'mensagem': 'Matrícula ou senha incorretos.'}, status=401)
                
        except Exception as e:
            return JsonResponse({'status': 'erro', 'mensagem': str(e)}, status=500)

class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('tela_login')