import logging
import uuid
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from django.conf import settings
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from docx import Document
from docx.shared import Cm
from PIL import Image, ImageOps, UnidentifiedImageError

from .dtos import (
    CargoFuncionario,
    EmpresaDTO,
    EquipamentoDTO,
    FuncionarioDTO,
    StatusPeca,
    TecnicoDTO,
    TriagemDTO,
)
from .models import (
    Empresa,
    Equipamento,
    FotoTriagem,
    Funcionario,
    Peca,
    SolicitacaoSenha,
    Tecnico,
    Triagem,
)
from .partsurfer import buscar_pecas_por_pn

logger = logging.getLogger(__name__)

FORMATO_DATA_HORA = '%d/%m/%Y %H:%M'
FORMATO_DATA = '%d/%m/%Y'


def _normalizar_part_number(valor) -> str:
    return str(valor or '').strip().upper()


class EmpresaService:
    @staticmethod
    def _para_dto(empresa: Empresa) -> EmpresaDTO:
        return EmpresaDTO(
            id_empresa=empresa.id_empresa,
            cnpj=empresa.cnpj,
            razao_social=empresa.razao_social,
            tipo=empresa.tipo,
        )

    @staticmethod
    def salvar(dto: EmpresaDTO) -> EmpresaDTO:
        if dto.id_empresa:
            empresa = Empresa.objects.get(pk=dto.id_empresa)
            empresa.cnpj = dto.cnpj
            empresa.razao_social = dto.razao_social
            empresa.tipo = dto.tipo
            empresa.save()
        else:
            empresa = Empresa.objects.create(
                cnpj=dto.cnpj,
                razao_social=dto.razao_social,
                tipo=dto.tipo,
            )
        return EmpresaService._para_dto(empresa)

    @staticmethod
    def listar(tipo_filtro: Optional[int] = None) -> List[EmpresaDTO]:
        empresas = Empresa.objects.all()
        if tipo_filtro is not None:
            empresas = empresas.filter(tipo=tipo_filtro)
        return [EmpresaService._para_dto(empresa) for empresa in empresas]


INTERVALO_MINIMO_POR_EQUIPAMENTO = 15
MAX_CONSULTAS_POR_MINUTO = 20
MAX_PECAS_POR_MODELO = 200
TAMANHO_MAX_PART_NUMBER = 100
TAMANHO_MAX_DESCRICAO_PECA = 255


class LimiteConsultasExcedido(Exception):
    pass


def _controlar_taxa(id_equipamento: int) -> None:
    if not cache.add(f"partsurfer:equip:{id_equipamento}", 1, INTERVALO_MINIMO_POR_EQUIPAMENTO):
        raise LimiteConsultasExcedido(
            f"Este modelo foi consultado agora há pouco. Aguarde {INTERVALO_MINIMO_POR_EQUIPAMENTO} segundos."
        )

    chave_global = "partsurfer:global"
    cache.add(chave_global, 0, 60)
    try:
        total = cache.incr(chave_global)
    except ValueError:
        cache.set(chave_global, 1, 60)
        total = 1
    if total > MAX_CONSULTAS_POR_MINUTO:
        raise LimiteConsultasExcedido("Muitas consultas ao PartSurfer no último minuto. Tente novamente em instantes.")


