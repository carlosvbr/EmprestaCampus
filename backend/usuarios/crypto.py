from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _fernet():
    """
    Instancia o Fernet a cada chamada, em vez de guardar em variável
    global no import. Isso evita travar a chave em memória no momento
    em que o modulo e carregado, antes das settings estarem prontas
    em todos os cenarios (management commands, testes, etc).
    """
    return Fernet(settings.ENCRYPTION_KEY.encode())


class CampoCriptografado(models.CharField):
    """
    Campo de texto que criptografa o valor antes de salvar no banco
    (item 3.4) usando Fernet, um algoritmo de criptografia simetrica
    autenticada (item 3.5).

    Diferente de hash (usado na senha), este valor pode ser recuperado
    de volta ao original, porque a aplicacao precisa mostra-lo ao
    usuario depois. Por isso nao pode ser unique=True: o mesmo valor
    original gera um resultado criptografado diferente a cada vez que
    e salvo, devido ao nonce interno do Fernet.
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        valor_cifrado = _fernet().encrypt(value.encode())
        return valor_cifrado.decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        valor_original = _fernet().decrypt(value.encode())
        return valor_original.decode()

    def to_python(self, value):
        return value