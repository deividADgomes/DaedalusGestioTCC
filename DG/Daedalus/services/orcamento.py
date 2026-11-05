from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import TruncMonth

from django.utils import timezone as django_timezone

from ..models import CotacaoPeca, Equipamento, Funcionario, ItemOrcamento, Orcamento, OrcamentoHistorico, Peca, Triagem
from .pecas import _parse_valor

CENTAVOS = Decimal('0.01')


def precificacao() -> dict:
    """Regras de preço lidas de settings.ORCAMENTO_PRECIFICACAO (margem, adicionais, validade)."""
    cfg = settings.ORCAMENTO_PRECIFICACAO
    return {
        'margem': Decimal(cfg['margem']),
        'adicionais': [Decimal(v) for v in cfg['adicionais_primeira_peca']],
        'validade_dias': int(cfg['validade_dias']),
    }


def precificacao_para_tela() -> dict:
    """Mesma configuração em tipos simples (JSON), para a tela calcular a prévia."""
    cfg = precificacao()
    return {'margem': float(cfg['margem']), 'adicionais': [float(v) for v in cfg['adicionais']],
            'validade_dias': cfg['validade_dias']}


def calcular_validade(data_emissao: date) -> date:
    """
    Último dia de validade do orçamento. O dia da emissão conta como o DIA 1:
    com 15 dias, emitido em 01/03 vale até 15/03 (e não 16/03).
    """
    return data_emissao + timedelta(days=precificacao()['validade_dias'] - 1)


def calcular_item(valor_base: Decimal, primeiro: bool, aplicar: bool = True):
    """
    Valor unitário cobrado = valor da peça x margem.
    A PRIMEIRA peça do orçamento recebe, além disso, os adicionais (soma única, não por unidade).
    Retorna (valor_unitario, adicional).
    """
    if not aplicar:
        # Sem a regra: o valor digitado é o valor cheio cobrado, sem margem e sem adicionais.
        return valor_base.quantize(CENTAVOS), Decimal('0.00')
    cfg = precificacao()
    unitario = (valor_base * cfg['margem']).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    adicional = sum(cfg['adicionais'], Decimal('0')) if primeiro else Decimal('0')
    return unitario, adicional.quantize(CENTAVOS)

# Quem pode mudar de qual status para qual. "emitido" é o documento entregue ao cliente.
TRANSICOES = {
    'rascunho': {'emitido', 'cancelado'},
    'emitido': {'aprovado', 'recusado', 'cancelado'},
    'recusado': {'emitido'},
    'aprovado': {'cancelado'},
    'cancelado': set(),
}

# Depois de emitido, o laudo ainda pode ser corrigido (com motivo e histórico), exceto se estiver cancelado.
STATUS_ALTERAVEIS = {'emitido', 'recusado', 'aprovado'}
CARGOS_GESTAO = {'Administrador', 'Gestor'}

ROTULOS = {
    'ticket': 'Ticket', 'cliente_nome': 'Cliente', 'cliente_responsavel': 'Responsável', 'cliente_email': 'E-mail do cliente',
    'cliente_telefone': 'Telefone', 'cliente_cidade': 'Cidade', 'cliente_uf': 'UF', 'cliente_endereco': 'Endereço',
    'cliente_cep': 'CEP', 'cliente_complemento': 'Complemento', 'equip_tipo': 'Tipo do equipamento',
    'equip_marca': 'Marca', 'equip_modelo': 'Modelo', 'equip_sn': 'Nº de série', 'motivo_problema': 'Motivo/Problema',
    'analise': 'Análise', 'disponibilidade': 'Disponibilidade das peças', 'prazo_estimado': 'Prazo estimado',
    'tecnico_responsavel': 'Técnico responsável', 'equipamento': 'Modelo cadastrado', 'aplicar_regra': 'Regra de preço',
}


def _bool(valor, padrao: bool = True) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, str):
        return valor.strip().lower() not in ('', '0', 'false', 'off', 'nao', 'não', 'no')
    return bool(valor)


def _brl(valor) -> str:
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def _curto(valor, limite: int = 160) -> str:
    texto = str(valor or '').strip() or '—'
    return texto if len(texto) <= limite else texto[:limite - 1] + '…'


def _resumo_itens(itens) -> str:
    return '; '.join(f"{i.nome or i.part_number or i.descricao} ({i.quantidade}x {_brl(i.valor_base)})" for i in itens)


