import logging
import re
from typing import List

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone as django_timezone

from ..dtos import EquipamentoDTO
from ..models import Equipamento, Peca
from ..partsurfer import buscar_pecas_por_pn
from .pecas import cotacao_para_dict

logger = logging.getLogger(__name__)

# Limites para não sobrecarregar o PartSurfer (endpoint não oficial da HP).
LIMITE_IMPORTACAO = 2000                # linhas por planilha importada
INTERVALO_MINIMO_POR_EQUIPAMENTO = 15   # segundos entre consultas do mesmo equipamento
MAX_CONSULTAS_POR_MINUTO = 20           # total do sistema


class LimiteConsultasExcedido(Exception):
    """Muitas consultas ao PartSurfer em pouco tempo."""


def _normalizar_pn(pn: str) -> str:
    return (pn or '').strip().upper()


def _controlar_taxa(id_equipamento: int) -> None:
    if not cache.add(f"partsurfer:equip:{id_equipamento}", 1, INTERVALO_MINIMO_POR_EQUIPAMENTO):
        raise LimiteConsultasExcedido(
            f"Esse equipamento foi consultado agora há pouco. Aguarde {INTERVALO_MINIMO_POR_EQUIPAMENTO} segundos."
        )
    chave = "partsurfer:global"
    cache.add(chave, 0, 60)
    try:
        total = cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, 60)
        total = 1
    if total > MAX_CONSULTAS_POR_MINUTO:
        raise LimiteConsultasExcedido("Muitas consultas ao PartSurfer no último minuto. Tente novamente em instantes.")


def _peca_para_dict(peca: Peca) -> dict:
    return {
        'id': peca.id_peca,
        'part_number': peca.part_number,
        'descricao': peca.descricao,
        'equipamento_completo': peca.equipamento_completo,
        'cotacao_atual': cotacao_para_dict(peca.cotacao_atual()),
    }


