"""
Camada de serviços (regras de negócio), dividida por assunto.

Os nomes continuam disponíveis em `Daedalus.services` para quem já importava de lá.
"""
from .agendamento import AgendamentoService
from .bi import BIService
from .chamado_rfb import ChamadoRFBService
from .empresa import EmpresaService, cnpj_valido
from .equipamento import EquipamentoService, LimiteConsultasExcedido
from .funcionario import FuncionarioService, SolicitacaoSenhaService
from .orcamento import OrcamentoService
from .pecas import CotacaoService
from .tecnico import TecnicoService
from .triagem import TriagemService
from .utils import consultar_ibge_metropolitana, get_feriados_nacionais, normalizar_texto

__all__ = [
    'AgendamentoService', 'BIService', 'ChamadoRFBService', 'CotacaoService', 'EmpresaService',
    'EquipamentoService', 'FuncionarioService', 'LimiteConsultasExcedido', 'OrcamentoService',
    'SolicitacaoSenhaService', 'TecnicoService', 'TriagemService', 'cnpj_valido', 'consultar_ibge_metropolitana',
    'get_feriados_nacionais', 'normalizar_texto',
]