class EquipamentoService:
    @staticmethod
    def salvar(dto: EquipamentoDTO) -> EquipamentoDTO:
        pn = (dto.pn or '').strip()
        modelo = (dto.modelo or '').strip()
        if not pn or not modelo:
            raise ValueError("Part Number (PN) e Modelo são obrigatórios.")

        duplicados = Equipamento.objects.filter(pn__iexact=pn)
        if dto.id_equipamento:
            duplicados = duplicados.exclude(pk=dto.id_equipamento)
        if duplicados.exists():
            raise ValueError("Já existe um equipamento cadastrado com este Part Number.")

        if dto.id_equipamento:
            equipamento = Equipamento.objects.get(pk=dto.id_equipamento)
            equipamento.pn = pn
            equipamento.modelo = modelo
            equipamento.save()
        else:
            equipamento = Equipamento.objects.create(pn=pn, modelo=modelo)

        return EquipamentoDTO(
            id_equipamento=equipamento.id_equipamento,
            pn=equipamento.pn,
            modelo=equipamento.modelo,
        )

    @staticmethod
    def listar() -> List[EquipamentoDTO]:
        equipamentos = Equipamento.objects.annotate(total_pecas=Count('pecas'))
        return [
            EquipamentoDTO(
                id_equipamento=equipamento.id_equipamento,
                pn=equipamento.pn,
                modelo=equipamento.modelo,
                total_pecas=equipamento.total_pecas,
            )
            for equipamento in equipamentos
        ]

    @staticmethod
    def listar_pecas(id_equipamento: int) -> List[dict]:
        equipamento = Equipamento.objects.get(pk=id_equipamento)
        return [
            {'id': peca.id_peca, 'part_number': peca.part_number, 'descricao': peca.descricao}
            for peca in equipamento.pecas.order_by('part_number')
        ]

    @staticmethod
    def consultar_partsurfer(id_equipamento: int) -> List[dict]:
        equipamento = Equipamento.objects.get(pk=id_equipamento)
        _controlar_taxa(id_equipamento)
        pecas_hp = buscar_pecas_por_pn(equipamento.pn)

        if not pecas_hp:
            raise ValueError(
                f"O PartSurfer não retornou peças para o PN {equipamento.pn}. Confira se o Part Number está correto."
            )

        vinculadas = {peca.part_number: peca for peca in equipamento.pecas.all()}
        candidatas, vistos = [], set()
        for item in pecas_hp:
            part_number = _normalizar_part_number(item.get('part_number'))
            if not part_number or part_number in vistos:
                continue
            vistos.add(part_number)
            candidatas.append({
                'part_number': part_number,
                'descricao': item.get('descricao', ''),
                'selecionada': part_number in vinculadas,
                'somente_local': False,
            })

        for part_number, peca in vinculadas.items():
            if part_number not in vistos:
                candidatas.append({
                    'part_number': part_number,
                    'descricao': peca.descricao,
                    'selecionada': True,
                    'somente_local': True,
                })

        candidatas.sort(key=lambda candidata: candidata['part_number'])
        return candidatas

    @staticmethod
    def _escolher_pecas(itens: List[dict]) -> dict:
        if not isinstance(itens, list):
            raise ValueError("Lista de peças inválida.")

        escolhidas = {}
        for item in itens:
            if not isinstance(item, dict):
                continue
            part_number = _normalizar_part_number(item.get('part_number'))
            if not part_number:
                continue
            if len(part_number) > TAMANHO_MAX_PART_NUMBER:
                raise ValueError(f"Part Number muito longo: {part_number[:20]}...")
            descricao = str(item.get('descricao') or '').strip()
            escolhidas[part_number] = descricao[:TAMANHO_MAX_DESCRICAO_PECA]

        if len(escolhidas) > MAX_PECAS_POR_MODELO:
            raise ValueError(f"Limite de {MAX_PECAS_POR_MODELO} peças por modelo.")
        return escolhidas

    @staticmethod
    def salvar_pecas(id_equipamento: int, itens: List[dict]) -> List[dict]:
        escolhidas = EquipamentoService._escolher_pecas(itens)
        equipamento = Equipamento.objects.get(pk=id_equipamento)

        with transaction.atomic():
            existentes = {
                peca.part_number: peca
                for peca in Peca.objects.filter(part_number__in=list(escolhidas))
            }
            vinculos = []
            for part_number, descricao in escolhidas.items():
                peca = existentes.get(part_number)
                if peca is None:
                    peca = Peca.objects.create(part_number=part_number, descricao=descricao)
                elif descricao and peca.descricao != descricao:
                    peca.descricao = descricao
                    peca.save(update_fields=['descricao'])
                vinculos.append(peca)
            equipamento.pecas.set(vinculos)

        return EquipamentoService.listar_pecas(id_equipamento)


