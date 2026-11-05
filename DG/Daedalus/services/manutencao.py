"""Rotinas de manutenção de dados (rodadas por comandos, nunca pela tela)."""
from ..models import Triagem
from .estatistica import normalizar_texto


class ManutencaoService:
    @staticmethod
    def vincular_pecas_trocadas(aplicar: bool = False) -> dict:
        """
        Liga o texto livre antigo de "peça trocada" a uma peça cadastrada no modelo do equipamento, para o
        ranking de peças do BI aproveitar o histórico. Só vincula quando há UMA correspondência clara:
        o part number aparece como palavra inteira no texto, ou a descrição é igual ao texto.
        Não altera o texto da triagem. Sem `aplicar`, apenas simula.
        """
        resultado = {'analisadas': 0, 'vinculadas': 0, 'sem_correspondencia': 0, 'ambiguas': 0, 'exemplos': []}
        pendentes = (Triagem.objects.filter(peca_trocada__isnull=True).exclude(troca__isnull=True).exclude(troca='')
                     .select_related('equipamento').prefetch_related('equipamento__pecas'))
        for triagem in pendentes:
            resultado['analisadas'] += 1
            texto = normalizar_texto(triagem.troca)
            envolto = f" {texto} "
            achadas = [
                p for p in triagem.equipamento.pecas.all()
                if (normalizar_texto(p.part_number) and f" {normalizar_texto(p.part_number)} " in envolto)
                or (normalizar_texto(p.descricao) and normalizar_texto(p.descricao) == texto)
            ]
            if len(achadas) == 1:
                resultado['vinculadas'] += 1
                if len(resultado['exemplos']) < 10:
                    resultado['exemplos'].append(f"#{triagem.n_ticket}: \"{triagem.troca}\" -> {achadas[0].part_number}")
                if aplicar:
                    Triagem.objects.filter(pk=triagem.pk).update(peca_trocada=achadas[0])
            elif achadas:
                resultado['ambiguas'] += 1
            else:
                resultado['sem_correspondencia'] += 1
        return resultado
