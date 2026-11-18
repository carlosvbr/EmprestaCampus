"""
Eliminação, anonimização e retenção de dados pessoais (LGPD, arts. 15 e 16).

A rotina de retenção recebe a data "de agora" como parâmetro, então os
testes simulam a passagem do tempo sem precisar envelhecer os registros.
A exceção é a auditoria: o trigger usa o relógio do PostgreSQL, por isso
os registros antigos são inseridos direto com a data no passado.
"""

import io
from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import Client
from django.utils import timezone

from auditoria.models import RegistroAuditoria
from emprestimos.models import Emprestimo
from notificacoes.models import Notificacao
from usuarios.models import DispositivoTOTP, Finalidade, TokenRecuperacaoSenha, Usuario
from usuarios.retencao import PRAZOS, STATUS_EM_ABERTO, aplicar_retencao

URL_ENCERRAR = "/api/usuarios/perfil/encerrar-conta/"
URL_REVOGAR = "/api/usuarios/perfil/revogar-consentimento/"
BACKEND_SESSAO = "django.contrib.auth.backends.ModelBackend"
TELEFONE = "(00) 00000-0000"  # fictício: DDD 00 não existe
UM_DIA = timedelta(days=1)


def logado(usuario):
    client = Client()
    client.force_login(usuario, backend=BACKEND_SESSAO)
    return client