# ==========================================
# SERVIÇO DE EQUIPAMENTO
# ==========================================
class EquipamentoService:
    @staticmethod
    def salvar(dto: EquipamentoDTO) -> EquipamentoDTO:
        pn = _normalizar_pn(dto.pn)
        modelo = (dto.modelo or '').strip()
        tipo = (dto.tipo or '').strip()[:100]
        marca = (dto.marca or '').strip()[:100]
        if not pn or not modelo:
            raise ValueError("PN e modelo são obrigatórios.")

        duplicado = Equipamento.objects.filter(pn=pn)
        if dto.id_equipamento:
            duplicado = duplicado.exclude(pk=dto.id_equipamento)
        if duplicado.exists():
            raise ValueError(f"Já existe um modelo cadastrado com o PN {pn}.")

        try:
            with transaction.atomic():
                if dto.id_equipamento:
                    equip = Equipamento.objects.get(pk=dto.id_equipamento)
                    equip.pn = pn
                    equip.modelo = modelo
                    equip.tipo = tipo
                    equip.marca = marca
                    equip.save()
                else:
                    equip = Equipamento.objects.create(pn=pn, modelo=modelo, tipo=tipo, marca=marca)
        except IntegrityError:
            raise ValueError(f"Já existe um modelo cadastrado com o PN {pn}.")

        return EquipamentoDTO(id_equipamento=equip.id_equipamento, pn=equip.pn, modelo=equip.modelo,
                              tipo=equip.tipo, marca=equip.marca)

    @staticmethod
    def listar(busca: str = '') -> List[EquipamentoDTO]:
        """Todos os modelos. Com `busca`, só os que casam com o modelo, PN, tipo, marca ou com alguma peça vinculada (PN ou descrição)."""
        qs = Equipamento.objects.annotate(total_pecas=Count('pecas'))
        busca = ' '.join((busca or '').split())
        if busca:
            ligacoes = Equipamento.pecas.through.objects.filter(
                Q(peca__part_number__icontains=busca) | Q(peca__descricao__icontains=busca)).values('equipamento_id')
            qs = qs.filter(Q(modelo__icontains=busca) | Q(pn__icontains=busca) | Q(tipo__icontains=busca)
                           | Q(marca__icontains=busca) | Q(pk__in=ligacoes))
        return [
            EquipamentoDTO(
                id_equipamento=eq.id_equipamento,
                pn=eq.pn,
                modelo=eq.modelo,
                tipo=eq.tipo,
                marca=eq.marca,
                rfb=eq.rfb,
                total_pecas=eq.total_pecas,
                pecas_sincronizadas_em=(
                    django_timezone.localtime(eq.pecas_sincronizadas_em).isoformat()
                    if eq.pecas_sincronizadas_em else None
                ),
            )
            for eq in qs
        ]

    @staticmethod
    def listar_rfb(todos: bool = False) -> List[dict]:
        """Modelos do RFB (os que aparecem ao abrir chamados). Com todos=True traz também os fora do RFB."""
        qs = Equipamento.objects.annotate(total_pecas=Count('pecas')).order_by('modelo')
        if not todos:
            qs = qs.filter(rfb=True)
        return [{'id': e.id_equipamento, 'modelo': e.modelo, 'pn': e.pn, 'tipo': e.tipo, 'marca': e.marca,
                 'total_pecas': e.total_pecas, 'rfb': e.rfb} for e in qs]

    @staticmethod
    def definir_rfb(id_equipamento: int, ativo: bool) -> None:
        """Adiciona ou retira o modelo da lista do RFB. Retirar só esconde: nada é apagado e os chamados continuam."""
        if Equipamento.objects.filter(pk=id_equipamento).update(rfb=bool(ativo)) == 0:
            raise Equipamento.DoesNotExist("Modelo não encontrado.")

    @staticmethod
    def listar_pecas(id_equipamento: int) -> List[dict]:
        """Peças escolhidas para o equipamento, com a cotação mais recente de cada uma."""
        equip = Equipamento.objects.get(pk=id_equipamento)
        return [_peca_para_dict(p) for p in equip.pecas.order_by('part_number')]

    @staticmethod
    def consultar_partsurfer(id_equipamento: int) -> List[dict]:
        """
        Consulta o PartSurfer pelo PN e devolve as peças CANDIDATAS, sem gravar nada.

        O usuário escolhe quais usar (ver salvar_selecao), porque nem tudo que o
        PartSurfer lista é útil. Peças já vinculadas vêm marcadas (selecionada=True)
        e as vinculadas que a HP não retornou continuam na lista (somente_local=True),
        para o usuário decidir se mantém.

        Levanta PartSurferError (falha de comunicação), ValueError (HP sem peças)
        e LimiteConsultasExcedido.
        """
        equip = Equipamento.objects.get(pk=id_equipamento)
        _controlar_taxa(id_equipamento)
        pecas_hp = buscar_pecas_por_pn(equip.pn)

        if not pecas_hp:
            raise ValueError(
                f"O PartSurfer não retornou peças para o PN {equip.pn}. "
                "Confira se o Part Number está correto."
            )

        vinculadas = {p.part_number: p for p in equip.pecas.all()}
        candidatas = []
        vistos = set()
        for item in pecas_hp:
            pn = _normalizar_pn(item['part_number'])
            if not pn or pn in vistos:
                continue
            vistos.add(pn)
            candidatas.append({
                'part_number': pn,
                'descricao': item.get('descricao', ''),
                'selecionada': pn in vinculadas,
                'somente_local': False,
            })
        for pn, peca in vinculadas.items():
            if pn not in vistos:
                candidatas.append({
                    'part_number': pn,
                    'descricao': peca.descricao,
                    'selecionada': True,
                    'somente_local': True,
                })

        equip.pecas_sincronizadas_em = django_timezone.now()
        equip.save(update_fields=['pecas_sincronizadas_em'])
        candidatas.sort(key=lambda c: c['part_number'])
        return candidatas

    @staticmethod
    def adicionar_peca_manual(id_equipamento: int, dados: dict) -> List[dict]:
        """
        Cadastra uma peça direto no modelo, sem consultar o PartSurfer. Serve também para o "equipamento
        completo" (a máquina inteira como item). Se o PN já existir, reaproveita a peça e atualiza os dados.
        """
        equip = Equipamento.objects.get(pk=id_equipamento)
        pn = _normalizar_pn((dados or {}).get('part_number'))
        descricao = ((dados or {}).get('descricao') or '').strip()
        completo = (dados or {}).get('equipamento_completo')
        completo = completo.strip().lower() in ('1', 'true', 'on', 'sim') if isinstance(completo, str) else bool(completo)
        if not pn:
            raise ValueError("Informe o Part Number.")
        if len(pn) > 100:
            raise ValueError("Part Number muito longo (máximo de 100 caracteres).")
        if not descricao:
            raise ValueError("Informe a descrição.")
        with transaction.atomic():
            peca, criada = Peca.objects.get_or_create(part_number=pn, defaults={'descricao': descricao, 'equipamento_completo': completo})
            if not criada and (peca.descricao != descricao or peca.equipamento_completo != completo):
                peca.descricao = descricao
                peca.equipamento_completo = completo
                peca.save(update_fields=['descricao', 'equipamento_completo', 'atualizado_em'])
            equip.pecas.add(peca)
        return EquipamentoService.listar_pecas(id_equipamento)

    @staticmethod
    def remover_peca(id_equipamento: int, id_peca: int) -> List[dict]:
        """Tira a peça do modelo. A peça e as cotações continuam no catálogo (outros modelos podem usá-la)."""
        equip = Equipamento.objects.get(pk=id_equipamento)
        peca = equip.pecas.filter(pk=id_peca).first()
        if peca is None:
            raise Peca.DoesNotExist("Peça não encontrada neste modelo.")
        equip.pecas.remove(peca)
        return EquipamentoService.listar_pecas(id_equipamento)

    @staticmethod
    def importar_pecas(texto: str) -> dict:
        """
        Importa peças de vários modelos de uma vez a partir de uma planilha colada ou enviada como CSV.
        Uma peça por linha: PN do modelo ; PN da peça ; Descrição ; Equipamento completo (opcional: sim/não).
        Só ACRESCENTA: cria a peça se não existir, atualiza a descrição e vincula ao modelo; nunca remove vínculos.
        Linhas com problema são puladas e listadas, sem impedir as outras.
        """
        resultado = {'linhas': 0, 'criadas': 0, 'vinculadas': 0, 'atualizadas': 0, 'erros': []}
        linhas = [l for l in (texto or '').splitlines() if l.strip()]
        if not linhas:
            raise ValueError("Cole ou envie a planilha com as peças.")
        if len(linhas) > LIMITE_IMPORTACAO:
            raise ValueError(f"A planilha tem mais de {LIMITE_IMPORTACAO} linhas. Divida em partes menores.")

        cabecalho = {'pn do modelo', 'pn modelo', 'modelo', 'pn_modelo', 'part number do modelo'}
        if re.split(r'[;\t]', linhas[0])[0].strip().lower() in cabecalho:
            linhas = linhas[1:]

        verdadeiros = {'sim', 's', '1', 'true', 'x', 'yes'}
        equipamentos, pecas_do_lote = {}, {}
        with transaction.atomic():
            for numero, linha in enumerate(linhas, start=1):
                resultado['linhas'] += 1
                colunas = [c.strip() for c in re.split(r'[;\t]', linha)]
                pn_modelo = _normalizar_pn(colunas[0])
                pn_peca = _normalizar_pn(colunas[1]) if len(colunas) > 1 else ''
                descricao = ' '.join(colunas[2].split()) if len(colunas) > 2 else ''
                completo = (colunas[3].strip().lower() in verdadeiros) if len(colunas) > 3 and colunas[3].strip() else None

                def erro(motivo):
                    if len(resultado['erros']) < 30:
                        resultado['erros'].append(f"Linha {numero}: {motivo}")

                if not pn_modelo or not pn_peca:
                    erro("faltou o PN do modelo ou o PN da peça (use ponto e vírgula ou tabulação entre as colunas).")
                    continue
                if len(pn_peca) > 100:
                    erro(f"o PN da peça \"{pn_peca[:20]}...\" passa de 100 caracteres.")
                    continue
                if pn_modelo not in equipamentos:
                    equipamentos[pn_modelo] = Equipamento.objects.filter(pn__iexact=pn_modelo).first()
                equipamento = equipamentos[pn_modelo]
                if equipamento is None:
                    erro(f"o modelo {pn_modelo} não está cadastrado.")
                    continue

                peca = pecas_do_lote.get(pn_peca) or Peca.objects.filter(part_number=pn_peca).first()
                if peca is None:
                    peca = Peca.objects.create(part_number=pn_peca, descricao=descricao, equipamento_completo=bool(completo))
                    resultado['criadas'] += 1
                else:
                    campos = []
                    if descricao and peca.descricao != descricao:
                        peca.descricao = descricao
                        campos.append('descricao')
                    if completo is not None and peca.equipamento_completo != completo:
                        peca.equipamento_completo = completo
                        campos.append('equipamento_completo')
                    if campos:
                        peca.save(update_fields=campos + ['atualizado_em'])
                        resultado['atualizadas'] += 1
                pecas_do_lote[pn_peca] = peca
                if not equipamento.pecas.filter(pk=peca.pk).exists():
                    equipamento.pecas.add(peca)
                    resultado['vinculadas'] += 1
        return resultado

    @staticmethod
    def salvar_selecao(id_equipamento: int, itens: List[dict]) -> List[dict]:
        """
        Define exatamente quais peças pertencem ao equipamento.

        `itens` é a lista marcada pelo usuário: [{part_number, descricao, equipamento_completo?}, ...].
        Peças novas são criadas no catálogo; as que saem da seleção só perdem o vínculo com este
        equipamento (a peça e as cotações dela continuam no catálogo). `equipamento_completo` é
        opcional: se vier, grava a marcação; se não vier, a peça mantém a que já tinha.
        """
        if not isinstance(itens, list):
            raise ValueError("Seleção inválida.")
        equip = Equipamento.objects.get(pk=id_equipamento)

        escolhidas = {}
        for item in itens:
            pn = _normalizar_pn(item.get('part_number', '') if isinstance(item, dict) else '')
            if not pn:
                continue
            if len(pn) > 100:
                raise ValueError(f"Part Number muito longo: {pn[:20]}...")
            completo = item.get('equipamento_completo') if isinstance(item, dict) else None
            escolhidas[pn] = ((item.get('descricao') or '').strip(), None if completo is None else bool(completo))

        with transaction.atomic():
            existentes = {p.part_number: p for p in Peca.objects.filter(part_number__in=list(escolhidas))}
            vinculos = []
            for pn, (descricao, completo) in escolhidas.items():
                peca = existentes.get(pn)
                if peca is None:
                    peca = Peca.objects.create(part_number=pn, descricao=descricao, equipamento_completo=bool(completo))
                else:
                    campos = []
                    if descricao and peca.descricao != descricao:
                        peca.descricao = descricao
                        campos.append('descricao')
                    if completo is not None and peca.equipamento_completo != completo:
                        peca.equipamento_completo = completo
                        campos.append('equipamento_completo')
                    if campos:
                        peca.save(update_fields=campos + ['atualizado_em'])
                vinculos.append(peca)
            equip.pecas.set(vinculos)

        return EquipamentoService.listar_pecas(id_equipamento)
