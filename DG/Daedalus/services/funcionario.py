import hmac
import logging
from typing import List, Optional

from django.conf import settings
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.utils import timezone

from ..dtos import FuncionarioDTO
from ..models import Funcionario, SolicitacaoSenha

logger = logging.getLogger(__name__)


def _senha_ja_tem_hash(valor: str) -> bool:
    try:
        identify_hasher(valor)
        return True
    except ValueError:
        return False


def _validar_nova_senha(senha: str) -> None:
    try:
        validate_password(senha)
    except ValidationError as e:
        raise ValueError(" ".join(e.messages))


def _normalizar_email(email: Optional[str]) -> str:
    email = (email or '').strip().lower()
    if not email:
        return ''
    try:
        validate_email(email)
    except ValidationError:
        raise ValueError("E-mail inválido.")
    return email


def _para_dto(func: Funcionario) -> FuncionarioDTO:
    return FuncionarioDTO(
        id_funcionario=func.id_funcionario,
        cargo=func.cargo,
        nome=func.nome,
        login=func.login,
        primeiro_acesso=func.primeiro_acesso,
        email=func.email,
    )


# ==========================================
# SERVIÇO DE FUNCIONÁRIO
# ==========================================
class FuncionarioService:
    @staticmethod
    def salvar(dto: FuncionarioDTO) -> FuncionarioDTO:
        if not (dto.nome or '').strip():
            raise ValueError("O nome é obrigatório.")
        if dto.email is not None:
            _normalizar_email(dto.email)    # só valida; a gravação normaliza de novo
        mesma_matricula = Funcionario.objects.filter(login=dto.login)
        if dto.id_funcionario:
            mesma_matricula = mesma_matricula.exclude(pk=dto.id_funcionario)
        if mesma_matricula.exists():
            raise ValueError("Já existe um funcionário com esta matrícula.")

        if dto.id_funcionario:
            func = Funcionario.objects.get(pk=dto.id_funcionario)
            func.cargo = dto.cargo
            func.nome = dto.nome.strip()
            func.login = dto.login
            if dto.email is not None:
                func.email = _normalizar_email(dto.email)
            if dto.senha:
                _validar_nova_senha(dto.senha)
                func.senha = make_password(dto.senha)
                # Senha redefinida por um gestor: o funcionário deve trocá-la no próximo acesso.
                func.primeiro_acesso = True
            func.save()
            if dto.senha:
                # Senha redefinida: os pedidos de recuperação pendentes deste funcionário ficam atendidos.
                SolicitacaoSenha.objects.filter(funcionario=func, atendida=False).update(atendida=True)
        else:
            if not dto.senha:
                raise ValueError("A senha é obrigatória para novos funcionários.")
            _validar_nova_senha(dto.senha)
            func = Funcionario.objects.create(
                cargo=dto.cargo,
                nome=dto.nome.strip(),
                login=dto.login,
                senha=make_password(dto.senha),
                primeiro_acesso=True,
                email=_normalizar_email(dto.email),
            )

        return _para_dto(func)

    @staticmethod
    def listar() -> List[FuncionarioDTO]:
        return [_para_dto(f) for f in Funcionario.objects.all()]

    @staticmethod
    def obter(id_funcionario: int) -> Optional[Funcionario]:
        return Funcionario.objects.filter(pk=id_funcionario).first()

    @staticmethod
    def _senha_confere(func: Funcionario, senha: str) -> bool:
        if _senha_ja_tem_hash(func.senha):
            return check_password(senha, func.senha)
        # Senha antiga ainda em texto puro (antes da migração 0014): compara em tempo constante
        # e, se confere, já converte para hash.
        if hmac.compare_digest(func.senha.encode(), senha.encode()):
            func.senha = make_password(senha)
            func.save(update_fields=['senha'])
            return True
        return False

    @staticmethod
    def autenticar(login: int, senha: str) -> Optional[FuncionarioDTO]:
        try:
            login = int(login)
        except (TypeError, ValueError):
            return None
        func = Funcionario.objects.filter(login=login).first()
        if func and FuncionarioService._senha_confere(func, str(senha)):
            return _para_dto(func)
        return None

    @staticmethod
    def trocar_senha(id_funcionario: int, senha_atual: str, nova_senha: str) -> None:
        func = Funcionario.objects.get(pk=id_funcionario)
        if not FuncionarioService._senha_confere(func, senha_atual or ''):
            raise ValueError("A senha atual está incorreta.")
        if senha_atual == nova_senha:
            raise ValueError("A nova senha deve ser diferente da atual.")
        _validar_nova_senha(nova_senha)
        func.senha = make_password(nova_senha)
        func.primeiro_acesso = False
        func.save(update_fields=['senha', 'primeiro_acesso'])


