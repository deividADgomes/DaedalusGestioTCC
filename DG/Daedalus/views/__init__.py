"""
Views da aplicação, divididas por assunto. `urls.py` continua usando `views.NomeDaView`.
"""
from .autenticacao import (AlterarSenhaAPIView, LoginAPIView, LoginView, LogoutView, RecuperarSenhaView,
                           SolicitacoesSenhaView)
from .cadastros import (ConsultarPartSurferView, CotacaoDetalheView, CotacoesPecaView, EmpresaView,
                        EquipamentoView, FuncionarioView, ImportarPecasView, PecaManualView, PecaRemoverView, PecasEquipamentoView,
                        TecnicoView)
from .orcamentos import (OrcamentoDetalheView, OrcamentoHistoricoView, OrcamentoCopiaView, OrcamentoDocxView, OrcamentoEmailView, OrcamentoEstatisticasView,
                         OrcamentoPrePreenchimentoView, OrcamentoStatusView, OrcamentosPendentesView,
                         OrcamentosView)
from .rfb import AgendamentoAPIView, ChamadosRFBAPIView, RFBModelosView
from .telas import (daedalus_saidas, daedalus_estoque, daedalus_auditoria, daedalus_serie, daedalus_dashboard, daedalus_emissao_laudos, daedalus_estatisticas_laudos,
                    daedalus_gerenciar_chamados_rfb, daedalus_gerenciarEmpresa,
                    daedalus_gerenciarFuncionario, daedalus_gerenciarMdeloEquipamento,
                    daedalus_gerenciarTecnico, daedalus_pesquisa, daedalus_pesquisa_laudos,
                    daedalus_principal, daedalus_triagem, daedalus_visualizar_triagem)
from .bi import (BIAtualizarView, BIComercialView, BIExecutivoView, BIFiltrosView, BIInsightLidoView, BIInsightsView,
                 BIOperacaoView, BIPecasView, BIChamadosAnalistaView, BIPecaRegioesView, BIQualidadeView)
from .auditoria import AuditoriaView
from .avisos import AvisosView, BuscaView, SessaoPingView
from .estoque import (EstoqueCatalogoView, EstoqueConfigView, EstoqueHistoricoView, EstoqueMovimentarView,
                      EstoqueView)
from .saidas import (SaidaCancelarView, SaidaCsvView, SaidaDetalheView, SaidaEnviarView, SaidaNotaView,
                     SaidaRetornoView, SaidasView)
from .serie import SerieView, TriagemPorSerieView
from .triagem import ExportarTriagemDocxView, TriagemHistoricoView, TriagemOpcoesView, TriagemView
