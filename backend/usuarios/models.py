import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
from django.db import models
from django.utils import timezone
from django_otp.models import Device, ThrottlingMixin, TimestampMixin
from django_otp.plugins.otp_totp.models import TOTPDevice, default_key

from .crypto import CampoCriptografado


class Papel(models.TextChoices):
    ALUNO = "ALUNO", "Aluno"
    DOCENTE = "DOCENTE", "Docente"
    ADMIN = "ADMIN", "Administrador"


class UsuarioManager(UserManager):
    """
    Manager do Usuario. A única diferença para o padrão do Django é o
    create_superuser (usado pelo comando createsuperuser): ele cria a
    conta já com papel ADMIN. Sem isso, o superusuário nasceria com o
    papel padrão (ALUNO) e o save() do model, que sincroniza is_staff e
    is_superuser a partir do papel, o rebaixaria na hora.
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("papel", Papel.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Usuário do sistema, estendendo o modelo padrão do Django.

    Herda de AbstractUser os campos de autenticação (username, password
    já com hash, email, etc). Adicionamos o campo 'papel' para controle
    de acesso baseado em papel (RBAC), que define o que cada usuário
    pode fazer no fluxo de empréstimo.

    O 'papel' é a fonte única da verdade sobre privilégios: ADMIN tem
    is_staff e is_superuser (acesso ao /admin/ e às ações de aprovação),
    qualquer outro papel não tem. Essa sincronização é feita no save().
    """

    objects = UsuarioManager()

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
    telefone = CampoCriptografado(
        max_length=255,
        null=True,
        blank=True,
        help_text="Telefone pessoal, armazenado criptografado com Fernet (item 3.4).",
    )

    # --- LGPD: Trilha de Consentimento ---
    consentimento_dados = models.BooleanField(
        default=False, 
        help_text="Indica se o usuário aceitou os termos de uso e privacidade (LGPD 4.4 e 4.5)"
    )
    data_consentimento = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Data e hora exata do aceite (LGPD 4.7)"
    )

    versao_documento_aceito = models.CharField(
        max_length=10, 
        blank=True, 
        null=True, 
        help_text="Versão da Política de Privacidade aceita (ex: v1.0) (LGPD 4.7)"
    )
    consentimento_revogado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o titular revogou o consentimento e teve o acesso suspenso. "
                  "Conta suspensa há mais de 12 meses é anonimizada pela rotina de retenção.",
    )

    def save(self, *args, **kwargs):
        # Se o consentimento foi marcado como True e não tem data, registra a data exata agora
        if self.consentimento_dados and not self.data_consentimento:
            self.data_consentimento = timezone.now()
            self.versao_documento_aceito = settings.VERSAO_POLITICA_PRIVACIDADE 

        # RBAC: o papel manda. is_staff (entrar no /admin/) e is_superuser
        # (ter todas as permissões lá dentro) acompanham o papel ADMIN, e
        # só ele. Assim não existe mais "admin só no papel" nem "admin só
        # no is_staff": quem aprova empréstimos, recebe as notificações de
        # solicitação (notificar_admins) e escreve no inventário é sempre
        # o mesmo conjunto de pessoas.
        eh_admin = self.papel == Papel.ADMIN
        self.is_staff = eh_admin
        self.is_superuser = eh_admin

        # Se o save foi parcial (update_fields) e mexeu no papel, os dois
        # campos derivados precisam ir junto, senão a mudança não chega
        # ao banco.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "papel" in update_fields:
            kwargs["update_fields"] = {*update_fields, "is_staff", "is_superuser"}

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_papel_display()})"

    
    # --- LGPD: consentimento por finalidade ---

    def consentiu(self, finalidade):
        """Situação atual do consentimento para uma finalidade opcional."""
        ultimo = self.consentimentos.filter(finalidade=finalidade).first()
        return bool(ultimo and ultimo.aceito)

    def definir_consentimento(self, finalidade, aceito):
        """
        Registra a escolha do titular para uma finalidade, só se ela mudou.
        Devolve True quando houve mudança.

        Sem consentimento para o contato por telefone, o telefone guardado
        é apagado: o dado deixa de ter finalidade (art. 15, III e art. 16).
        """
        if self.consentimentos.filter(finalidade=finalidade).exists() and self.consentiu(finalidade) == aceito:
            return False

        ConsentimentoFinalidade.objects.create(
            usuario=self,
            finalidade=finalidade,
            aceito=aceito,
            versao_politica=settings.VERSAO_POLITICA_PRIVACIDADE,
        )
        if finalidade == Finalidade.CONTATO_TELEFONE and not aceito and self.telefone:
            self.telefone = None
            self.save(update_fields=["telefone"])
        return True


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


