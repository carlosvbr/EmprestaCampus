from django.contrib import admin
from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'mensagem_resumida', 'lida', 'data_criacao')
    list_filter = ('tipo', 'lida')
    search_fields = ('usuario__username', 'mensagem')

    # Notificações são geradas pelo sistema (via helper em
    # notificacoes/utils.py), não cadastradas manualmente pelo admin
    readonly_fields = ('data_criacao',)

    @admin.display(description='Mensagem')
    def mensagem_resumida(self, obj):
        # Evita que mensagens longas quebrem o layout da listagem do
        # admin, mostrando só os primeiros 60 caracteres.
        return obj.mensagem[:60] + ('...' if len(obj.mensagem) > 60 else '')