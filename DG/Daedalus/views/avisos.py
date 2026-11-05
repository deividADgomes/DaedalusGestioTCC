from django.http import JsonResponse
from django.views import View

from ..services.avisos import AvisosService, BuscaService
from .utils import erro_interno


class AvisosView(View):
    """GET: avisos do sino (consultado ao abrir a página e ao clicar no sino; nunca em intervalo, para não renovar a sessão)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dado': AvisosService.listar(request.session.get('funcionario_cargo', ''))})
        except Exception as e:
            return erro_interno(e)


class BuscaView(View):
    """GET ?q=: busca global por ticket, número de série, NF, laudo ou chamado RFB."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': BuscaService.buscar(request.GET.get('q'))})
        except Exception as e:
            return erro_interno(e)


class SessaoPingView(View):
    """GET: só renova a sessão. A tela chama quando o usuário está ativo (digitando, rolando), para não perder um formulário longo."""
    def get(self, request):
        return JsonResponse({'status': 'sucesso'})
