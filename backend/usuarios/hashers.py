from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2HasherReforcado(PBKDF2PasswordHasher):
    """
    Hasher personalizado para definir explicitamente
    o custo computacional do armazenamento de senhas.
    """

    iterations = 600_000