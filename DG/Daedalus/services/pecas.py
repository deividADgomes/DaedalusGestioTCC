from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from ..dtos import TipoEmpresa
from ..models import CotacaoPeca, Empresa, Funcionario, Peca


def cotacao_para_dict(cotacao: Optional[CotacaoPeca]) -> Optional[dict]:
    if cotacao is None:
        return None
    return {
        'id': cotacao.id_cotacao,
        'peca_id': cotacao.peca_id,
        'fornecedor_id': cotacao.fornecedor_id,
        'fornecedor': cotacao.fornecedor.razao_social,
        'valor': float(cotacao.valor),
        'data_cotacao': cotacao.data_cotacao.isoformat(),
        'observacao': cotacao.observacao,
    }


def _parse_valor(valor) -> Decimal:
    try:
        texto = str(valor).strip().replace('R$', '').replace(' ', '')
        # aceita "1.234,56" e "1234.56"
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        numero = Decimal(texto)
    except (InvalidOperation, AttributeError):
        raise ValueError("Valor inválido.")
    if not numero.is_finite() or numero <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    if numero >= Decimal('10000000'):
        raise ValueError("Valor acima do limite permitido.")
    return numero.quantize(Decimal('0.01'))


def _parse_data(valor) -> date:
    try:
        data = datetime.strptime(str(valor), '%Y-%m-%d').date()
    except ValueError:
        raise ValueError("Data da cotação inválida.")
    if data > date.today():
        raise ValueError("A data da cotação não pode estar no futuro.")
    return data


# ==========================================
# SERVIÇO DE COTAÇÕES DE PEÇAS (lançadas manualmente)
# ==========================================
def resumo_de_precos(cotacoes: list) -> Optional[dict]:
    """
    Resumo do histórico (lista da mais recente para a mais antiga): a última cotação de cada fornecedor, do mais
    barato ao mais caro, e quanto a cotação atual variou em relação à anterior do MESMO fornecedor.
    """
    if not cotacoes:
        return None
    ultima_por_fornecedor = {}
    for c in cotacoes:
        ultima_por_fornecedor.setdefault(c.fornecedor_id, c)
    por_fornecedor = sorted(
        ({'fornecedor': c.fornecedor.razao_social, 'valor': float(c.valor), 'data_cotacao': c.data_cotacao.isoformat()}
         for c in ultima_por_fornecedor.values()), key=lambda x: x['valor'])
    atual = cotacoes[0]
    anterior = next((c for c in cotacoes[1:] if c.fornecedor_id == atual.fornecedor_id), None)
    variacao = None
    if anterior is not None and anterior.valor:
        variacao = round(float((atual.valor - anterior.valor) / anterior.valor * 100), 1)
    return {'por_fornecedor': por_fornecedor, 'melhor': por_fornecedor[0], 'variacao_pct': variacao}


class CotacaoService:
    @staticmethod
    def listar(id_peca: int) -> dict:
        peca = Peca.objects.get(pk=id_peca)
        cotacoes = peca.cotacoes.select_related('fornecedor')
        return {
            'resumo': resumo_de_precos(list(cotacoes)),
            'peca': {'id': peca.id_peca, 'part_number': peca.part_number, 'descricao': peca.descricao},
            'cotacoes': [cotacao_para_dict(c) for c in cotacoes],
            # A cotação pertence à PEÇA (PN), então vale para todos os modelos que a usam.
            'modelos': [{'id': e.id_equipamento, 'modelo': e.modelo, 'pn': e.pn} for e in peca.equipamentos.order_by('modelo')],
        }

    @staticmethod
    def criar(id_peca: int, dados: dict, id_funcionario: Optional[int] = None) -> dict:
        peca = Peca.objects.get(pk=id_peca)

        try:
            fornecedor = Empresa.objects.get(pk=int(dados.get('fornecedor_id')))
        except (TypeError, ValueError, Empresa.DoesNotExist):
            raise ValueError("Selecione um fornecedor válido.")
        if fornecedor.tipo != int(TipoEmpresa.FORNECEDOR):
            raise ValueError("A empresa escolhida não está cadastrada como Fornecedor.")

        observacao = (dados.get('observacao') or '').strip()[:255]
        cotacao = CotacaoPeca.objects.create(
            peca=peca,
            fornecedor=fornecedor,
            valor=_parse_valor(dados.get('valor')),
            data_cotacao=_parse_data(dados.get('data_cotacao')),
            observacao=observacao,
            criado_por=Funcionario.objects.filter(pk=id_funcionario).first() if id_funcionario else None,
        )
        return cotacao_para_dict(cotacao)

    @staticmethod
    def excluir(id_cotacao: int) -> None:
        apagados, _ = CotacaoPeca.objects.filter(pk=id_cotacao).delete()
        if apagados == 0:
            raise CotacaoPeca.DoesNotExist("Cotação não encontrada.")
