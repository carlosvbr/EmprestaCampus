"""
Consentimento associado à finalidade (LGPD).

Cada finalidade opcional tem aceite próprio, independente das outras, com
histórico de data e versão. A escolha tem efeito real: sem consentimento,
o dado não é guardado e o aviso não é enviado.
"""

import importlib

import pytest
from django.apps import apps
from django.conf import settings
from django.core import mail
from django.test import Client

from auditoria.models import RegistroAuditoria
from notificacoes.models import Notificacao
from notificacoes.utils import notificar
from usuarios.lgpd import FINALIDADES
from usuarios.models import ConsentimentoFinalidade, Finalidade, Usuario

URL_REGISTRO = "/api/usuarios/registro/"
URL_CONSENTIMENTOS = "/api/usuarios/perfil/consentimentos/"
TELEFONE = "(00) 00000-0000"  # fictício: DDD 00 não existe
BACKEND_SESSAO = "django.contrib.auth.backends.ModelBackend"


def cadastrar(**extra):
    dados = {
        "username": "titular", "first_name": "Titular", "last_name": "Teste",
        "email": "titular@exemplo.com", "password": "Emp!Campus#2026x",
        "matricula": "2026777", "consentimento_dados": True,
    }
    dados.update(extra)
    return Client().post(URL_REGISTRO, dados, content_type="application/json")


@pytest.fixture
def titular(db):
    usuario = Usuario.objects.create_user(
        username="titular", email="titular@exemplo.com", consentimento_dados=True
    )
    usuario.definir_consentimento(Finalidade.CONTATO_TELEFONE, False)
    usuario.definir_consentimento(Finalidade.AVISOS_EMAIL, False)
    return usuario


def cliente_logado(usuario):
    client = Client()
    client.force_login(usuario, backend=BACKEND_SESSAO)
    return client


class TestFinalidadesOpcionais:

    def test_finalidades_opcionais_estao_no_mapeamento_com_base_no_consentimento(self):
        for finalidade in Finalidade.values:
            assert finalidade in FINALIDADES
            assert FINALIDADES[finalidade]["base_legal"].startswith("Consentimento")


@pytest.mark.django_db
class TestConsentimentoNoCadastro:

    def test_cadastro_sem_marcar_nada_registra_as_duas_recusas(self):
        assert cadastrar().status_code == 201
        usuario = Usuario.objects.get(username="titular")

        historico = {c.finalidade: c for c in usuario.consentimentos.all()}
        assert set(historico) == set(Finalidade.values)
        assert not any(c.aceito for c in historico.values())
        assert all(c.versao_politica == settings.VERSAO_POLITICA_PRIVACIDADE for c in historico.values())

    def test_cada_finalidade_e_escolhida_separadamente(self):
        cadastrar(consentimento_avisos_email=True)
        usuario = Usuario.objects.get(username="titular")
        assert usuario.consentiu(Finalidade.AVISOS_EMAIL)
        assert not usuario.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_telefone_sem_autorizacao_e_recusado(self):
        resposta = cadastrar(telefone=TELEFONE)
        assert resposta.status_code == 400
        assert "telefone" in resposta.json()
        assert not Usuario.objects.filter(username="titular").exists()

    def test_telefone_com_autorizacao_e_guardado(self):
        assert cadastrar(telefone=TELEFONE, consentimento_telefone=True).status_code == 201
        usuario = Usuario.objects.get(username="titular")
        assert usuario.telefone == TELEFONE
        assert usuario.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_aceite_da_politica_continua_obrigatorio(self):
        assert cadastrar(consentimento_dados=False).status_code == 400


