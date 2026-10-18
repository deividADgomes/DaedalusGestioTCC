from typing import List, Optional
import logging
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from .models import Empresa, Equipamento, Funcionario, SolicitacaoSenha, Tecnico, Triagem
from .dtos import EmpresaDTO, EquipamentoDTO, FuncionarioDTO, TecnicoDTO, TriagemDTO, StatusPeca
import os
from django.conf import settings
from docx import Document
from io import BytesIO
from datetime import date
from django.contrib.auth.hashers import make_password, check_password, identify_hasher
from django.utils import timezone
from django.utils.crypto import constant_time_compare

logger = logging.getLogger(__name__)


# ==========================================
# SERVIÇO DE EMPRESA
# ==========================================
class EmpresaService:
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
                tipo=dto.tipo
            )
        
        return EmpresaDTO(
            id_empresa=empresa.id_empresa,
            cnpj=empresa.cnpj,
            razao_social=empresa.razao_social,
            tipo=empresa.tipo
        )

    @staticmethod
    def listar(tipo_filtro: Optional[int] = None) -> List[EmpresaDTO]:
        # Se receber um filtro, busca apenas aquele tipo. Senão, busca todos.
        if tipo_filtro is not None:
            empresas = Empresa.objects.filter(tipo=tipo_filtro)
        else:
            empresas = Empresa.objects.all()
            
        return [
            EmpresaDTO(
                id_empresa=emp.id_empresa,
                cnpj=emp.cnpj,
                razao_social=emp.razao_social,
                tipo=emp.tipo
            ) for emp in empresas
        ]

# ==========================================
# SERVIÇO DE EQUIPAMENTO
# ==========================================
class EquipamentoService:
    @staticmethod
    def salvar(dto: EquipamentoDTO) -> EquipamentoDTO:
        pn = (dto.pn or '').strip()
        modelo = (dto.modelo or '').strip()
        if not pn or not modelo:
            raise ValueError("Part Number (PN) e Modelo são obrigatórios.")
        dto.pn, dto.modelo = pn, modelo

        # UC12: impede cadastro duplicado no catálogo (o PN identifica a peça de forma única)
        duplicado = Equipamento.objects.filter(pn__iexact=pn)
        if dto.id_equipamento:
            duplicado = duplicado.exclude(pk=dto.id_equipamento)
        if duplicado.exists():
            raise ValueError("Já existe um equipamento cadastrado com este Part Number.")

        if dto.id_equipamento:
            equip = Equipamento.objects.get(pk=dto.id_equipamento)
            equip.pn = dto.pn
            equip.modelo = dto.modelo
            equip.save()
        else:
            equip = Equipamento.objects.create(
                pn=dto.pn,
                modelo=dto.modelo
            )
            
        return EquipamentoDTO(
            id_equipamento=equip.id_equipamento,
            pn=equip.pn,
            modelo=equip.modelo
        )

    @staticmethod
    def listar() -> List[EquipamentoDTO]:
        equipamentos = Equipamento.objects.all()
        return [
            EquipamentoDTO(
                id_equipamento=eq.id_equipamento,
                pn=eq.pn,
                modelo=eq.modelo
            ) for eq in equipamentos
        ]


