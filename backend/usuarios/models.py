import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


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


class TokenRecuperacaoSenha(models.Model):
    """
    Token de uso único para redefinição de senha.

    O token é gerado com secrets.token_urlsafe, que usa uma fonte
    criptograficamente segura de aleatoriedade (não é sequencial nem
    previsível, ao contrário de um contador ou de random.random()).
    Expira sozinho após 1 hora e só pode ser usado uma vez.
    """

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="tokens_recuperacao")
    token = models.CharField(max_length=64, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(editable=False)
    usado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expira_em:
            self.expira_em = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def esta_valido(self):
        return not self.usado and timezone.now() < self.expira_em

    def __str__(self):
        return f"Token de {self.usuario.username} (usado={self.usado})"

class LogAutenticacao(models.Model):
    """
    Registro de eventos ligados a autenticação e recuperação de senha.

    Existe separado da trilha de auditoria do empréstimo porque cobre
    um domínio diferente: tentativas de acesso e recuperação de senha,
    inclusive de solicitações que falham ou nunca chegam a virar um
    usuário autenticado.
    """

    class TipoEvento(models.TextChoices):
        SOLICITACAO_RECUPERACAO = "SOLICITACAO_RECUPERACAO", "Solicitação de recuperação"
        RECUPERACAO_SUCESSO = "RECUPERACAO_SUCESSO", "Recuperação concluída"
        RECUPERACAO_FALHA = "RECUPERACAO_FALHA", "Recuperação falhou"

    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs_autenticacao"
    )
    email_informado = models.EmailField(
        help_text="Guardado mesmo se o e-mail não existir no sistema, para fins de auditoria."
    )
    tipo_evento = models.CharField(max_length=30, choices=TipoEvento.choices)
    detalhe = models.CharField(max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_evento_display()} - {self.email_informado} em {self.criado_em}"