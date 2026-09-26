from rest_framework import serializers
from .models import Categoria, Equipamento


class CategoriaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Categoria
        fields = ["id", "nome", "descricao"]

class EquipamentoSerializer(serializers.ModelSerializer):

    categoria_nome = serializers.CharField(source="categoria.nome", read_only=True)

    class Meta:
        model = Equipamento
        fields = [
            "id",
            "nome",
            "patrimonio",
            "categoria",
            "categoria_nome",
            "status",
            "data_cadastro",
            "observacoes",
        ]

        read_only_fields = ["data_cadastro"]