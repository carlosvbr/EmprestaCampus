from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2HasherReforcado(PBKDF2PasswordHasher):
    """
    PBKDF2-SHA256 com custo elevado explicitamente declarado.

    600.000 iterações é o mínimo recomendado pela OWASP (2023) para
    PBKDF2-SHA256. Herdar do hasher padrão do Django e sobrescrever
    apenas 'iterations' evita depender do valor implícito da versão
    instalada do framework, que muda entre releases sem aviso.
    """

    iterations = 600_000