CAMPOS_TEXTO = {
    'ticket': 50, 'cliente_nome': 255, 'cliente_responsavel': 255, 'cliente_email': 255,
    'cliente_telefone': 30, 'cliente_cidade': 100, 'cliente_endereco': 255, 'cliente_cep': 10,
    'cliente_complemento': 255, 'equip_tipo': 100, 'equip_marca': 100, 'equip_modelo': 150,
    'equip_sn': 100, 'prazo_estimado': 100, 'tecnico_responsavel': 255,
}
CAMPOS_LONGOS = ('motivo_problema', 'analise')

_VALOR_ITEM = F('itens__valor_unitario') * F('itens__quantidade') + F('itens__adicional')
_DECIMAL = DecimalField(max_digits=14, decimal_places=2)


def _data(valor, obrigatoria=False) -> Optional[date]:
    if not valor:
        if obrigatoria:
            raise ValueError("Data inválida.")
        return None
    try:
        return datetime.strptime(str(valor)[:10], '%Y-%m-%d').date()
    except ValueError:
        raise ValueError("Data inválida.")


COTACAO_VELHA_DIAS = 90   # acima disso a cotação usada no rascunho merece uma conferida


def avisos_de_cotacao(itens) -> list:
    """Avisos (sem bloquear nada) sobre peças do rascunho sem cotação ou com cotação antiga."""
    ids = [i.cotacao_id for i in itens if i.cotacao_id]
    datas = dict(CotacaoPeca.objects.filter(pk__in=ids).values_list('pk', 'data_cotacao')) if ids else {}
    hoje = date.today()
    avisos = []
    for i in itens:
        if not i.peca_id:
            continue
        rotulo = i.part_number or i.nome or 'Peça'
        if not i.cotacao_id:
            avisos.append(f"{rotulo}: sem cotação vinculada (o valor foi digitado à mão).")
            continue
        data = datas.get(i.cotacao_id)
        if data and (hoje - data).days > COTACAO_VELHA_DIAS:
            avisos.append(f"{rotulo}: a cotação usada tem {(hoje - data).days} dias (mais de {COTACAO_VELHA_DIAS}). Vale conferir o preço.")
    return avisos


def orcamento_para_dict(orc: Orcamento, com_itens: bool = True) -> dict:
    itens = list(orc.itens.all())
    total = sum((i.subtotal for i in itens), Decimal('0.00'))
    dados = {
        'id': orc.id_orcamento,
        'numero': orc.numero,
        'status': orc.status,
        'status_nome': orc.get_status_display(),
        'motivo_recusa': orc.motivo_recusa,
        'triagem_id': orc.triagem_id,
        'ticket': orc.ticket,
        'cliente_nome': orc.cliente_nome,
        'cliente_responsavel': orc.cliente_responsavel,
        'cliente_email': orc.cliente_email,
        'cliente_telefone': orc.cliente_telefone,
        'cliente_cidade': orc.cliente_cidade,
        'cliente_uf': orc.cliente_uf,
        'cliente_endereco': orc.cliente_endereco,
        'cliente_cep': orc.cliente_cep,
        'cliente_complemento': orc.cliente_complemento,
        'equipamento_id': orc.equipamento_id,
        'equip_tipo': orc.equip_tipo,
        'equip_marca': orc.equip_marca,
        'equip_modelo': orc.equip_modelo,
        'equip_sn': orc.equip_sn,
        'motivo_problema': orc.motivo_problema,
        'analise': orc.analise,
        'disponibilidade': orc.disponibilidade,
        'prazo_estimado': orc.prazo_estimado,
        'tecnico_responsavel': orc.tecnico_responsavel,
        'analista_nome': orc.analista_nome,
        'analista_email': orc.analista_email,
        'data_emissao': orc.data_emissao.isoformat(),
        'validade_ate': orc.validade_ate.isoformat() if orc.validade_ate else None,
        'valor_total': float(total),
        'editavel': orc.status == 'rascunho',
        'aplicar_regra': orc.aplicar_regra,
        'alteravel': orc.status in STATUS_ALTERAVEIS,
        'total_alteracoes': orc.historico.count(),
        'avisos_cotacao': avisos_de_cotacao(itens) if orc.status == 'rascunho' else [],
    }
    if com_itens:
        dados['itens'] = [
            {
                'id': i.id_item,
                'peca_id': i.peca_id,
                'cotacao_id': i.cotacao_id,
                'nome': i.nome,
                'descricao': i.descricao,
                'part_number': i.part_number,
                'quantidade': i.quantidade,
                'valor_base': float(i.valor_base),
                'valor_unitario': float(i.valor_unitario),
                'adicional': float(i.adicional),
                'subtotal': float(i.subtotal),
            }
            for i in itens
        ]
    return dados


