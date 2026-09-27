from django.contrib import admin
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from auditoria.models import RegistroAuditoria
from .models import Emprestimo


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = (
        'equipamento', 'usuario', 'status', 'data_solicitacao',
        'data_devolucao_prevista', 'esta_atrasado_admin', 'prorrogacao_solicitada',
    )
    list_filter = ('status', 'prorrogacao_solicitada')
    search_fields = ('usuario__username', 'equipamento__nome', 'equipamento__patrimonio')

    # Esses três campos só devem mudar através das ações abaixo, por isso ficam readonly no admin.
    readonly_fields = ('data_solicitacao', 'data_retirada', 'data_devolucao_real')

    actions = [
        'aprovar_emprestimos', 'rejeitar_emprestimos', 'marcar_devolvido',
        'aprovar_prorrogacao', 'rejeitar_prorrogacao',
    ]

    @admin.display(boolean=True, description='Atrasado?')
    def esta_atrasado_admin(self, obj):
        return obj.esta_atrasado()

    @admin.action(description='Aprovar empréstimos selecionados')
    def aprovar_emprestimos(self, request, queryset):
        pendentes = list(queryset.filter(status='SOLICITADO'))
        aprovados = 0

        for emprestimo in pendentes:

            if emprestimo.equipamento.status != 'DISPONIVEL':
                continue

            agora = timezone.now()
            emprestimo.status = 'APROVADO'
            emprestimo.data_retirada = agora
            emprestimo.data_devolucao_prevista = agora + timedelta(
                days=settings.PRAZO_PADRAO_EMPRESTIMO_DIAS
            )
            emprestimo.save()

            emprestimo.equipamento.status = 'EMPRESTADO'
            emprestimo.equipamento.save()

            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Empréstimos',
                descricao=f'Empréstimo aprovado: {emprestimo.equipamento.nome} para {emprestimo.usuario.username}. Devolução prevista: {emprestimo.data_devolucao_prevista:%d/%m/%Y}.',
            )
            aprovados += 1

        self.message_user(request, f'{aprovados} empréstimo(s) aprovado(s).')

    @admin.action(description='Rejeitar empréstimos selecionados')
    def rejeitar_emprestimos(self, request, queryset):
        pendentes = list(queryset.filter(status='SOLICITADO'))

        for emprestimo in pendentes:
            emprestimo.status = 'REJEITADO'
            emprestimo.save()

            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Empréstimos',
                descricao=f'Empréstimo rejeitado: {emprestimo.equipamento.nome} para {emprestimo.usuario.username}.',
            )

        self.message_user(request, f'{len(pendentes)} empréstimo(s) rejeitado(s).')

    @admin.action(description='Marcar como devolvido')
    def marcar_devolvido(self, request, queryset):
        aprovados = list(queryset.filter(status='APROVADO'))

        for emprestimo in aprovados:
            emprestimo.status = 'DEVOLVIDO'
            emprestimo.data_devolucao_real = timezone.now()
            emprestimo.prorrogacao_solicitada = False
            emprestimo.save()

            emprestimo.equipamento.status = 'DISPONIVEL'
            emprestimo.equipamento.save()

            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Empréstimos',
                descricao=f'Devolução registrada: {emprestimo.equipamento.nome} de {emprestimo.usuario.username}.',
            )

        self.message_user(request, f'{len(aprovados)} devolução(ões) registrada(s).')

    @admin.action(description='Aprovar prorrogação (estende o prazo)')
    def aprovar_prorrogacao(self, request, queryset):
        pendentes = list(queryset.filter(status='APROVADO', prorrogacao_solicitada=True))

        for emprestimo in pendentes:

            emprestimo.data_devolucao_prevista += timedelta(
                days=settings.PRAZO_PADRAO_EMPRESTIMO_DIAS
            )
            emprestimo.prorrogacao_solicitada = False
            emprestimo.save()

            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Empréstimos',
                descricao=f'Prorrogação aprovada: {emprestimo.equipamento.nome} para {emprestimo.usuario.username}. Nova devolução prevista: {emprestimo.data_devolucao_prevista:%d/%m/%Y}.',
            )

        self.message_user(request, f'{len(pendentes)} prorrogação(ões) aprovada(s).')

    @admin.action(description='Rejeitar prorrogação')
    def rejeitar_prorrogacao(self, request, queryset):
        pendentes = list(queryset.filter(prorrogacao_solicitada=True))

        for emprestimo in pendentes:
            emprestimo.prorrogacao_solicitada = False
            emprestimo.save()

            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Empréstimos',
                descricao=f'Prorrogação rejeitada: {emprestimo.equipamento.nome} para {emprestimo.usuario.username}.',
            )

        self.message_user(request, f'{len(pendentes)} pedido(s) de prorrogação rejeitado(s).')