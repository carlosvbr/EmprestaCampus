"""
Registra as escolhas dos usuários que já existiam antes do consentimento
por finalidade (LGPD).

Na versão v1.0 da política, um único aceite cobria o telefone e os avisos
por e-mail. Para não mudar o que essas pessoas já recebiam, a migração
grava, com a versão v1.0:
- avisos por e-mail: aceito, para quem tinha o consentimento ativo;
- contato por telefone: aceito só para quem informou um telefone.

Cada titular pode mudar essas escolhas depois, em "Meu Perfil".
"""

from django.db import migrations


def registrar(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Consentimento = apps.get_model("usuarios", "ConsentimentoFinalidade")
    for usuario in Usuario.objects.filter(consentimento_dados=True):
        Consentimento.objects.create(
            usuario=usuario, finalidade="avisos_emprestimo", aceito=True, versao_politica="v1.0",
        )
        if usuario.telefone:
            Consentimento.objects.create(
                usuario=usuario, finalidade="contato_alternativo", aceito=True, versao_politica="v1.0",
            )


def desfazer(apps, schema_editor):
    apps.get_model("usuarios", "ConsentimentoFinalidade").objects.filter(versao_politica="v1.0").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0012_consentimentofinalidade"),
    ]

    operations = [
        migrations.RunPython(registrar, desfazer),
    ]