# ==========================================
# SERVIÇO DE FUNCIONÁRIO
# ==========================================
class FuncionarioService:
    SENHA_MIN = 4

    # ---------- senhas ----------
    @staticmethod
    def _senha_em_hash(valor: str) -> bool:
        try:
            identify_hasher(valor)
            return True
        except ValueError:
            return False

    @staticmethod
    def _conferir_senha(func: Funcionario, senha_informada: str) -> bool:
        """Confere a senha. Registros antigos (texto puro) são aceitos uma vez e convertidos para hash."""
        armazenada = func.senha or ''
        if FuncionarioService._senha_em_hash(armazenada):
            return check_password(senha_informada, armazenada)
        if constant_time_compare(str(senha_informada), armazenada):
            func.senha = make_password(senha_informada)
            func.save(update_fields=['senha'])
            return True
        return False

    # ---------- cadastro ----------
    @staticmethod
    def salvar(dto: FuncionarioDTO) -> FuncionarioDTO:
        nome = (dto.nome or '').strip()
        if not nome:
            raise ValueError("O nome é obrigatório.")
        if not dto.cargo:
            raise ValueError("O cargo é obrigatório.")
        cargo = dto.cargo.value if hasattr(dto.cargo, 'value') else dto.cargo

        email = (dto.email or '').strip()
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("E-mail inválido.")

        duplicado = Funcionario.objects.filter(login=dto.login)
        if dto.id_funcionario:
            duplicado = duplicado.exclude(pk=dto.id_funcionario)
        if duplicado.exists():
            raise ValueError("Já existe um funcionário com esta matrícula.")

        if dto.id_funcionario:
            func = Funcionario.objects.get(pk=dto.id_funcionario)
            func.cargo = cargo
            func.nome = nome
            func.login = dto.login
            func.email = email
            if dto.senha:
                # Redefinição feita pelo Administrador (UC09 - FA02): exige nova troca no próximo login
                func.senha = make_password(dto.senha)
                func.primeiro_acesso = True
            func.save()
            if dto.senha:
                # Encerra os pedidos de recuperação pendentes deste funcionário
                SolicitacaoSenha.objects.filter(funcionario=func, atendida=False).update(atendida=True)
        else:
            # UC07: sem senha informada, a matrícula vira a senha provisória
            senha_provisoria = dto.senha or str(dto.login)
            func = Funcionario.objects.create(
                cargo=cargo,
                nome=nome,
                login=dto.login,
                email=email,
                senha=make_password(senha_provisoria),
                primeiro_acesso=True
            )

        return FuncionarioDTO(
            id_funcionario=func.id_funcionario,
            cargo=func.cargo,
            nome=func.nome,
            login=func.login,
            primeiro_acesso=func.primeiro_acesso,
            email=func.email
        )

    @staticmethod
    def listar() -> List[FuncionarioDTO]:
        funcionarios = Funcionario.objects.all()
        return [
            FuncionarioDTO(
                id_funcionario=func.id_funcionario,
                cargo=func.cargo,
                nome=func.nome,
                login=func.login,
                primeiro_acesso=func.primeiro_acesso,
                email=func.email
            ) for func in funcionarios
        ]

    # ---------- autenticação ----------
    @staticmethod
    def autenticar(login: int, senha: str) -> Optional[FuncionarioDTO]:
        func = Funcionario.objects.filter(login=login).first()

        if func and FuncionarioService._conferir_senha(func, senha):
            return FuncionarioDTO(
                id_funcionario=func.id_funcionario,
                cargo=func.cargo,
                nome=func.nome,
                login=func.login,
                primeiro_acesso=func.primeiro_acesso,
                email=func.email
            )
        return None

    @staticmethod
    def alterar_senha(id_funcionario: int, senha_atual: str, nova_senha: str) -> None:
        """RF13/RF14: troca de senha pelo próprio usuário (inclusive a troca obrigatória do primeiro acesso)."""
        func = Funcionario.objects.filter(pk=id_funcionario).first()
        if not func:
            raise ValueError("Funcionário não encontrado.")
        if not senha_atual or not nova_senha:
            raise ValueError("Informe a senha atual e a nova senha.")
        if not FuncionarioService._conferir_senha(func, senha_atual):
            raise ValueError("Senha atual incorreta.")
        if len(nova_senha) < FuncionarioService.SENHA_MIN:
            raise ValueError(f"A nova senha deve ter pelo menos {FuncionarioService.SENHA_MIN} caracteres.")
        if nova_senha == senha_atual:
            raise ValueError("A nova senha deve ser diferente da atual.")
        if nova_senha == str(func.login):
            raise ValueError("A nova senha não pode ser igual à matrícula.")

        func.senha = make_password(nova_senha)
        func.primeiro_acesso = False
        func.save(update_fields=['senha', 'primeiro_acesso'])

