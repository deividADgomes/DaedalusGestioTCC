"""
Saída de peças sem orçamento: uma lista, no formato da planilha da operação, enviada ao setor fiscal para emitir as notas.

Cada LINHA é uma peça com o seu ticket e o seu destinatário:
    Ticket | Cliente | Equip. | Peça | QTDE | PN | Dest. | Número | Cidade | Estado | Dia Solic. | NF | RASTREIO | Observação

Fluxo: rascunho -> enviada ao fiscal -> nota emitida (ou cancelada). A baixa no estoque acontece quando a lista é enviada ao
fiscal, só nas linhas "que saem do nosso estoque"; cancelar uma lista já enviada devolve as peças. NF e rastreio são
preenchidos depois, linha a linha, e quando todas as linhas têm NF a lista passa a "nota emitida".
"""
import csv
import io
import logging
import re
from datetime import date, datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ..models import Funcionario, ItemSaida, Peca, SaidaPecas
from .equipamento import _normalizar_pn
from .estoque import LIMITE_QUANTIDADE, EstoqueService

logger = logging.getLogger(__name__)

MAX_ITENS = 300
ORIGENS = {'estoque': 'Sai do nosso estoque', 'externa': 'Não sai do nosso estoque'}
# Cabeçalho do CSV e do e-mail: exatamente as colunas da planilha da operação.
COLUNAS_PLANILHA = ['Ticket', 'Cliente', 'Equip.', 'Peça', 'QTDE', 'PN', 'Dest.', 'Número', 'Cidade', 'Estado',
                    'Dia Solic.', 'NF', 'RASTREIO', 'Observação']


def _texto(valor, limite: int) -> str:
    return ' '.join(str(valor or '').split())[:limite]


def _data(valor, padrao=None) -> date:
    """Aceita 2026-03-11 e 11/03/2026 (também 11/3/2026, como vem da planilha)."""
    texto = str(valor or '').strip()
    if not texto:
        return padrao or timezone.localdate()
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(texto[:10] if formato == '%Y-%m-%d' else texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto}. Use dia/mês/ano, por exemplo 11/03/2026.")


def _emails(texto: str) -> list:
    emails = []
    for e in str(texto or '').replace(';', ',').split(','):
        e = e.strip()
        if not e:
            continue
        try:
            validate_email(e)
        except ValidationError:
            raise ValueError(f"E-mail inválido: {e}")
        if e.lower() not in [x.lower() for x in emails]:
            emails.append(e)
    return emails


