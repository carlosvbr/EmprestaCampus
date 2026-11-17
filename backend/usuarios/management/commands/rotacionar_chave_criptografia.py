"""
Recifra todos os dados protegidos com a chave atual (item 3.4).

Uso, depois de mover a chave antiga para ENCRYPTION_KEYS_ANTIGAS e
colocar a chave nova em ENCRYPTION_KEY:

    python manage.py rotacionar_chave_criptografia

Cada valor é lido (o MultiFernet decifra com a chave que servir) e
gravado de novo (o CampoCriptografado cifra sempre com a chave atual).
Tudo roda numa única transação: se algum valor não puder ser decifrado,
nada é alterado e o comando para com erro, sem deixar o banco pela
metade.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from usuarios.models import DispositivoTOTP, Usuario


class Command(BaseCommand):
    help = "Recifra telefones e chaves de 2FA com a ENCRYPTION_KEY atual."

    @transaction.atomic
    def handle(self, *args, **options):
        telefones = 0
        for usuario in Usuario.objects.exclude(telefone__isnull=True).exclude(telefone=""):
            usuario.save(update_fields=["telefone"])
            telefones += 1

        dispositivos = 0
        for dispositivo in DispositivoTOTP.objects.all():
            dispositivo.save(update_fields=["key"])
            dispositivos += 1

        self.stdout.write(self.style.SUCCESS(
            f"Recifrados: {telefones} telefone(s) e {dispositivos} chave(s) de 2FA."
        ))