class SolicitacaoSenhaService:
    """UC09: o usuário informa matrícula e e-mail cadastrados; o sistema avisa o administrador por e-mail."""

    @staticmethod
    def registrar(login: int, email: str) -> None:
        email = (email or '').strip()
        if not email:
            return
        # Só aceita o pedido quando matrícula e e-mail conferem com o cadastro
        func = Funcionario.objects.filter(login=login, email__iexact=email).first()
        if not func:
            return
        # Um único pedido pendente por funcionário evita repetição e spam
        if SolicitacaoSenha.objects.filter(funcionario=func, atendida=False).exists():
            return

        pedido = SolicitacaoSenha.objects.create(funcionario=func)
        SolicitacaoSenhaService._avisar_administradores(func, pedido)

    @staticmethod
    def _destinatarios_admin() -> list:
        emails = list(
            Funcionario.objects.filter(cargo='Administrador').exclude(email='').values_list('email', flat=True)
        )
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
        corpo = (
            f"O funcionário {func.nome} (matrícula {func.login}, e-mail {func.email}) "
            f"solicitou a redefinição de senha em {data}.\n\n"
            "Para atender: acesse Funcionário no Daedalus Gestio, localize o pedido no painel "
            "\"Solicitações de redefinição de senha\", clique em \"Redefinir senha\" e informe uma senha provisória. "
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
            # O pedido continua visível no painel mesmo se o servidor de e-mail falhar
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


# ==========================================
# SERVIÇO DE TÉCNICO
# ==========================================
class TecnicoService:
    @staticmethod
    def salvar(dto: TecnicoDTO) -> TecnicoDTO:
        # Busca a instância da Empresa no banco usando o ID recebido da tela
        empresa_obj = Empresa.objects.get(pk=dto.id_empresa)
        
        if dto.id_tecnico:
            tec = Tecnico.objects.get(pk=dto.id_tecnico)
            tec.nome = dto.nome
            tec.empresa = empresa_obj
            tec.save()
        else:
            tec = Tecnico.objects.create(nome=dto.nome, empresa=empresa_obj)
            
        return TecnicoDTO(
            id_tecnico=tec.id_tecnico,
            nome=tec.nome,
            id_empresa=tec.empresa.id_empresa
        )

    @staticmethod
    def listar() -> List[TecnicoDTO]:
        # select_related('empresa') evita o problema de N+1 queries no banco
        tecnicos = Tecnico.objects.select_related('empresa').all()
        return [
            TecnicoDTO(
                id_tecnico=tec.id_tecnico,
                nome=tec.nome,
                id_empresa=tec.empresa.id_empresa,
                nome_empresa=tec.empresa.razao_social
            ) for tec in tecnicos
        ]

# ==========================================
# SERVIÇO DE TRIAGEM
# ==========================================
class TriagemService:

    @staticmethod
    def validar(dto: TriagemDTO):
        if not dto.n_ticket:
            raise ValueError("O número do Ticket é obrigatório.")
        if not dto.sn or not str(dto.sn).strip():
            raise ValueError("O Serial Number (SN) é obrigatório.")
        # Validação atualizada para exigir os DOIS analistas
        if not dto.id_tecnico or not dto.id_cliente or not dto.id_analista_chamado or not dto.id_analista_triagem or not dto.id_equipamento:
            raise ValueError("Todos os vínculos (Técnico, Cliente, Analistas e Equipamento) são obrigatórios.")

    @staticmethod
    def salvar(dto: TriagemDTO) -> TriagemDTO:
        TriagemService.validar(dto)

        tecnico = Tecnico.objects.get(pk=dto.id_tecnico)
        cliente = Empresa.objects.get(pk=dto.id_cliente)
        equipamento = Equipamento.objects.get(pk=dto.id_equipamento)
        
        # Buscando as instâncias dos dois analistas
        analista_chamado = Funcionario.objects.get(pk=dto.id_analista_chamado)
        analista_triagem = Funcionario.objects.get(pk=dto.id_analista_triagem)

        if dto.id_triagem:
            triagem = Triagem.objects.get(pk=dto.id_triagem)
            triagem.n_ticket = dto.n_ticket
            triagem.nf = dto.nf
            triagem.cidade = dto.cidade
            triagem.estado = dto.estado
            triagem.sn = dto.sn
            triagem.status = dto.status_peca.value if hasattr(dto.status_peca, 'value') else dto.status_peca
            triagem.troca = dto.troca
            triagem.defeito_usuario = dto.defeito_usuario
            triagem.defeito_tecnico = dto.defeito_tecnico
            triagem.defeito_constatado = dto.defeito_constatado
            triagem.testes = dto.testes
            triagem.analise = dto.analise
            triagem.conclusao = dto.conclusao
            
            triagem.tecnico = tecnico
            triagem.cliente = cliente
            triagem.equipamento = equipamento
            # Atualizando os dois analistas
            triagem.analista_chamado = analista_chamado
            triagem.analista_triagem = analista_triagem
            
            triagem.save()
        else:
            triagem = Triagem.objects.create(
                n_ticket=dto.n_ticket,
                nf=dto.nf,
                cidade=dto.cidade,
                estado=dto.estado,
                sn=dto.sn,
                status=dto.status_peca.value if hasattr(dto.status_peca, 'value') else dto.status_peca,
                troca=dto.troca,
                defeito_usuario=dto.defeito_usuario,
                defeito_tecnico=dto.defeito_tecnico,
                defeito_constatado=dto.defeito_constatado,
                testes=dto.testes,
                analise=dto.analise,
                conclusao=dto.conclusao,
                tecnico=tecnico,
                cliente=cliente,
                equipamento=equipamento,
                # Salvando os dois analistas
                analista_chamado=analista_chamado,
                analista_triagem=analista_triagem
            )

        dto.id_triagem = triagem.id_triagem
        return dto

    @staticmethod
    def listar() -> List[TriagemDTO]:
        triagens = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').all()
        return [TriagemService._mapear_para_dto(t) for t in triagens]

    @staticmethod
    def buscar_por_id(id_triagem: int) -> Optional[TriagemDTO]:
        triagem = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(pk=id_triagem).first()
        if triagem:
            return TriagemService._mapear_para_dto(triagem)
        return None

    @staticmethod
    def buscar_por_ticket(ticket: int) -> Optional[TriagemDTO]:
        if not ticket:
            raise ValueError("Ticket obrigatório para a busca.")
            
        triagem = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(n_ticket=ticket).first()
        if triagem:
            return TriagemService._mapear_para_dto(triagem)
        return None

    @staticmethod
    def buscar_por_filtro(campo: str, valor: str) -> List[TriagemDTO]:
        if not valor or not campo:
            raise ValueError("Campo e valor de busca são obrigatórios.")
        
        campos_permitidos = ('n_ticket', 'nf', 'sn', 'cidade', 'estado',
                             'tecnico__nome', 'cliente__razao_social', 'equipamento__modelo')
        if campo not in campos_permitidos:
            raise ValueError("Campo de busca inválido.")

        filtro = {f"{campo}__icontains": valor}
        triagens = Triagem.objects.select_related('cliente', 'equipamento', 'tecnico', 'analista_chamado', 'analista_triagem').filter(**filtro)
        return [TriagemService._mapear_para_dto(t) for t in triagens]

    @staticmethod
    def deletar(ticket: int):
        if not ticket:
            raise ValueError("Ticket obrigatório para exclusão.")
        
        registros_apagados, _ = Triagem.objects.filter(n_ticket=ticket).delete()
        if registros_apagados == 0:
            raise ObjectDoesNotExist("Nenhuma triagem encontrada com este ticket.")
        

    # =======================================================
    # MÉTRICAS E ESTATÍSTICAS
    # =======================================================

    @staticmethod
    def total_triagens() -> int:
        return Triagem.objects.count()

    @staticmethod
    def total_peca_funcional() -> int:
        return Triagem.objects.filter(status=StatusPeca.FUNCIONAL).count()

    @staticmethod
    def total_peca_nao_funcional() -> int:
        return Triagem.objects.filter(status=StatusPeca.NAO_FUNCIONAL).count()

    # =======================================================
    # MÉTODOS AUXILIARES (Privados)
    # =======================================================
    
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
            
            # --- Mapeamento dos DOIS Analistas ---
            id_analista_chamado=triagem.analista_chamado_id,
            id_analista_triagem=triagem.analista_triagem_id,
            
            sn=triagem.sn,
            status_peca=StatusPeca(triagem.status),
            troca=triagem.troca,
            defeito_usuario=triagem.defeito_usuario,
            defeito_tecnico=triagem.defeito_tecnico,
            defeito_constatado=triagem.defeito_constatado,
            testes=triagem.testes,
            analise=triagem.analise,
            conclusao=triagem.conclusao,
            data_triagem=triagem.data_triagem,
            
            # --- Nomes para o Front-end e Exportação ---
            nome_cliente=triagem.cliente.razao_social,
            nome_equipamento=triagem.equipamento.modelo,
            nome_tecnico=triagem.tecnico.nome,
            nome_analista_chamado=triagem.analista_chamado.nome,
            nome_analista_triagem=triagem.analista_triagem.nome
        )

    @staticmethod
    def gerar_docx(id_triagem: int) -> tuple[BytesIO, str]:
        tri = TriagemService.buscar_por_id(id_triagem)
        if not tri:
            raise ValueError("Triagem não encontrada")

        template_path = os.path.join(settings.BASE_DIR, 'templates', 'Daedalus', 'TRIAGEM.docx')
        
        if not os.path.exists(template_path):
            raise FileNotFoundError("Modelo TRIAGEM.docx não encontrado.")
            
        doc = Document(template_path)
        # Data real da triagem (e não a data da exportação)
        data_triagem = timezone.localtime(tri.data_triagem).strftime("%d/%m/%Y") if tri.data_triagem else ""

        # ==========================================
        # TABELA 2: DADOS DO CHAMADO
        # ==========================================
        t2 = doc.tables[2]
        t2.cell(0, 0).text = f"Data: {data_triagem}"
        t2.cell(0, 1).text = f"NF: {tri.nf or ''}"
        t2.cell(0, 2).text = f"Ticket: {tri.n_ticket or ''}"
        
        t2.cell(1, 1).text = f"Técnico: {tri.nome_tecnico or ''}"
        
        # Insere ambos os analistas na tabela
        t2.cell(1, 2).text = f"Analista Chamado: {tri.nome_analista_chamado or ''} | Triagem: {tri.nome_analista_triagem or ''}"
        
        t2.cell(2, 1).text = f"Região: {tri.cidade or ''} - {tri.estado or ''}"
        t2.cell(2, 2).text = f"Equipamento: {tri.nome_equipamento or ''}"
        
        t2.cell(3, 1).text = f"N° de Série: {tri.sn or ''}"
        t2.cell(4, 1).text = f"Peça/Equipamento Trocado: {tri.troca or ''}"
        t2.cell(5, 1).text = f"Defeito alegado: {tri.defeito_usuario or ''}"
        t2.cell(6, 1).text = f"Constatação do Técnico: {tri.defeito_tecnico or ''}"

        # ==========================================
        # TABELA 4: LAUDO TÉCNICO
        # ==========================================
        t4 = doc.tables[4]
        t4.cell(0, 0).text = f"Defeito constatado: {tri.defeito_constatado or ''}"
        t4.cell(1, 0).text = f"Testes Realizados: {tri.testes or ''}"
        t4.cell(2, 0).text = f"Análise: {tri.analise or ''}"
        t4.cell(3, 0).text = f"Conclusão: {tri.conclusao or ''}"

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        # ==========================================
        # NOME DO ARQUIVO FORMATADO
        # ==========================================
        modelo_str = str(tri.nome_equipamento or 'SemModelo').replace(" ", "")
        cliente_str = str(tri.nome_cliente or 'SemCliente').replace(" ", "")
        ticket_str = str(tri.n_ticket)
        
        nome_arquivo = f"Triagem_{ticket_str}_{modelo_str}_{cliente_str}.docx"
        
        return buffer, nome_arquivo