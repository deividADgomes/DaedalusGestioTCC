from typing import List, Optional
from django.core.exceptions import ObjectDoesNotExist
from .models import Empresa, Equipamento, Funcionario, Tecnico, Triagem
from .dtos import EmpresaDTO, EquipamentoDTO, FuncionarioDTO, TecnicoDTO, TriagemDTO, StatusPeca
import os
from django.conf import settings
from docx import Document
from io import BytesIO
from datetime import date


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
    @staticmethod
    def salvar(dto: FuncionarioDTO) -> FuncionarioDTO:
        if dto.id_funcionario:
            func = Funcionario.objects.get(pk=dto.id_funcionario)
            func.cargo = dto.cargo
            func.nome = dto.nome
            func.login = dto.login
            if dto.senha:
                func.senha = dto.senha
                # Opcional: Se o Admin resetar a senha, podemos forçar o primeiro acesso de novo
                # func.primeiro_acesso = True 
            func.save()
        else:
            func = Funcionario.objects.create(
                cargo=dto.cargo,
                nome=dto.nome,
                login=dto.login,
                senha=dto.senha,
                primeiro_acesso=True # Garante que todo novo usuário comece com True
            )
            
        return FuncionarioDTO(
            id_funcionario=func.id_funcionario,
            cargo=func.cargo,
            nome=func.nome,
            login=func.login,
            primeiro_acesso=func.primeiro_acesso
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
                primeiro_acesso=func.primeiro_acesso
            ) for func in funcionarios
        ]
    
    @staticmethod
    def autenticar(login: int, senha: str) -> Optional[FuncionarioDTO]:
        # Busca no Banco de Dados o Funcionário correspondente
        func = Funcionario.objects.filter(login=login, senha=senha).first()
        
        if func:
            return FuncionarioDTO(
                id_funcionario=func.id_funcionario,
                cargo=func.cargo,
                nome=func.nome,
                login=func.login,
                primeiro_acesso=func.primeiro_acesso
            )
        return None

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
        data_hoje = date.today().strftime("%d/%m/%Y")

        # ==========================================
        # TABELA 2: DADOS DO CHAMADO
        # ==========================================
        t2 = doc.tables[2]
        t2.cell(0, 0).text = f"Data: {data_hoje}"
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