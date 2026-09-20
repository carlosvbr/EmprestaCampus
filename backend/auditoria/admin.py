from django.contrib import admin
from .models import RegistroAuditoria

@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'usuario', 'acao', 'modulo_afetado', 'ip_origem')
    list_filter = ('acao', 'modulo_afetado', 'data_hora')
    search_fields = ('usuario__username', 'ip_origem', 'descricao')
    readonly_fields = ('usuario', 'acao', 'modulo_afetado', 'descricao', 'ip_origem', 'data_hora')

    # Garante que os logs sejam automáticos
    def has_add_permission(self, request):
        return False

    # Garante que o log não possa ser adulterado
    def has_change_permission(self, request, obj=None):
        return False

    # Garante que os logs sejam um histórico permanente
    def has_delete_permission(self, request, obj=None):
        return False
    