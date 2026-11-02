from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect

from .dtos import CARGOS_DE_GESTAO


class AutenticacaoMiddleware:
    ROTAS_PUBLICAS = ('/', '/api/login/', '/api/recuperar-senha/', '/logout/')
    PREFIXOS_PUBLICOS = ('/admin/',)
    ROTAS_PRIMEIRO_ACESSO = ('/primeiro-acesso/', '/api/alterar-senha/', '/logout/')
    ROTAS_SOMENTE_GESTAO = ('/gerenciar-funcionario/', '/api/solicitacoes-senha/')
    ROTA_API_FUNCIONARIO = '/api/funcionario/'

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixo_static = '/' + settings.STATIC_URL.strip('/') + '/'

    def __call__(self, request):
        get_token(request)

        if self._eh_publica(request.path):
            return self.get_response(request)

        if not request.session.get('funcionario_id'):
            return self._negar(request, 401, 'Sessão expirada. Faça login novamente.', '/')

        if request.session.get('primeiro_acesso') and request.path not in self.ROTAS_PRIMEIRO_ACESSO:
            return self._negar(request, 403, 'Altere a senha provisória para continuar.', '/primeiro-acesso/')

        if self._exige_gestao(request) and request.session.get('funcionario_cargo') not in CARGOS_DE_GESTAO:
            return self._negar(request, 403, 'Acesso restrito a Administrador ou Gestor.', '/principal/')

        return self.get_response(request)

    def _eh_publica(self, caminho):
        return (
            caminho in self.ROTAS_PUBLICAS
            or caminho.startswith(self.prefixo_static)
            or caminho.startswith(self.PREFIXOS_PUBLICOS)
        )

    def _exige_gestao(self, request):
        if request.path in self.ROTAS_SOMENTE_GESTAO:
            return True
        return request.path == self.ROTA_API_FUNCIONARIO and request.method != 'GET'

    @staticmethod
    def _negar(request, status, mensagem, destino):
        if request.path.startswith('/api/'):
            return JsonResponse({'status': 'erro', 'mensagem': mensagem}, status=status)
        return redirect(destino)
