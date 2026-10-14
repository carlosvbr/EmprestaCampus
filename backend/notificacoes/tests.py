import re
from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from emprestimos.models import Emprestimo
from notificacoes.models import Notificacao
from notificacoes.utils import notificar, notificar_admins
from usuarios.models import TokenRecuperacaoSenha, Usuario


def _acao_admin(cliente, acao, emprestimo):
    """Simula o admin escolhendo uma ação na lista de empréstimos do /admin/."""
    return cliente.post(
        reverse("admin:emprestimos_emprestimo_changelist"),
        {"action": acao, "_selected_action": [emprestimo.id], "index": 0},
    )


@pytest.mark.django_db
class TestNotificar:
    """
    notificar() faz duas coisas: grava o histórico no banco e envia o
    e-mail. O mailoutbox é a "caixa de saída" falsa do pytest-django:
    nos testes, nenhum e-mail sai de verdade.
    """

    def test_grava_o_registro_no_banco(self, aluno):
        notificar(aluno, "Mensagem de teste.")

        registro = Notificacao.objects.get(usuario=aluno)
        assert registro.mensagem == "Mensagem de teste."
        assert registro.tipo == "EMAIL"
        assert registro.lida is False
        assert registro.data_criacao is not None

    def test_envia_o_email_para_o_usuario(self, aluno, mailoutbox):
        notificar(aluno, "Mensagem de teste.")

        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.to == [aluno.email]
        assert email.subject == "EmprestaCampus - Notificação"
        assert email.body == "Mensagem de teste."
        assert email.from_email == settings.DEFAULT_FROM_EMAIL

    def test_tipo_sistema_grava_mas_nao_envia_email(self, aluno, mailoutbox):
        notificar(aluno, "Aviso interno.", tipo="SISTEMA")

        assert Notificacao.objects.filter(usuario=aluno, tipo="SISTEMA").count() == 1
        assert len(mailoutbox) == 0

    def test_usuario_sem_email_grava_mas_nao_envia(self, db, mailoutbox):
        sem_email = Usuario.objects.create_user(username="sem_email", papel="ALUNO")

        notificar(sem_email, "Mensagem de teste.")

        assert Notificacao.objects.filter(usuario=sem_email).count() == 1
        assert len(mailoutbox) == 0


@pytest.mark.django_db
class TestNotificarAdmins:
    def test_avisa_todos_os_administradores_ativos(self, mailoutbox):
        Usuario.objects.create_user(username="admin_a", email="a@exemplo.com", papel="ADMIN")
        Usuario.objects.create_user(username="admin_b", email="b@exemplo.com", papel="ADMIN")

        notificar_admins("Nova solicitação de teste.")

        assert Notificacao.objects.count() == 2
        assert sorted(email.to[0] for email in mailoutbox) == ["a@exemplo.com", "b@exemplo.com"]

    def test_nao_avisa_aluno_nem_admin_inativo(self, aluno, mailoutbox):
        ativo = Usuario.objects.create_user(
            username="admin_ativo", email="ativo@exemplo.com", papel="ADMIN"
        )
        Usuario.objects.create_user(
            username="admin_inativo",
            email="inativo@exemplo.com",
            papel="ADMIN",
            is_active=False,
        )

        notificar_admins("Nova solicitação de teste.")

        assert list(Notificacao.objects.values_list("usuario", flat=True)) == [ativo.id]
        assert [email.to for email in mailoutbox] == [["ativo@exemplo.com"]]

    def test_sem_administradores_nao_da_erro(self, aluno, mailoutbox):
        notificar_admins("Ninguém para avisar.")

        assert Notificacao.objects.count() == 0
        assert len(mailoutbox) == 0


@pytest.mark.django_db
class TestNotificacaoEUsuarioExcluido:
    def test_excluir_usuario_apaga_as_notificacoes_dele(self, aluno):
        notificar(aluno, "Mensagem de teste.")
        assert Notificacao.objects.count() == 1

        aluno.delete()

        assert Notificacao.objects.count() == 0


@pytest.mark.django_db
class TestAdminDeNotificacoes:
    def test_listagem_resume_mensagens_longas(self, cliente_admin, aluno):
        Notificacao.objects.create(usuario=aluno, mensagem="a" * 100, tipo="EMAIL")

        html = cliente_admin.get(
            reverse("admin:notificacoes_notificacao_changelist")
        ).content.decode()

        assert "a" * 60 + "..." in html
        assert "a" * 61 not in html


