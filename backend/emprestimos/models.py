from django.db import models
from django.conf import settings
from inventario.models import Equipamento

class Emprestimo(models.Model):
    STATUS_CHOICES = [
        ('SOLICITADO', 'Solicitado'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('RETIRADO', 'Retirado (Em Andamento)'),
        ('DEVOLVIDO', 'Devolvido'),
        ('ATRASADO', 'Atrasado'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT)
    
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_retirada = models.DateTimeField(blank=True, null=True)
    data_devolucao_prevista = models.DateTimeField()
    data_devolucao_real = models.DateTimeField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SOLICITADO')
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.equipamento.nome} - {self.usuario.username} ({self.get_status_display()})"