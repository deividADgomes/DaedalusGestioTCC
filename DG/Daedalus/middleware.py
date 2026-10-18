from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect


class AutenticacaoMiddleware:
    """
    Controle de acesso do Daedalus Gestio (RF10, RF12, RF14 e RNF05).

    - Todas as rotas, exceto login, logout e arquivos estáticos, exigem sessão ativa.
    - Enquanto o usuário estiver no primeiro acesso, só pode trocar a senha ou sair.
    - Apenas Administrador e Gestor acessam a tela de funcionários e podem
      criar ou alterar funcionários (a listagem GET fica liberada porque o
      formulário de triagem precisa dela).
    """

    ROTAS_PUBLICAS = ('/', '/api/login/', '/api/recuperar-senha/', '/logout/')
    PREFIXOS_PUBLICOS = ('/admin/',)
    ROTAS_PRIMEIRO_ACESSO = ('/primeiro-acesso/', '/api/alterar-senha/', '/logout/')
    CARGOS_ADMIN = ('Administrador', 'Gestor')

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixo_static = '/' + settings.STATIC_URL.strip('/') + '/'

    def __call__(self, request):
        path = request.path

        # Garante o cookie csrftoken em todas as páginas (o front envia no cabeçalho X-CSRFToken)
        get_token(request)

        if self._publica(path):
            return self.get_response(request)

        if not request.session.get('funcionario_id'):
            return self._negar(request, 401, 'Sessão expirada. Faça login novamente.', '/')

        if request.session.get('primeiro_acesso') and path not in self.ROTAS_PRIMEIRO_ACESSO:
            return self._negar(request, 403, 'Altere a senha provisória para continuar.', '/primeiro-acesso/')

        if self._exige_admin(request) and request.session.get('funcionario_cargo') not in self.CARGOS_ADMIN:
            return self._negar(request, 403, 'Acesso restrito a Administrador ou Gestor.', '/principal/')

        return self.get_response(request)

    def _publica(self, path):
        return (
            path in self.ROTAS_PUBLICAS
            or path.startswith(self.prefixo_static)
            or path.startswith(self.PREFIXOS_PUBLICOS)
        )

    @staticmethod
    def _exige_admin(request):
        if request.path in ('/gerenciar-funcionario/', '/api/solicitacoes-senha/'):
            return True
        return request.path == '/api/funcionario/' and request.method != 'GET'

    @staticmethod
    def _negar(request, status, mensagem, destino):
        if request.path.startswith('/api/'):
            return JsonResponse({'status': 'erro', 'mensagem': mensagem}, status=status)
        return redirect(destino)
