from django.conf import settings
from django.core.mail import send_mail

from .models import Notificacao


def notificar(usuario, mensagem, tipo='EMAIL'):
    """
    Ponto único de notificação do sistema. Faz duas coisas:

    1. Grava um registro em Notificacao — histórico/auditoria de que
       a notificação foi gerada.

    2. Envia o e-mail via send_mail(). 
    """
    Notificacao.objects.create(
        usuario=usuario,
        mensagem=mensagem,
        tipo=tipo,
    )

    if tipo == 'EMAIL' and usuario.email:
        send_mail(
            subject='EmprestaCampus - Notificação',
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=True,
        )


def notificar_admins(mensagem, tipo='EMAIL'):
    """
    Notifica todos os usuários com acesso ao Django Admin (is_staff),
    que são quem de fato consegue agir sobre solicitações pendentes.
    """
    from django.contrib.auth import get_user_model
    Usuario = get_user_model()

    admins = Usuario.objects.filter(is_staff=True, is_active=True)
    for admin_usuario in admins:
        notificar(admin_usuario, mensagem, tipo)