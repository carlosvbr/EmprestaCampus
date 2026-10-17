import base64
import io

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from notificacoes.utils import enviar_email, notificar
from auditoria.models import RegistroAuditoria
from auditoria.utils import get_client_ip
from .models import TokenRecuperacaoSenha, Usuario
from .serializers import RegistroSerializer


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
            acao='RECUPERACAO_SOLICITADA',
            modulo_afetado='Autenticação/Recuperação',
            descricao=(
                'Solicitação de recuperação de senha.'
                if usuario else
                'Solicitação de recuperação de senha para e-mail não cadastrado.'
            ),
            ip_origem=ip
        )

        if usuario:
            token = TokenRecuperacaoSenha.objects.create(usuario=usuario)

            caminho_base = reverse('redefinir_senha_web').lstrip('/')
            link = request.build_absolute_uri(f"/{caminho_base}?token={token.token}")
            enviar_email(
                            usuario,
                            'EmprestaCampus - Recuperação de senha',
                            'Recebemos um pedido para redefinir a senha da sua conta.\n\n'
                            f'Para escolher uma nova senha, acesse:\n{link}\n\n'
                            'O link vale por 1 hora e só pode ser usado uma vez. '
                            'Se não foi você, ignore este e-mail: sua senha continua a mesma.'
                        )

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
                acao='RECUPERACAO_FALHA',
                modulo_afetado='Autenticação/Recuperação',
                descricao='Falha na recuperação: Token inexistente.',
                ip_origem=ip
            )
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if not token.esta_valido():
            motivo = "Token já utilizado" if token.usado else "Token expirado"
            RegistroAuditoria.objects.create(
                usuario=token.usuario,
                acao='RECUPERACAO_FALHA',
                modulo_afetado='Autenticação/Recuperação',
                descricao=f'Falha na recuperação: {motivo}.',
                ip_origem=ip
            )
            return Response({"detail": motivo + "."}, status=status.HTTP_400_BAD_REQUEST)

        if len(nova_senha) < 8:
            RegistroAuditoria.objects.create(
                usuario=token.usuario,
                acao='RECUPERACAO_FALHA',
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

        TokenRecuperacaoSenha.objects.filter(usuario=token.usuario, usado=False).update(usado=True)

        RegistroAuditoria.objects.create(
            usuario=token.usuario,
            acao='RECUPERACAO_SUCESSO',
            modulo_afetado='Autenticação/Recuperação',
            descricao='Senha redefinida com sucesso.',
            ip_origem=ip
        )

        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


REATIVACAO_VALIDADE_SEGUNDOS = 300


def pode_reativar(usuario):
    """
    Diz se a conta está suspensa SÓ porque o titular revogou o
    consentimento, que é o único caso em que ele mesmo pode reativá-la.

    - Revogou o consentimento: is_active=False e consentimento_dados=False.
    - Desativada pelo administrador: is_active=False, mas o consentimento
      continua True. Não pode se reativar sozinha (correção da falha F2).
    - Anonimizada (encerrar conta): a senha vira inutilizável
      (set_unusable_password), então nunca passa daqui.
    """
    return (
        usuario is not None
        and not usuario.is_active
        and not usuario.consentimento_dados
        and usuario.has_usable_password()
    )


def login_view(request):
    """
    Interface visual (Stateful) para autenticação de usuários via web.

    Correção A1/F2: antes, a view procurava o usuário e mandava para a
    tela de reativação ANTES de conferir a senha, então bastava saber o
    username para reativar a conta de outra pessoa. Agora a senha é
    sempre conferida primeiro, e a reativação só é oferecida a quem
    provou ser o dono da conta.
    """
    if request.method == 'POST':
        usuario_digitado = request.POST.get('username', '')
        senha_digitada = request.POST.get('password', '')
        ip = get_client_ip(request)

        user = authenticate(request, username=usuario_digitado, password=senha_digitada)

        usuario_obj = Usuario.objects.filter(username=usuario_digitado).first()

        if (
            user is None
            and not getattr(request, 'axes_locked_out', False)
            and pode_reativar(usuario_obj)
            and usuario_obj.check_password(senha_digitada)
        ):

            request.session['usuario_inativo_id'] = usuario_obj.id
            request.session['reativacao_autorizada_em'] = timezone.now().timestamp()
            messages.error(request, "Sua conta está inativa devido à revogação do consentimento (LGPD).")
            return redirect('reativar_conta_lgpd')

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
                descricao='Credenciais inválidas.',
                ip_origem=ip
            )
            messages.error(request, 'Credenciais inválidas. Verifique seu acesso e tente novamente.')

    return render(request, 'usuarios/login.html')

@login_required(login_url='/api/usuarios/entrar/')
def home_view(request):
    return render(request, 'usuarios/home.html')


