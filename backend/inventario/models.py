from django.db import models

class Categoria(models.Model):
    # O ORM mapeia esta classe para a tabela 'inventario_categoria' no PostgreSQL
    nome = models.CharField(max_length=100, help_text="Ex: Notebooks, Tablets")
    descricao = models.TextField(blank=True, null=True) # null=True libera o preenchimento no SGBD

    def __str__(self):
        return self.nome

class Equipamento(models.Model):
    # Enumeração imutável para domínio de estados, otimizando consultas sem criar tabelas extras
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('EMPRESTADO', 'Emprestado'),
        ('MANUTENCAO', 'Em Manutenção'),
        ('INATIVO', 'Inativo'),
    ]

    nome = models.CharField(max_length=200)
    
    # unique=True aplica constraint UNIQUE no banco, impedindo duplicidade de patrimônio
    patrimonio = models.CharField(max_length=50, unique=True, help_text="Número da etiqueta da faculdade")
    
    # models.PROTECT aplica integridade referencial rígida: impede exclusão de categorias em uso
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')

    def __str__(self):
        return f"{self.nome} - {self.patrimonio}"