import logging

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect

from .models import Funcionario

logger = logging.getLogger(__name__)

# Rotas que funcionam sem login.
ROTAS_PUBLICAS_EXATAS = {'/', '/api/login/', '/api/recuperar-senha/', '/logout/'}
ROTAS_PUBLICAS_PREFIXOS = ('/static/', '/admin/')

# Com a senha provisória (primeiro acesso), só estas rotas de API ficam liberadas.
ROTAS_LIBERADAS_NO_PRIMEIRO_ACESSO = {'/api/alterar-senha/'}


def _resposta_json(mensagem, status, **extra):
    return JsonResponse({'status': 'erro', 'mensagem': mensagem, **extra}, status=status)


class AutenticacaoMiddleware:
    """
    Exige login em todas as páginas e APIs (exceto as públicas) e aplica as permissões
    por cargo definidas em settings.DAEDALUS_PERMISSOES.

    O cargo é lido do banco a cada requisição, então uma mudança de cargo (ou a exclusão
    do usuário) vale imediatamente, sem depender do que ficou guardado na sessão.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho = request.path
        if caminho in ROTAS_PUBLICAS_EXATAS or caminho.startswith(ROTAS_PUBLICAS_PREFIXOS):
            return self.get_response(request)

        eh_api = caminho.startswith('/api/')
        id_funcionario = request.session.get('funcionario_id')
        dados = None
        if id_funcionario:
            dados = Funcionario.objects.filter(pk=id_funcionario).values('cargo', 'nome', 'primeiro_acesso', 'email').first()

        if not dados:
            request.session.flush()
            if eh_api:
                return _resposta_json('Sessão expirada. Faça login novamente.', 401)
            return redirect('tela_login')

        # Mantém a sessão em dia com o banco (cargo/nome podem ter mudado).
        if request.session.get('funcionario_cargo') != dados['cargo']:
            request.session['funcionario_cargo'] = dados['cargo']
        if request.session.get('funcionario_nome') != dados['nome']:
            request.session['funcionario_nome'] = dados['nome']
        request.session['primeiro_acesso'] = bool(dados['primeiro_acesso'])
        request.funcionario_cargo = dados['cargo']
        request.funcionario_nome = dados['nome']
        request.funcionario_email = dados['email']

        if dados['primeiro_acesso'] and eh_api and caminho not in ROTAS_LIBERADAS_NO_PRIMEIRO_ACESSO:
            return _resposta_json('Troque a senha provisória para continuar.', 403, codigo='trocar_senha')

        for prefixo, metodos, cargos in getattr(settings, 'DAEDALUS_PERMISSOES', []):
            if caminho.startswith(prefixo) and (metodos is None or request.method in metodos):
                if dados['cargo'] not in cargos:
                    logger.warning("Acesso negado: funcionario=%s cargo=%s %s %s",
                                   id_funcionario, dados['cargo'], request.method, caminho)
                    return _resposta_json('Seu cargo não tem permissão para esta ação.', 403)
                break

        if not eh_api and request.method == 'GET':
            get_token(request)  # garante o cookie do CSRF para os fetch() da página

        return self.get_response(request)
