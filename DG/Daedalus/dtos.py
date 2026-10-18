from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import IntEnum, Enum


class TipoEmpresa(IntEnum):
    PRESTADORA = 1
    CLIENTE = 2

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

@dataclass
class FuncionarioDTO:
    cargo: CargoFuncionario
    nome: str
    login: int
    id_funcionario: Optional[int] = None
    senha: Optional[str] = None
    primeiro_acesso: bool = True
    email: Optional[str] = None

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
    defeito_usuario: Optional[str] = None
    defeito_tecnico: Optional[str] = None
    defeito_constatado: Optional[str] = None
    testes: Optional[str] = None
    analise: Optional[str] = None
    conclusao: Optional[str] = None
    data_triagem: Optional[datetime] = None