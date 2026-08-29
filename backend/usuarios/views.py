from rest_framework import generics, permissions

from .serializers import RegistroSerializer


class RegistroView(generics.CreateAPIView):
    """
    Endpoint público de cadastro de usuário.

    Não exige autenticação (AllowAny), já que é justamente o passo que
    cria a conta. A senha chega em texto puro na requisição, mas nunca
    é salva assim: o RegistroSerializer.create() chama set_password,
    que aplica hash (PBKDF2, padrão do Django) antes de gravar no banco.
    """

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]
