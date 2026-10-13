import pytest
from django.test import Client
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from auditoria.models import RegistroAuditoria
from emprestimos.models import Emprestimo
from notificacoes.models import Notificacao
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


@pytest.mark.django_db
class TestSolicitacaoPelaTela:
    """
    Fluxo do botão "Solicitar" do catálogo: só aceita POST, exige login,
    nasce como SOLICITADO, avisa os administradores, registra auditoria
    e impede pedidos em aberto repetidos do mesmo aluno.
    """

    def _solicitar(self, cliente, equipamento):
        return cliente.post(reverse("solicitar_emprestimo_web", args=[equipamento.id]))

    def test_aluno_logado_cria_solicitacao(self, cliente_aluno, aluno, equipamento):
        resposta = self._solicitar(cliente_aluno, equipamento)

        assert resposta.status_code == 302
        emprestimo = Emprestimo.objects.get(usuario=aluno, equipamento=equipamento)
        assert emprestimo.status == "SOLICITADO"
        # O prazo só é definido quando o admin aprova.
        assert emprestimo.data_devolucao_prevista is None

    def test_solicitacao_notifica_o_administrador(
        self, cliente_aluno, administrador, equipamento
    ):
        self._solicitar(cliente_aluno, equipamento)

        assert Notificacao.objects.filter(usuario=administrador).count() == 1

    def test_solicitacao_gera_registro_de_auditoria(
        self, cliente_aluno, aluno, equipamento
    ):
        self._solicitar(cliente_aluno, equipamento)

        assert RegistroAuditoria.objects.filter(
            usuario=aluno, acao="CREATE", modulo_afetado="Empréstimos"
        ).exists()

    def test_visitante_sem_login_e_mandado_para_o_login(self, equipamento):
        resposta = self._solicitar(Client(), equipamento)

        assert resposta.status_code == 302
        assert "/api/usuarios/entrar/" in resposta.url
        assert Emprestimo.objects.count() == 0

    def test_get_nao_cria_solicitacao(self, cliente_aluno, equipamento):
        resposta = cliente_aluno.get(reverse("solicitar_emprestimo_web", args=[equipamento.id]))

        assert resposta.status_code == 302
        assert Emprestimo.objects.count() == 0

    def test_equipamento_indisponivel_nao_pode_ser_solicitado(
        self, cliente_aluno, equipamento
    ):
        equipamento.status = "EMPRESTADO"
        equipamento.save()

        self._solicitar(cliente_aluno, equipamento)

        assert Emprestimo.objects.count() == 0

    def test_segunda_solicitacao_em_aberto_e_barrada(
        self, cliente_aluno, aluno, equipamento
    ):
        self._solicitar(cliente_aluno, equipamento)
        self._solicitar(cliente_aluno, equipamento)

        assert Emprestimo.objects.filter(usuario=aluno, equipamento=equipamento).count() == 1

    def test_pedido_rejeitado_nao_impede_nova_solicitacao(
        self, cliente_aluno, aluno, equipamento
    ):
        Emprestimo.objects.create(usuario=aluno, equipamento=equipamento, status="REJEITADO")

        self._solicitar(cliente_aluno, equipamento)

        assert Emprestimo.objects.filter(
            usuario=aluno, equipamento=equipamento, status="SOLICITADO"
        ).count() == 1