def logout_view(request):
    if request.method != 'POST':
        return redirect('home')
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

        TOTPDevice.objects.filter(user=usuario).delete()
        TokenRecuperacaoSenha.objects.filter(usuario=usuario).delete()

        usuario.username = prefixo
        usuario.first_name = "Usuário"
        usuario.last_name = "Anonimizado"
        usuario.email = f"{prefixo}@emprestacampus.local"
        usuario.matricula = prefixo
        usuario.telefone = None

        usuario.is_active = False
        usuario.set_unusable_password()
        usuario.save()
        logout(request)

        messages.success(request, "Conta encerrada. Seus dados pessoais foram anonimizados irreversivelmente.")
        return redirect('login_web')

    return redirect('perfil')


@login_required
def exportar_dados_view(request):
    """
    Portabilidade dos dados pessoais (LGPD 4.9): devolve um JSON com tudo o
    que a página "Meu Perfil" mostra ao usuário, mais os dados da conta e da
    trilha de consentimento. O arquivo é só do próprio titular (login_required
    e request.user), nunca de outro usuário.
    """
    from emprestimos.models import Emprestimo

    usuario = request.user

    def formatar(data):
        return data.strftime("%d/%m/%Y %H:%M:%S") if data else None

    emprestimos = [
        {
            "equipamento": emprestimo.equipamento.nome,
            "patrimonio": emprestimo.equipamento.patrimonio,
            "status": emprestimo.get_status_display(),
            "data_solicitacao": formatar(emprestimo.data_solicitacao),
            "data_retirada": formatar(emprestimo.data_retirada),
            "data_devolucao_prevista": formatar(emprestimo.data_devolucao_prevista),
            "data_devolucao_real": formatar(emprestimo.data_devolucao_real),
            "prorrogacao_solicitada": emprestimo.prorrogacao_solicitada,
            "observacoes": emprestimo.observacoes or "",
        }
        for emprestimo in Emprestimo.objects.filter(usuario=usuario)
        .select_related('equipamento')
        .order_by('-data_solicitacao')
    ]

    dados_pessoais = {
        "id_conta": usuario.id,
        "nome_de_usuario": usuario.username,
        "nome_completo": usuario.get_full_name(),
        "nome": usuario.first_name,
        "sobrenome": usuario.last_name,
        "email": usuario.email,
        "matricula": usuario.matricula or "Não registrada",
        "telefone": usuario.telefone or "Não informado",
        "vinculo": usuario.get_papel_display(),
        "data_criacao_conta": formatar(usuario.date_joined),
        "status_conta": "Ativa" if usuario.is_active else "Inativa",
        "consentimento_dados": usuario.consentimento_dados,
        "data_consentimento": formatar(usuario.data_consentimento),
        "versao_documento_aceito": usuario.versao_documento_aceito,
        "emprestimos": emprestimos,
    }

    response = JsonResponse(dados_pessoais, json_dumps_params={'ensure_ascii': False, 'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="dados_pessoais_{usuario.username}.json"'

    return response

@login_required
def configurar_2fa_view(request):

    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        return render(request, 'usuarios/configurar_2fa.html', {'ativo': True})

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
            RegistroAuditoria.objects.create(
                usuario=request.user,
                acao='UPDATE',
                modulo_afetado='Segurança/2FA',
                descricao='Falha: Código inválido na ativação do 2FA pela web.',
                ip_origem=ip
            )
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

@login_required(login_url='/api/usuarios/entrar/')
def revogar_2fa_view(request):
    """
    Desativa a autenticação de dois fatores do usuário logado.

    A ação deixa rastro na auditoria e o dono da conta é avisado por e-mail.
    """
    if request.method != 'POST':
        return redirect('perfil')

    ip = get_client_ip(request)
    dispositivos = TOTPDevice.objects.filter(user=request.user)

    if not dispositivos.filter(confirmed=True).exists():

        dispositivos.delete()
        messages.info(request, 'A autenticação de dois fatores não está ativa.')
        return redirect('perfil')

    dispositivos.delete()

    RegistroAuditoria.objects.create(
        usuario=request.user,
        acao='UPDATE',
        modulo_afetado='Segurança/2FA',
        descricao='Autenticação de Dois Fatores (2FA) desativada pelo usuário.',
        ip_origem=ip
    )

    notificar(
        request.user,
        'A autenticação de dois fatores da sua conta no EmprestaCampus foi desativada. '
        'Se não foi você, entre em contato com o administrador e troque sua senha.'
    )

    messages.success(request, 'Autenticação de dois fatores desativada.')
    return redirect('perfil')

def reativar_conta_lgpd_view(request):
    """
    Tela onde o titular que revogou o consentimento pode restaurá-lo.

    Só é alcançável pelo login_view, depois da senha correta. Mesmo
    assim, as condições são conferidas de novo aqui, porque o estado da
    conta pode ter mudado entre o login e o POST (por exemplo, o admin
    desativou a conta nesse meio-tempo).
    """
    user_id = request.session.get('usuario_inativo_id')
    autorizado_em = request.session.get('reativacao_autorizada_em')
    ip = get_client_ip(request)

    def negar():
        # Limpa a autorização da sessão e manda de volta para o login.
        request.session.pop('usuario_inativo_id', None)
        request.session.pop('reativacao_autorizada_em', None)
        return redirect('login_web')

    if not user_id or not autorizado_em:
        return negar()

    # Autorização vencida: a pessoa precisa provar a senha de novo.
    if timezone.now().timestamp() - autorizado_em > REATIVACAO_VALIDADE_SEGUNDOS:
        messages.error(request, "O tempo para reativar a conta expirou. Entre novamente.")
        return negar()

    usuario = Usuario.objects.filter(id=user_id).first()

    # Conta desativada pelo admin, anonimizada ou já reativada.
    if not pode_reativar(usuario):
        return negar()

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

        # A autorização é de uso único: some da sessão depois de usada.
        request.session.pop('usuario_inativo_id', None)
        request.session.pop('reativacao_autorizada_em', None)
        messages.success(request, "Consentimento restaurado e conta reativada com sucesso! Faça login novamente.")
        return redirect('login_web')

    return render(request, 'usuarios/reativar_conta.html', {'usuario': usuario})


# Token intermediario do login JWT com 2FA.
#
# Emitido por LoginAPIView so depois da senha correta e exigido por
# VerificarDoisFatoresLoginView. E assinado com a SECRET_KEY (nao da
# para forjar a partir de um user_id) e expira em
# TOKEN_2FA_VALIDADE_SEGUNDOS, entao a segunda etapa nunca e acessivel
# sem ter passado pela primeira.
TOKEN_2FA_SALT = "usuarios.login_spa_2fa"
TOKEN_2FA_VALIDADE_SEGUNDOS = 300


def gerar_token_2fa(usuario):
    return signing.dumps({"uid": usuario.id}, salt=TOKEN_2FA_SALT)


def ler_token_2fa(token):
    """Devolve o usuario do token, ou None se invalido, adulterado ou expirado."""
    try:
        dados = signing.loads(token, salt=TOKEN_2FA_SALT, max_age=TOKEN_2FA_VALIDADE_SEGUNDOS)
    except (signing.BadSignature, TypeError):
        # SignatureExpired e subclasse de BadSignature
        return None
    return Usuario.objects.filter(id=dados.get("uid"), is_active=True).first()


class LoginAPIView(APIView):
    """
    Login para clientes JWT (SPA React), com suporte a 2FA.

    Diferente do TokenObtainPairView padrao do simplejwt, esta view
    verifica se o usuario tem 2FA confirmado antes de emitir o par de
    tokens. Se tiver, devolve apenas um sinal pedindo o codigo, sem
    nenhum token ainda, ate a segunda etapa ser concluida em
    VerificarDoisFatoresLoginView.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        ip = get_client_ip(request)

        user = authenticate(request, username=username, password=password)

        if user is None:
            RegistroAuditoria.objects.create(
                usuario=None,
                acao='LOGIN_FALHA',
                modulo_afetado='Autenticação/API',
                descricao='Credenciais invalidas via API.',
                ip_origem=ip,
            )
            return Response({"detail": "Credenciais invalidas."}, status=status.HTTP_401_UNAUTHORIZED)

        tem_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()

        if tem_2fa:
            return Response(
                {"requer_2fa": True, "token_2fa": gerar_token_2fa(user)},
                status=status.HTTP_200_OK,
            )

        RegistroAuditoria.objects.create(
            usuario=user,
            acao='LOGIN_SUCESSO',
            modulo_afetado='Autenticação/API',
            descricao='Login via API concluido com sucesso (sem 2FA).',
            ip_origem=ip,
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "requer_2fa": False,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class VerificarDoisFatoresLoginView(APIView):
    """
    Segunda etapa do login JWT para usuarios com 2FA confirmado.

    So emite o par de tokens depois do codigo TOTP correto, nunca
    antes. O usuario vem do token_2fa assinado devolvido por
    LoginAPIView (uma SPA nao usa sessao Django), nunca de um id
    enviado pelo cliente.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("token_2fa", "")
        codigo = request.data.get("codigo", "")
        ip = get_client_ip(request)

        usuario = ler_token_2fa(token)

        if not usuario:
            return Response(
                {"detail": "Sessao de login invalida ou expirada. Entre novamente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        device = TOTPDevice.objects.filter(user=usuario, confirmed=True).first()

        if not device or not device.verify_token(codigo):
            RegistroAuditoria.objects.create(
                usuario=usuario,
                acao='2FA_FALHA',
                modulo_afetado='Autenticação/API',
                descricao='Codigo incorreto no login via API.',
                ip_origem=ip,
            )
            return Response({"detail": "Codigo invalido."}, status=status.HTTP_400_BAD_REQUEST)

        RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='2FA_SUCESSO',
            modulo_afetado='Autenticação/API',
            descricao='2FA via API concluido com sucesso.',
            ip_origem=ip,
        )

        refresh = RefreshToken.for_user(usuario)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )