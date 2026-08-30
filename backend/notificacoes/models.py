from django.db import models
from django.conf import settings

class Notificacao(models.Model):
    TIPO_CHOICES = [
        ('SISTEMA', 'Alerta do Sistema'),
        ('EMAIL', 'Enviado por E-mail'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SISTEMA')
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Lida" if self.lida else "Pendente"
        return f"[{status}] {self.usuario.username}: {self.mensagem[:30]}..."