from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from ..services import FuncionarioService, SolicitacaoSenhaService
from .utils import erro_interno, ler_json, resposta_erro

MAX_FALHAS_LOGIN = 5
BLOQUEIO_LOGIN_SEGUNDOS = 15 * 60
MAX_PEDIDOS_SENHA = 5            # pedidos de recuperação por IP
JANELA_PEDIDOS_SENHA = 15 * 60   # ... a cada 15 minutos
MENSAGEM_PEDIDO_SENHA = ('Se a matrícula e o e-mail estiverem corretos, o administrador foi avisado '
                         'por e-mail e vai redefinir sua senha.')


def _chave_falhas(request, login) -> str:
    return f"login_falhas:{request.META.get('REMOTE_ADDR', '')}:{login}"


# ==========================================
# AUTENTICAÇÃO E LOGIN
# ==========================================
@method_decorator(ensure_csrf_cookie, name='dispatch')
class LoginView(View):
    def get(self, request):
        if request.session.get('funcionario_id'):
            return redirect('/principal/')
        return render(request, 'Daedalus/Login/login.html')


class LoginAPIView(View):
    def post(self, request):
        try:
            dados = ler_json(request)
            login_informado = dados.get('login')
            senha_informada = dados.get('senha')

            if not login_informado or not senha_informada:
                return resposta_erro('Credenciais em branco.', 400)

            chave = _chave_falhas(request, login_informado)
            if cache.get(chave, 0) >= MAX_FALHAS_LOGIN:
                return resposta_erro('Muitas tentativas incorretas. Aguarde 15 minutos e tente novamente.', 429)

            funcionario_dto = FuncionarioService.autenticar(login=login_informado, senha=senha_informada)

            if not funcionario_dto:
                cache.add(chave, 0, BLOQUEIO_LOGIN_SEGUNDOS)
                try:
                    cache.incr(chave)
                except ValueError:
                    cache.set(chave, 1, BLOQUEIO_LOGIN_SEGUNDOS)
                return resposta_erro('Matrícula ou senha incorretos.', 401)

            cache.delete(chave)
            request.session.cycle_key()  # nova sessão após o login (evita fixação de sessão)
            request.session['funcionario_id'] = funcionario_dto.id_funcionario
            request.session['funcionario_nome'] = funcionario_dto.nome
            request.session['funcionario_cargo'] = funcionario_dto.cargo
            request.session['primeiro_acesso'] = funcionario_dto.primeiro_acesso
            return JsonResponse({
                'status': 'sucesso',
                'mensagem': 'Login aprovado.',
                'primeiro_acesso': funcionario_dto.primeiro_acesso,
            })
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class AlterarSenhaAPIView(View):
    def post(self, request):
        try:
            dados = ler_json(request)
            FuncionarioService.trocar_senha(
                request.session['funcionario_id'],
                dados.get('senha_atual') or '',
                dados.get('nova_senha') or '',
            )
            request.session['primeiro_acesso'] = False
            return JsonResponse({'status': 'sucesso', 'mensagem': 'Senha alterada com sucesso!'})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class RecuperarSenhaView(View):
    """
    Pública (tela de login). O usuário informa matrícula e e-mail e o administrador é avisado por e-mail.
    A resposta é sempre a mesma, exista ou não a matrícula, e há limite de pedidos por IP.
    """
    def post(self, request):
        try:
            chave = f"recuperar_senha:{request.META.get('REMOTE_ADDR', '')}"
            cache.add(chave, 0, JANELA_PEDIDOS_SENHA)
            try:
                tentativas = cache.incr(chave)
            except ValueError:
                cache.set(chave, 1, JANELA_PEDIDOS_SENHA)
                tentativas = 1
            if tentativas > MAX_PEDIDOS_SENHA:
                return resposta_erro('Muitos pedidos seguidos. Aguarde 15 minutos e tente novamente.', 429)

            dados = ler_json(request)
            SolicitacaoSenhaService.registrar(dados.get('login'), dados.get('email'))
            return JsonResponse({'status': 'sucesso', 'mensagem': MENSAGEM_PEDIDO_SENHA})
        except ValueError as ve:
            return resposta_erro(str(ve), 400)
        except Exception as e:
            return erro_interno(e)


class SolicitacoesSenhaView(View):
    """GET: pedidos de redefinição pendentes (acesso restrito a Administrador/Gestor por DAEDALUS_PERMISSOES)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': SolicitacaoSenhaService.listar_pendentes()})
        except Exception as e:
            return erro_interno(e)


class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('tela_login')
