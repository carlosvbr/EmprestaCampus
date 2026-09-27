from django.utils import timezone
from rest_framework import serializers
from .models import Emprestimo


class SolicitarEmprestimoSerializer(serializers.ModelSerializer):
    """
    Usado quando o ALUNO solicita um empréstimo. Não expõe o campo
    'status' pra edição: toda solicitação nova nasce como SOLICITADO,
    forçado no create(), e só o admin muda isso depois.
    """

    class Meta:
        model = Emprestimo
        fields = ["id", "equipamento", "observacoes"]

    def validate_equipamento(self, equipamento):
        if equipamento.status != "DISPONIVEL":
            raise serializers.ValidationError(
                "Este equipamento não está disponível para empréstimo no momento."
            )

        # impede pedido duplicado em aberto do mesmo aluno para o mesmo equipamento.
        usuario = self.context["request"].user
        ja_tem_pedido_aberto = Emprestimo.objects.filter(
            usuario=usuario,
            equipamento=equipamento,
            status__in=["SOLICITADO", "APROVADO"],
        ).exists()

        if ja_tem_pedido_aberto:
            raise serializers.ValidationError(
                "Você já tem uma solicitação em aberto para este equipamento."
            )

        return equipamento

    def create(self, validated_data):
        validated_data["usuario"] = self.context["request"].user
        validated_data["status"] = "SOLICITADO"
        return super().create(validated_data)


class EmprestimoSerializer(serializers.ModelSerializer):
    """
    Usado para LISTAR empréstimos (histórico do usuário). Campos extras
    (equipamento_nome, status_display, esta_atrasado) evitam que o
    frontend precise fazer consultas adicionais só para exibir a tela.
    """

    equipamento_nome = serializers.CharField(source="equipamento.nome", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    esta_atrasado = serializers.SerializerMethodField()

    class Meta:
        model = Emprestimo
        fields = [
            "id", "equipamento", "equipamento_nome", "data_solicitacao",
            "data_retirada", "data_devolucao_prevista", "data_devolucao_real",
            "status", "status_display", "observacoes", "esta_atrasado",
        ]

        # o aluno pode ver a data depois que o admin aprova, mas nunca
        # define ou edita ela via API.
        read_only_fields = [
            "data_solicitacao", "data_retirada", "data_devolucao_prevista",
            "data_devolucao_real", "status",
        ]

    def get_esta_atrasado(self, obj):
        return obj.esta_atrasado()