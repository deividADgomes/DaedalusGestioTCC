from django.http import JsonResponse
from django.views import View

from ..services.auditoria import AuditoriaService
from .utils import erro_interno


class AuditoriaView(View):
    """GET ?q=: últimas gravações e exclusões de cadastros (acesso restrito a Administrador/Gestor)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dados': AuditoriaService.listar(request.GET.get('q'), request.GET.get('limite') or 300)})
        except ValueError:
            return JsonResponse({'status': 'erro', 'mensagem': 'Limite inválido.'}, status=400)
        except Exception as e:
            return erro_interno(e)
