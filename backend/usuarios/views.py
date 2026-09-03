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


from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import LogAutenticacao, TokenRecuperacaoSenha, Usuario


class SolicitarRecuperacaoSenhaView(APIView):
    """
    Recebe um e-mail e, se existir um usuário com ele, gera um token de
    recuperação e "envia" por e-mail (console, em desenvolvimento).

    Sempre responde 200, mesmo se o e-mail não existir no sistema. Isso
    é proposital: evita que alguém descubra quais e-mails têm conta
    só testando esse endpoint (enumeration attack). Toda solicitação,
    exista o e-mail ou não, é registrada no log (item 2.6).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "")
        usuario = Usuario.objects.filter(email=email).first()

        LogAutenticacao.objects.create(
            usuario=usuario,
            email_informado=email,
            tipo_evento=LogAutenticacao.TipoEvento.SOLICITACAO_RECUPERACAO,
        )

        if usuario:
            token = TokenRecuperacaoSenha.objects.create(usuario=usuario)
            link = f"{settings.FRONTEND_URL}/redefinir-senha?token={token.token}"
            send_mail(
                subject="Recuperação de senha - EmprestaCampus",
                message=f"Use o link abaixo para redefinir sua senha (válido por 1 hora):\n{link}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )

        return Response(
            {"detail": "Se o e-mail existir, um link de recuperação foi enviado."},
            status=status.HTTP_200_OK,
        )

class RedefinirSenhaView(APIView):
    """
    Recebe um token de recuperação e uma nova senha, valida e aplica.

    Validações, na ordem: token existe, ainda não expirou (2.3, 2.5),
    ainda não foi usado (2.4). Qualquer falha é registrada no log
    (2.7) e retorna 400 com mensagem clara, sem revelar detalhes que
    ajudem alguém tentando adivinhar tokens.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token_str = request.data.get("token", "")
        nova_senha = request.data.get("password", "")

        token = TokenRecuperacaoSenha.objects.filter(token=token_str).first()

        if not token:
            LogAutenticacao.objects.create(
                email_informado="",
                tipo_evento=LogAutenticacao.TipoEvento.RECUPERACAO_FALHA,
                detalhe="Token inexistente",
            )
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if not token.esta_valido():
            motivo = "Token já utilizado" if token.usado else "Token expirado"
            LogAutenticacao.objects.create(
                usuario=token.usuario,
                email_informado=token.usuario.email,
                tipo_evento=LogAutenticacao.TipoEvento.RECUPERACAO_FALHA,
                detalhe=motivo,
            )
            return Response({"detail": motivo + "."}, status=status.HTTP_400_BAD_REQUEST)

        if len(nova_senha) < 8:
            return Response(
                {"detail": "A senha precisa ter ao menos 8 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token.usuario.set_password(nova_senha)
        token.usuario.save()

        token.usado = True
        token.save()

        LogAutenticacao.objects.create(
            usuario=token.usuario,
            email_informado=token.usuario.email,
            tipo_evento=LogAutenticacao.TipoEvento.RECUPERACAO_SUCESSO,
        )

        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)