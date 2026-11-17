from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from .models import Finalidade, Usuario

# Papéis que o próprio usuário pode escolher ao se cadastrar.
# ADMIN fica de fora de propósito: ele concede poderes administrativos
# (escrita no inventário pela API), então só pode ser atribuído por um
# administrador, no /admin/. Se o cadastro público aceitasse esse valor,
# qualquer pessoa poderia se auto-promover enviando "papel": "ADMIN"
# direto para a API.
PAPEIS_AUTOCADASTRO = ["ALUNO", "DOCENTE"]


class RegistroSerializer(serializers.ModelSerializer):
    """
    Serializer usado no cadastro de um novo usuário.

    A senha é write_only para nunca ser devolvida em nenhuma resposta da
    API, e é hasheada explicitamente com set_password, em vez de salva
    como texto puro.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    matricula = serializers.CharField(required=True, max_length=20)

    # --- LGPD: Validação explícita do consentimento ---
    consentimento_dados = serializers.BooleanField(
        required=True,
        error_messages={'required': 'O consentimento dos dados é obrigatório.'}
    )

    # --- LGPD: consentimento por finalidade ---
    # Finalidades opcionais, cada uma com a sua própria caixa, desmarcada
    # por padrão. Recusar não impede o cadastro.
    consentimento_telefone = serializers.BooleanField(required=False, default=False, write_only=True)
    consentimento_avisos_email = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Usuario
        fields = [
            "id", "username", "first_name", "last_name", "email", "password", "papel",
            "matricula", "telefone", "consentimento_dados",
            "consentimento_telefone", "consentimento_avisos_email",
        ]

    def validate(self, dados):
        """O telefone só pode ser guardado com o consentimento para essa finalidade."""
        if dados.get("telefone") and not dados.get("consentimento_telefone"):
            raise serializers.ValidationError({
                "telefone": "Para informar o telefone, autorize o contato por telefone. "
                            "Se preferir, deixe o campo em branco."
            })
        return dados

    def validate_papel(self, value):
        """
        Barra, com Erro 400, qualquer tentativa de se cadastrar com um
        papel privilegiado. Roda só quando o cliente envia o campo; se
        ele for omitido, vale o default do model (ALUNO).
        """
        if value not in PAPEIS_AUTOCADASTRO:
            raise serializers.ValidationError(
                "Este perfil não pode ser escolhido no cadastro. "
                "Perfis administrativos são atribuídos por um administrador."
            )
        return value

    def validate_consentimento_dados(self, value):
        """
        Garante que o usuário marcou a caixa como True (aceitou).
        Se tentar enviar False via API, o serializer barra com Erro 400.
        """
        if not value:
            raise serializers.ValidationError("Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar uma conta.")
        return value

    def create(self, validated_data):
        senha = validated_data.pop("password")
        aceita_telefone = validated_data.pop("consentimento_telefone")
        aceita_avisos = validated_data.pop("consentimento_avisos_email")
        usuario = Usuario(**validated_data)
        # Aplica as regras de settings.AUTH_PASSWORD_VALIDATORS (senha comum,
        # só números, parecida com nome/e-mail/usuário) antes de gravar.
        try:
            password_validation.validate_password(senha, user=usuario)
        except DjangoValidationError as erro:
            raise serializers.ValidationError({"password": list(erro.messages)})
        usuario.set_password(senha)
        usuario.save() # Dispara a lógica automática do models.py para registrar data e versão do aceite

        # Registra as duas escolhas, inclusive a recusa: fica provado que o
        # titular decidiu cada finalidade separadamente.
        usuario.definir_consentimento(Finalidade.CONTATO_TELEFONE, aceita_telefone)
        usuario.definir_consentimento(Finalidade.AVISOS_EMAIL, aceita_avisos)
        return usuario