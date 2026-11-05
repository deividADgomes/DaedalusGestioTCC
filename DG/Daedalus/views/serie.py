from django.http import JsonResponse
from django.views import View

from ..services.serie import SerieService
from .utils import erro_interno


class TriagemPorSerieView(View):
    """GET ?sn=&excluir=: triagens anteriores do mesmo número de série (aviso de reincidência)."""
    def get(self, request):
        try:
            excluir = int(request.GET.get('excluir') or 0) or None
            return JsonResponse({'status': 'sucesso', 'dados': SerieService.triagens_da_serie(request.GET.get('sn'), excluir)})
        except ValueError:
            return JsonResponse({'status': 'sucesso', 'dados': []})
        except Exception as e:
            return erro_interno(e)


class SerieView(View):
    """GET ?sn=: linha do tempo do número de série (triagens, laudos e chamados RFB)."""
    def get(self, request):
        try:
            return JsonResponse({'status': 'sucesso', 'dado': SerieService.linha_do_tempo(request.GET.get('sn'))})
        except ValueError as ve:
            return JsonResponse({'status': 'erro', 'mensagem': str(ve)}, status=400)
        except Exception as e:
            return erro_interno(e)
