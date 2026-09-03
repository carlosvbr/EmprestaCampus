from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegistroView, RedefinirSenhaView, SolicitarRecuperacaoSenhaView

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("login/renovar/", TokenRefreshView.as_view(), name="login_renovar"),
    path("recuperar-senha/", SolicitarRecuperacaoSenhaView.as_view(), name="recuperar_senha"),
    path("redefinir-senha/", RedefinirSenhaView.as_view(), name="redefinir_senha"),
]