from django.urls import path
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

from .views import (
    RegistroView,
    RedefinirSenhaView,
    SolicitarRecuperacaoSenhaView,
    login_view,
    home_view,
    logout_view,
    AtivarDoisFatoresView,
    ConfirmarDoisFatoresView,
    validar_dois_fatores_view,
)

urlpatterns = [
    # --- ROTAS DA API (Processam os dados em JSON)
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", TokenObtainPairView.as_view(), name="login_api"),
    path("login/renovar/", TokenRefreshView.as_view(), name="login_renovar"),
    path("recuperar-senha/", SolicitarRecuperacaoSenhaView.as_view(), name="recuperar_senha"),
    path("redefinir-senha/", RedefinirSenhaView.as_view(), name="redefinir_senha"),
    path("2fa/ativar/", AtivarDoisFatoresView.as_view(), name="ativar_2fa"),
    path("2fa/confirmar/", ConfirmarDoisFatoresView.as_view(), name="confirmar_2fa"),

    # --- ROTAS DO FRONT-END HTML (Renderizam as telas visuais)
    path("entrar/", login_view, name="login_web"),
    path("home/", home_view, name="home"),
    path("sair/", logout_view, name="logout_web"),
    path("esqueci-minha-senha/", TemplateView.as_view(template_name="usuarios/recuperar_senha.html"), name="recuperar_senha_web"),
    path("esqueci-minha-senha/confirmar/", TemplateView.as_view(template_name="usuarios/redefinir_senha.html"), name="redefinir_senha_web"),
    path("2fa/validar/", validar_dois_fatores_view, name="validar_2fa_web"),
    path("cadastrar/", TemplateView.as_view(template_name="usuarios/cadastro.html"), name="cadastro_web"),
    path('perfil/', views.perfil_view, name='perfil'),
    path('perfil/exportar/', views.exportar_dados_view, name='exportar_dados'),
    path('perfil/2fa/', views.configurar_2fa_view, name='configurar_2fa'),
    path('perfil/revogar-consentimento/', views.revogar_consentimento_view, name='revogar_consentimento'),
    path('perfil/encerrar-conta/', views.encerrar_conta_view, name='encerrar_conta'),
]