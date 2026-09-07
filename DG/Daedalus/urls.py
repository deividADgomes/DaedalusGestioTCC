from django.urls import path, include
from . import views

urlpatterns = [
    # ==========================================
    # TELAS (FRONT-END)
    # ==========================================
    path('', views.LoginView.as_view(), name='tela_login'), # Acessa via raiz
    path("principal/", views.daedalus_principal, name="principal"), # <--- CORRIGIDO: Rota isolada
    path("pesquisa/", views.daedalus_pesquisa, name="pesquisa"),
    path("visualizar/", views.daedalus_visualizar_triagem, name="visualizar"),
    path("dashboard/", views.daedalus_dashboard, name="dashboard"),
    
    # Telas de Gerenciamento
    path("gerenciar-empresa/", views.daedalus_gerenciarEmpresa, name="gerenciarEmpresa"),
    path("gerenciar-tecnico/", views.daedalus_gerenciarTecnico, name="gerenciarTecnico"),
    path("gerenciar-funcionario/", views.daedalus_gerenciarFuncionario, name="gerenciarFuncionario"),
    path("gerenciar-modelo-equipamento/", views.daedalus_gerenciarMdeloEquipamento, name="gerenciarModeloEquipamento"),
    
    # ==========================================
    # APIs E LÓGICA DE BACK-END
    # ==========================================
    path('api/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('api/empresa/', views.EmpresaView.as_view(), name='api_empresa'),
    path('api/tecnico/', views.TecnicoView.as_view(), name='api_tecnico'),
    path('api/funcionario/', views.FuncionarioView.as_view(), name='api_funcionario'),
    path('api/modelo-equipamento/', views.EquipamentoView.as_view(), name='api_modelo_equipamento'),
    path('api/triagem/', views.TriagemView.as_view(), name='api_triagem'),
    path('api/triagem/exportar-docx/', views.ExportarTriagemDocxView.as_view(), name='exportar_docx'),
    path('api/dashboard/', views.DashboardView.as_view(), name='api_dashboard'),
]