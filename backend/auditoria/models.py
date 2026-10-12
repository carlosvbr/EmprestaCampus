from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class RegistroAuditoriaQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Registros de auditoria são imutáveis e não podem ser atualizados em lote.")

    def delete(self):
        raise ValidationError("Registros de auditoria são imutáveis e não podem ser excluídos em lote.")

class RegistroAuditoriaManager(models.Manager):
    def get_queryset(self):
        return RegistroAuditoriaQuerySet(self.model, using=self._db)

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

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField(max_length=50, choices=ACAO_CHOICES)
    modulo_afetado = models.CharField(max_length=50)
    descricao = models.TextField()
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    objects = RegistroAuditoriaManager()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Um registro de auditoria existente não pode ser modificado.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Registros de auditoria não podem ser excluídos.")

    def __str__(self):
        user = self.usuario.username if self.usuario else "Sistema"
        return f"{self.data_hora.strftime('%d/%m/%Y %H:%M')} | {user} -> {self.get_acao_display()}"