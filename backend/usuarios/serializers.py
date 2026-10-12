from rest_framework import serializers

from .models import Usuario

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

    class Meta:
        model = Usuario
        fields = ["id","username","first_name","last_name","email","password","papel","matricula","telefone","consentimento_dados"]

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
        usuario = Usuario(**validated_data)
        usuario.set_password(senha)
        usuario.save() # Dispara a lógica automática do models.py para registrar data e versão do aceite
        return usuario