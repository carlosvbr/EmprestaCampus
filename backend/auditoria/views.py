from auditoria.models import RegistroAuditoria
from django.contrib.auth.models import User

# Função auxiliar (se ainda não tiver) para capturar o IP real
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

# Na sua view de login:
def login_view(request):
    # código de extração do formulário
    
    if request.method == 'POST':
        user = authenticate(request, username=username, password=password)
        ip = get_client_ip(request)

        if user is not None:
            RegistroAuditoria.objects.create(
                usuario=user,
                acao='LOGIN_SUCESSO',
                modulo_afetado='Autenticação',
                descricao='Autenticação primária concluída com sucesso.',
                ip_origem=ip
            )
            login(request, user)
        else:
            usuario_tentado = User.objects.filter(username=username).first()
            RegistroAuditoria.objects.create(
                usuario=usuario_tentado,
                acao='LOGIN_FALHA',
                modulo_afetado='Autenticação',
                descricao='Credenciais inválidas submetidas.',
                ip_origem=ip
            )