# ==========================================
# SERVIÇO DE ORÇAMENTOS / LAUDOS
# ==========================================
class OrcamentoService:
    @staticmethod
    def _proximo_numero(ano: int) -> str:
        prefixo = f"ORC-{ano}-"
        ultimo = Orcamento.objects.filter(numero__startswith=prefixo).order_by('-numero').first()
        seq = int(ultimo.numero.rsplit('-', 1)[-1]) + 1 if ultimo else 1
        return f"{prefixo}{seq:04d}"

    @staticmethod
    def pre_preencher_por_ticket(ticket) -> dict:
        """Dados iniciais do laudo a partir de uma triagem já feita (busca pelo nº do ticket)."""
        try:
            ticket_num = int(ticket)
        except (TypeError, ValueError):
            raise ValueError("Informe o número do ticket.")
        triagem = (
            Triagem.objects.select_related('cliente', 'equipamento', 'analista_triagem')
            .filter(n_ticket=ticket_num).order_by('-id_triagem').first()
        )
        if triagem is None:
            raise Triagem.DoesNotExist("Nenhuma triagem encontrada para esse ticket.")
        return {
            'triagem_id': triagem.id_triagem,
            'ticket': str(triagem.n_ticket),
            'cliente_nome': triagem.cliente.razao_social,
            'cliente_cidade': triagem.cidade,
            'cliente_uf': triagem.estado,
            'equipamento_id': triagem.equipamento_id,
            'equip_tipo': triagem.equipamento.tipo,
            'equip_marca': triagem.equipamento.marca,
            'equip_modelo': triagem.equipamento.modelo,
            'equip_sn': triagem.sn,
            'motivo_problema': triagem.defeito_usuario or '',
            'analise': triagem.analise or triagem.defeito_constatado or '',
        }

    @staticmethod
    def obter(id_orcamento: int) -> dict:
        orc = Orcamento.objects.prefetch_related('itens').get(pk=id_orcamento)
        return orcamento_para_dict(orc)

    @staticmethod
    def _montar_itens(itens_dados, aplicar_regra: bool = True) -> list:
        """
        Converte os itens recebidos da tela e calcula os preços NO SERVIDOR (a tela só mostra uma prévia).
        O primeiro item da lista recebe os adicionais; os demais só a margem.
        """
        if not isinstance(itens_dados, list):
            raise ValueError("Lista de peças inválida.")
        itens = []
        for bruto in itens_dados:
            if not isinstance(bruto, dict):
                raise ValueError("Item de orçamento inválido.")
            peca = Peca.objects.filter(pk=bruto.get('peca_id')).first() if bruto.get('peca_id') else None
            cotacao = None
            if bruto.get('valor_base') not in (None, ''):
                base = _parse_valor(bruto['valor_base'])
                if bruto.get('cotacao_id'):
                    cotacao = CotacaoPeca.objects.filter(pk=bruto['cotacao_id']).first()
            elif peca is not None:
                # Sem valor informado: usa a cotação mais recente da peça.
                cotacao = peca.cotacao_atual()
                if cotacao is None:
                    raise ValueError(f"A peça {peca.part_number} não tem cotação. Lance uma cotação ou informe o valor.")
                base = cotacao.valor
            else:
                raise ValueError("Informe o valor de cada peça.")

            bruta = bruto.get('quantidade')
            if bruta is None or bruta == '':
                quantidade = 1          # não informada: assume 1
            else:
                try:
                    quantidade = int(bruta)   # 0 e negativos NÃO viram 1: caem na validação abaixo
                except (TypeError, ValueError):
                    raise ValueError("Quantidade inválida.")
            if not 1 <= quantidade <= 999:
                raise ValueError("A quantidade deve estar entre 1 e 999.")

            unitario, adicional = calcular_item(base, primeiro=not itens, aplicar=aplicar_regra)
            itens.append(ItemOrcamento(
                peca=peca,
                cotacao=cotacao,
                nome=(bruto.get('nome') or (peca.part_number if peca else ''))[:150],
                descricao=(bruto.get('descricao') or (peca.descricao if peca else ''))[:255],
                part_number=(bruto.get('part_number') or (peca.part_number if peca else ''))[:100],
                quantidade=quantidade,
                valor_base=base,
                valor_unitario=unitario,
                adicional=adicional,
            ))
        if not itens:
            return itens
        if not all(i.nome or i.descricao or i.part_number for i in itens):
            raise ValueError("Cada peça precisa de nome, descrição ou PN.")
        return itens

    @staticmethod
    def salvar(dados: dict, funcionario_id: Optional[int], cargo: str = '') -> dict:
        id_orcamento = dados.get('id')
        funcionario = Funcionario.objects.filter(pk=funcionario_id).first() if funcionario_id else None

        valores = {}
        for campo, tamanho in CAMPOS_TEXTO.items():
            valores[campo] = (dados.get(campo) or '').strip()[:tamanho]
        for campo in CAMPOS_LONGOS:
            valores[campo] = (dados.get(campo) or '').strip()[:5000]
        valores['cliente_uf'] = (dados.get('cliente_uf') or '').strip().upper()[:2]

        if not valores['cliente_nome']:
            raise ValueError("Informe o nome do cliente.")
        if not valores['equip_modelo']:
            raise ValueError("Informe o modelo do equipamento.")

        disponibilidade = dados.get('disponibilidade') or ''
        if disponibilidade not in ('', 'disponivel', 'indisponivel'):
            raise ValueError("Disponibilidade inválida.")
        valores['disponibilidade'] = disponibilidade

        # Datas não vêm da tela: a emissão é hoje e a validade é de N dias corridos, contando o dia da emissão como dia 1.
        data_emissao = date.today()
        validade = calcular_validade(data_emissao)

        valores['triagem'] = Triagem.objects.filter(pk=dados.get('triagem_id')).first() if dados.get('triagem_id') else None
        valores['equipamento'] = Equipamento.objects.filter(pk=dados.get('equipamento_id')).first() if dados.get('equipamento_id') else None
        # O analista (e o e-mail dele) é sempre o do usuário logado, nunca digitado na tela.
        valores['analista_nome'] = funcionario.nome if funcionario else ''
        valores['analista_email'] = funcionario.email if funcionario else ''

        aplicar_regra = _bool(dados.get('aplicar_regra'), True)
        valores['aplicar_regra'] = aplicar_regra
        itens = OrcamentoService._montar_itens(dados.get('itens', []), aplicar_regra)

        with transaction.atomic():
            if id_orcamento:
                orc = Orcamento.objects.select_for_update().get(pk=id_orcamento)
                if orc.status != 'rascunho':
                    # Laudo já emitido: altera mantendo status, datas e analista, e registra no histórico.
                    OrcamentoService._alterar_emitido(orc, valores, itens, dados, funcionario, cargo)
                    return OrcamentoService.obter(orc.id_orcamento)
                for campo, valor in valores.items():
                    setattr(orc, campo, valor)
                orc.data_emissao = data_emissao
                orc.validade_ate = validade
                orc.analista = funcionario
                orc.save()
                orc.itens.all().delete()
            else:
                for _tentativa in range(3):
                    try:
                        with transaction.atomic():
                            orc = Orcamento.objects.create(
                                numero=OrcamentoService._proximo_numero(data_emissao.year),
                                data_emissao=data_emissao,
                                validade_ate=validade,
                                analista=funcionario,
                                **valores,
                            )
                        break
                    except IntegrityError:
                        continue  # outro usuário pegou o mesmo número; tenta o próximo
                else:
                    raise ValueError("Não foi possível gerar o número do orçamento. Tente novamente.")
            for item in itens:
                item.orcamento = orc
            ItemOrcamento.objects.bulk_create(itens)

        return OrcamentoService.obter(orc.id_orcamento)

    @staticmethod
    def _diferencas(orc: Orcamento, valores: dict, itens: list) -> list:
        """Lista o que mudou entre o laudo gravado e os dados recebidos (campos, peças e valor total)."""
        difs = []
        for campo, novo in valores.items():
            if campo == 'triagem':
                continue
            if campo == 'equipamento':
                if orc.equipamento_id != (novo.pk if novo else None):
                    difs.append({'campo': ROTULOS[campo], 'de': orc.equipamento.modelo if orc.equipamento else '—',
                                 'para': novo.modelo if novo else '—'})
                continue
            atual = getattr(orc, campo)
            if (atual or '') != (novo or ''):
                if campo == 'aplicar_regra':
                    difs.append({'campo': ROTULOS[campo], 'de': 'Aplicada' if atual else 'Não aplicada (valor cheio)',
                                 'para': 'Aplicada' if novo else 'Não aplicada (valor cheio)'})
                elif campo == 'disponibilidade':
                    nomes = dict(Orcamento.DISPONIBILIDADE_CHOICES)
                    difs.append({'campo': ROTULOS[campo], 'de': nomes.get(atual, '—') or '—', 'para': nomes.get(novo, '—') or '—'})
                else:
                    difs.append({'campo': ROTULOS.get(campo, campo), 'de': _curto(atual), 'para': _curto(novo)})
        antigos = list(orc.itens.all())
        antes, depois = _resumo_itens(antigos), _resumo_itens(itens)
        if antes != depois:
            difs.append({'campo': 'Peças do orçamento', 'de': antes or '—', 'para': depois or '—'})
        total_antes = sum((i.subtotal for i in antigos), Decimal('0'))
        total_depois = sum((i.valor_unitario * i.quantidade + i.adicional for i in itens), Decimal('0'))
        if total_antes != total_depois:
            difs.append({'campo': 'Valor total', 'de': _brl(total_antes), 'para': _brl(total_depois)})
        return difs

    @staticmethod
    def _alterar_emitido(orc: Orcamento, valores: dict, itens: list, dados: dict, funcionario, cargo: str) -> None:
        if orc.status not in STATUS_ALTERAVEIS:
            raise ValueError("Laudos cancelados não podem ser alterados.")
        if orc.status == 'aprovado' and cargo not in CARGOS_GESTAO:
            raise ValueError("Somente Gestor ou Administrador pode alterar um laudo já aprovado.")
        motivo = (dados.get('motivo_alteracao') or '').strip()
        if len(motivo) < 5:
            raise ValueError("Informe o motivo da alteração (mínimo de 5 caracteres).")

        # Analista, datas e número do laudo emitido não mudam.
        valores.pop('analista_nome', None)
        valores.pop('analista_email', None)
        difs = OrcamentoService._diferencas(orc, valores, itens)
        if not difs:
            raise ValueError("Nenhuma alteração foi feita no laudo.")

        for campo, valor in valores.items():
            setattr(orc, campo, valor)
        orc.save()
        orc.itens.all().delete()
        for item in itens:
            item.orcamento = orc
        ItemOrcamento.objects.bulk_create(itens)
        OrcamentoHistorico.objects.create(
            orcamento=orc, funcionario=funcionario, funcionario_nome=funcionario.nome if funcionario else '',
            motivo=motivo[:500], alteracoes=difs,
        )

    @staticmethod
    def historico(id_orcamento: int) -> list:
        orc = Orcamento.objects.get(pk=id_orcamento)
        return [
            {'id': h.id_historico, 'quando': django_timezone.localtime(h.criado_em).isoformat(),
             'usuario': h.funcionario_nome or '—', 'motivo': h.motivo, 'alteracoes': h.alteracoes}
            for h in orc.historico.all()
        ]

    @staticmethod
    def alterar_status(id_orcamento: int, novo_status: str, funcionario_id: Optional[int] = None, motivo_recusa: str = '') -> dict:
        motivo_recusa = ' '.join((motivo_recusa or '').split())[:300]
        with transaction.atomic():
            orc = Orcamento.objects.select_for_update().get(pk=id_orcamento)
            if novo_status not in TRANSICOES.get(orc.status, set()):
                raise ValueError(f"Não é possível mudar de '{orc.get_status_display()}' para '{novo_status}'.")
            if novo_status == 'emitido':
                faltando = []
                if not orc.cliente_nome: faltando.append('cliente')
                if not orc.equip_modelo: faltando.append('modelo do equipamento')
                if not orc.motivo_problema.strip(): faltando.append('motivo/problema')
                if not orc.analise.strip(): faltando.append('análise')
                if faltando:
                    raise ValueError("Para emitir, preencha: " + ", ".join(faltando) + ".")

                # Quem emite é o analista responsável; o e-mail é sempre o do cadastro dele.
                emissor = Funcionario.objects.filter(pk=funcionario_id).first() if funcionario_id else None
                if emissor is None:
                    raise ValueError("Não foi possível identificar o usuário que está emitindo o laudo.")
                if not emissor.email:
                    raise ValueError(
                        "Seu usuário não tem e-mail cadastrado. Peça a um Gestor para cadastrá-lo "
                        "em Gerenciar → Funcionário e tente emitir novamente."
                    )
                hoje = date.today()
                orc.analista = emissor
                orc.analista_nome = emissor.nome
                orc.analista_email = emissor.email
                orc.data_emissao = hoje
                orc.validade_ate = calcular_validade(hoje)
            status_antigo = orc.get_status_display()
            orc.status = novo_status
            # O motivo só existe enquanto o laudo está recusado (se voltar a 'emitido', ele é apagado).
            orc.motivo_recusa = motivo_recusa if novo_status == 'recusado' else ''
            orc.save()
            responsavel = Funcionario.objects.filter(pk=funcionario_id).first() if funcionario_id else None
            OrcamentoHistorico.objects.create(
                orcamento=orc, funcionario=responsavel, funcionario_nome=responsavel.nome if responsavel else '',
                motivo='Mudança de status',
                alteracoes=[{'campo': 'Status', 'de': status_antigo, 'para': orc.get_status_display()}]
                + ([{'campo': 'Motivo da recusa', 'de': '—', 'para': motivo_recusa}] if novo_status == 'recusado' and motivo_recusa else []),
            )
        return OrcamentoService.obter(id_orcamento)

    @staticmethod
    def excluir_rascunho(id_orcamento: int) -> None:
        orc = Orcamento.objects.get(pk=id_orcamento)
        if orc.status != 'rascunho':
            raise ValueError("Só é possível excluir rascunhos. Os demais podem ser cancelados.")
        orc.delete()

    @staticmethod
    def pesquisar(q: str = '', status: str = 'todos', de: str = '', ate: str = '',
                  pagina: int = 1, limite: int = 30) -> dict:
        qs = Orcamento.objects.annotate(total_calc=Sum(_VALOR_ITEM, output_field=_DECIMAL))
        q = (q or '').strip()
        if q:
            qs = qs.filter(
                Q(numero__icontains=q) | Q(ticket__icontains=q) | Q(cliente_nome__icontains=q)
                | Q(equip_sn__icontains=q) | Q(equip_modelo__icontains=q) | Q(analista_nome__icontains=q)
            )
        if status and status != 'todos':
            qs = qs.filter(status=status)
        if de:
            qs = qs.filter(data_emissao__gte=_data(de))
        if ate:
            qs = qs.filter(data_emissao__lte=_data(ate))

        total = qs.count()
        pagina = max(1, pagina)
        inicio = (pagina - 1) * limite
        pagina_qs = qs.order_by('-data_emissao', '-id_orcamento')[inicio:inicio + limite]
        itens = [
            {
                'id': o.id_orcamento,
                'numero': o.numero,
                'status': o.status,
                'status_nome': o.get_status_display(),
                'ticket': o.ticket,
                'cliente_nome': o.cliente_nome,
                'equip_modelo': o.equip_modelo,
                'equip_sn': o.equip_sn,
                'analista_nome': o.analista_nome,
                'data_emissao': o.data_emissao.isoformat(),
                'validade_ate': o.validade_ate.isoformat() if o.validade_ate else None,
                'valor_total': float(o.total_calc or 0),
            }
            for o in pagina_qs
        ]
        return {'dados': itens, 'total': total, 'pagina': pagina, 'paginas': max(1, -(-total // limite))}

    @staticmethod
    def pendentes_decisao() -> dict:
        """
        Laudos emitidos cuja validade já passou e que ainda não foram marcados como aprovados ou recusados.
        A validade vale até o fim do dia indicado em validade_ate; só no dia seguinte o laudo entra nesta lista.
        """
        hoje = date.today()
        qs = (Orcamento.objects.filter(status='emitido', validade_ate__lt=hoje)
              .annotate(total_calc=Sum(_VALOR_ITEM, output_field=_DECIMAL))
              .order_by('validade_ate', 'id_orcamento'))
        dados = [
            {
                'id': o.id_orcamento,
                'numero': o.numero,
                'cliente_nome': o.cliente_nome,
                'equip_modelo': o.equip_modelo,
                'ticket': o.ticket,
                'analista_nome': o.analista_nome,
                'data_emissao': o.data_emissao.isoformat(),
                'validade_ate': o.validade_ate.isoformat(),
                'dias_vencido': (hoje - o.validade_ate).days,
                'valor_total': float(o.total_calc or 0),
            }
            for o in qs[:200]
        ]
        return {'dados': dados, 'total': qs.count()}

    @staticmethod
    def estatisticas(de: str = '', ate: str = '') -> dict:
        qs = Orcamento.objects.all()
        if de:
            qs = qs.filter(data_emissao__gte=_data(de))
        if ate:
            qs = qs.filter(data_emissao__lte=_data(ate))

        por_status = {s: 0 for s, _ in Orcamento.STATUS_CHOICES}
        for linha in qs.values('status').annotate(n=Count('id_orcamento')):
            por_status[linha['status']] = linha['n']

        # Valores consideram só documentos que chegaram ao cliente (não rascunhos/cancelados).
        validos = qs.filter(status__in=['emitido', 'aprovado', 'recusado'])
        itens_validos = ItemOrcamento.objects.filter(orcamento__in=validos)
        soma = lambda base: base.aggregate(t=Sum(F('valor_unitario') * F('quantidade') + F('adicional'), output_field=_DECIMAL))['t'] or Decimal('0')

        valor_emitido = soma(itens_validos)
        valor_aprovado = soma(ItemOrcamento.objects.filter(orcamento__in=qs.filter(status='aprovado')))
        qtd_validos = validos.count()
        decididos = por_status['aprovado'] + por_status['recusado']

        por_mes = [
            {
                'mes': linha['mes'].strftime('%Y-%m'),
                'quantidade': linha['n'],
                'valor': float(linha['v'] or 0),
            }
            for linha in (
                validos.annotate(mes=TruncMonth('data_emissao')).values('mes')
                .annotate(n=Count('id_orcamento', distinct=True),
                          v=Sum(_VALOR_ITEM, output_field=_DECIMAL))
                .order_by('mes')
            )
        ]

        def ranking(campo, limite=8):
            return [
                {'nome': linha[campo] or '(sem nome)', 'quantidade': linha['n'], 'valor': float(linha['v'] or 0)}
                for linha in (
                    itens_validos.values(campo)
                    .annotate(n=Sum('quantidade'), v=Sum(F('valor_unitario') * F('quantidade') + F('adicional'), output_field=_DECIMAL))
                    .order_by('-n', '-v')[:limite]
                )
            ]

        top_clientes = [
            {'nome': linha['cliente_nome'], 'quantidade': linha['n'], 'valor': float(linha['v'] or 0)}
            for linha in (
                validos.values('cliente_nome')
                .annotate(n=Count('id_orcamento', distinct=True), v=Sum(_VALOR_ITEM, output_field=_DECIMAL))
                .order_by('-v')[:8]
            )
        ]
        top_modelos = [
            {'nome': linha['equip_modelo'], 'quantidade': linha['n']}
            for linha in qs.values('equip_modelo').annotate(n=Count('id_orcamento')).order_by('-n')[:8]
        ]

        motivos_recusa = [
            {'nome': linha['motivo_recusa'] or '(não informado)', 'quantidade': linha['n']}
            for linha in qs.filter(status='recusado').values('motivo_recusa').annotate(n=Count('id_orcamento')).order_by('-n')[:8]
        ]

        return {
            'total': qs.count(),
            'por_status': por_status,
            'motivos_recusa': motivos_recusa,
            'valor_emitido': float(valor_emitido),
            'valor_aprovado': float(valor_aprovado),
            'ticket_medio': float(valor_emitido / qtd_validos) if qtd_validos else 0.0,
            'taxa_aprovacao': round(por_status['aprovado'] * 100 / decididos, 1) if decididos else None,
            'por_mes': por_mes,
            'pecas_mais_orcadas': ranking('part_number'),
            'top_clientes': top_clientes,
            'top_modelos': top_modelos,
        }
