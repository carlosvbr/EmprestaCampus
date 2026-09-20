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

# Importação alterada para usar o módulo central de auditoria e remover LogAutenticacao
from auditoria.models import RegistroAuditoria
from .models import TokenRecuperacaoSenha, Usuario
from .serializers import RegistroSerializer

# Função auxiliar para capturar o IP real
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


class RegistroView(generics.CreateAPIView):
    """
    Endpoint público de cadastro de usuário via API REST.
    """
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


class SolicitarRecuperacaoSenhaView(APIView):
    """
    Recebe um e-mail e gera um token de recuperação.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "")
        usuario = Usuario.objects.filter(email=email).first()
        ip = get_client_ip(request)

        RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='RECUPERACAO',
            modulo_afetado='Autenticação/Recuperação',
            descricao=f'Solicitação de recuperação de senha. E-mail informado: {email}',
            ip_origem=ip
        )

        if usuario:
            token = TokenRecuperacaoSenha.objects.create(usuario=usuario)
            
            caminho_base = reverse('redefinir_senha_web').lstrip('/')
            link = request.build_absolute_uri(f"/{caminho_base}?token={token.token}")
            
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
    Recebe um token de recuperação e uma nova senha.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token_str = request.data.get("token", "")
        nova_senha = request.data.get("password", "")
        ip = get_client_ip(request)

        token = TokenRecuperacaoSenha.objects.filter(token=token_str).first()

        if not token:
            RegistroAuditoria.objects.create(
                usuario=None,
                acao='UPDATE',
                modulo_afetado='Autenticação/Recuperação',
                descricao='Falha na recuperação: Token inexistente.',
                ip_origem=ip
            )
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if not token.esta_valido():
            motivo = "Token já utilizado" if token.usado else "Token expirado"
            RegistroAuditoria.objects.create(
                usuario=token.usuario,
                acao='UPDATE',
                modulo_afetado='Autenticação/Recuperação',
                descricao=f'Falha na recuperação: {motivo}.',
                ip_origem=ip
            )
            return Response({"detail": motivo + "."}, status=status.HTTP_400_BAD_REQUEST)

        if len(nova_senha) < 8:
            RegistroAuditoria.objects.create(
                usuario=token.usuario,
                acao='UPDATE',
                modulo_afetado='Autenticação/Recuperação',
                descricao='Falha na recuperação: Senha nova com menos de 8 caracteres.',
                ip_origem=ip
            )
            return Response(
                {"detail": "A senha precisa ter ao menos 8 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token.usuario.set_password(nova_senha)
        token.usuario.save()

        token.usado = True
        token.save()

        RegistroAuditoria.objects.create(
            usuario=token.usuario,
            acao='RECUPERACAO',
            modulo_afetado='Autenticação/Recuperação',
            descricao='Senha redefinida com sucesso.',
            ip_origem=ip
        )

        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


def login_view(request):
    """
    Interface visual (Stateful) para autenticação de usuários via web.
    """
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username')
        senha_digitada = request.POST.get('password')
        ip = get_client_ip(request)

        usuario_obj = Usuario.objects.filter(username=usuario_digitado).first() or \
                      Usuario.objects.filter(email=usuario_digitado).first()

        if usuario_obj and (not usuario_obj.consentimento_dados or not usuario_obj.is_active):
            request.session['usuario_inativo_id'] = usuario_obj.id
            messages.error(request, "Sua conta está inativa devido à revogação do consentimento (LGPD).")
            return redirect('reativar_conta_lgpd')

        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        if user is not None:
            tem_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()

            if tem_2fa:
                request.session['pre_2fa_user_id'] = user.id
                return redirect('validar_2fa_web')

            RegistroAuditoria.objects.create(
                usuario=user,
                acao='LOGIN_SUCESSO',
                modulo_afetado='Autenticação',
                descricao='Autenticação primária concluída com sucesso (sem 2FA).',
                ip_origem=ip
            )
            login(request, user)
            return redirect('home')
        else:
            RegistroAuditoria.objects.create(
                usuario=usuario_obj,
                acao='LOGIN_FALHA',
                modulo_afetado='Autenticação',
                descricao=f'Credenciais inválidas. Login tentado: {usuario_digitado}',
                ip_origem=ip
            )
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')

@login_required(login_url='/api/usuarios/entrar/')
def home_view(request):
    return render(request, 'usuarios/home.html')


def logout_view(request):
    logout(request)
    return redirect('login_web')


class AtivarDoisFatoresView(APIView):
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
        ip = get_client_ip(request)

        if not device:
            return Response(
                {"detail": "Nenhuma ativação de 2FA pendente para este usuário."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not device.verify_token(codigo):
            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Segurança/2FA',
                descricao='Falha: Código inválido na confirmação da ativação do 2FA.',
                ip_origem=ip
            )
            return Response({"detail": "Código inválido."}, status=status.HTTP_400_BAD_REQUEST)

        device.confirmed = True
        device.save()

        RegistroAuditoria.objects.create(
            usuario=request.user,
            acao='UPDATE',
            modulo_afetado='Segurança/2FA',
            descricao='2FA ativado com sucesso via API.',
            ip_origem=ip
        )

        return Response({"detail": "2FA ativado com sucesso."}, status=status.HTTP_200_OK)


def validar_dois_fatores_view(request):
    user_id = request.session.get('pre_2fa_user_id')
    ip = get_client_ip(request)

    if not user_id:
        return redirect('login_web')

    usuario = Usuario.objects.filter(id=user_id).first()

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        device = TOTPDevice.objects.filter(user=usuario, confirmed=True).first()

        if device and device.verify_token(codigo):
            del request.session['pre_2fa_user_id']
            login(request, usuario, backend='django.contrib.auth.backends.ModelBackend')

            RegistroAuditoria.objects.create(
                usuario=usuario,
                acao='2FA_SUCESSO',
                modulo_afetado='Autenticação',
                descricao='Autenticação 2FA concluída com sucesso.',
                ip_origem=ip
            )

            return redirect('home')

        RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='2FA_FALHA',
            modulo_afetado='Autenticação',
            descricao='Falha no 2FA: Código incorreto no login.',
            ip_origem=ip
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
        ip = get_client_ip(request)
        
        if usuario.consentimento_dados:
            usuario.consentimento_dados = False
            usuario.data_consentimento = None
            usuario.versao_documento_aceito = None
            usuario.is_active = False
            usuario.save()
            
            RegistroAuditoria.objects.create(
                usuario=usuario,
                acao='UPDATE',
                modulo_afetado='Privacidade/LGPD',
                descricao='Usuário revogou o consentimento de dados (LGPD 4.6) e teve acesso suspenso.',
                ip_origem=ip
            )
            logout(request)
            messages.warning(request, "Você revogou seu consentimento. Seu acesso foi suspenso.")
            return redirect('login_web')
            
        else:
            usuario.consentimento_dados = True
            usuario.data_consentimento = timezone.now()
            usuario.versao_documento_aceito = "v1.0"
            usuario.is_active = True
            usuario.save()
            
            RegistroAuditoria.objects.create(
                usuario=usuario,
                acao='UPDATE',
                modulo_afetado='Privacidade/LGPD',
                descricao='Usuário restaurou o consentimento de dados.',
                ip_origem=ip
            )
            messages.success(request, "Consentimento restaurado com sucesso!")
            return redirect('perfil')
            
    return redirect('perfil')


@login_required
def encerrar_conta_view(request):
    if request.method == 'POST':
        usuario = request.user
        ip = get_client_ip(request)
        
        prefixo = f"anon_{usuario.id}"
        
        RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='DELETE',
            modulo_afetado='Privacidade/LGPD',
            descricao='Usuário solicitou encerramento de conta. Dados pessoais anonimizados.',
            ip_origem=ip
        )
        
        usuario.username = prefixo
        usuario.first_name = "Usuário"
        usuario.last_name = "Anonimizado"
        usuario.email = f"{prefixo}@emprestacampus.local"
        usuario.matricula = prefixo
        
        usuario.is_active = False
        usuario.set_unusable_password() 
        usuario.save()
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
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        ip = get_client_ip(request)

        if device and device.verify_token(codigo):
            device.confirmed = True
            device.save()
            
            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Segurança/2FA',
                descricao='Autenticação de Dois Fatores (2FA) ativada com sucesso.',
                ip_origem=ip
            )
            
            messages.success(request, 'Autenticação de Dois Fatores (2FA) ativada com sucesso!')
            return redirect('perfil')
        else:
            messages.error(request, 'Código inválido. Tente novamente.')

    TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
    
    device = TOTPDevice.objects.create(
        user=request.user,
        name="dispositivo-padrao",
        confirmed=False,
    )
    
    img = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return render(request, 'usuarios/configurar_2fa.html', {'qr_code': qr_b64})


def reativar_conta_lgpd_view(request):
    user_id = request.session.get('usuario_inativo_id')
    ip = get_client_ip(request)

    if not user_id:
        return redirect('login_web')
        
    usuario = Usuario.objects.filter(id=user_id).first()
    if not usuario:
        return redirect('login_web')
        
    if request.method == 'POST':
        usuario.consentimento_dados = True
        usuario.data_consentimento = timezone.now()
        usuario.versao_documento_aceito = "v1.0"
        usuario.is_active = True
        usuario.save()
        
        RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='UPDATE',
            modulo_afetado='Privacidade/LGPD',
            descricao='Conta reativada e consentimento restaurado.',
            ip_origem=ip
        )
        
        del request.session['usuario_inativo_id']
        messages.success(request, "Consentimento restaurado e conta reativada com sucesso! Faça login novamente.")
        return redirect('login_web')
        
    return render(request, 'usuarios/reativar_conta.html', {'usuario': usuario})