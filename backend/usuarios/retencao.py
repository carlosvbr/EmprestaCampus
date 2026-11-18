"""
Eliminação, anonimização e retenção de dados pessoais (LGPD, arts. 15 e 16).

Dois pontos de entrada:

- anonimizar_usuario(): usado no encerramento da conta e na rotina abaixo.
  Remove ou anonimiza todos os vínculos do titular, e não só os campos da
  conta.
- aplicar_retencao(): elimina o que passou do prazo. Roda pelo comando
  "python manage.py aplicar_retencao", que deve ser agendado uma vez por
  dia (cron ou agendador do servidor).

Os prazos são os do documento "Mapeamento de Dados Pessoais.md".
"""

from datetime import timedelta

from axes.models import AccessAttempt
from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django.db import connection, transaction
from django.utils import timezone

PRAZOS = {
    "token_recuperacao_apos_expirar": timedelta(days=7),
    "notificacoes": timedelta(days=90),
    "tentativas_de_login": timedelta(days=30),
    "conta_suspensa": timedelta(days=365),
    "emprestimos_encerrados": timedelta(days=5 * 365),
    "auditoria": timedelta(days=5 * 365),
}

# Empréstimos em que o titular ainda tem, ou pode vir a ter, um equipamento.
STATUS_EM_ABERTO = ("SOLICITADO", "APROVADO", "RETIRADO", "ATRASADO")


def tem_emprestimo_em_aberto(usuario):
    from emprestimos.models import Emprestimo
    return Emprestimo.objects.filter(usuario=usuario, status__in=STATUS_EM_ABERTO).exists()


def encerrar_sessoes(usuario):
    """Encerra as sessões abertas do usuário em qualquer navegador."""
    for sessao in Session.objects.filter(expire_date__gte=timezone.now()):
        if sessao.get_decoded().get("_auth_user_id") == str(usuario.pk):
            sessao.delete()


@transaction.atomic
def anonimizar_usuario(usuario):
    """
    Anonimiza a conta e elimina os dados pessoais ligados a ela.

    Fica só o que tem base legal para continuar (art. 16): o histórico de
    empréstimos, para o controle patrimonial, ligado à conta já anônima;
    o histórico de consentimento, como prova; e a auditoria, que é
    imutável durante o prazo de retenção.
    """
    from emprestimos.models import Emprestimo
    from notificacoes.models import Notificacao
    from usuarios.models import DispositivoTOTP, TokenRecuperacaoSenha

    identificadores = {usuario.username, usuario.email} - {"", None}

    DispositivoTOTP.objects.filter(user=usuario).delete()
    TokenRecuperacaoSenha.objects.filter(usuario=usuario).delete()
    Notificacao.objects.filter(usuario=usuario).delete()
    Emprestimo.objects.filter(usuario=usuario).update(observacoes=None)
    AccessAttempt.objects.filter(username__in=identificadores).delete()
    encerrar_sessoes(usuario)

    prefixo = f"anon_{usuario.pk}"
    usuario.username = prefixo
    usuario.first_name = "Usuário"
    usuario.last_name = "Anonimizado"
    usuario.email = f"{prefixo}@emprestacampus.local"
    usuario.matricula = prefixo
    usuario.telefone = None
    usuario.last_login = None
    usuario.consentimento_revogado_em = None
    usuario.is_active = False
    usuario.set_unusable_password()
    usuario.save()


def aplicar_retencao(agora=None):
    """
    Elimina os dados que passaram do prazo de retenção.
    Devolve quantos registros foram tratados em cada categoria.
    """
    from emprestimos.models import Emprestimo
    from notificacoes.models import Notificacao
    from usuarios.models import TokenRecuperacaoSenha, Usuario

    agora = agora or timezone.now()
    resultado = {}

    resultado["tokens_recuperacao"] = TokenRecuperacaoSenha.objects.filter(
        expira_em__lt=agora - PRAZOS["token_recuperacao_apos_expirar"]
    ).delete()[0]

    resultado["notificacoes"] = Notificacao.objects.filter(
        data_criacao__lt=agora - PRAZOS["notificacoes"]
    ).delete()[0]

    resultado["tentativas_de_login"] = AccessAttempt.objects.filter(
        attempt_time__lt=agora - PRAZOS["tentativas_de_login"]
    ).delete()[0]

    resultado["sessoes_expiradas"] = Session.objects.filter(expire_date__lt=agora).delete()[0]

    # Conta suspensa por revogação há mais de 12 meses. Quem ainda está com
    # um equipamento fica de fora, porque o controle patrimonial depende de
    # saber quem é; ela é anonimizada numa execução depois da devolução.
    suspensas = Usuario.objects.filter(
        is_active=False,
        consentimento_dados=False,
        consentimento_revogado_em__lt=agora - PRAZOS["conta_suspensa"],
    )
    anonimizadas = 0
    for usuario in suspensas:
        if not tem_emprestimo_em_aberto(usuario):
            anonimizar_usuario(usuario)
            anonimizadas += 1
    resultado["contas_suspensas_anonimizadas"] = anonimizadas

    limite = agora - PRAZOS["emprestimos_encerrados"]
    resultado["emprestimos"] = (
        Emprestimo.objects.filter(status="DEVOLVIDO", data_devolucao_real__lt=limite).delete()[0]
        + Emprestimo.objects.filter(status="REJEITADO", data_solicitacao__lt=limite).delete()[0]
    )

    limite = agora - PRAZOS["auditoria"]
    resultado["acoes_do_admin"] = LogEntry.objects.filter(action_time__lt=limite).delete()[0]

    # A auditoria é imutável: o ORM recusa qualquer exclusão, e o trigger do
    # PostgreSQL só deixa apagar registros com mais de 5 anos. Por isso a
    # exclusão é feita em SQL e só alcança o que já passou do prazo.
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM auditoria_registroauditoria WHERE data_hora < %s", [limite])
        resultado["auditoria"] = cursor.rowcount

    return resultado
