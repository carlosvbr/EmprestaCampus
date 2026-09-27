from django.urls import path
from . import views

urlpatterns = [
    # --- API ---
    path("solicitar/", views.SolicitarEmprestimoView.as_view(), name="solicitar_emprestimo_api"),
    path("meus/", views.MeusEmprestimosAPIView.as_view(), name="meus_emprestimos_api"),

    # --- Telas HTML ---
    path("novo/<int:equipamento_id>/", views.solicitar_emprestimo_view, name="solicitar_emprestimo_web"),
    path("historico/", views.meus_emprestimos_view, name="meus_emprestimos_web"),
    path("prorrogar/<int:emprestimo_id>/", views.solicitar_prorrogacao_view, name="solicitar_prorrogacao_web"),
]