class FuncionarioService:
    SENHA_MIN = 4

    @staticmethod
    def _senha_em_hash(valor: str) -> bool:
        try:
            identify_hasher(valor)
            return True
        except ValueError:
            return False

    @staticmethod
    def _conferir_senha(funcionario: Funcionario, senha_informada: str) -> bool:
        armazenada = funcionario.senha or ''
        if FuncionarioService._senha_em_hash(armazenada):
            return check_password(senha_informada, armazenada)

        if constant_time_compare(str(senha_informada), armazenada):
            funcionario.senha = make_password(senha_informada)
            funcionario.save(update_fields=['senha'])
            return True
        return False

    @staticmethod
    def _para_dto(funcionario: Funcionario) -> FuncionarioDTO:
        return FuncionarioDTO(
            id_funcionario=funcionario.id_funcionario,
            cargo=funcionario.cargo,
            nome=funcionario.nome,
            login=funcionario.login,
            primeiro_acesso=funcionario.primeiro_acesso,
            email=funcionario.email,
        )

    @staticmethod
    def _validar_cadastro(dto: FuncionarioDTO) -> tuple:
        nome = (dto.nome or '').strip()
        if not nome:
            raise ValueError("O nome é obrigatório.")
        if not dto.cargo:
            raise ValueError("O cargo é obrigatório.")
        cargo = CargoFuncionario(dto.cargo).value

        email = (dto.email or '').strip()
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("E-mail inválido.")

        duplicados = Funcionario.objects.filter(login=dto.login)
        if dto.id_funcionario:
            duplicados = duplicados.exclude(pk=dto.id_funcionario)
        if duplicados.exists():
            raise ValueError("Já existe um funcionário com esta matrícula.")

        return nome, cargo, email

    @staticmethod
    def salvar(dto: FuncionarioDTO) -> FuncionarioDTO:
        nome, cargo, email = FuncionarioService._validar_cadastro(dto)

        if dto.id_funcionario:
            funcionario = Funcionario.objects.get(pk=dto.id_funcionario)
            funcionario.cargo = cargo
            funcionario.nome = nome
            funcionario.login = dto.login
            funcionario.email = email
            if dto.senha:
                funcionario.senha = make_password(dto.senha)
                funcionario.primeiro_acesso = True
            funcionario.save()
            if dto.senha:
                SolicitacaoSenha.objects.filter(funcionario=funcionario, atendida=False).update(atendida=True)
        else:
            senha_provisoria = dto.senha or str(dto.login)
            funcionario = Funcionario.objects.create(
                cargo=cargo,
                nome=nome,
                login=dto.login,
                email=email,
                senha=make_password(senha_provisoria),
                primeiro_acesso=True,
            )

        return FuncionarioService._para_dto(funcionario)

    @staticmethod
    def listar() -> List[FuncionarioDTO]:
        return [FuncionarioService._para_dto(funcionario) for funcionario in Funcionario.objects.all()]

    @staticmethod
    def autenticar(login: int, senha: str) -> Optional[FuncionarioDTO]:
        funcionario = Funcionario.objects.filter(login=login).first()
        if funcionario and FuncionarioService._conferir_senha(funcionario, senha):
            return FuncionarioService._para_dto(funcionario)
        return None

    @staticmethod
    def alterar_senha(id_funcionario: int, senha_atual: str, nova_senha: str) -> None:
        funcionario = Funcionario.objects.filter(pk=id_funcionario).first()
        if not funcionario:
            raise ValueError("Funcionário não encontrado.")
        if not senha_atual or not nova_senha:
            raise ValueError("Informe a senha atual e a nova senha.")
        if not FuncionarioService._conferir_senha(funcionario, senha_atual):
            raise ValueError("Senha atual incorreta.")
        if len(nova_senha) < FuncionarioService.SENHA_MIN:
            raise ValueError(f"A nova senha deve ter pelo menos {FuncionarioService.SENHA_MIN} caracteres.")
        if nova_senha == senha_atual:
            raise ValueError("A nova senha deve ser diferente da atual.")
        if nova_senha == str(funcionario.login):
            raise ValueError("A nova senha não pode ser igual à matrícula.")

        funcionario.senha = make_password(nova_senha)
        funcionario.primeiro_acesso = False
        funcionario.save(update_fields=['senha', 'primeiro_acesso'])


