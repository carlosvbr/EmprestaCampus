import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notificacao

logger = logging.getLogger(__name__)


def enviar_email(usuario, assunto, mensagem):
    """
    Envia um e-mail ao usuário pelo mailer "default" (settings.MAILERS).
    Devolve True se enviou, False se não havia e-mail ou o envio falhou.

    """
    if not usuario.email:
        return False

    try:
        send_mail(
            subject=assunto,
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
        )
    except Exception:
        logger.exception("Falha ao enviar e-mail para o usuário id=%s", usuario.id)
        return False

    return True


def notificar(usuario, mensagem, tipo='EMAIL'):
    """
    Ponto único de notificação do sistema. Faz duas coisas:

    1. Grava um registro em Notificacao (histórico consultável no /admin/),
       independente de o e-mail ter sido entregue ou não.
    2. Se o tipo for EMAIL, envia o e-mail.

    """
    Notificacao.objects.create(
        usuario=usuario,
        mensagem=mensagem,
        tipo=tipo,
    )

    if tipo == 'EMAIL':
        enviar_email(usuario, 'EmprestaCampus - Notificação', mensagem)


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