class SaidaService:
    @staticmethod
    def config() -> dict:
        return {'fiscal_email': getattr(settings, 'FISCAL_EMAIL', '') or '', 'email_ativo': bool(getattr(settings, 'EMAIL_ENABLED', False)),
                'colunas': COLUNAS_PLANILHA}

    # ------------------------------------------------------------------ validação das linhas
    @staticmethod
    def _validar_itens(brutos) -> list:
        if not isinstance(brutos, list) or not brutos:
            raise ValueError("Inclua ao menos uma peça na lista.")
        if len(brutos) > MAX_ITENS:
            raise ValueError(f"Máximo de {MAX_ITENS} linhas por lista.")
        itens = []
        for n, bruto in enumerate(brutos, start=1):
            if not isinstance(bruto, dict):
                raise ValueError(f"Linha {n}: dados inválidos.")
            pn = ''.join(_normalizar_pn(str(bruto.get('part_number') or '')).split())
            if not pn:
                raise ValueError(f"Linha {n}: informe o PN.")
            if len(pn) > 100:
                raise ValueError(f"Linha {n}: o PN passa de 100 caracteres.")
            rotulo = f"Linha {n} ({pn})"
            try:
                quantidade = int(str(bruto.get('quantidade')).strip())
            except (TypeError, ValueError):
                raise ValueError(f"{rotulo}: quantidade inválida.")
            if quantidade < 1 or quantidade > LIMITE_QUANTIDADE:
                raise ValueError(f"{rotulo}: a quantidade deve ser de 1 a {LIMITE_QUANTIDADE}.")
            origem = bruto.get('origem') or 'auto'
            if origem not in ORIGENS and origem != 'auto':
                raise ValueError(f"{rotulo}: origem inválida.")

            destinatario, cidade = _texto(bruto.get('destinatario'), 255), _texto(bruto.get('cidade'), 100)
            estado = _texto(bruto.get('estado'), 2).upper()
            if not destinatario or not cidade or not re.fullmatch(r'[A-Z]{2}', estado):
                raise ValueError(f"{rotulo}: informe o destinatário, a cidade e o estado (UF com 2 letras) para a nota.")
            try:
                data_solicitacao = _data(bruto.get('data_solicitacao'))
            except ValueError as erro:
                raise ValueError(f"{rotulo}: {erro}")
            itens.append({
                'part_number': pn, 'quantidade': quantidade, 'origem': origem, 'descricao': _texto(bruto.get('descricao'), 500),
                'ticket': _texto(bruto.get('ticket'), 30), 'cliente': _texto(bruto.get('cliente'), 255),
                'equipamento': _texto(bruto.get('equipamento'), 255), 'destinatario': destinatario,
                'telefone': _texto(bruto.get('telefone'), 30), 'cidade': cidade, 'estado': estado,
                'data_solicitacao': data_solicitacao, 'numero_nf': _texto(bruto.get('numero_nf'), 30),
                'rastreio': _texto(bruto.get('rastreio'), 100), 'observacao': _texto(bruto.get('observacao'), 500)})

        catalogo = {p.part_number: p for p in Peca.objects.filter(part_number__in={i['part_number'] for i in itens})}
        for n, item in enumerate(itens, start=1):
            item['peca'] = catalogo.get(item['part_number'])
            if item['origem'] == 'auto':                    # linhas coladas da planilha: no catálogo = nosso estoque
                item['origem'] = 'estoque' if item['peca'] is not None else 'externa'
            if item['origem'] == 'estoque' and item['peca'] is None:
                raise ValueError(f"Linha {n} ({item['part_number']}): para sair do nosso estoque o PN precisa estar no catálogo de peças. "
                                 "Se a peça não é nossa, marque \"Não sai do nosso estoque\".")
            if not item['descricao'] and item['peca'] is not None:
                item['descricao'] = _texto(item['peca'].descricao, 500)
        return itens

    @staticmethod
    def _novo_numero() -> str:
        prefixo = f"SAI-{timezone.localdate().year}-"
        ultimo = SaidaPecas.objects.filter(numero__startswith=prefixo).order_by('-numero').first()
        sequencia = int(ultimo.numero.rsplit('-', 1)[1]) + 1 if ultimo else 1
        return f"{prefixo}{sequencia:04d}"

    # ------------------------------------------------------------------ consulta
    @staticmethod
    def _item_dict(i: ItemSaida) -> dict:
        return {'id': i.id_item, 'ticket': i.ticket, 'cliente': i.cliente, 'equipamento': i.equipamento, 'descricao': i.descricao,
                'quantidade': i.quantidade, 'part_number': i.part_number, 'origem': i.origem, 'destinatario': i.destinatario,
                'telefone': i.telefone, 'cidade': i.cidade, 'estado': i.estado, 'data_solicitacao': i.data_solicitacao.isoformat(),
                'numero_nf': i.numero_nf, 'rastreio': i.rastreio, 'observacao': i.observacao}

    @staticmethod
    def _dict(s: SaidaPecas, com_itens: bool = True) -> dict:
        itens = list(s.itens.select_related('peca').all())
        d = {
            'id': s.id_saida, 'numero': s.numero, 'status': s.status, 'status_nome': s.get_status_display(), 'observacao': s.observacao,
            'criado_por': s.criado_por_nome or '—', 'criado_em': timezone.localtime(s.criado_em).isoformat(),
            'enviado_em': timezone.localtime(s.enviado_em).isoformat() if s.enviado_em else None,
            'enviado_por': s.enviado_por_nome, 'emails_fiscal': s.emails_fiscal,
            'cancelado_em': timezone.localtime(s.cancelado_em).isoformat() if s.cancelado_em else None,
            'motivo_cancelamento': s.motivo_cancelamento,
            'total_itens': len(itens), 'com_nf': sum(1 for i in itens if i.numero_nf),
            'destinatarios': sorted({i.destinatario for i in itens if i.destinatario}),
            'tickets': sorted({i.ticket for i in itens if i.ticket}),
        }
        if com_itens:
            d['itens'] = [SaidaService._item_dict(i) for i in itens]
            d['avisos'] = SaidaService._avisos(s, itens)
        return d

    @staticmethod
    def _avisos(s: SaidaPecas, itens: list) -> list:
        """Só no rascunho: onde o pedido (somando as linhas do mesmo PN) passa do saldo, o envio ao fiscal seria recusado."""
        if s.status != 'rascunho':
            return []
        pedido, pecas = {}, {}
        for i in itens:
            if i.origem == 'estoque' and i.peca is not None:
                pedido[i.peca_id] = pedido.get(i.peca_id, 0) + i.quantidade
                pecas[i.peca_id] = i.peca
        avisos = []
        for id_peca, qtd in pedido.items():
            saldo = getattr(getattr(pecas[id_peca], 'estoque', None), 'saldo', 0)
            if saldo < qtd:
                avisos.append(f"{pecas[id_peca].part_number}: pedido {qtd}, saldo em estoque {max(saldo, 0)}.")
        return avisos

    @staticmethod
    def listar(status: str = '', busca: str = '') -> list:
        qs = SaidaPecas.objects.all()
        if status in dict(SaidaPecas.STATUS):
            qs = qs.filter(status=status)
        busca = (busca or '').strip()
        if busca:
            qs = qs.filter(Q(numero__icontains=busca) | Q(itens__ticket__icontains=busca) | Q(itens__cliente__icontains=busca)
                           | Q(itens__destinatario__icontains=busca) | Q(itens__part_number__icontains=busca.replace(' ', ''))
                           | Q(itens__numero_nf__icontains=busca) | Q(itens__rastreio__icontains=busca)).distinct()
        return [SaidaService._dict(s, com_itens=False) for s in qs[:300]]

    @staticmethod
    def obter(id_saida: int) -> dict:
        return SaidaService._dict(SaidaPecas.objects.get(pk=id_saida))

    # ------------------------------------------------------------------ gravação do rascunho
    @staticmethod
    def salvar(dados: dict, id_funcionario) -> dict:
        observacao = str(dados.get('observacao') or '').strip()[:2000]
        itens = SaidaService._validar_itens(dados.get('itens'))
        funcionario = Funcionario.objects.filter(pk=id_funcionario).first()

        with transaction.atomic():
            if dados.get('id'):
                saida = SaidaPecas.objects.select_for_update().get(pk=dados['id'])
                if saida.status != 'rascunho':
                    raise ValueError("Só é possível alterar uma saída em rascunho.")
                saida.itens.all().delete()
            else:
                saida = SaidaPecas(criado_por=funcionario, criado_por_nome=funcionario.nome if funcionario else '')
            saida.observacao = observacao
            if saida.pk is None:
                for _ in range(5):                      # duas pessoas criando ao mesmo tempo: tenta o próximo número
                    saida.numero = SaidaService._novo_numero()
                    try:
                        with transaction.atomic():
                            saida.save()
                        break
                    except IntegrityError:
                        saida.pk = None
                else:
                    raise ValueError("Não foi possível gerar o número da lista. Tente novamente.")
            else:
                saida.save()
            ItemSaida.objects.bulk_create([ItemSaida(saida=saida, **item) for item in itens])
        return SaidaService.obter(saida.pk)

    # ------------------------------------------------------------------ envio ao fiscal (dá a baixa no estoque)
    @staticmethod
    def enviar(id_saida: int, id_funcionario, enviar_email: bool = False, destinatarios: str = '', mensagem: str = '') -> dict:
        funcionario = Funcionario.objects.filter(pk=id_funcionario).first()
        nome = funcionario.nome if funcionario else ''
        with transaction.atomic():
            saida = SaidaPecas.objects.select_for_update().get(pk=id_saida)
            if saida.status != 'rascunho':
                raise ValueError("Esta lista já foi enviada ou cancelada.")
            itens = list(saida.itens.select_related('peca'))
            if not itens:
                raise ValueError("A lista não tem itens.")

            emails = []
            if enviar_email:
                if not getattr(settings, 'EMAIL_ENABLED', False):
                    raise ValueError("O envio de e-mail não está configurado neste servidor. Baixe o CSV, envie ao fiscal pelo seu e-mail e desmarque o envio automático.")
                emails = _emails(destinatarios or getattr(settings, 'FISCAL_EMAIL', ''))
                if not emails:
                    raise ValueError("Informe o e-mail do setor fiscal.")

            for item in itens:
                if item.origem != 'estoque':
                    continue
                if item.peca_id is None:
                    raise ValueError(f"{item.part_number}: a peça não está mais no catálogo. Marque \"Não sai do nosso estoque\".")
                motivo = f"Saída {saida.numero}: ticket {item.ticket or '—'} para {item.destinatario}"
                try:
                    EstoqueService.movimentar(item.peca_id, 'saida', item.quantidade, motivo=motivo, id_funcionario=id_funcionario, referencia=saida.numero)
                except ValueError as erro:
                    raise ValueError(f"{item.part_number}: {erro} Se a peça não sai do nosso estoque, marque \"Não sai do nosso estoque\".")

            saida.status = 'enviada'
            saida.enviado_em = timezone.now()
            saida.enviado_por_nome = nome
            saida.emails_fiscal = ', '.join(emails)
            saida.save()
            if emails:
                SaidaService._enviar_email(saida, itens, emails, mensagem, funcionario)   # se falhar, tudo é desfeito
        return SaidaService.obter(id_saida)

    @staticmethod
    def _linha_planilha(i: ItemSaida) -> list:
        return [i.ticket, i.cliente, i.equipamento, i.descricao, i.quantidade, i.part_number, i.destinatario, i.telefone, i.cidade,
                i.estado, i.data_solicitacao.strftime('%d/%m/%Y'), i.numero_nf, i.rastreio, i.observacao]

    @staticmethod
    def _corpo_email(saida: SaidaPecas, itens: list, mensagem: str, funcionario) -> str:
        linhas = [f"Lista de saída de peças {saida.numero}", '']
        if saida.observacao:
            linhas += [f"Observação: {saida.observacao}", '']
        linhas.append('Peças (ticket | cliente | equipamento | PN | peça | qtde | destinatário | cidade/UF | dia da solicitação):')
        for i in itens:
            nota = '' if i.origem == 'estoque' else ' [peça de fora do nosso estoque]'
            contato = f"{i.destinatario} ({i.telefone})" if i.telefone else i.destinatario
            linhas.append(f"- {i.ticket or '—'} | {i.cliente or '—'} | {i.equipamento or '—'} | {i.part_number} | {i.descricao or '—'} | {i.quantidade}"
                          f" | {contato} | {i.cidade}/{i.estado} | {i.data_solicitacao:%d/%m/%Y}{nota}")
        if mensagem.strip():
            linhas += ['', mensagem.strip()[:2000]]
        linhas += ['', 'Pedimos a emissão das notas fiscais correspondentes. A lista segue também em anexo (CSV, abre no Excel).']
        if funcionario:
            linhas.append(f"Solicitado por: {funcionario.nome}")
        return '\n'.join(linhas)

    @staticmethod
    def _enviar_email(saida: SaidaPecas, itens: list, emails: list, mensagem: str, funcionario) -> None:
        conteudo, nome = SaidaService.csv_bytes(saida, itens)
        email = EmailMessage(
            subject=f"[Daedalus] Lista de saída de peças {saida.numero}", body=SaidaService._corpo_email(saida, itens, mensagem, funcionario),
            from_email=settings.DEFAULT_FROM_EMAIL, to=emails, reply_to=[funcionario.email] if funcionario and funcionario.email else None)
        email.attach(nome, conteudo, 'text/csv')
        try:
            email.send(fail_silently=False)
        except Exception:
            logger.exception("Falha ao enviar a lista %s ao fiscal", saida.numero)
            raise ValueError("Não foi possível enviar o e-mail agora, então a lista continua em rascunho e o estoque não foi alterado. Confira a configuração de e-mail e tente de novo.")

    # ------------------------------------------------------------------ retorno do fiscal: NF e rastreio por linha
    @staticmethod
    def registrar_retorno(id_saida: int, linhas=None, nf_geral: str = '') -> dict:
        """
        Preenche NF, rastreio e observação das linhas (só esses campos, e só depois do envio ao fiscal).
        `nf_geral` entra em todas as linhas que ainda não têm NF. Com todas as linhas com NF, a lista vira "nota emitida".
        """
        linhas = linhas or []
        nf_geral = _texto(nf_geral, 30)
        if not linhas and not nf_geral:
            raise ValueError("Informe a NF ou o rastreio de ao menos uma linha.")
        with transaction.atomic():
            saida = SaidaPecas.objects.select_for_update().get(pk=id_saida)
            if saida.status not in ('enviada', 'nota_emitida'):
                raise ValueError("A NF e o rastreio só podem ser registrados depois que a lista é enviada ao fiscal.")
            itens = {i.id_item: i for i in saida.itens.all()}
            for linha in linhas:
                item = itens.get(int(linha.get('id') or 0))
                if item is None:
                    raise ValueError("Linha não encontrada nesta lista.")
                if 'numero_nf' in linha:
                    item.numero_nf = _texto(linha['numero_nf'], 30)
                if 'rastreio' in linha:
                    item.rastreio = _texto(linha['rastreio'], 100)
                if 'observacao' in linha:
                    item.observacao = _texto(linha['observacao'], 500)
            if nf_geral:
                for item in itens.values():
                    if not item.numero_nf:
                        item.numero_nf = nf_geral
            ItemSaida.objects.bulk_update(itens.values(), ['numero_nf', 'rastreio', 'observacao'])
            saida.status = 'nota_emitida' if all(i.numero_nf for i in itens.values()) else 'enviada'
            saida.save()
        return SaidaService.obter(id_saida)

    @staticmethod
    def registrar_nota(id_saida: int, numero_nf: str) -> dict:
        """Atalho: a mesma NF para todas as linhas que ainda não têm uma."""
        if not _texto(numero_nf, 30):
            raise ValueError("Informe o número da nota fiscal.")
        return SaidaService.registrar_retorno(id_saida, [], numero_nf)

    @staticmethod
    def cancelar(id_saida: int, motivo: str, id_funcionario) -> dict:
        motivo = _texto(motivo, 300)
        with transaction.atomic():
            saida = SaidaPecas.objects.select_for_update().get(pk=id_saida)
            if saida.status not in ('rascunho', 'enviada'):
                raise ValueError("Esta lista não pode mais ser cancelada.")
            if saida.status == 'enviada':
                if not motivo:
                    raise ValueError("Informe o motivo do cancelamento (as peças voltam ao estoque).")
                for item in saida.itens.filter(origem='estoque', peca__isnull=False):
                    EstoqueService.movimentar(item.peca_id, 'entrada', item.quantidade, motivo=f"Estorno da saída {saida.numero} (cancelada)",
                                              id_funcionario=id_funcionario, referencia=saida.numero)
            saida.status, saida.cancelado_em, saida.motivo_cancelamento = 'cancelada', timezone.now(), motivo
            saida.save()
        return SaidaService.obter(id_saida)

    # ------------------------------------------------------------------ CSV (as mesmas colunas da planilha; abre direto no Excel)
    @staticmethod
    def csv_bytes(saida: SaidaPecas, itens=None):
        itens = list(saida.itens.all()) if itens is None else itens
        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
        escritor.writerow(COLUNAS_PLANILHA)
        for i in itens:
            escritor.writerow(SaidaService._linha_planilha(i))
        return buffer.getvalue().encode('utf-8-sig'), f"{saida.numero}.csv"

    @staticmethod
    def csv_da_saida(id_saida: int):
        return SaidaService.csv_bytes(SaidaPecas.objects.get(pk=id_saida))