class SolicitacaoSenhaService:
    @staticmethod
    def registrar(login: int, email: str) -> None:
        email = (email or '').strip()
        if not email:
            return

        funcionario = Funcionario.objects.filter(login=login, email__iexact=email).first()
        if not funcionario:
            return
        if SolicitacaoSenha.objects.filter(funcionario=funcionario, atendida=False).exists():
            return

        pedido = SolicitacaoSenha.objects.create(funcionario=funcionario)
        SolicitacaoSenhaService._avisar_administradores(funcionario, pedido)

    @staticmethod
    def _destinatarios_admin() -> List[str]:
        emails = list(
            Funcionario.objects
            .filter(cargo=CargoFuncionario.ADMINISTRADOR.value)
            .exclude(email='')
            .values_list('email', flat=True)
        )
        extras = getattr(settings, 'DAEDALUS_EMAIL_ADMIN', '') or ''
        emails += [email.strip() for email in extras.split(',') if email.strip()]

        sem_repeticao = {}
        for email in emails:
            sem_repeticao.setdefault(email.lower(), email)
        return list(sem_repeticao.values())

    @staticmethod
    def _montar_corpo_email(funcionario: Funcionario, pedido: SolicitacaoSenha) -> str:
        data = timezone.localtime(pedido.data_solicitacao).strftime(FORMATO_DATA_HORA)
        return (
            f"O funcionário {funcionario.nome} (matrícula {funcionario.login}, e-mail {funcionario.email}) "
            f"solicitou a redefinição de senha em {data}.\n\n"
            "Para atender: acesse Funcionário no Daedalus Gestio, localize o pedido no painel "
            "\"Solicitações de redefinição de senha\", clique em \"Redefinir senha\" e informe uma senha provisória. "
            "No próximo login o usuário será obrigado a trocá-la.\n\n"
            "Você pode responder a este e-mail para falar diretamente com o solicitante."
        )

    @staticmethod
    def _avisar_administradores(funcionario: Funcionario, pedido: SolicitacaoSenha) -> None:
        destinatarios = SolicitacaoSenhaService._destinatarios_admin()
        if not destinatarios:
            logger.warning(
                "Pedido de redefinição de senha sem administrador com e-mail cadastrado (matrícula %s).",
                funcionario.login,
            )
            return

        try:
            EmailMessage(
                subject=f"[Daedalus Gestio] Redefinição de senha solicitada: {funcionario.nome}",
                body=SolicitacaoSenhaService._montar_corpo_email(funcionario, pedido),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=destinatarios,
                reply_to=[funcionario.email],
            ).send(fail_silently=False)
        except Exception:
            logger.exception("Falha ao enviar o e-mail de redefinição de senha (matrícula %s).", funcionario.login)

    @staticmethod
    def listar_pendentes() -> List[dict]:
        pedidos = (
            SolicitacaoSenha.objects
            .filter(atendida=False)
            .select_related('funcionario')
            .order_by('data_solicitacao')
        )
        return [
            {
                'id': pedido.id_solicitacao,
                'id_funcionario': pedido.funcionario.id_funcionario,
                'nome': pedido.funcionario.nome,
                'cargo': pedido.funcionario.cargo,
                'login': pedido.funcionario.login,
                'email': pedido.funcionario.email,
                'data': timezone.localtime(pedido.data_solicitacao).strftime(FORMATO_DATA_HORA),
            }
            for pedido in pedidos
        ]


class TecnicoService:
    @staticmethod
    def salvar(dto: TecnicoDTO) -> TecnicoDTO:
        empresa = Empresa.objects.get(pk=dto.id_empresa)

        if dto.id_tecnico:
            tecnico = Tecnico.objects.get(pk=dto.id_tecnico)
            tecnico.nome = dto.nome
            tecnico.empresa = empresa
            tecnico.save()
        else:
            tecnico = Tecnico.objects.create(nome=dto.nome, empresa=empresa)

        return TecnicoDTO(
            id_tecnico=tecnico.id_tecnico,
            nome=tecnico.nome,
            id_empresa=tecnico.empresa.id_empresa,
        )

    @staticmethod
    def listar() -> List[TecnicoDTO]:
        tecnicos = Tecnico.objects.select_related('empresa')
        return [
            TecnicoDTO(
                id_tecnico=tecnico.id_tecnico,
                nome=tecnico.nome,
                id_empresa=tecnico.empresa.id_empresa,
                nome_empresa=tecnico.empresa.razao_social,
            )
            for tecnico in tecnicos
        ]


