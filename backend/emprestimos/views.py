from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import generics, permissions

from auditoria.models import RegistroAuditoria
from inventario.models import Equipamento
from .models import Emprestimo
from .serializers import EmprestimoSerializer, SolicitarEmprestimoSerializer


def get_client_ip(request):
    # Mesma função repetida em usuarios/ e inventario/, mantendo o
    # padrão de cada app ser independente (sem import cruzado só por
    # causa dessa função auxiliar).
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class SolicitarEmprestimoView(generics.CreateAPIView):
    """POST /api/emprestimos/solicitar/ — qualquer usuário logado pode pedir."""
    serializer_class = SolicitarEmprestimoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        emprestimo = serializer.save()

        RegistroAuditoria.objects.create(
            usuario=self.request.user,
            acao='CREATE',
            modulo_afetado='Empréstimos',
            descricao=f'Solicitação criada para o equipamento {emprestimo.equipamento.nome}.',
            ip_origem=get_client_ip(self.request),
        )


class MeusEmprestimosAPIView(generics.ListAPIView):
    """GET /api/emprestimos/meus/ — só retorna empréstimos do próprio usuário logado."""
    serializer_class = EmprestimoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Emprestimo.objects
            .filter(usuario=self.request.user)
            .select_related('equipamento')
            .order_by('-data_solicitacao')
        )


@login_required(login_url='/api/usuarios/entrar/')
def solicitar_emprestimo_view(request, equipamento_id):
    if request.method != 'POST':
        return redirect('catalogo_web')

    equipamento = get_object_or_404(
        Equipamento,
        id=equipamento_id
    )

    if equipamento.status != 'DISPONIVEL':
        messages.error(
            request,
            'Este equipamento não está mais disponível.'
        )
        return redirect('catalogo_web')

    ja_tem_pedido_aberto = Emprestimo.objects.filter(
        usuario=request.user,
        equipamento=equipamento,
        status__in=['SOLICITADO', 'APROVADO'],
    ).exists()

    if ja_tem_pedido_aberto:
        messages.error(
            request,
            'Você já tem uma solicitação em aberto para este equipamento.'
        )
        return redirect('catalogo_web')

    Emprestimo.objects.create(
        usuario=request.user,
        equipamento=equipamento,
        observacoes='',
        status='SOLICITADO',
    )

    RegistroAuditoria.objects.create(
        usuario=request.user,
        acao='CREATE',
        modulo_afetado='Empréstimos',
        descricao=(
            f'Solicitação criada para o equipamento '
            f'{equipamento.nome}.'
        ),
        ip_origem=get_client_ip(request),
    )

    messages.success(
        request,
        'Sua solicitação foi enviada.'
    )

    return redirect('catalogo_web')


@login_required(login_url='/api/usuarios/entrar/')
def meus_emprestimos_view(request):
    emprestimos = (
        Emprestimo.objects
        .filter(usuario=request.user)
        .select_related('equipamento')
        .order_by('-data_solicitacao')
    )

    return render(
        request,
        'emprestimos/meus_emprestimos.html',
        {'emprestimos': emprestimos}
    )


@login_required(login_url='/api/usuarios/entrar/')
def solicitar_prorrogacao_view(request, emprestimo_id):

    if request.method != 'POST':
        return redirect('meus_emprestimos_web')

    emprestimo = get_object_or_404(
        Emprestimo,
        id=emprestimo_id,
        usuario=request.user,
    )

    if emprestimo.status != 'APROVADO' or emprestimo.prorrogacao_solicitada:
        messages.error(
            request,
            'Não é possível solicitar prorrogação para este empréstimo no momento.'
        )
        return redirect('meus_emprestimos_web')

    emprestimo.prorrogacao_solicitada = True
    emprestimo.save()

    RegistroAuditoria.objects.create(
        usuario=request.user,
        acao='UPDATE',
        modulo_afetado='Empréstimos',
        descricao=(
            f'Prorrogação solicitada para o equipamento '
            f'{emprestimo.equipamento.nome}.'
        ),
        ip_origem=get_client_ip(request),
    )

    messages.success(
        request,
        'Solicitação de prorrogação enviada. Aguarde a aprovação do administrador.'
    )

    return redirect('meus_emprestimos_web')