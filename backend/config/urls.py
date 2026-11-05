"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # Raiz do site leva para a tela de login (também serve de ponto de
    # entrada para o spider do OWASP ZAP no pipeline de DAST).
    path('', RedirectView.as_view(url='/api/usuarios/entrar/', permanent=False)),
    path('admin/', admin.site.urls),
    path('admin/', admin.site.urls),
    path('api/usuarios/', include('usuarios.urls')),
    path('api/inventario/', include('inventario.urls')),
    path('api/emprestimos/', include('emprestimos.urls')),
]