class TriagemService:
    CAMPOS_BUSCA_PERMITIDOS = (
        'n_ticket', 'nf', 'sn', 'cidade', 'estado',
        'tecnico__nome', 'cliente__razao_social', 'equipamento__modelo',
    )
    MODELO_LAUDO = Path(settings.BASE_DIR) / 'templates' / 'Daedalus' / 'TRIAGEM.docx'

    @staticmethod
    def validar(dto: TriagemDTO) -> None:
        if not dto.n_ticket:
            raise ValueError("O número do Ticket é obrigatório.")
        if not dto.sn or not str(dto.sn).strip():
            raise ValueError("O Serial Number (SN) é obrigatório.")

        vinculos = (
            dto.id_tecnico,
            dto.id_cliente,
            dto.id_analista_chamado,
            dto.id_analista_triagem,
            dto.id_equipamento,
        )
        if not all(vinculos):
            raise ValueError("Todos os vínculos (Técnico, Cliente, Analistas e Equipamento) são obrigatórios.")

    @staticmethod
    def _buscar_peca_do_modelo(equipamento: Equipamento, id_peca: Optional[int]) -> Optional[Peca]:
        if not id_peca:
            return None
        peca = equipamento.pecas.filter(pk=id_peca).first()
        if peca is None:
            raise ValueError("A peça trocada não pertence ao modelo de equipamento selecionado.")
        return peca

    @staticmethod
    def salvar(dto: TriagemDTO) -> TriagemDTO:
        TriagemService.validar(dto)

        equipamento = Equipamento.objects.get(pk=dto.id_equipamento)
        campos = {
            'n_ticket': dto.n_ticket,
            'nf': dto.nf,
            'cidade': dto.cidade,
            'estado': dto.estado,
            'sn': dto.sn,
            'status': int(dto.status_peca),
            'troca': dto.troca,
            'peca_trocada': TriagemService._buscar_peca_do_modelo(equipamento, dto.id_peca_trocada),
            'defeito_usuario': dto.defeito_usuario,
            'defeito_tecnico': dto.defeito_tecnico,
            'defeito_constatado': dto.defeito_constatado,
            'testes': dto.testes,
            'analise': dto.analise,
            'conclusao': dto.conclusao,
            'tecnico': Tecnico.objects.get(pk=dto.id_tecnico),
            'cliente': Empresa.objects.get(pk=dto.id_cliente),
            'equipamento': equipamento,
            'analista_chamado': Funcionario.objects.get(pk=dto.id_analista_chamado),
            'analista_triagem': Funcionario.objects.get(pk=dto.id_analista_triagem),
        }

        if dto.id_triagem:
            triagem = Triagem.objects.get(pk=dto.id_triagem)
            for campo, valor in campos.items():
                setattr(triagem, campo, valor)
            triagem.save()
        else:
            triagem = Triagem.objects.create(**campos)

        dto.id_triagem = triagem.id_triagem
        return dto

    @staticmethod
    def _consulta_com_relacionamentos():
        return Triagem.objects.select_related(
            'cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem', 'peca_trocada'
        )

    @staticmethod
    def listar() -> List[TriagemDTO]:
        return [TriagemService._mapear_para_dto(t) for t in TriagemService._consulta_com_relacionamentos()]

    @staticmethod
    def buscar_por_id(id_triagem: int) -> Optional[TriagemDTO]:
        triagem = TriagemService._consulta_com_relacionamentos().filter(pk=id_triagem).first()
        return TriagemService._mapear_para_dto(triagem) if triagem else None

    @staticmethod
    def buscar_por_filtro(campo: str, valor: str) -> List[TriagemDTO]:
        if not valor or not campo:
            raise ValueError("Campo e valor de busca são obrigatórios.")
        if campo not in TriagemService.CAMPOS_BUSCA_PERMITIDOS:
            raise ValueError("Campo de busca inválido.")

        triagens = TriagemService._consulta_com_relacionamentos().filter(**{f"{campo}__icontains": valor})
        return [TriagemService._mapear_para_dto(t) for t in triagens]

    @staticmethod
    def deletar(ticket: int) -> None:
        if not ticket:
            raise ValueError("Ticket obrigatório para exclusão.")

        for foto in FotoTriagem.objects.filter(triagem__n_ticket=ticket):
            foto.arquivo.delete(save=False)
        registros_apagados, _ = Triagem.objects.filter(n_ticket=ticket).delete()
        if registros_apagados == 0:
            raise ObjectDoesNotExist("Nenhuma triagem encontrada com este ticket.")

    @staticmethod
    def _mapear_para_dto(triagem: Triagem) -> TriagemDTO:
        return TriagemDTO(
            id_triagem=triagem.id_triagem,
            n_ticket=triagem.n_ticket,
            nf=triagem.nf,
            cidade=triagem.cidade,
            estado=triagem.estado,
            id_tecnico=triagem.tecnico_id,
            id_cliente=triagem.cliente_id,
            id_equipamento=triagem.equipamento_id,
            id_analista_chamado=triagem.analista_chamado_id,
            id_analista_triagem=triagem.analista_triagem_id,
            sn=triagem.sn,
            status_peca=StatusPeca(triagem.status),
            troca=triagem.troca,
            id_peca_trocada=triagem.peca_trocada_id,
            peca_trocada=str(triagem.peca_trocada) if triagem.peca_trocada_id else None,
            defeito_usuario=triagem.defeito_usuario,
            defeito_tecnico=triagem.defeito_tecnico,
            defeito_constatado=triagem.defeito_constatado,
            testes=triagem.testes,
            analise=triagem.analise,
            conclusao=triagem.conclusao,
            data_triagem=triagem.data_triagem,
            nome_cliente=triagem.cliente.razao_social,
            nome_equipamento=triagem.equipamento.modelo,
            nome_tecnico=triagem.tecnico.nome,
            nome_analista_chamado=triagem.analista_chamado.nome,
            nome_analista_triagem=triagem.analista_triagem.nome,
        )

    @staticmethod
    def _preencher_dados_do_chamado(documento, triagem: TriagemDTO) -> None:
        data = timezone.localtime(triagem.data_triagem).strftime(FORMATO_DATA) if triagem.data_triagem else ""
        pecas_trocadas = ' | '.join(item for item in (triagem.peca_trocada, triagem.troca) if item)
        analistas = (
            f"Analista Chamado: {triagem.nome_analista_chamado or ''} | "
            f"Triagem: {triagem.nome_analista_triagem or ''}"
        )

        tabela = documento.tables[2]
        tabela.cell(0, 0).text = f"Data: {data}"
        tabela.cell(0, 1).text = f"NF: {triagem.nf or ''}"
        tabela.cell(0, 2).text = f"Ticket: {triagem.n_ticket or ''}"
        tabela.cell(1, 1).text = f"Técnico: {triagem.nome_tecnico or ''}"
        tabela.cell(1, 2).text = analistas
        tabela.cell(2, 1).text = f"Região: {triagem.cidade or ''} - {triagem.estado or ''}"
        tabela.cell(2, 2).text = f"Equipamento: {triagem.nome_equipamento or ''}"
        tabela.cell(3, 1).text = f"N° de Série: {triagem.sn or ''}"
        tabela.cell(4, 1).text = f"Peça/Equipamento Trocado: {pecas_trocadas}"
        tabela.cell(5, 1).text = f"Defeito alegado: {triagem.defeito_usuario or ''}"
        tabela.cell(6, 1).text = f"Constatação do Técnico: {triagem.defeito_tecnico or ''}"

    @staticmethod
    def _preencher_laudo_tecnico(documento, triagem: TriagemDTO) -> None:
        tabela = documento.tables[4]
        tabela.cell(0, 0).text = f"Defeito constatado: {triagem.defeito_constatado or ''}"
        tabela.cell(1, 0).text = f"Testes Realizados: {triagem.testes or ''}"
        tabela.cell(2, 0).text = f"Análise: {triagem.analise or ''}"
        tabela.cell(3, 0).text = f"Conclusão: {triagem.conclusao or ''}"

    @staticmethod
    def _nome_do_arquivo_docx(triagem: TriagemDTO) -> str:
        modelo = str(triagem.nome_equipamento or 'SemModelo').replace(" ", "")
        cliente = str(triagem.nome_cliente or 'SemCliente').replace(" ", "")
        return f"Triagem_{triagem.n_ticket}_{modelo}_{cliente}.docx"

    @staticmethod
    def gerar_docx(id_triagem: int) -> tuple[BytesIO, str]:
        triagem = TriagemService.buscar_por_id(id_triagem)
        if not triagem:
            raise ValueError("Triagem não encontrada")
        if not TriagemService.MODELO_LAUDO.exists():
            raise FileNotFoundError("Modelo TRIAGEM.docx não encontrado.")

        documento = Document(TriagemService.MODELO_LAUDO)
        TriagemService._preencher_dados_do_chamado(documento, triagem)
        TriagemService._preencher_laudo_tecnico(documento, triagem)
        FotoService.inserir_no_docx(documento, id_triagem)

        buffer = BytesIO()
        documento.save(buffer)
        buffer.seek(0)
        return buffer, TriagemService._nome_do_arquivo_docx(triagem)


