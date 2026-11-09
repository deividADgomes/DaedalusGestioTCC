from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import IntEnum, Enum


class TipoEmpresa(IntEnum):
    PRESTADORA = 1
    CLIENTE = 2
    FORNECEDOR = 3

class StatusPeca(IntEnum):
    FUNCIONAL = 1
    NAO_FUNCIONAL = 2

class CargoFuncionario(str, Enum):
    FUNCIONARIO = "Funcionário"
    ANALISTA_TRIAGEM = "Analista de Triagem"
    GESTOR = "Gestor" 
    ADMINISTRADOR = "Administrador"
@dataclass
class EmpresaDTO:
    cnpj: str
    razao_social: str
    tipo: TipoEmpresa
    id_empresa: Optional[int] = None

@dataclass
class EquipamentoDTO:
    pn: str
    modelo: str
    id_equipamento: Optional[int] = None
    total_pecas: int = 0
    pecas_sincronizadas_em: Optional[str] = None
    tipo: str = ''
    marca: str = ''
    rfb: bool = False

@dataclass
class PecaDTO:
    part_number: str
    descricao: str = ""
    id_peca: Optional[int] = None
    cotacao_atual: Optional[dict] = None

@dataclass
class FuncionarioDTO:
    cargo: CargoFuncionario
    nome: str
    login: int
    id_funcionario: Optional[int] = None
    senha: Optional[str] = None
    primeiro_acesso: bool = True
    email: Optional[str] = None   # None = não alterar

@dataclass
class TecnicoDTO:
    nome: str
    id_empresa: int
    id_tecnico: Optional[int] = None
    nome_empresa: Optional[str] = None
@dataclass
class TriagemDTO:
    n_ticket: int
    nf: int
    cidade: str
    estado: str
    id_tecnico: int
    id_cliente: int
    id_analista_chamado: int
    id_analista_triagem: int

    id_equipamento: int
    sn: str
    status_peca: StatusPeca 
    id_triagem: Optional[int] = None
    
    # AGORA COM O TÉCNICO INCLUÍDO:
    nome_cliente: Optional[str] = None
    nome_analista_chamado: Optional[str] = None
    nome_analista_triagem: Optional[str] = None
    nome_equipamento: Optional[str] = None
    nome_tecnico: Optional[str] = None  # <--- Faltava esta linha!
    
    troca: Optional[str] = None
    id_peca_trocada: Optional[int] = None
    troca_indevida: Optional[bool] = None
    ct: Optional[str] = None
    motivo_troca_indevida: Optional[str] = None
    justificativa_troca_indevida: Optional[str] = None
    defeito_usuario: Optional[str] = None
    defeito_tecnico: Optional[str] = None
    defeito_constatado: Optional[str] = None
    testes: Optional[str] = None
    analise: Optional[str] = None
    conclusao: Optional[str] = None
    criado_em: Optional[datetime] = None