from django.db import models
from django.conf import settings

class RegistroAuditoria(models.Model):
    ACAO_CHOICES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('LOGIN', 'Autenticação'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    modulo_afetado = models.CharField(max_length=50) 
    descricao = models.TextField()
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user = self.usuario.username if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} | {user} -> {self.acao}"