class FotoService:
    MAX_FOTOS = 10
    MAX_BYTES = 10 * 1024 * 1024
    MAX_LADO = 1600
    FORMATOS = ('JPEG', 'PNG', 'WEBP')
    MAX_LEGENDA = 150
    QUALIDADE_JPEG = 85
    LARGURA_NO_LAUDO = Cm(7.0)

    @staticmethod
    def _para_dict(foto: FotoTriagem) -> dict:
        return {
            'id': foto.id_foto,
            'url': f"/fotos/{foto.id_foto}/",
            'legenda': foto.legenda,
            'criado_em': timezone.localtime(foto.criado_em).isoformat(),
        }

    @staticmethod
    def listar(id_triagem: int) -> List[dict]:
        return [FotoService._para_dict(foto) for foto in FotoTriagem.objects.filter(triagem_id=id_triagem)]

    @staticmethod
    def _abrir_imagem(arquivo):
        try:
            imagem = Image.open(arquivo)
            if imagem.format not in FotoService.FORMATOS:
                raise ValueError("Formato não suportado. Envie JPG, PNG ou WEBP.")
            imagem = ImageOps.exif_transpose(imagem)
            imagem.load()
            return imagem
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValueError("O arquivo enviado não é uma imagem válida.")

    @staticmethod
    def _converter_para_rgb(imagem):
        if imagem.mode == 'RGB':
            return imagem
        if imagem.mode == 'L':
            return imagem.convert('RGB')

        fundo = Image.new('RGB', imagem.size, (255, 255, 255))
        com_transparencia = imagem.convert('RGBA')
        fundo.paste(com_transparencia, mask=com_transparencia.split()[-1])
        return fundo

    @staticmethod
    def _processar(arquivo) -> bytes:
        if arquivo.size > FotoService.MAX_BYTES:
            raise ValueError("A foto excede o limite de 10 MB.")

        imagem = FotoService._converter_para_rgb(FotoService._abrir_imagem(arquivo))
        imagem.thumbnail((FotoService.MAX_LADO, FotoService.MAX_LADO))

        saida = BytesIO()
        imagem.save(saida, format='JPEG', quality=FotoService.QUALIDADE_JPEG, optimize=True)
        return saida.getvalue()

    @staticmethod
    def adicionar(id_triagem: int, arquivo, legenda: str = '') -> dict:
        triagem = Triagem.objects.get(pk=id_triagem)
        if triagem.fotos.count() >= FotoService.MAX_FOTOS:
            raise ValueError(f"Limite de {FotoService.MAX_FOTOS} fotos por triagem.")

        conteudo = FotoService._processar(arquivo)
        foto = FotoTriagem(triagem=triagem, legenda=(legenda or '').strip()[:FotoService.MAX_LEGENDA])
        foto.arquivo.save(f"{uuid.uuid4().hex}.jpg", ContentFile(conteudo), save=False)
        foto.save()
        return FotoService._para_dict(foto)

    @staticmethod
    def excluir(id_foto: int) -> None:
        foto = FotoTriagem.objects.filter(pk=id_foto).first()
        if foto is None:
            raise ObjectDoesNotExist("Foto não encontrada.")
        foto.arquivo.delete(save=False)
        foto.delete()

    @staticmethod
    def inserir_no_docx(documento, id_triagem: int) -> None:
        fotos = list(FotoTriagem.objects.filter(triagem_id=id_triagem))
        if not fotos:
            return

        documento.add_paragraph().add_run("Registro fotográfico").bold = True
        linhas = (len(fotos) + 1) // 2
        tabela = documento.add_table(rows=linhas, cols=2)

        for indice, foto in enumerate(fotos):
            celula = tabela.cell(indice // 2, indice % 2)
            paragrafo = celula.paragraphs[0]
            try:
                with foto.arquivo.open('rb') as arquivo:
                    paragrafo.add_run().add_picture(BytesIO(arquivo.read()), width=FotoService.LARGURA_NO_LAUDO)
            except (FileNotFoundError, OSError):
                paragrafo.add_run("[foto indisponível]")
            if foto.legenda:
                celula.add_paragraph(foto.legenda)