@pytest.mark.django_db
class TestConsentimentoNoPerfil:

    def test_perfil_mostra_uma_opcao_para_cada_finalidade(self, titular):
        html = cliente_logado(titular).get("/api/usuarios/perfil/").content.decode()
        assert 'name="consentimento_telefone"' in html
        assert 'name="consentimento_avisos_email"' in html

    def test_autorizar_uma_finalidade_nao_muda_a_outra(self, titular):
        cliente_logado(titular).post(URL_CONSENTIMENTOS, {"consentimento_avisos_email": "on"})
        assert titular.consentiu(Finalidade.AVISOS_EMAIL)
        assert not titular.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_autorizar_telefone_exige_o_numero(self, titular):
        cliente_logado(titular).post(URL_CONSENTIMENTOS, {"consentimento_telefone": "on"})
        assert not titular.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_autorizar_telefone_guarda_o_numero(self, titular):
        cliente_logado(titular).post(
            URL_CONSENTIMENTOS, {"consentimento_telefone": "on", "telefone": TELEFONE}
        )
        titular.refresh_from_db()
        assert titular.telefone == TELEFONE
        assert titular.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_retirar_autorizacao_do_telefone_apaga_o_numero(self, titular):
        client = cliente_logado(titular)
        client.post(URL_CONSENTIMENTOS, {"consentimento_telefone": "on", "telefone": TELEFONE})
        client.post(URL_CONSENTIMENTOS, {})

        titular.refresh_from_db()
        assert titular.telefone is None
        assert not titular.consentiu(Finalidade.CONTATO_TELEFONE)

    def test_retirar_autorizacao_nao_bloqueia_o_acesso(self, titular):
        client = cliente_logado(titular)
        client.post(URL_CONSENTIMENTOS, {"consentimento_avisos_email": "on"})
        client.post(URL_CONSENTIMENTOS, {})

        titular.refresh_from_db()
        assert titular.is_active
        assert client.get("/api/usuarios/perfil/").status_code == 200

    def test_cada_mudanca_fica_no_historico_e_na_auditoria(self, titular):
        client = cliente_logado(titular)
        client.post(URL_CONSENTIMENTOS, {"consentimento_avisos_email": "on"})
        client.post(URL_CONSENTIMENTOS, {})

        avisos = titular.consentimentos.filter(finalidade=Finalidade.AVISOS_EMAIL)
        assert [c.aceito for c in avisos] == [False, True, False]  # mais recente primeiro
        assert RegistroAuditoria.objects.filter(
            usuario=titular, modulo_afetado="Privacidade/LGPD", descricao__contains="avisos por e-mail"
        ).count() == 2

    def test_historico_nao_pode_ser_alterado(self, titular):
        registro = titular.consentimentos.first()
        registro.aceito = True
        with pytest.raises(ValueError):
            registro.save()

    def test_exportacao_inclui_o_historico(self, titular):
        dados = cliente_logado(titular).get("/api/usuarios/perfil/exportar/").json()
        finalidades = {c["finalidade"] for c in dados["consentimentos_por_finalidade"]}
        assert finalidades == {rotulo for _, rotulo in Finalidade.choices}


@pytest.mark.django_db
class TestEfeitoDoConsentimento:

    def test_sem_consentimento_o_aviso_de_emprestimo_nao_e_enviado(self, titular):
        notificar(titular, "Seu empréstimo foi aprovado.", finalidade=Finalidade.AVISOS_EMAIL)
        assert len(mail.outbox) == 0
        assert not Notificacao.objects.filter(usuario=titular).exists()

    def test_com_consentimento_o_aviso_de_emprestimo_e_enviado(self, titular):
        titular.definir_consentimento(Finalidade.AVISOS_EMAIL, True)
        notificar(titular, "Seu empréstimo foi aprovado.", finalidade=Finalidade.AVISOS_EMAIL)
        assert len(mail.outbox) == 1

    def test_aviso_de_seguranca_nao_depende_de_consentimento(self, titular):
        notificar(titular, "A autenticação de dois fatores foi desativada.")
        assert len(mail.outbox) == 1


@pytest.mark.django_db
class TestMigracaoDosUsuariosExistentes:

    def test_mantem_o_que_cada_usuario_ja_recebia(self):
        com_telefone = Usuario.objects.create_user(
            username="com_tel", consentimento_dados=True, telefone=TELEFONE
        )
        sem_telefone = Usuario.objects.create_user(username="sem_tel", consentimento_dados=True)
        revogado = Usuario.objects.create_user(username="revogado", consentimento_dados=False)

        migracao = importlib.import_module("usuarios.migrations.0013_consentimentos_existentes")
        migracao.registrar(apps, None)

        assert com_telefone.consentiu(Finalidade.AVISOS_EMAIL)
        assert com_telefone.consentiu(Finalidade.CONTATO_TELEFONE)
        assert sem_telefone.consentiu(Finalidade.AVISOS_EMAIL)
        assert not sem_telefone.consentiu(Finalidade.CONTATO_TELEFONE)
        assert not ConsentimentoFinalidade.objects.filter(usuario=revogado).exists()
        assert set(ConsentimentoFinalidade.objects.values_list("versao_politica", flat=True)) == {"v1.0"}