from django.contrib.auth.models import AbstractUser
from django.db import models


class Papel(models.TextChoices):
    ALUNO = "ALUNO", "Aluno"
    DOCENTE = "DOCENTE", "Docente"
    TECNICO = "TECNICO", "Técnico"
    ADMIN = "ADMIN", "Administrador"


class Usuario(AbstractUser):
    """
    Usuário do sistema, estendendo o modelo padrão do Django.

    Herda de AbstractUser os campos de autenticação (username, password
    já com hash, email, etc). Adicionamos o campo 'papel' para controle
    de acesso baseado em papel (RBAC), que define o que cada usuário
    pode fazer no fluxo de empréstimo.
    """

    papel = models.CharField(
        max_length=10,
        choices=Papel.choices,
        default=Papel.ALUNO,
        help_text="Define as permissões do usuário no sistema (RBAC).",
    )
    matricula = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Matrícula institucional. Vazio para contas administrativas.",
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_papel_display()})"