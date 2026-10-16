from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework import generics, permissions

from auditoria.models import RegistroAuditoria
from auditoria.utils import get_client_ip
from .models import Categoria, Equipamento
from .serializers import CategoriaSerializer, EquipamentoSerializer

class IsAdmin(permissions.BasePermission):
    """
    Permissão customizada baseada no RBAC do model Usuario (campo 'papel').

    Qualquer usuário autenticado pode LER o catálogo (GET), mas só
    o ADMIN pode CRIAR/EDITAR/EXCLUIR equipamentos e categorias, pois
    é ele quem faz a gestão do inventário, não o aluno que só empresta.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.papel == "ADMIN"
        )


class CategoriaListCreateView(generics.ListCreateAPIView):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdmin]


class CategoriaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdmin]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "Esta categoria possui equipamentos cadastrados e não pode ser excluída."
            )


class EquipamentoListCreateView(generics.ListCreateAPIView):

    queryset = Equipamento.objects.select_related("categoria").all()
    serializer_class = EquipamentoSerializer
    permission_classes = [IsAdmin]

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
    permission_classes = [IsAdmin]

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
        try:
            instance.delete()
        except ProtectedError:

            raise ValidationError(
                "Este equipamento tem empréstimos no histórico e não pode ser excluído. "
                "Marque-o como Inativo."
            )
        
        RegistroAuditoria.objects.create(
            usuario=self.request.user,
            acao='DELETE',
            modulo_afetado='Inventário',
            descricao=descricao,
            ip_origem=get_client_ip(self.request),
        )

@login_required(login_url='/api/usuarios/entrar/')
def catalogo_view(request):
    """
    Tela HTML de consulta do catálogo. select_related('categoria')
    evita N+1 queries pra mostrar o nome da categoria de cada
    equipamento.
    """
    from emprestimos.models import Emprestimo  # import local pra evitar import circular entre os apps

    equipamentos = Equipamento.objects.select_related('categoria').all()

    equipamentos_ja_solicitados = set(
        Emprestimo.objects.filter(
            usuario=request.user,
            status__in=['SOLICITADO', 'APROVADO'],
        ).values_list('equipamento_id', flat=True)
    )

    return render(request, 'inventario/catalogo.html', {
        'equipamentos': equipamentos,
        'equipamentos_ja_solicitados': equipamentos_ja_solicitados,
    })