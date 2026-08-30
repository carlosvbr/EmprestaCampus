from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegistroView, login_view, home_view

urlpatterns = [
    # --- ROTAS DA API COM JWT
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", TokenObtainPairView.as_view(), name="login_api"), # Alterado levemente o 'name' para evitar conflito
    path("login/renovar/", TokenRefreshView.as_view(), name="login_renovar"),

    # --- ROTAS DO FRONT-END HTML
    path("entrar/", login_view, name="login_web"),

    # --- ROTA DE DESTINO PÓS-LOGIN ---
    path("home/", home_view, name="home"), # O name="home" conecta com o redirect('home')
]