@pytest.mark.django_db
class TestEmailsDoFluxoDeEmprestimo:
    """
    Ponta a ponta: cada evento do empréstimo dispara o e-mail certo para
    a pessoa certa (aluno ou administrador).
    """

    def test_solicitacao_avisa_o_admin_por_email(
        self, cliente_aluno, aluno, administrador, equipamento, mailoutbox
    ):
        cliente_aluno.post(reverse("solicitar_emprestimo_web", args=[equipamento.id]))

        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.to == [administrador.email]
        assert equipamento.nome in email.body
        assert aluno.username in email.body

    def test_aprovacao_avisa_o_aluno_com_o_prazo(
        self, cliente_admin, aluno, equipamento, mailoutbox
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _acao_admin(cliente_admin, "aprovar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()

        assert len(mailoutbox) == 1
        email = mailoutbox[0]
        assert email.to == [aluno.email]
        assert "aprovado" in email.body
        assert equipamento.nome in email.body
        assert f"{emprestimo.data_devolucao_prevista:%d/%m/%Y}" in email.body

    def test_rejeicao_avisa_o_aluno(self, cliente_admin, aluno, equipamento, mailoutbox):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _acao_admin(cliente_admin, "rejeitar_emprestimos", emprestimo)

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [aluno.email]
        assert "rejeitado" in mailoutbox[0].body

    def test_devolucao_avisa_o_aluno(self, cliente_admin, aluno, equipamento, mailoutbox):
        equipamento.status = "EMPRESTADO"
        equipamento.save()
        agora = timezone.now()
        emprestimo = Emprestimo.objects.create(
            usuario=aluno,
            equipamento=equipamento,
            status="APROVADO",
            data_retirada=agora,
            data_devolucao_prevista=agora + timedelta(days=7),
        )

        _acao_admin(cliente_admin, "marcar_devolvido", emprestimo)

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [aluno.email]
        assert "devolução" in mailoutbox[0].body

@pytest.mark.django_db
class TestFalhaNoEnvioNaoQuebraNada:
    def test_erro_de_smtp_e_registrado_e_a_notificacao_continua_gravada(
        self, aluno, monkeypatch, caplog
    ):
        def smtp_fora_do_ar(*args, **kwargs):
            raise OSError("SMTP fora do ar")

        monkeypatch.setattr("notificacoes.utils.send_mail", smtp_fora_do_ar)

        notificar(aluno, "Mensagem de teste.")

        assert Notificacao.objects.filter(usuario=aluno).count() == 1
        assert "SMTP fora do ar" in caplog.text


@pytest.mark.django_db
class TestRecuperacaoDeSenhaPorEmail:
    URL_SOLICITAR = "/api/usuarios/recuperar-senha/"
    URL_REDEFINIR = "/api/usuarios/redefinir-senha/"

    def _solicitar(self, email):
        return Client().post(
            self.URL_SOLICITAR, {"email": email}, content_type="application/json"
        )

    def test_envia_o_link_por_email(self, aluno, mailoutbox):
        resposta = self._solicitar(aluno.email)
        token = TokenRecuperacaoSenha.objects.get(usuario=aluno)

        assert resposta.status_code == 200
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [aluno.email]
        assert f"token={token.token}" in mailoutbox[0].body

    def test_email_inexistente_responde_igual_e_nao_envia(self, db, mailoutbox):
        resposta = self._solicitar("ninguem@exemplo.com")

        assert resposta.status_code == 200
        assert resposta.json()["detail"] == (
            "Se o e-mail existir, um link de recuperação foi enviado."
        )
        assert len(mailoutbox) == 0
        assert TokenRecuperacaoSenha.objects.count() == 0

    def test_o_token_nao_fica_gravado_nas_notificacoes(self, aluno):
        self._solicitar(aluno.email)

        assert Notificacao.objects.count() == 0

    def test_o_link_do_email_redefine_a_senha(self, aluno, mailoutbox):
        self._solicitar(aluno.email)
        token = re.search(r"token=([\w-]+)", mailoutbox[0].body).group(1)

        resposta = Client().post(
            self.URL_REDEFINIR,
            {"token": token, "password": "NovaSenha123"},
            content_type="application/json",
        )
        aluno.refresh_from_db()

        assert resposta.status_code == 200
        assert aluno.check_password("NovaSenha123")