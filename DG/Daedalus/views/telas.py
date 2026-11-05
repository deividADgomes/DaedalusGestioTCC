from django.shortcuts import render

from ..services import ChamadoRFBService
from ..services.orcamento import precificacao_para_tela


# ==========================================
# RENDERIZAÇÃO DAS TELAS (FRONT-END)
# O login é exigido pelo AutenticacaoMiddleware.
# ==========================================
def daedalus_principal(request):
    """Menu principal (tela inicial): atalhos para todos os módulos."""
    nome = (getattr(request, 'funcionario_nome', '') or '').split()
    return render(request, 'Daedalus/TelaPrincipal/menu.html', {'primeiro_nome': nome[0] if nome else ''})


def daedalus_triagem(request):
    """Formulário de triagem (antes era a tela principal)."""
    return render(request, 'Daedalus/TelaPrincipal/index.html')


def daedalus_pesquisa(request):
    return render(request, 'Daedalus/Pesquisa/pesquisa.html')


def daedalus_gerenciarEmpresa(request):
    return render(request, 'Daedalus/GerenciarEmpresa/G_empresa.html')


def daedalus_gerenciarTecnico(request):
    return render(request, 'Daedalus/GerenciarTecnico/G_tecnico.html')


def daedalus_gerenciarFuncionario(request):
    return render(request, 'Daedalus/GerenciarFuncionario/G_funcionario.html')


def daedalus_gerenciarMdeloEquipamento(request):
    return render(request, 'Daedalus/GerenciarModeloEquipamento/G_modeloEquipamento.html')


def daedalus_dashboard(request):
    return render(request, 'Daedalus/Dashboard/dashboard.html')


def daedalus_visualizar_triagem(request):
    return render(request, 'Daedalus/Visualizar/visualizar.html')


def daedalus_saidas(request):
    """Saída de peças sem orçamento: lista enviada ao fiscal para emissão de nota."""
    return render(request, 'Daedalus/Saidas/saidas.html')


def daedalus_estoque(request):
    """Controle de estoque das peças."""
    return render(request, 'Daedalus/Estoque/estoque.html')


def daedalus_auditoria(request):
    """Quem alterou o quê nos cadastros (só Administrador/Gestor, regra em DAEDALUS_PERMISSOES)."""
    return render(request, 'Daedalus/Auditoria/auditoria.html')


def daedalus_serie(request):
    """Linha do tempo de um número de série (triagens, laudos e chamados RFB)."""
    return render(request, 'Daedalus/Serie/serie.html')


def daedalus_gerenciar_chamados_rfb(request):
    contexto = ChamadoRFBService.obter_dashboard()
    return render(request, 'Daedalus/GerenciarRFB/G_RFB.html', contexto)


def daedalus_emissao_laudos(request):
    # A tela usa estes números só para mostrar a prévia; o cálculo valendo é o do servidor.
    return render(request, 'Daedalus/Orcamentos/emissao.html', {'precificacao': precificacao_para_tela()})


def daedalus_pesquisa_laudos(request):
    return render(request, 'Daedalus/Orcamentos/pesquisa.html')


def daedalus_estatisticas_laudos(request):
    return render(request, 'Daedalus/Orcamentos/estatisticas.html')