class Finalidade(models.TextChoices):
    """
    Finalidades opcionais, que dependem de consentimento próprio.
    Os códigos são os mesmos do mapeamento em usuarios/lgpd.py.
    """

    CONTATO_TELEFONE = "contato_alternativo", "Contato por telefone sobre os meus empréstimos"
    AVISOS_EMAIL = "avisos_emprestimo", "Avisos por e-mail sobre o andamento dos meus empréstimos"


class ConsentimentoFinalidade(models.Model):
    """
    Histórico de consentimentos por finalidade (LGPD).

    Cada aceite ou recusa vira uma linha nova, com data e versão da
    política; nenhuma linha é alterada depois de gravada. A situação
    atual de uma finalidade é a da linha mais recente. Assim fica
    registrado não só o que o titular escolheu, mas quando escolheu.
    """

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="consentimentos")
    finalidade = models.CharField(max_length=30, choices=Finalidade.choices)
    aceito = models.BooleanField()
    data_hora = models.DateTimeField(auto_now_add=True)
    versao_politica = models.CharField(max_length=10)

    class Meta:
        ordering = ["-data_hora", "-id"]
        verbose_name = "consentimento por finalidade"
        verbose_name_plural = "consentimentos por finalidade"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Um registro de consentimento não pode ser alterado; registre uma nova escolha.")
        super().save(*args, **kwargs)

    def __str__(self):
        situacao = "aceito" if self.aceito else "recusado"
        return f"{self.usuario_id} - {self.finalidade}: {situacao} em {self.data_hora:%d/%m/%Y %H:%M}"
    

class DispositivoTOTP(TimestampMixin, ThrottlingMixin, Device):
    """
    Dispositivo de 2FA (TOTP) com a chave secreta cifrada no banco.

    O TOTPDevice do django-otp guarda a chave secreta em texto puro
    (hexadecimal). Aqui a chave usa o mesmo CampoCriptografado do telefone,
    com Fernet e rotação de chaves.

    Só muda onde a chave fica guardada. Os demais campos são os mesmos
    do TOTPDevice, e a verificação do código é reaproveitada dele, sem
    reescrever a lógica já testada pela biblioteca: atraso progressivo
    após erros (ThrottlingMixin) e proteção contra reuso do mesmo
    código (last_t).
    """

    key = CampoCriptografado(
        max_length=255,
        default=default_key,
        help_text="Chave secreta do TOTP, cifrada com Fernet.",
    )
    step = models.PositiveSmallIntegerField(default=30)
    t0 = models.BigIntegerField(default=0)
    digits = models.PositiveSmallIntegerField(choices=[(6, 6), (8, 8)], default=6)
    tolerance = models.PositiveSmallIntegerField(default=1)
    drift = models.SmallIntegerField(default=0)
    last_t = models.BigIntegerField(default=-1)

    class Meta(Device.Meta):
        verbose_name = "dispositivo TOTP"
        verbose_name_plural = "dispositivos TOTP"

    bin_key = TOTPDevice.bin_key
    verify_token = TOTPDevice.verify_token
    get_throttle_factor = TOTPDevice.get_throttle_factor
    config_url = TOTPDevice.config_url
    _read_str_from_settings = TOTPDevice._read_str_from_settings