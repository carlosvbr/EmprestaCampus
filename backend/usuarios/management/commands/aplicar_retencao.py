"""
Aplica os prazos de retenção de dados pessoais (LGPD, arts. 15 e 16).

Uso, agendado uma vez por dia (cron ou agendador do servidor):

    python manage.py aplicar_retencao

Os prazos estão em usuarios/retencao.py e no documento
"Mapeamento de Dados Pessoais.md".
"""

from django.core.management.base import BaseCommand

from usuarios.retencao import aplicar_retencao


class Command(BaseCommand):
    help = "Elimina ou anonimiza os dados pessoais que passaram do prazo de retenção."

    def handle(self, *args, **options):
        resultado = aplicar_retencao()
        for categoria, quantidade in resultado.items():
            self.stdout.write(f"{categoria}: {quantidade}")
        self.stdout.write(self.style.SUCCESS("Retenção aplicada."))
