import base64
import io

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LogAutenticacao, TokenRecuperacaoSenha, Usuario
from .serializers import RegistroSerializer


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
    Sempre responde 200, mesmo se o e-mail não existir no sistema.
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
            
            # 1. Gera a rota de forma limpa, baseada no urls.py
            caminho_base = reverse('redefinir_senha_web').lstrip('/')
            link = request.build_absolute_uri(f"/{caminho_base}?token={token.token}")
            
            # 2. Imprime o link limpo direto no terminal (Fura o bloqueio do EmailBackend)
            print("\n" + "="*70)
            print("LINK DE RECUPERAÇÃO (LIMPO PARA ACESSO DIRETO):")
            print(link)
            print("="*70 + "\n")

        return Response(
            {"detail": "Se o e-mail existir, um link de recuperação foi enviado."},
            status=status.HTTP_200_OK,
        )


class RedefinirSenhaView(APIView):
    """
    Recebe um token de recuperação e uma nova senha, valida e aplica.
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
    """
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username')
        senha_digitada = request.POST.get('password')

        # 1. Verifica preventivamente se o usuário existe para checar o status de consentimento LGPD
        usuario_obj = Usuario.objects.filter(username=usuario_digitado).first() or \
                      Usuario.objects.filter(email=usuario_digitado).first()

        # 2. Se a conta foi desativada por revogação de consentimento, redireciona para a tela de reativação
        if usuario_obj and (not usuario_obj.consentimento_dados or not usuario_obj.is_active):
            request.session['usuario_inativo_id'] = usuario_obj.id
            messages.error(request, "Sua conta está inativa devido à revogação do consentimento (LGPD).")
            return redirect('reativar_conta_lgpd')

        # 3. Fluxo normal de autenticação do Django
        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        if user is not None:
            tem_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()

            if tem_2fa:
                request.session['pre_2fa_user_id'] = user.id
                return redirect('validar_2fa_web')

            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')


@login_required(login_url='/api/usuarios/entrar/')
def home_view(request):
    return render(request, 'usuarios/home.html')


def logout_view(request):
    logout(request)
    return redirect('login_web')


class AtivarDoisFatoresView(APIView):
    """
    Endpoints de API para 2FA (Mantidos para compatibilidade com outros clientes)
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


@login_required
def perfil_view(request):
    return render(request, 'usuarios/perfil.html')


@login_required
def revogar_consentimento_view(request):
    if request.method == 'POST':
        usuario = request.user
        
        # Se estiver ativo, nós revogamos e desativamos a conta
        if usuario.consentimento_dados:
            usuario.consentimento_dados = False
            usuario.data_consentimento = None
            usuario.versao_documento_aceito = None
            usuario.is_active = False
            usuario.save()
            
            LogAutenticacao.objects.create(
                usuario=usuario,
                email_informado=usuario.email,
                tipo_evento=LogAutenticacao.TipoEvento.DOISFA_DESATIVADO,
                detalhe="Usuário revogou o consentimento de dados (LGPD 4.6)"
            )
            logout(request)
            messages.warning(request, "Você revogou seu consentimento. Seu acesso foi suspenso.")
            return redirect('login_web')
            
        # Se já estiver revogado e ele clicou em reativar
        else:
            usuario.consentimento_dados = True
            usuario.data_consentimento = timezone.now()
            usuario.versao_documento_aceito = "v1.0"
            usuario.is_active = True
            usuario.save()
            
            messages.success(request, "Consentimento restaurado com sucesso!")
            return redirect('perfil')
            
    return redirect('perfil')


@login_required
def encerrar_conta_view(request):
    if request.method == 'POST':
        usuario = request.user
        
        # 1. Mascarar dados pessoais (LGPD 4.10 - Anonimização)
        prefixo = f"anon_{usuario.id}"
        
        usuario.username = prefixo
        usuario.first_name = "Usuário"
        usuario.last_name = "Anonimizado"
        usuario.email = f"{prefixo}@emprestacampus.local"
        usuario.matricula = prefixo
        
        # 2. Revogar acesso e destruir credenciais
        usuario.is_active = False
        usuario.set_unusable_password() 
        
        # 3. Persistir a anonimização no PostgreSQL
        usuario.save()
        
        # 4. Destruir a sessão atual do navegador
        logout(request)
        
        messages.success(request, "Conta encerrada. Seus dados pessoais foram anonimizados irreversivelmente.")
        
        return redirect('login_web')
        
    return redirect('perfil')


@login_required
def exportar_dados_view(request):
    usuario = request.user
    
    dados_pessoais = {
        "id_conta": usuario.id,
        "usuario": usuario.username,
        "nome": usuario.first_name,
        "sobrenome": usuario.last_name,
        "email": usuario.email,
        "matricula": getattr(usuario, 'matricula', 'Não registrada'),
        "data_criacao_conta": usuario.date_joined.strftime("%d/%m/%Y %H:%M:%S") if usuario.date_joined else None,
        "status_conta": "Ativa" if usuario.is_active else "Inativa",
    }
    
    response = JsonResponse(dados_pessoais, json_dumps_params={'ensure_ascii': False, 'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="dados_pessoais_{usuario.username}.json"'
    
    return response


@login_required
def configurar_2fa_view(request):
    # Processa a confirmação do código digitado
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()

        if device and device.verify_token(codigo):
            device.confirmed = True
            device.save()
            
            LogAutenticacao.objects.create(
                usuario=request.user,
                email_informado=request.user.email,
                tipo_evento=LogAutenticacao.TipoEvento.DOISFA_ATIVADO,
            )
            
            messages.success(request, 'Autenticação de Dois Fatores (2FA) ativada com sucesso!')
            return redirect('perfil')
        else:
            messages.error(request, 'Código inválido. Tente novamente.')

    # Geração do QR Code para exibição (Método GET ou falha no POST)
    TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
    
    device = TOTPDevice.objects.create(
        user=request.user,
        name="dispositivo-padrao",
        confirmed=False,
    )
    
    # Converte a imagem gerada para texto Base64
    img = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return render(request, 'usuarios/configurar_2fa.html', {'qr_code': qr_b64})


def reativar_conta_lgpd_view(request):
    user_id = request.session.get('usuario_inativo_id')
    if not user_id:
        return redirect('login_web')
        
    usuario = Usuario.objects.filter(id=user_id).first()
    if not usuario:
        return redirect('login_web')
        
    if request.method == 'POST':
        # Restaura o consentimento e reativa a conta
        usuario.consentimento_dados = True
        usuario.data_consentimento = timezone.now()
        usuario.versao_documento_aceito = "v1.0"
        usuario.is_active = True
        usuario.save()
        
        # Limpa a sessão e manda para o login
        del request.session['usuario_inativo_id']
        messages.success(request, "Consentimento restaurado e conta reativada com sucesso! Faça login novamente.")
        return redirect('login_web')
        
    return render(request, 'usuarios/reativar_conta.html', {'usuario': usuario})