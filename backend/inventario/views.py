from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import generics, permissions

from auditoria.models import RegistroAuditoria
from .models import Categoria, Equipamento
from .serializers import CategoriaSerializer, EquipamentoSerializer


def get_client_ip(request):

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class IsAdminOuTecnico(permissions.BasePermission):
    """
    Permissão customizada baseada no RBAC do model Usuario (campo 'papel').

    Qualquer usuário autenticado pode LER o catálogo (GET), mas só
    ADMIN ou TECNICO podem CRIAR/EDITAR/EXCLUIR equipamentos e
    categorias, são eles que fazem a gestão física do inventário,
    não o aluno que só empresta.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.papel in ("ADMIN", "TECNICO")
        )


class CategoriaListCreateView(generics.ListCreateAPIView):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOuTecnico]


class CategoriaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOuTecnico]


class EquipamentoListCreateView(generics.ListCreateAPIView):

    queryset = Equipamento.objects.select_related("categoria").all()
    serializer_class = EquipamentoSerializer
    permission_classes = [IsAdminOuTecnico]

    def perform_create(self, serializer):
        equipamento = serializer.save()

        RegistroAuditoria.objects.create(
            usuario=self.request.user,
            acao='CREATE',
            modulo_afetado='Inventário',
            descricao=f'Equipamento cadastrado: {equipamento.nome} (patrimônio {equipamento.patrimonio}).',
            ip_origem=get_client_ip(self.request),
        )


class EquipamentoDetailView(generics.RetrieveUpdateDestroyAPIView):

    queryset = Equipamento.objects.select_related("categoria").all()
    serializer_class = EquipamentoSerializer
    permission_classes = [IsAdminOuTecnico]

    def perform_update(self, serializer):
        equipamento = serializer.save()
        RegistroAuditoria.objects.create(
            usuario=self.request.user,
            acao='UPDATE',
            modulo_afetado='Inventário',
            descricao=f'Equipamento atualizado: {equipamento.nome} (patrimônio {equipamento.patrimonio}).',
            ip_origem=get_client_ip(self.request),
        )

    def perform_destroy(self, instance):
        # Guarda os dados antes de apagar, porque depois do delete()
        # a instância não existe mais para ser lida na descrição do log.
        descricao = f'Equipamento excluído: {instance.nome} (patrimônio {instance.patrimonio}).'
        RegistroAuditoria.objects.create(
            usuario=self.request.user,
            acao='DELETE',
            modulo_afetado='Inventário',
            descricao=descricao,
            ip_origem=get_client_ip(self.request),
        )
        instance.delete()

@login_required(login_url='/api/usuarios/entrar/')
def catalogo_view(request):

    equipamentos = Equipamento.objects.select_related('categoria').all()
    return render(request, 'inventario/catalogo.html', {'equipamentos': equipamentos})