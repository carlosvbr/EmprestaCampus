import pytest
from axes.models import AccessAttempt, AccessLog
from django.apps import apps
from django.conf import settings
from django.test import Client

from auditoria.models import RegistroAuditoria
from usuarios.lgpd import CAMPOS_TECNICOS, FINALIDADES, MAPEAMENTO
from usuarios.models import Usuario

URL_REGISTRO = "/api/usuarios/registro/"
URL_LOGIN_WEB = "/api/usuarios/entrar/"
APPS_DO_PROJETO = ("usuarios", "emprestimos", "notificacoes", "auditoria", "inventario")


def campos_do_modelo(rotulo):
    modelo = apps.get_model(rotulo)
    return {f.name for f in modelo._meta.concrete_fields if not f.primary_key}


def dados_cadastro(**extra):
    dados = {
        "username": "titular_lgpd",
        "first_name": "Titular",
        "last_name": "Teste",
        "email": "titular@exemplo.com",
        "password": "Emp!Campus#2026x",
        "matricula": "2026999",
        "consentimento_dados": True,
    }
    dados.update(extra)
    return dados


class TestMapeamentoDosDados:

    @pytest.mark.parametrize("rotulo", sorted(set(MAPEAMENTO) | set(CAMPOS_TECNICOS)))
    def test_todo_campo_esta_mapeado(self, rotulo):
        mapeados = set(MAPEAMENTO.get(rotulo, {}))
        tecnicos = CAMPOS_TECNICOS.get(rotulo, set())

        assert not mapeados & tecnicos, "campo classificado duas vezes"
        assert mapeados | tecnicos == campos_do_modelo(rotulo)

    def test_todo_modelo_ligado_a_um_usuario_esta_mapeado(self):
        """Um modelo novo com dado de usuário não passa sem entrar no mapeamento."""
        for modelo in apps.get_models():
            if modelo._meta.app_label not in APPS_DO_PROJETO:
                continue
            ligado = any(
                f.is_relation and f.related_model is Usuario
                for f in modelo._meta.concrete_fields
            )
            rotulo = modelo._meta.label
            if ligado or rotulo == "usuarios.Usuario":
                assert rotulo in MAPEAMENTO, f"{rotulo} guarda dado de usuário e não está mapeado"

    def test_toda_finalidade_usada_existe_e_tem_base_legal(self):
        usadas = {f for campos in MAPEAMENTO.values() for f in campos.values()}
        assert usadas == set(FINALIDADES)
        for finalidade in FINALIDADES.values():
            assert "art. 7º" in finalidade["base_legal"]
            assert finalidade["descricao"]


@pytest.mark.django_db
class TestMinimizacao:

    def test_cadastro_funciona_sem_telefone(self):
        resposta = Client().post(URL_REGISTRO, dados_cadastro(), content_type="application/json")
        assert resposta.status_code == 201
        assert Usuario.objects.get(username="titular_lgpd").telefone is None

    def test_formulario_de_cadastro_nao_exige_telefone(self):
        html = Client().get("/api/usuarios/cadastrar/").content.decode()
        campo = html[html.index('id="telefone"'):]
        assert "required" not in campo[:campo.index(">")]

    def test_cadastro_descarta_dados_nao_previstos(self):
        extras = {"cpf": "000.000.000-00", "endereco": "Rua X", "data_nascimento": "2000-01-01",
                  "is_staff": True, "is_superuser": True}
        resposta = Client().post(URL_REGISTRO, dados_cadastro(**extras), content_type="application/json")
        assert resposta.status_code == 201

        corpo = resposta.json()
        assert not set(extras) & set(corpo)
        assert "password" not in corpo

        usuario = Usuario.objects.get(username="titular_lgpd")
        assert not usuario.is_staff and not usuario.is_superuser

    def test_login_nao_grava_copia_no_axes(self):
        Usuario.objects.create_user(username="titular", password="Emp!Campus#2026x", consentimento_dados=True)
        Client().post(URL_LOGIN_WEB, {"username": "titular", "password": "Emp!Campus#2026x"})

        assert settings.AXES_DISABLE_ACCESS_LOG is True
        assert not AccessLog.objects.exists()
        assert RegistroAuditoria.objects.filter(acao="LOGIN_SUCESSO").exists()

    def test_tentativa_errada_continua_registrada_para_o_bloqueio(self):
        Usuario.objects.create_user(username="titular", password="Emp!Campus#2026x", consentimento_dados=True)
        Client().post(URL_LOGIN_WEB, {"username": "titular", "password": "errada"})

        tentativa = AccessAttempt.objects.get(username="titular")
        assert "errada" not in tentativa.post_data  # a senha digitada não é guardada
