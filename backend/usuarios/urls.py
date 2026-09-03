from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegistroView, RedefinirSenhaView, SolicitarRecuperacaoSenhaView, login_view, home_view

urlpatterns = [
    # --- ROTAS DA API COM JWT
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", TokenObtainPairView.as_view(), name="login_api"),
    path("login/renovar/", TokenRefreshView.as_view(), name="login_renovar"),
    path("recuperar-senha/", SolicitarRecuperacaoSenhaView.as_view(), name="recuperar_senha"),
    path("redefinir-senha/", RedefinirSenhaView.as_view(), name="redefinir_senha"),

    # --- ROTAS DO FRONT-END HTML
    path("entrar/", login_view, name="login_web"),
    path("home/", home_view, name="home"),
]