import json
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from .analytics import FiltroInvalido, exportar_csv, montar_dashboard
from .dtos import (
    CARGOS_DE_GESTAO,
    CargoFuncionario,
    EmpresaDTO,
    EquipamentoDTO,
    FuncionarioDTO,
    StatusPeca,
    TecnicoDTO,
    TipoEmpresa,
    TriagemDTO,
)
from .models import Equipamento, FotoTriagem, Funcionario, Triagem
from .partsurfer import PartSurferError
from .services import (
    EmpresaService,
    EquipamentoService,
    FotoService,
    FuncionarioService,
    LimiteConsultasExcedido,
    SolicitacaoSenhaService,
    TecnicoService,
    TriagemService,
)

CONTENT_TYPE_DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
MENSAGEM_SESSAO_EXPIRADA = 'Sessão expirada. Faça login novamente.'


def _sucesso(**campos):
    return JsonResponse({'status': 'sucesso', **campos})


def _erro(mensagem, status):
    return JsonResponse({'status': 'erro', 'mensagem': mensagem}, status=status)


def _corpo_json(request):
    return json.loads(request.body)


def _valor(enum_ou_texto):
    return getattr(enum_ou_texto, 'value', enum_ou_texto)


def _inteiro_ou_none(valor):
    return int(valor) if valor else None


