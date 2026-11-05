from django.db.models import Q
from django.utils import timezone

from ..models import AuditoriaLog


class AuditoriaService:
    @staticmethod
    def listar(busca: str = '', limite: int = 300) -> list:
        qs = AuditoriaLog.objects.all()
        busca = (busca or '').strip()
        if busca:
            qs = qs.filter(Q(funcionario_nome__icontains=busca) | Q(entidade__icontains=busca)
                           | Q(acao__icontains=busca) | Q(descricao__icontains=busca))
        return [
            {'id': l.id_log, 'quando': timezone.localtime(l.criado_em).isoformat(), 'usuario': l.funcionario_nome or '—',
             'acao': l.acao, 'entidade': l.entidade, 'entidade_id': l.entidade_id, 'descricao': l.descricao}
            for l in qs[:max(1, min(int(limite), 1000))]
        ]
