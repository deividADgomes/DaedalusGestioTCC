"""Controle de estoque das peças (etapa 1: saldo, entradas, saídas, contagem e estoque mínimo)."""
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from ..models import EstoquePeca, Funcionario, MovimentoEstoque, Peca
from .pecas import _parse_valor

LIMITE_QUANTIDADE = 1_000_000
CENTAVOS = Decimal('0.01')


def _situacao(e: EstoquePeca) -> str:
    if e.saldo <= 0:
        return 'sem_saldo'
    if e.minimo and e.saldo < e.minimo:
        return 'abaixo'
    return 'ok'


def _para_dict(e: EstoquePeca) -> dict:
    return {
        'id_peca': e.peca_id, 'part_number': e.peca.part_number, 'descricao': e.peca.descricao,
        'equipamento_completo': e.peca.equipamento_completo, 'saldo': e.saldo, 'minimo': e.minimo, 'local': e.local,
        'custo_medio': float(e.custo_medio), 'valor_total': float(max(e.saldo, 0) * e.custo_medio), 'situacao': _situacao(e),
    }


def _quantidade(valor, minimo: int) -> int:
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError("Informe a quantidade com um número inteiro.")
    if n < minimo:
        raise ValueError("A quantidade deve ser maior que zero." if minimo > 0 else "A quantidade não pode ser negativa.")
    if n > LIMITE_QUANTIDADE:
        raise ValueError("Quantidade acima do limite permitido.")
    return n


class EstoqueService:
    @staticmethod
    def listar(busca: str = '', situacao: str = 'todos') -> dict:
        qs = EstoquePeca.objects.select_related('peca')
        todos = [_para_dict(e) for e in qs.order_by('peca__part_number')]
        resumo = {
            'itens': len(todos), 'valor_total': round(sum(i['valor_total'] for i in todos), 2),
            'abaixo_minimo': sum(1 for i in todos if i['minimo'] > 0 and i['saldo'] < i['minimo']),
            'sem_saldo': sum(1 for i in todos if i['saldo'] <= 0),
        }
        busca = (busca or '').strip().lower()
        itens = [i for i in todos if not busca or busca in i['part_number'].lower()
                 or busca in (i['descricao'] or '').lower() or busca in i['local'].lower()]
        if situacao == 'abaixo':
            itens = [i for i in itens if i['minimo'] > 0 and i['saldo'] < i['minimo']]
        elif situacao == 'sem_saldo':
            itens = [i for i in itens if i['situacao'] == 'sem_saldo']
        return {'dados': itens, 'resumo': resumo}

    @staticmethod
    def catalogo(busca: str) -> list:
        """Peças do catálogo para escolher numa nova entrada (as que já têm estoque vêm marcadas)."""
        busca = (busca or '').strip()
        if len(busca) < 2:
            return []
        pecas = Peca.objects.filter(Q(part_number__icontains=busca) | Q(descricao__icontains=busca)).order_by('part_number')[:10]
        saldos = dict(EstoquePeca.objects.filter(peca__in=pecas).values_list('peca_id', 'saldo'))
        return [{'id_peca': p.id_peca, 'part_number': p.part_number, 'descricao': p.descricao,
                 'controlada': p.id_peca in saldos, 'saldo': saldos.get(p.id_peca, 0)} for p in pecas]

    @staticmethod
    def movimentar(id_peca: int, tipo: str, quantidade, custo=None, motivo: str = '', id_funcionario=None, referencia: str = '') -> dict:
        if tipo not in ('entrada', 'saida', 'contagem'):
            raise ValueError("Tipo de movimento inválido.")
        quantidade = _quantidade(quantidade, 0 if tipo == 'contagem' else 1)
        motivo = ' '.join((motivo or '').split())[:300]
        if tipo in ('saida', 'contagem') and not motivo:
            raise ValueError("Informe o motivo (para quê a peça saiu, ou por que o saldo foi ajustado).")
        custo_unitario = _parse_valor(custo) if (tipo == 'entrada' and str(custo or '').strip()) else None

        peca = Peca.objects.get(pk=id_peca)
        funcionario = Funcionario.objects.filter(pk=id_funcionario).first()
        with transaction.atomic():
            estoque, _ = EstoquePeca.objects.get_or_create(peca=peca)
            estoque = EstoquePeca.objects.select_for_update().select_related('peca').get(pk=estoque.pk)

            if tipo == 'entrada':
                delta = quantidade
                novo_saldo = estoque.saldo + delta
                if custo_unitario is not None:
                    base = max(estoque.saldo, 0)
                    estoque.custo_medio = ((base * estoque.custo_medio + delta * custo_unitario) / (base + delta)).quantize(CENTAVOS)
            elif tipo == 'saida':
                if quantidade > estoque.saldo:
                    raise ValueError(f"Saldo insuficiente: há {estoque.saldo} unidade(s) em estoque.")
                delta = -quantidade
                novo_saldo = estoque.saldo + delta
            else:  # contagem: a quantidade informada é o saldo contado
                delta = quantidade - estoque.saldo
                if delta == 0:
                    raise ValueError("A contagem é igual ao saldo atual; não há o que ajustar.")
                novo_saldo = quantidade

            estoque.saldo = novo_saldo
            estoque.save()
            MovimentoEstoque.objects.create(
                peca=peca, tipo=tipo, quantidade=delta, saldo_apos=novo_saldo, custo_unitario=custo_unitario, motivo=motivo, referencia=(referencia or '')[:30],
                funcionario=funcionario, funcionario_nome=funcionario.nome if funcionario else '')
        return _para_dict(estoque)

    @staticmethod
    def configurar(id_peca: int, minimo, local: str) -> dict:
        minimo = _quantidade(0 if minimo in (None, '') else minimo, 0)
        local = ' '.join((local or '').split())
        if len(local) > 100:
            raise ValueError("O local pode ter no máximo 100 caracteres.")
        peca = Peca.objects.get(pk=id_peca)
        with transaction.atomic():
            estoque, _ = EstoquePeca.objects.get_or_create(peca=peca)
            estoque.minimo, estoque.local = minimo, local
            estoque.save(update_fields=['minimo', 'local', 'atualizado_em'])
        return _para_dict(EstoquePeca.objects.select_related('peca').get(pk=estoque.pk))

    @staticmethod
    def historico(id_peca: int, limite: int = 100) -> list:
        peca = Peca.objects.get(pk=id_peca)
        return [
            {'id': m.id_movimento, 'quando': timezone.localtime(m.criado_em).isoformat(), 'tipo': m.get_tipo_display(),
             'quantidade': m.quantidade, 'saldo_apos': m.saldo_apos,
             'custo_unitario': float(m.custo_unitario) if m.custo_unitario is not None else None,
             'motivo': m.motivo, 'referencia': m.referencia, 'usuario': m.funcionario_nome or '—'}
            for m in peca.movimentos_estoque.all()[:limite]
        ]

    @staticmethod
    def abaixo_do_minimo() -> int:
        return EstoquePeca.objects.filter(minimo__gt=0, saldo__lt=F('minimo')).count()
