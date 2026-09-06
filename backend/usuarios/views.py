from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

import io
import qrcode
from django_otp.plugins.otp_totp.models import TOTPDevice

from .serializers import RegistroSerializer
from .models import LogAutenticacao, TokenRecuperacaoSenha, Usuario


class RegistroView(generics.CreateAPIView):
    """
    Endpoint público de cadastro de usuário via API REST.
    Não exige autenticação (AllowAny), pois atua como porta de entrada.
    A senha é recebida em texto plano, mas o RegistroSerializer delega
    a criptografia ao set_password(), aplicando hash (PBKDF2) antes da
    persistência no banco PostgreSQL.
    """

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


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
            LogAutenticacao.objects.create(
                usuario=token.usuario,
                email_informado=token.usuario.email,
                tipo_evento=LogAutenticacao.TipoEvento.RECUPERACAO_FALHA,
                detalhe="Senha nova com menos de 8 caracteres",
            )
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


def login_view(request):
    """
    Interface visual (Stateful) para autenticação de usuários via web.
    Integra a checagem segura de credenciais com o modelo do PostgreSQL.

    Quando o usuário tem 2FA confirmado, a sessão NÃO é criada aqui.
    Em vez disso, guardamos o id do usuário em request.session (fora da
    sessão autenticada de verdade) e redirecionamos para a validação do
    código. A sessão autenticada só existe depois do código correto,
    em validar_dois_fatores_view.
    """
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username')
        senha_digitada = request.POST.get('password')

        # authenticate(): Abstrai a verificação de hash e previne SQL Injection na consulta
        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        if user is not None:
            tem_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()

            if tem_2fa:
                request.session['pre_2fa_user_id'] = user.id
                return redirect('validar_2fa_web')

            # login(): Acopla o usuário validado à sessão, gerando o cookie HTTP-only
            login(request, user)
            return redirect('home')
        else:
            # Mensagem genérica intencional para mitigar vulnerabilidade de Enumeração de Usuários
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')


def home_view(request):
    """
    Endpoint de validação visual para comprovar a transição
    de estado após o login via front-end (Caminho Feliz).
    """
    return HttpResponse("<h1>Login bem-sucedido! Bem-vindo ao EmprestaCampus.</h1><p>Esta é a tela inicial provisória.</p>")


def logout_view(request):
    """
    Encerra a sessão do usuário autenticado via web.

    logout() limpa os dados de sessão no servidor e invalida o cookie
    de sessão do navegador, não apenas remove os dados do lado do
    cliente. Uma sessão encerrada aqui não pode ser reaproveitada.
    """
    logout(request)
    return redirect('login_web')


class AtivarDoisFatoresView(APIView):
    """
    Cria um dispositivo TOTP não confirmado para o usuário autenticado
    e devolve o QR Code (imagem PNG) para escanear no app autenticador.

    O dispositivo só é considerado ativo de fato depois que o usuário
    confirma o primeiro código gerado, em ConfirmarDoisFatoresView.
    Antes da confirmação, ele existe mas não bloqueia o login (ver
    device.confirmed).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()

        device = TOTPDevice.objects.create(
            user=request.user,
            name="dispositivo-padrao",
            confirmed=False,
        )

        url_provisionamento = device.config_url

        imagem = qrcode.make(url_provisionamento)
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")

        return HttpResponse(buffer.getvalue(), content_type="image/png")


class ConfirmarDoisFatoresView(APIView):
    """
    Confirma o dispositivo TOTP pendente com o primeiro código gerado
    pelo app autenticador. Sem essa confirmação, o dispositivo nunca
    passa a exigir código no login (device.confirmed continua False).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        codigo = request.data.get("codigo", "")

        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()

        if not device:
            return Response(
                {"detail": "Nenhuma ativação de 2FA pendente para este usuário."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not device.verify_token(codigo):
            LogAutenticacao.objects.create(
                usuario=request.user,
                email_informado=request.user.email,
                tipo_evento=LogAutenticacao.TipoEvento.DOISFA_FALHA,
                detalhe="Código inválido na confirmação da ativação",
            )
            return Response({"detail": "Código inválido."}, status=status.HTTP_400_BAD_REQUEST)

        device.confirmed = True
        device.save()

        LogAutenticacao.objects.create(
            usuario=request.user,
            email_informado=request.user.email,
            tipo_evento=LogAutenticacao.TipoEvento.DOISFA_ATIVADO,
        )

        return Response({"detail": "2FA ativado com sucesso."}, status=status.HTTP_200_OK)


def validar_dois_fatores_view(request):
    """
    Segunda etapa do login para usuários com 2FA confirmado.

    Só é possível chegar aqui depois de senha correta (login_view
    guardou 'pre_2fa_user_id' na sessão). A sessão autenticada de
    verdade (login()) só é criada se o código TOTP for válido.
    """
    user_id = request.session.get('pre_2fa_user_id')

    if not user_id:
        return redirect('login_web')

    usuario = Usuario.objects.filter(id=user_id).first()

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        device = TOTPDevice.objects.filter(user=usuario, confirmed=True).first()

        if device and device.verify_token(codigo):
            del request.session['pre_2fa_user_id']
            login(request, usuario, backend='django.contrib.auth.backends.ModelBackend')

            LogAutenticacao.objects.create(
                usuario=usuario,
                email_informado=usuario.email,
                tipo_evento=LogAutenticacao.TipoEvento.DOISFA_SUCESSO,
            )

            return redirect('home')

        LogAutenticacao.objects.create(
            usuario=usuario,
            email_informado=usuario.email,
            tipo_evento=LogAutenticacao.TipoEvento.DOISFA_FALHA,
            detalhe="Código incorreto no login",
        )
        messages.error(request, 'Código incorreto.')

    return render(request, 'usuarios/validar_2fa.html')