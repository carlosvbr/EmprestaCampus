from django.db import migrations, models
from django.utils import timezone


def marcar_suspensas_existentes(apps, schema_editor):
    """
    Contas que já estavam suspensas por revogação não têm a data guardada.
    O prazo de 12 meses passa a contar a partir desta migração, o que só
    pode adiar a anonimização, nunca antecipá-la.
    """
    Usuario = apps.get_model("usuarios", "Usuario")
    (
        Usuario.objects
        .filter(is_active=False, consentimento_dados=False)
        .exclude(password__startswith="!")  # contas já anonimizadas
        .update(consentimento_revogado_em=timezone.now())
    )


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0013_consentimentos_existentes"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="consentimento_revogado_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Quando o titular revogou o consentimento e teve o acesso suspenso. Conta suspensa há mais de 12 meses é anonimizada pela rotina de retenção.",
                null=True,
            ),
        ),
        migrations.RunPython(marcar_suspensas_existentes, migrations.RunPython.noop),
    ]