@pytest.mark.django_db
class TestSolicitacaoPelaAPI:
    """
    Mesmas regras pela API JWT, mais a proteção contra o cliente
    escolher o próprio status ou o dono do pedido (mass assignment).
    """

    URL_SOLICITAR = "/api/emprestimos/solicitar/"
    URL_MEUS = "/api/emprestimos/meus/"

    def _cabecalho(self, usuario):
        token = str(RefreshToken.for_user(usuario).access_token)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def _solicitar(self, autor, **dados):
        return Client().post(
            self.URL_SOLICITAR,
            dados,
            content_type="application/json",
            **self._cabecalho(autor),
        )

    def test_cria_solicitacao(self, aluno, equipamento):
        resposta = self._solicitar(aluno, equipamento=equipamento.id)

        assert resposta.status_code == 201
        assert Emprestimo.objects.get(usuario=aluno).status == "SOLICITADO"

    def test_cliente_nao_consegue_escolher_status_nem_dono(
        self, aluno, outro_aluno, equipamento
    ):
        resposta = self._solicitar(
            aluno,
            equipamento=equipamento.id,
            status="APROVADO",
            usuario=outro_aluno.id,
        )

        assert resposta.status_code == 201
        emprestimo = Emprestimo.objects.get()
        assert emprestimo.status == "SOLICITADO"
        assert emprestimo.usuario == aluno
        equipamento.refresh_from_db()
        assert equipamento.status == "DISPONIVEL"

    def test_sem_token_e_recusado(self, equipamento):
        resposta = Client().post(
            self.URL_SOLICITAR,
            {"equipamento": equipamento.id},
            content_type="application/json",
        )

        assert resposta.status_code == 401
        assert Emprestimo.objects.count() == 0

    def test_equipamento_indisponivel_e_recusado(self, aluno, equipamento):
        equipamento.status = "MANUTENCAO"
        equipamento.save()

        resposta = self._solicitar(aluno, equipamento=equipamento.id)

        assert resposta.status_code == 400
        assert Emprestimo.objects.count() == 0

    def test_segunda_solicitacao_em_aberto_e_recusada(self, aluno, equipamento):
        # Se este teste falhar (segunda resposta 201), a validação de
        # pedido duplicado não foi aplicada ao serializer, só à view.
        primeira = self._solicitar(aluno, equipamento=equipamento.id)
        segunda = self._solicitar(aluno, equipamento=equipamento.id)

        assert primeira.status_code == 201
        assert segunda.status_code == 400
        assert Emprestimo.objects.count() == 1

    def test_solicitacao_notifica_o_administrador(
        self, aluno, administrador, equipamento
    ):
        self._solicitar(aluno, equipamento=equipamento.id)

        assert Notificacao.objects.filter(usuario=administrador).count() == 1

    def test_meus_emprestimos_lista_so_os_do_proprio_usuario(
        self, aluno, outro_aluno, equipamento
    ):
        meu = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)
        Emprestimo.objects.create(usuario=outro_aluno, equipamento=equipamento)

        resposta = Client().get(self.URL_MEUS, **self._cabecalho(aluno))

        assert resposta.status_code == 200
        assert [item["id"] for item in resposta.json()] == [meu.id]

def _executar_acao(cliente, acao, *emprestimos):
    """
    Simula o administrador marcando empréstimos na lista do /admin/ e
    escolhendo uma ação no menu (aprovar, rejeitar, devolver...).
    O campo "index" faz parte do formulário de ações do Django.
    """
    return cliente.post(
        reverse("admin:emprestimos_emprestimo_changelist"),
        {
            "action": acao,
            "_selected_action": [e.id for e in emprestimos],
            "index": 0,
        },
    )


def _emprestimo_aprovado(usuario, equipamento, dias_para_vencer=7, **extra):
    """Empréstimo já aprovado e em andamento (dias_para_vencer < 0 = atrasado)."""
    equipamento.status = "EMPRESTADO"
    equipamento.save()
    agora = timezone.now()
    return Emprestimo.objects.create(
        usuario=usuario,
        equipamento=equipamento,
        status="APROVADO",
        data_retirada=agora,
        data_devolucao_prevista=agora + timedelta(days=dias_para_vencer),
        **extra,
    )


