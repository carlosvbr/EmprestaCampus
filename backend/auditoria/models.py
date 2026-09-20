from django.db import models
from django.conf import settings

class RegistroAuditoria(models.Model):
    ACAO_CHOICES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('LOGIN_SUCESSO', 'Login com Sucesso'),
        ('LOGIN_FALHA', 'Falha no Login'),
        ('2FA_SUCESSO', 'Sucesso no 2FA'),
        ('2FA_FALHA', 'Falha no 2FA'),
        ('RECUPERACAO', 'Recuperação de Senha'),
        ('RECUPERACAO_SOLICITADA', 'Solicitação de Recuperação'),
        ('RECUPERACAO_SUCESSO', 'Recuperação com Sucesso'),
        ('RECUPERACAO_FALHA', 'Falha na Recuperação'),
    ]

    # SET_NULL é vital para a auditoria. Se um utilizador for apagado da base, 
    # o histórico das ações é preservado (a FK recebe NULL, mas o registo não é apagado).
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    acao = models.CharField(max_length=50, choices=ACAO_CHOICES)
    modulo_afetado = models.CharField(max_length=50) 
    descricao = models.TextField()
    
    # Mapeado para o tipo 'inet' no PostgreSQL. Valida nativamente formatos IPv4 e IPv6.
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    
    # auto_now_add garante a imutabilidade temporal do log
    data_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user = self.usuario.username if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} | {user} -> {self.get_acao_display()}"