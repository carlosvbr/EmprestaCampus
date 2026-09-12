from rest_framework import serializers

from .models import Usuario


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

    class Meta:
        model = Usuario
        fields = ["id", "username","first_name","last_name","email", "password", "papel", "matricula","telefone"]

    def create(self, validated_data):
        senha = validated_data.pop("password")
        usuario = Usuario(**validated_data)
        usuario.set_password(senha)
        usuario.save()
        return usuario
