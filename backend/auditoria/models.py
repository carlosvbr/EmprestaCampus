from django.db import models
from django.conf import settings
from django.db import models
from django.conf import settings

class RegistroAuditoria(models.Model):
    ACAO_CHOICES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('LOGIN', 'Autenticação'),
    ]

    # SET_NULL é vital para a auditoria. Se um usuário for deletado da base, 
    # o histórico de suas ações é preservado (a FK recebe NULL, mas o registro não é apagado).
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    modulo_afetado = models.CharField(max_length=50) 
    descricao = models.TextField()
    
    # Mapeado para o tipo 'inet' no PostgreSQL. Valida nativamente formatos IPv4 e IPv6,
    # fundamental para o rastreio de acessos suspeitos e aderência a regras de Segurança da Informação.
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    
    # auto_now_add garante a imutabilidade temporal do log (timestamp no momento exato do evento)
    data_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Fallback de segurança na exibição: caso a FK seja nula, atribui a ação ao 'Sistema'
        user = self.usuario.username if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} | {user} -> {self.acao}"