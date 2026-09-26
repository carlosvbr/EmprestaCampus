from django.urls import path
from . import views

urlpatterns = [
    path("categorias/", views.CategoriaListCreateView.as_view(), name="categoria_list_create"),
    path("categorias/<int:pk>/", views.CategoriaDetailView.as_view(), name="categoria_detail"),

    path("equipamentos/", views.EquipamentoListCreateView.as_view(), name="equipamento_list_create"),
    path("equipamentos/<int:pk>/", views.EquipamentoDetailView.as_view(), name="equipamento_detail"),
    
    path("catalogo/", views.catalogo_view, name="catalogo_web"),
]