@pytest.mark.django_db
class TestAprovacao:
    def test_aprovar_define_status_prazo_e_marca_equipamento(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "aprovar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()
        equipamento.refresh_from_db()

        assert emprestimo.status == "APROVADO"
        assert emprestimo.data_retirada is not None
        prazo = emprestimo.data_devolucao_prevista - emprestimo.data_retirada
        assert prazo == timedelta(days=settings.PRAZO_PADRAO_EMPRESTIMO_DIAS)
        assert equipamento.status == "EMPRESTADO"

    def test_aprovar_notifica_o_aluno_e_registra_auditoria(
        self, cliente_admin, administrador, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "aprovar_emprestimos", emprestimo)

        assert "aprovado" in Notificacao.objects.get(usuario=aluno).mensagem
        assert RegistroAuditoria.objects.filter(
            usuario=administrador, acao="UPDATE", modulo_afetado="Empréstimos"
        ).exists()

    def test_aprovar_ignora_equipamento_indisponivel(
        self, cliente_admin, aluno, equipamento
    ):
        equipamento.status = "MANUTENCAO"
        equipamento.save()
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "aprovar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.status == "SOLICITADO"
        assert emprestimo.data_devolucao_prevista is None

    def test_aprovar_so_afeta_pedidos_solicitados(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(
            usuario=aluno, equipamento=equipamento, status="REJEITADO"
        )

        _executar_acao(cliente_admin, "aprovar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()
        equipamento.refresh_from_db()

        assert emprestimo.status == "REJEITADO"
        assert equipamento.status == "DISPONIVEL"

    def test_dois_pedidos_do_mesmo_equipamento_so_um_e_aprovado(
        self, cliente_admin, aluno, outro_aluno, equipamento
    ):
        """
        Dois alunos pedem o mesmo tablet e o admin aprova os dois de uma
        vez. Só um equipamento existe, então só um pedido pode ser aprovado.
        """
        primeiro = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)
        segundo = Emprestimo.objects.create(usuario=outro_aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "aprovar_emprestimos", primeiro, segundo)

        assert Emprestimo.objects.filter(status="APROVADO").count() == 1
        assert Emprestimo.objects.filter(status="SOLICITADO").count() == 1

    def test_aluno_nao_consegue_executar_acao_do_admin(
        self, cliente_aluno, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        resposta = _executar_acao(cliente_aluno, "aprovar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()

        assert resposta.status_code == 302
        assert "/admin/login/" in resposta.url
        assert emprestimo.status == "SOLICITADO"


@pytest.mark.django_db
class TestRejeicao:
    def test_rejeitar_muda_status_notifica_e_nao_mexe_no_equipamento(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "rejeitar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()
        equipamento.refresh_from_db()

        assert emprestimo.status == "REJEITADO"
        assert equipamento.status == "DISPONIVEL"
        assert "rejeitado" in Notificacao.objects.get(usuario=aluno).mensagem

    def test_rejeitar_nao_afeta_emprestimo_ja_aprovado(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = _emprestimo_aprovado(aluno, equipamento)

        _executar_acao(cliente_admin, "rejeitar_emprestimos", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.status == "APROVADO"


@pytest.mark.django_db
class TestDevolucao:
    def test_devolver_libera_o_equipamento_e_registra_a_data(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, prorrogacao_solicitada=True)

        _executar_acao(cliente_admin, "marcar_devolvido", emprestimo)
        emprestimo.refresh_from_db()
        equipamento.refresh_from_db()

        assert emprestimo.status == "DEVOLVIDO"
        assert emprestimo.data_devolucao_real is not None
        assert emprestimo.prorrogacao_solicitada is False
        assert equipamento.status == "DISPONIVEL"
        assert "devolução" in Notificacao.objects.get(usuario=aluno).mensagem

    def test_devolver_nao_afeta_pedido_que_nao_foi_aprovado(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        _executar_acao(cliente_admin, "marcar_devolvido", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.status == "SOLICITADO"
        assert emprestimo.data_devolucao_real is None


@pytest.mark.django_db
class TestPedidoDeProrrogacao:
    def _pedir(self, cliente, emprestimo):
        return cliente.post(reverse("solicitar_prorrogacao_web", args=[emprestimo.id]))

    def test_aluno_solicita_prorrogacao(
        self, cliente_aluno, aluno, administrador, equipamento
    ):
        emprestimo = _emprestimo_aprovado(aluno, equipamento)

        self._pedir(cliente_aluno, emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.prorrogacao_solicitada is True
        assert Notificacao.objects.filter(usuario=administrador).count() == 1
        assert RegistroAuditoria.objects.filter(usuario=aluno, acao="UPDATE").exists()

    def test_so_emprestimo_aprovado_pode_ser_prorrogado(
        self, cliente_aluno, aluno, administrador, equipamento
    ):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        self._pedir(cliente_aluno, emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.prorrogacao_solicitada is False
        assert Notificacao.objects.count() == 0

    def test_pedido_repetido_nao_avisa_o_admin_de_novo(
        self, cliente_aluno, aluno, administrador, equipamento
    ):
        emprestimo = _emprestimo_aprovado(aluno, equipamento)

        self._pedir(cliente_aluno, emprestimo)
        self._pedir(cliente_aluno, emprestimo)

        assert Notificacao.objects.filter(usuario=administrador).count() == 1

    def test_aluno_nao_pede_prorrogacao_do_emprestimo_de_outro(
        self, cliente_aluno, outro_aluno, equipamento
    ):
        emprestimo = _emprestimo_aprovado(outro_aluno, equipamento)

        resposta = self._pedir(cliente_aluno, emprestimo)
        emprestimo.refresh_from_db()

        assert resposta.status_code == 404
        assert emprestimo.prorrogacao_solicitada is False


@pytest.mark.django_db
class TestDecisaoDeProrrogacao:
    def test_admin_aprova_e_o_prazo_aumenta(self, cliente_admin, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, prorrogacao_solicitada=True)
        prazo_antes = emprestimo.data_devolucao_prevista

        _executar_acao(cliente_admin, "aprovar_prorrogacao", emprestimo)
        emprestimo.refresh_from_db()

        extensao = emprestimo.data_devolucao_prevista - prazo_antes
        assert extensao == timedelta(days=settings.PRAZO_PADRAO_EMPRESTIMO_DIAS)
        assert emprestimo.prorrogacao_solicitada is False
        assert "aprovada" in Notificacao.objects.get(usuario=aluno).mensagem

    def test_admin_rejeita_e_o_prazo_continua(self, cliente_admin, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, prorrogacao_solicitada=True)
        prazo_antes = emprestimo.data_devolucao_prevista

        _executar_acao(cliente_admin, "rejeitar_prorrogacao", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.data_devolucao_prevista == prazo_antes
        assert emprestimo.prorrogacao_solicitada is False
        assert "rejeitado" in Notificacao.objects.get(usuario=aluno).mensagem

    def test_aprovar_prorrogacao_sem_pedido_nao_altera_o_prazo(
        self, cliente_admin, aluno, equipamento
    ):
        emprestimo = _emprestimo_aprovado(aluno, equipamento)
        prazo_antes = emprestimo.data_devolucao_prevista

        _executar_acao(cliente_admin, "aprovar_prorrogacao", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.data_devolucao_prevista == prazo_antes


@pytest.mark.django_db
class TestAtraso:
    """
    Regra: atrasado = aprovado, não devolvido e com o prazo vencido.
    É calculado na hora da consulta, não gravado no banco.
    """

    def test_emprestimo_vencido_esta_atrasado(self, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, dias_para_vencer=-1)

        assert emprestimo.esta_atrasado() is True

    def test_emprestimo_no_prazo_nao_esta_atrasado(self, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, dias_para_vencer=3)

        assert emprestimo.esta_atrasado() is False

    def test_pedido_sem_prazo_nao_esta_atrasado(self, aluno, equipamento):
        emprestimo = Emprestimo.objects.create(usuario=aluno, equipamento=equipamento)

        assert emprestimo.esta_atrasado() is False

    def test_emprestimo_devolvido_nao_esta_atrasado(self, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento, dias_para_vencer=-1)
        emprestimo.status = "DEVOLVIDO"
        emprestimo.data_devolucao_real = timezone.now()
        emprestimo.save()

        assert emprestimo.esta_atrasado() is False

    def test_prorrogacao_aprovada_tira_o_atraso(self, cliente_admin, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(
            aluno, equipamento, dias_para_vencer=-1, prorrogacao_solicitada=True
        )
        assert emprestimo.esta_atrasado() is True

        _executar_acao(cliente_admin, "aprovar_prorrogacao", emprestimo)
        emprestimo.refresh_from_db()

        assert emprestimo.esta_atrasado() is False

    def test_tela_so_marca_atrasado_quando_vencido(self, cliente_aluno, aluno, equipamento):
        emprestimo = _emprestimo_aprovado(aluno, equipamento)
        url = reverse("meus_emprestimos_web")

        assert b'class="tag-atraso"' not in cliente_aluno.get(url).content

        emprestimo.data_devolucao_prevista = timezone.now() - timedelta(days=1)
        emprestimo.save()

        assert b'class="tag-atraso"' in cliente_aluno.get(url).content        