def responder_erro_inesperado(metodo):
    @wraps(metodo)
    def envelope(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except Exception as erro:
            return _erro(str(erro), 500)

    return envelope


class EmpresaView(View):
    @responder_erro_inesperado
    def get(self, request):
        tipo = request.GET.get('tipo')
        empresas = EmpresaService.listar(tipo_filtro=int(tipo)) if tipo else EmpresaService.listar()
        dados = [
            {
                'id': empresa.id_empresa,
                'razao_social': empresa.razao_social,
                'cnpj': empresa.cnpj,
                'tipo': empresa.tipo,
            }
            for empresa in empresas
        ]
        return _sucesso(dados=dados)

    @responder_erro_inesperado
    def post(self, request):
        try:
            corpo = _corpo_json(request)
            dto = EmpresaDTO(
                id_empresa=corpo.get('id'),
                cnpj=corpo.get('cnpj'),
                razao_social=corpo.get('razaoSocial'),
                tipo=TipoEmpresa(int(corpo.get('tipo'))),
            )
            salvo = EmpresaService.salvar(dto)
        except ValueError as erro:
            return _erro(f"Dados inválidos: {erro}", 400)
        return _sucesso(mensagem='Empresa salva com sucesso!', id_gerado=salvo.id_empresa)


class TecnicoView(View):
    @responder_erro_inesperado
    def get(self, request):
        dados = [
            {'id': tecnico.id_tecnico, 'nome': tecnico.nome, 'nome_empresa': tecnico.nome_empresa}
            for tecnico in TecnicoService.listar()
        ]
        return _sucesso(dados=dados)

    @responder_erro_inesperado
    def post(self, request):
        corpo = _corpo_json(request)
        TecnicoService.salvar(TecnicoDTO(
            id_tecnico=corpo.get('id'),
            nome=corpo.get('nome'),
            id_empresa=corpo.get('id_empresa'),
        ))
        return _sucesso(mensagem='Técnico salvo com sucesso!')


class FuncionarioView(View):
    @responder_erro_inesperado
    def get(self, request):
        dados = [
            {
                'id': funcionario.id_funcionario,
                'nome': funcionario.nome,
                'cargo': _valor(funcionario.cargo),
                'login': funcionario.login,
                'email': funcionario.email,
                'primeiroAcesso': funcionario.primeiro_acesso,
            }
            for funcionario in FuncionarioService.listar()
        ]
        return _sucesso(dados=dados)

    @staticmethod
    def _gestor_mexe_em_cargo_de_gestao(request, dto):
        if request.session.get('funcionario_cargo') != CargoFuncionario.GESTOR.value:
            return False
        alvo = Funcionario.objects.filter(pk=dto.id_funcionario).first() if dto.id_funcionario else None
        return dto.cargo.value in CARGOS_DE_GESTAO or (alvo is not None and alvo.cargo in CARGOS_DE_GESTAO)

    @responder_erro_inesperado
    def post(self, request):
        try:
            corpo = _corpo_json(request)
            dto = FuncionarioDTO(
                id_funcionario=corpo.get('id'),
                nome=corpo.get('nome'),
                cargo=CargoFuncionario(corpo.get('cargo')),
                login=int(corpo.get('login')),
                senha=corpo.get('senha'),
                email=corpo.get('email'),
            )
            if self._gestor_mexe_em_cargo_de_gestao(request, dto):
                return _erro('Gestor não pode criar ou alterar Gestor/Administrador.', 403)
            salvo = FuncionarioService.salvar(dto)
        except ValueError as erro:
            return _erro(f"Dados inválidos: {erro}", 400)
        return _sucesso(mensagem='Funcionário salvo com sucesso!', id_gerado=salvo.id_funcionario)


class EquipamentoView(View):
    @responder_erro_inesperado
    def get(self, request):
        dados = [
            {
                'id': equipamento.id_equipamento,
                'pn': equipamento.pn,
                'modelo': equipamento.modelo,
                'total_pecas': equipamento.total_pecas,
            }
            for equipamento in EquipamentoService.listar()
        ]
        return _sucesso(dados=dados)

    @responder_erro_inesperado
    def post(self, request):
        try:
            corpo = _corpo_json(request)
            salvo = EquipamentoService.salvar(EquipamentoDTO(
                id_equipamento=corpo.get('id'),
                pn=corpo.get('pn'),
                modelo=corpo.get('modelo'),
            ))
        except ValueError as erro:
            return _erro(f"Dados inválidos: {erro}", 400)
        return _sucesso(mensagem='Equipamento salvo com sucesso!', id_gerado=salvo.id_equipamento)


class PecasEquipamentoView(View):
    @responder_erro_inesperado
    def get(self, request):
        try:
            id_equipamento = int(request.GET.get('id_equipamento'))
            return _sucesso(dados=EquipamentoService.listar_pecas(id_equipamento))
        except (TypeError, ValueError):
            return _erro('Equipamento inválido.', 400)
        except Equipamento.DoesNotExist:
            return _erro('Equipamento não encontrado.', 404)

    @responder_erro_inesperado
    def post(self, request):
        try:
            corpo = _corpo_json(request)
            dados = EquipamentoService.salvar_pecas(int(corpo.get('id_equipamento')), corpo.get('pecas'))
            return _sucesso(mensagem='Peças do modelo salvas!', dados=dados)
        except (TypeError, ValueError) as erro:
            return _erro(f"Dados inválidos: {erro}", 400)
        except Equipamento.DoesNotExist:
            return _erro('Equipamento não encontrado.', 404)


class ConsultarPartSurferView(View):
    @responder_erro_inesperado
    def post(self, request, id_equipamento):
        try:
            candidatas = EquipamentoService.consultar_partsurfer(id_equipamento)
        except Equipamento.DoesNotExist:
            return _erro('Equipamento não encontrado.', 404)
        except LimiteConsultasExcedido as erro:
            return _erro(str(erro), 429)
        except ValueError as erro:
            return _erro(str(erro), 404)
        except PartSurferError as erro:
            return _erro(f'Falha ao consultar o PartSurfer: {erro}', 502)

        retornadas = sum(1 for candidata in candidatas if not candidata['somente_local'])
        return _sucesso(mensagem=f'O PartSurfer retornou {retornadas} peça(s).', dados=candidatas)


class FotoTriagemView(View):
    @responder_erro_inesperado
    def get(self, request):
        try:
            return _sucesso(dados=FotoService.listar(int(request.GET.get('id_triagem'))))
        except (TypeError, ValueError):
            return _erro('Triagem inválida.', 400)

    @responder_erro_inesperado
    def post(self, request):
        try:
            arquivo = request.FILES.get('arquivo')
            if arquivo is None:
                raise ValueError("Nenhuma foto enviada.")
            foto = FotoService.adicionar(
                int(request.POST.get('id_triagem')), arquivo, request.POST.get('legenda', '')
            )
            return _sucesso(mensagem='Foto adicionada!', dado=foto)
        except Triagem.DoesNotExist:
            return _erro('Triagem não encontrada.', 404)
        except (TypeError, ValueError) as erro:
            return _erro(str(erro), 400)

    @responder_erro_inesperado
    def delete(self, request):
        try:
            FotoService.excluir(int(request.GET.get('id')))
            return _sucesso(mensagem='Foto removida.')
        except (TypeError, ValueError):
            return _erro('Foto inválida.', 400)
        except ObjectDoesNotExist as erro:
            return _erro(str(erro), 404)


def entregar_foto(request, id_foto):
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
    @staticmethod
    def _detalhar(triagem):
        return {
            'id': triagem.id_triagem,
            'n_ticket': triagem.n_ticket,
            'nf': triagem.nf,
            'cidade': triagem.cidade,
            'estado': triagem.estado,
            'sn': triagem.sn,
            'status_peca': int(triagem.status_peca),
            'troca': triagem.troca,
            'id_equipamento': triagem.id_equipamento,
            'id_peca_trocada': triagem.id_peca_trocada,
            'peca_trocada': triagem.peca_trocada,
            'fotos': FotoService.listar(triagem.id_triagem),
            'defeito_usuario': triagem.defeito_usuario,
            'defeito_tecnico': triagem.defeito_tecnico,
            'defeito_constatado': triagem.defeito_constatado,
            'testes': triagem.testes,
            'analise': triagem.analise,
            'conclusao': triagem.conclusao,
            'nome_cliente': triagem.nome_cliente,
            'nome_equipamento': triagem.nome_equipamento,
            'nome_tecnico': triagem.nome_tecnico,
            'data_triagem': triagem.data_triagem.isoformat() if triagem.data_triagem else None,
            'nome_analista': triagem.nome_analista_triagem,
            'nome_analista_chamado': triagem.nome_analista_chamado,
        }

    @staticmethod
    def _resumir(triagem):
        return {
            'id': triagem.id_triagem,
            'n_ticket': triagem.n_ticket,
            'sn': triagem.sn,
            'status_peca': int(triagem.status_peca),
            'nome_cliente': triagem.nome_cliente,
            'defeito_usuario': triagem.defeito_usuario,
            'defeito_tecnico': triagem.defeito_tecnico,
            'conclusao': triagem.conclusao,
            'nome_analista': triagem.nome_analista_triagem,
        }

    @staticmethod
    def _montar_dto(corpo, id_analista_triagem):
        return TriagemDTO(
            id_triagem=corpo.get('id') or None,
            n_ticket=int(corpo.get('n_ticket')),
            nf=int(corpo.get('nf')),
            cidade=corpo.get('cidade'),
            estado=corpo.get('estado'),
            id_cliente=int(corpo.get('id_cliente')),
            id_equipamento=int(corpo.get('id_equipamento')),
            id_tecnico=int(corpo.get('id_tecnico')),
            id_analista_chamado=int(corpo.get('id_analista')),
            id_analista_triagem=id_analista_triagem,
            sn=corpo.get('sn'),
            status_peca=StatusPeca(int(corpo.get('status_peca'))),
            troca=corpo.get('troca'),
            id_peca_trocada=_inteiro_ou_none(corpo.get('id_peca_trocada')),
            defeito_usuario=corpo.get('defeito_usuario'),
            defeito_tecnico=corpo.get('defeito_tecnico'),
            defeito_constatado=corpo.get('defeito_constatado'),
            testes=corpo.get('testes'),
            analise=corpo.get('analise'),
            conclusao=corpo.get('conclusao'),
        )

    @responder_erro_inesperado
    def get(self, request):
        id_triagem = request.GET.get('id')
        if id_triagem:
            triagem = TriagemService.buscar_por_id(int(id_triagem))
            if not triagem:
                return _erro('Não encontrado', 404)
            return _sucesso(dado=self._detalhar(triagem))

        return _sucesso(dados=[self._resumir(triagem) for triagem in TriagemService.listar()])

    @responder_erro_inesperado
    def post(self, request):
        id_analista_logado = request.session.get('funcionario_id')
        if not id_analista_logado:
            return _erro(MENSAGEM_SESSAO_EXPIRADA, 401)

        try:
            dto = self._montar_dto(_corpo_json(request), id_analista_logado)
            salvo = TriagemService.salvar(dto)
        except ValueError as erro:
            return _erro(f"Erro de validação: {erro}", 400)
        return _sucesso(mensagem='Triagem salva com sucesso!', id_gerado=salvo.id_triagem)


class ExportarTriagemDocxView(View):
    @responder_erro_inesperado
    def get(self, request):
        buffer, nome_arquivo = TriagemService.gerar_docx(int(request.GET.get('id')))
        resposta = HttpResponse(buffer.getvalue(), content_type=CONTENT_TYPE_DOCX)
        resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        return resposta


class DashboardView(View):
    def get(self, request):
        try:
            dados = montar_dashboard(request.GET)
        except FiltroInvalido as erro:
            return _erro(str(erro), 400)
        except Exception as erro:
            return _erro(str(erro), 500)
        return _sucesso(vazio=dados['vazio'], dados=dados)


class DashboardExportarView(View):
    def get(self, request):
        try:
            conteudo = exportar_csv(request.GET)
        except FiltroInvalido as erro:
            return _erro(str(erro), 400)
        except Exception as erro:
            return _erro(str(erro), 500)
        resposta = HttpResponse(conteudo, content_type='text/csv; charset=utf-8')
        resposta['Content-Disposition'] = 'attachment; filename="triagens_daedalus.csv"'
        return resposta


class LoginView(View):
    def get(self, request):
        if request.session.get('funcionario_id'):
            return redirect('/principal/')
        return render(request, 'Daedalus/login/login.html')


class LoginAPIView(View):
    @responder_erro_inesperado
    def post(self, request):
        dados = _corpo_json(request)
        login_informado = dados.get('login')
        senha_informada = dados.get('senha')

        if not login_informado or not senha_informada:
            return _erro('Credenciais em branco.', 400)

        try:
            login_informado = int(login_informado)
        except (TypeError, ValueError):
            return _erro('Matrícula ou senha incorretos.', 401)

        funcionario = FuncionarioService.autenticar(login=login_informado, senha=senha_informada)
        if not funcionario:
            return _erro('Matrícula ou senha incorretos.', 401)

        request.session['funcionario_id'] = funcionario.id_funcionario
        request.session['funcionario_login'] = funcionario.login
        request.session['funcionario_nome'] = funcionario.nome
        request.session['funcionario_cargo'] = funcionario.cargo
        request.session['primeiro_acesso'] = funcionario.primeiro_acesso
        return _sucesso(mensagem='Login aprovado.', primeiro_acesso=funcionario.primeiro_acesso)


class AlterarSenhaView(View):
    @responder_erro_inesperado
    def post(self, request):
        id_logado = request.session.get('funcionario_id')
        if not id_logado:
            return _erro(MENSAGEM_SESSAO_EXPIRADA, 401)

        try:
            dados = _corpo_json(request)
            FuncionarioService.alterar_senha(
                id_funcionario=id_logado,
                senha_atual=dados.get('senha_atual'),
                nova_senha=dados.get('nova_senha'),
            )
        except ValueError as erro:
            return _erro(str(erro), 400)

        request.session['primeiro_acesso'] = False
        return _sucesso(mensagem='Senha alterada com sucesso.')


class RecuperarSenhaView(View):
    MENSAGEM_PADRAO = (
        'Se a matrícula e o e-mail estiverem corretos, '
        'o administrador foi avisado por e-mail e vai redefinir sua senha.'
    )

    @responder_erro_inesperado
    def post(self, request):
        dados = _corpo_json(request)
        try:
            login = int(dados.get('login'))
        except (TypeError, ValueError):
            login = None

        if login is not None:
            SolicitacaoSenhaService.registrar(login, dados.get('email'))
        return _sucesso(mensagem=self.MENSAGEM_PADRAO)


class SolicitacoesSenhaView(View):
    def get(self, request):
        return _sucesso(dados=SolicitacaoSenhaService.listar_pendentes())


class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('tela_login')
