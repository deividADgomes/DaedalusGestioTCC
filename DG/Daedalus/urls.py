from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path('', views.LoginView.as_view(), name='tela_login'),
    path('principal/', TemplateView.as_view(template_name='Daedalus/TelaPrincipal/index.html'), name='principal'),
    path('pesquisa/', TemplateView.as_view(template_name='Daedalus/Pesquisa/pesquisa.html'), name='pesquisa'),
    path('visualizar/', TemplateView.as_view(template_name='Daedalus/Visualizar/visualizar.html'), name='visualizar'),
    path('dashboard/', TemplateView.as_view(template_name='Daedalus/Dashboard/dashboard.html'), name='dashboard'),
    path(
        'primeiro-acesso/',
        TemplateView.as_view(template_name='Daedalus/PrimeiroAcesso/primeiro_acesso.html'),
        name='primeiro_acesso',
    ),
    path(
        'gerenciar-empresa/',
        TemplateView.as_view(template_name='Daedalus/GerenciarEmpresa/G_empresa.html'),
        name='gerenciarEmpresa',
    ),
    path(
        'gerenciar-tecnico/',
        TemplateView.as_view(template_name='Daedalus/GerenciarTecnico/G_tecnico.html'),
        name='gerenciarTecnico',
    ),
    path(
        'gerenciar-funcionario/',
        TemplateView.as_view(template_name='Daedalus/GerenciarFuncionario/G_funcionario.html'),
        name='gerenciarFuncionario',
    ),
    path(
        'gerenciar-modelo-equipamento/',
        TemplateView.as_view(template_name='Daedalus/GerenciarModeloEquipamento/G_modeloEquipamento.html'),
        name='gerenciarModeloEquipamento',
    ),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('fotos/<int:id_foto>/', views.entregar_foto, name='foto_arquivo'),
    path('api/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('api/alterar-senha/', views.AlterarSenhaView.as_view(), name='api_alterar_senha'),
    path('api/recuperar-senha/', views.RecuperarSenhaView.as_view(), name='api_recuperar_senha'),
    path('api/solicitacoes-senha/', views.SolicitacoesSenhaView.as_view(), name='api_solicitacoes_senha'),
    path('api/empresa/', views.EmpresaView.as_view(), name='api_empresa'),
    path('api/tecnico/', views.TecnicoView.as_view(), name='api_tecnico'),
    path('api/funcionario/', views.FuncionarioView.as_view(), name='api_funcionario'),
    path('api/modelo-equipamento/', views.EquipamentoView.as_view(), name='api_modelo_equipamento'),
    path(
        'api/modelo-equipamento/<int:id_equipamento>/partsurfer/',
        views.ConsultarPartSurferView.as_view(),
        name='api_partsurfer',
    ),
    path('api/modelo-equipamento/pecas/', views.PecasEquipamentoView.as_view(), name='api_pecas_equipamento'),
    path('api/triagem/', views.TriagemView.as_view(), name='api_triagem'),
    path('api/triagem/fotos/', views.FotoTriagemView.as_view(), name='api_triagem_fotos'),
    path('api/triagem/exportar-docx/', views.ExportarTriagemDocxView.as_view(), name='exportar_docx'),
    path('api/dashboard/', views.DashboardView.as_view(), name='api_dashboard'),
    path('api/dashboard/exportar/', views.DashboardExportarView.as_view(), name='api_dashboard_exportar'),
]