def auditoria_com_data(data_hora):
    """Insere um registro de auditoria com a data informada e devolve o id."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO auditoria_registroauditoria "
            "(acao, modulo_afetado, descricao, ip_origem, data_hora) "
            "VALUES ('UPDATE', 'Teste', 'registro de teste', '10.0.0.1', %s) RETURNING id",
            [data_hora],
        )
        return cursor.fetchone()[0]


@pytest.fixture
def titular(db):
    usuario = Usuario.objects.create_user(
        username="titular", email="titular@exemplo.com", first_name="Maria",
        last_name="Silva", matricula="2026555", consentimento_dados=True,
    )
    usuario.definir_consentimento(Finalidade.CONTATO_TELEFONE, True)
    usuario.telefone = TELEFONE
    usuario.save()
    return usuario


@pytest.mark.django_db
class TestEncerramentoDaConta:

    def test_elimina_todos_os_vinculos_do_titular(self, titular, equipamento):
        DispositivoTOTP.objects.create(user=titular, name="padrao", confirmed=True)
        TokenRecuperacaoSenha.objects.create(usuario=titular)
        Notificacao.objects.create(usuario=titular, mensagem="Olá, Maria")
        emprestimo = Emprestimo.objects.create(
            usuario=titular, equipamento=equipamento, status="DEVOLVIDO",
            observacoes="Falar com a Maria no ramal 1234",
        )
        AccessAttempt.objects.create(
            username="titular", ip_address="10.0.0.1", user_agent="x",
            http_accept="x", path_info="/", get_data="", post_data="", failures_since_start=1,
        )

        logado(titular).post(URL_ENCERRAR)
        titular.refresh_from_db()

        assert titular.username == f"anon_{titular.pk}"
        assert titular.first_name == "Usuário" and titular.last_name == "Anonimizado"
        assert titular.matricula == f"anon_{titular.pk}"
        assert titular.email.endswith("@emprestacampus.local")
        assert titular.telefone is None and titular.last_login is None
        assert not titular.is_active and not titular.has_usable_password()

        assert not DispositivoTOTP.objects.filter(user=titular).exists()
        assert not TokenRecuperacaoSenha.objects.filter(usuario=titular).exists()
        assert not Notificacao.objects.filter(usuario=titular).exists()
        assert not AccessAttempt.objects.filter(username="titular").exists()

        emprestimo.refresh_from_db()
        assert emprestimo.observacoes is None
        assert emprestimo.usuario_id == titular.pk  # histórico patrimonial fica, mas anônimo

    def test_mantem_o_historico_de_consentimento_como_prova(self, titular):
        logado(titular).post(URL_ENCERRAR)
        assert titular.consentimentos.exists()

    def test_encerra_as_sessoes_em_outros_navegadores(self, titular):
        celular = logado(titular)
        computador = logado(titular)

        computador.post(URL_ENCERRAR)

        assert celular.get("/api/usuarios/perfil/").status_code == 302
        sessoes = [s.get_decoded().get("_auth_user_id") for s in Session.objects.all()]
        assert str(titular.pk) not in sessoes

    @pytest.mark.parametrize("status", STATUS_EM_ABERTO)
    def test_bloqueia_com_emprestimo_em_aberto(self, titular, equipamento, status):
        Emprestimo.objects.create(usuario=titular, equipamento=equipamento, status=status)

        resposta = logado(titular).post(URL_ENCERRAR)
        titular.refresh_from_db()

        assert resposta.status_code == 302 and resposta.url.endswith("/perfil/")
        assert titular.username == "titular" and titular.is_active

    def test_encerramento_fica_na_auditoria(self, titular):
        logado(titular).post(URL_ENCERRAR)
        assert RegistroAuditoria.objects.filter(usuario=titular, acao="DELETE").exists()


@pytest.mark.django_db
class TestRotinaDeRetencao:

    def test_token_de_recuperacao_some_7_dias_depois_de_expirar(self, titular):
        token = TokenRecuperacaoSenha.objects.create(usuario=titular)
        prazo = token.expira_em + PRAZOS["token_recuperacao_apos_expirar"]

        aplicar_retencao(agora=prazo - UM_DIA)
        assert TokenRecuperacaoSenha.objects.filter(pk=token.pk).exists()

        aplicar_retencao(agora=prazo + UM_DIA)
        assert not TokenRecuperacaoSenha.objects.filter(pk=token.pk).exists()

    def test_notificacao_some_depois_de_90_dias(self, titular):
        aviso = Notificacao.objects.create(usuario=titular, mensagem="aviso")
        prazo = aviso.data_criacao + PRAZOS["notificacoes"]

        aplicar_retencao(agora=prazo - UM_DIA)
        assert Notificacao.objects.filter(pk=aviso.pk).exists()

        aplicar_retencao(agora=prazo + UM_DIA)
        assert not Notificacao.objects.filter(pk=aviso.pk).exists()

    def test_tentativa_de_login_some_depois_de_30_dias(self, db):
        tentativa = AccessAttempt.objects.create(
            username="alguem", ip_address="10.0.0.1", user_agent="x",
            http_accept="x", path_info="/", get_data="", post_data="", failures_since_start=1,
        )
        prazo = tentativa.attempt_time + PRAZOS["tentativas_de_login"]

        aplicar_retencao(agora=prazo - UM_DIA)
        assert AccessAttempt.objects.filter(pk=tentativa.pk).exists()

        aplicar_retencao(agora=prazo + UM_DIA)
        assert not AccessAttempt.objects.filter(pk=tentativa.pk).exists()

    def test_sessoes_expiradas_sao_apagadas(self, titular):
        logado(titular)
        assert Session.objects.exists()
        aplicar_retencao(agora=timezone.now() + timedelta(days=30))
        assert not Session.objects.exists()

    def test_conta_suspensa_e_anonimizada_depois_de_12_meses(self, titular):
        logado(titular).post(URL_REVOGAR)
        titular.refresh_from_db()
        assert titular.consentimento_revogado_em is not None
        prazo = titular.consentimento_revogado_em + PRAZOS["conta_suspensa"]

        aplicar_retencao(agora=prazo - UM_DIA)
        titular.refresh_from_db()
        assert titular.username == "titular"

        aplicar_retencao(agora=prazo + UM_DIA)
        titular.refresh_from_db()
        assert titular.username == f"anon_{titular.pk}"
        assert titular.consentimento_revogado_em is None

    def test_conta_suspensa_com_equipamento_nao_e_anonimizada(self, titular, equipamento):
        Emprestimo.objects.create(usuario=titular, equipamento=equipamento, status="RETIRADO")
        logado(titular).post(URL_REVOGAR)
        titular.refresh_from_db()

        aplicar_retencao(agora=titular.consentimento_revogado_em + PRAZOS["conta_suspensa"] + UM_DIA)
        titular.refresh_from_db()
        assert titular.username == "titular"

    def test_conta_desativada_pelo_admin_nao_entra_na_rotina(self, titular):
        Usuario.objects.filter(pk=titular.pk).update(is_active=False)
        aplicar_retencao(agora=timezone.now() + timedelta(days=10 * 365))
        titular.refresh_from_db()
        assert titular.username == "titular"

    def test_emprestimo_devolvido_some_depois_de_5_anos(self, titular, equipamento):
        devolvido = Emprestimo.objects.create(
            usuario=titular, equipamento=equipamento, status="DEVOLVIDO",
            data_devolucao_real=timezone.now(),
        )
        prazo = devolvido.data_devolucao_real + PRAZOS["emprestimos_encerrados"]

        aplicar_retencao(agora=prazo - UM_DIA)
        assert Emprestimo.objects.filter(pk=devolvido.pk).exists()

        aplicar_retencao(agora=prazo + UM_DIA)
        assert not Emprestimo.objects.filter(pk=devolvido.pk).exists()

    def test_emprestimo_em_aberto_nunca_e_apagado(self, titular, equipamento):
        aberto = Emprestimo.objects.create(usuario=titular, equipamento=equipamento, status="ATRASADO")
        aplicar_retencao(agora=timezone.now() + timedelta(days=20 * 365))
        assert Emprestimo.objects.filter(pk=aberto.pk).exists()

    def test_auditoria_com_mais_de_5_anos_e_eliminada(self, db):
        limite = timezone.now() - PRAZOS["auditoria"]
        antigo = auditoria_com_data(limite - UM_DIA)
        recente = auditoria_com_data(limite + UM_DIA)

        resultado = aplicar_retencao()

        assert resultado["auditoria"] == 1
        assert not RegistroAuditoria.objects.filter(pk=antigo).exists()
        assert RegistroAuditoria.objects.filter(pk=recente).exists()

    def test_comando_agendavel_executa_a_rotina(self, db):
        saida = io.StringIO()
        call_command("aplicar_retencao", stdout=saida)
        assert "Retenção aplicada." in saida.getvalue()


@pytest.mark.django_db
class TestTriggerDaAuditoriaComRetencao:
    """A retenção não abre brecha na imutabilidade da auditoria."""

    def test_registro_dentro_do_prazo_continua_sem_poder_ser_apagado(self, db):
        recente = auditoria_com_data(timezone.now() - timedelta(days=4 * 365))
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM auditoria_registroauditoria WHERE id = %s", [recente])
        assert RegistroAuditoria.objects.filter(pk=recente).exists()

    def test_nao_da_para_envelhecer_um_registro_para_apaga_lo(self, db):
        recente = auditoria_com_data(timezone.now())
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE auditoria_registroauditoria SET data_hora = %s WHERE id = %s",
                [timezone.now() - timedelta(days=10 * 365), recente],
            )

    def test_registro_antigo_continua_sem_poder_ser_alterado(self, db):
        antigo = auditoria_com_data(timezone.now() - timedelta(days=6 * 365))
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE auditoria_registroauditoria SET descricao = 'adulterado' WHERE id = %s",
                [antigo],
            )
