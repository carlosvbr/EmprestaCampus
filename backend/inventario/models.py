from django.db import models

class Categoria(models.Model):
    nome = models.CharField(max_length=100, help_text="Ex: Notebooks, Tablets")
    descricao = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome

class Equipamento(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('EMPRESTADO', 'Emprestado'),
        ('MANUTENCAO', 'Em Manutenção'),
        ('INATIVO', 'Inativo'),
    ]

    nome = models.CharField(max_length=200)
    patrimonio = models.CharField(max_length=50, unique=True, help_text="Número da etiqueta da faculdade")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')

    def __str__(self):
        return f"{self.nome} - {self.patrimonio}"