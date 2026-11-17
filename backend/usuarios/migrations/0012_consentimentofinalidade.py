import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0011_migrar_dispositivos_totp"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentimentoFinalidade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "finalidade",
                    models.CharField(
                        choices=[
                            (
                                "contato_alternativo",
                                "Contato por telefone sobre os meus empréstimos",
                            ),
                            (
                                "avisos_emprestimo",
                                "Avisos por e-mail sobre o andamento dos meus empréstimos",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                ("aceito", models.BooleanField()),
                ("data_hora", models.DateTimeField(auto_now_add=True)),
                ("versao_politica", models.CharField(max_length=10)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consentimentos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "consentimento por finalidade",
                "verbose_name_plural": "consentimentos por finalidade",
                "ordering": ["-data_hora", "-id"],
            },
        ),
    ]