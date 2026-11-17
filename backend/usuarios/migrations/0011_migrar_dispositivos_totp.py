from django.db import migrations

CAMPOS = (
    "user_id", "name", "confirmed",
    "throttling_failure_timestamp", "throttling_failure_count",
    "created_at", "last_used_at",
    "key", "step", "t0", "digits", "tolerance", "drift", "last_t",
)


def migrar(apps, schema_editor):
    Antigo = apps.get_model("otp_totp", "TOTPDevice")
    Novo = apps.get_model("usuarios", "DispositivoTOTP")
    for antigo in Antigo.objects.all():
        novo = Novo.objects.create(**{campo: getattr(antigo, campo) for campo in CAMPOS})
        Novo.objects.filter(pk=novo.pk).update(created_at=antigo.created_at)
    Antigo.objects.all().delete()


def desfazer(apps, schema_editor):
    Antigo = apps.get_model("otp_totp", "TOTPDevice")
    Novo = apps.get_model("usuarios", "DispositivoTOTP")
    for novo in Novo.objects.all():
        Antigo.objects.create(**{campo: getattr(novo, campo) for campo in CAMPOS})
    Novo.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0010_dispositivototp"),
        ("otp_totp", "0003_add_timestamps"),
    ]

    operations = [
        migrations.RunPython(migrar, desfazer),
    ]