# ==========================================
# RECUPERAÇÃO DE SENHA (pedido na tela de login, atendido pelo Administrador)
# ==========================================
class SolicitacaoSenhaService:
    @staticmethod
    def registrar(login, email: str) -> None:
        """
        Registra o pedido e avisa os administradores por e-mail.
        Só vale quando matrícula e e-mail conferem com o cadastro; fora isso não faz nada
        (quem chama responde sempre a mesma mensagem, para não revelar se a matrícula existe).
        """
        email = (email or '').strip()
        if not email:
            return
        try:
            login = int(login)
        except (TypeError, ValueError):
            return
        func = Funcionario.objects.filter(login=login, email__iexact=email).first()
        if not func:
            return
        # Um único pedido pendente por funcionário evita repetição.
        if SolicitacaoSenha.objects.filter(funcionario=func, atendida=False).exists():
            return
        pedido = SolicitacaoSenha.objects.create(funcionario=func)
        SolicitacaoSenhaService._avisar_administradores(func, pedido)

    @staticmethod
    def _destinatarios_admin() -> list:
        emails = list(Funcionario.objects.filter(cargo='Administrador').exclude(email='').values_list('email', flat=True))
        extras = getattr(settings, 'DAEDALUS_EMAIL_ADMIN', '') or ''
        emails += [e.strip() for e in extras.split(',') if e.strip()]
        vistos, unicos = set(), []
        for e in emails:
            if e.lower() not in vistos:
                vistos.add(e.lower())
                unicos.append(e)
        return unicos

    @staticmethod
    def _avisar_administradores(func: Funcionario, pedido: SolicitacaoSenha) -> None:
        destinatarios = SolicitacaoSenhaService._destinatarios_admin()
        if not destinatarios:
            logger.warning("Pedido de redefinição de senha sem administrador com e-mail cadastrado (matrícula %s).", func.login)
            return
        data = timezone.localtime(pedido.data_solicitacao).strftime('%d/%m/%Y %H:%M')
        link = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
        onde = f"{link}/gerenciar-funcionario/" if link else "Gerenciar → Funcionário"
        corpo = (
            f"O funcionário {func.nome} (matrícula {func.login}, e-mail {func.email}) "
            f"solicitou a redefinição de senha em {data}.\n\n"
            f"Para atender: acesse {onde}, localize o pedido no painel \"Solicitações de redefinição de senha\", "
            "clique em \"Redefinir senha\" e informe uma senha provisória. "
            "No próximo login o usuário será obrigado a trocá-la.\n\n"
            "Você pode responder a este e-mail para falar diretamente com o solicitante."
        )
        try:
            EmailMessage(
                subject=f"[Daedalus Gestio] Redefinição de senha solicitada: {func.nome}",
                body=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=destinatarios,
                reply_to=[func.email],
            ).send(fail_silently=False)
        except Exception:
            # O pedido continua visível no painel mesmo se o servidor de e-mail falhar.
            logger.exception("Falha ao enviar o e-mail de redefinição de senha (matrícula %s).", func.login)

    @staticmethod
    def listar_pendentes() -> list:
        pedidos = SolicitacaoSenha.objects.filter(atendida=False).select_related('funcionario').order_by('data_solicitacao')
        return [
            {
                'id': p.id_solicitacao,
                'id_funcionario': p.funcionario.id_funcionario,
                'nome': p.funcionario.nome,
                'cargo': p.funcionario.cargo,
                'login': p.funcionario.login,
                'email': p.funcionario.email,
                'data': timezone.localtime(p.data_solicitacao).strftime('%d/%m/%Y %H:%M'),
            }
            for p in pedidos
        ]
