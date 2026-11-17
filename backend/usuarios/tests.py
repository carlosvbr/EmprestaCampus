import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection
from django.test import Client
from django.urls import get_resolver
from django.utils import timezone
from django_otp.oath import TOTP
from usuarios.models import DispositivoTOTP, TokenRecuperacaoSenha, Usuario
from rest_framework_simplejwt.views import TokenObtainPairView, TokenObtainSlidingView

from auditoria.models import RegistroAuditoria
from usuarios.models import TokenRecuperacaoSenha, Usuario

URL_LOGIN_SPA = "/api/usuarios/login/spa/"
URL_LOGIN_SPA_2FA = "/api/usuarios/login/spa/2fa/"
URL_RENOVAR = "/api/usuarios/login/renovar/"
URL_LOGIN_WEB = "/api/usuarios/entrar/"
URL_2FA_WEB = "/api/usuarios/2fa/validar/"
URL_RECUPERAR = "/api/usuarios/recuperar-senha/"
URL_REDEFINIR = "/api/usuarios/redefinir-senha/"
SENHA = "Emp!Campus#2026x"


def codigo_atual(device):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time()
    return f"{totp.token():06d}"


@pytest.fixture
def usuario_2fa(db):
    usuario = Usuario.objects.create_user(
        username="aval_2fa", password=SENHA, email="aval2fa@exemplo.com", consentimento_dados=True
    )
    device = DispositivoTOTP.objects.create(user=usuario, name="padrao", confirmed=True)
    return usuario, device


def token_2fa(client):
    resposta = client.post(URL_LOGIN_SPA, {"username": "aval_2fa", "password": SENHA},
                           content_type="application/json")
    assert resposta.status_code == 200
    return resposta.json()["token_2fa"]


@pytest.mark.django_db
class TestNenhumaRotaContornaO2FA:

    def test_nenhuma_rota_expoe_emissao_direta_de_jwt(self):
        """Não existe TokenObtainPairView/SlidingView em nenhuma URL do projeto."""
        proibidas = (TokenObtainPairView, TokenObtainSlidingView)

        def views(resolver):
            for p in resolver.url_patterns:
                if hasattr(p, "url_patterns"):
                    yield from views(p)
                else:
                    yield getattr(p.callback, "view_class", None)

        assert not [v for v in views(get_resolver()) if v and issubclass(v, proibidas)]

    def test_renovacao_nao_emite_jwt_sem_refresh_valido(self, usuario_2fa):
        resposta = Client().post(URL_RENOVAR, {"refresh": "invalido"}, content_type="application/json")
        assert resposta.status_code == 401
        assert "access" not in resposta.json()

    def test_senha_correta_sozinha_nao_gera_jwt_nem_sessao(self, usuario_2fa):
        client = Client()
        corpo = client.post(URL_LOGIN_SPA, {"username": "aval_2fa", "password": SENHA},
                            content_type="application/json").json()
        assert corpo["requer_2fa"] is True
        assert "access" not in corpo and "refresh" not in corpo
        assert "_auth_user_id" not in client.session

    def test_login_web_com_2fa_nao_autentica_antes_do_codigo(self, usuario_2fa):
        client = Client()
        resposta = client.post(URL_LOGIN_WEB, {"username": "aval_2fa", "password": SENHA})
        assert resposta.status_code == 302 and resposta.url.endswith("/2fa/validar/")
        assert "_auth_user_id" not in client.session


@pytest.mark.django_db
class TestCodigosTOTP:

    def test_codigo_invalido_e_recusado(self, usuario_2fa):
        client = Client()
        resposta = client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token_2fa(client), "codigo": "123456"},
                               content_type="application/json")
        assert resposta.status_code == 400
        assert "access" not in resposta.json()

    def test_replay_o_mesmo_codigo_nao_vale_duas_vezes(self, usuario_2fa):
        _, device = usuario_2fa
        client = Client()
        codigo = codigo_atual(device)

        primeira = client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token_2fa(client), "codigo": codigo},
                               content_type="application/json")
        assert primeira.status_code == 200

        segunda = client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token_2fa(client), "codigo": codigo},
                              content_type="application/json")
        assert segunda.status_code == 400
        assert "access" not in segunda.json()

    def test_apos_erro_o_dispositivo_fica_bloqueado_por_um_tempo(self, usuario_2fa):
        """Atraso progressivo do django-otp: logo após um erro, nem o código certo passa."""
        _, device = usuario_2fa
        client = Client()
        client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token_2fa(client), "codigo": "000000"},
                    content_type="application/json")

        resposta = client.post(URL_LOGIN_SPA_2FA,
                               {"token_2fa": token_2fa(client), "codigo": codigo_atual(device)},
                               content_type="application/json")
        assert resposta.status_code == 400

        device.refresh_from_db()
        assert device.throttling_failure_count >= 1

    def test_tentativas_repetidas_sao_limitadas_por_ip(self, usuario_2fa):
        """Mais de 10 tentativas por minuto na segunda etapa recebem HTTP 429."""
        client = Client()
        token = token_2fa(client)
        status = [
            client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token, "codigo": "000000"},
                        content_type="application/json").status_code
            for _ in range(11)
        ]
        assert status[:10] == [400] * 10
        assert status[10] == 429

    def test_falhas_de_2fa_ficam_registradas_na_auditoria(self, usuario_2fa):
        client = Client()
        client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token_2fa(client), "codigo": "000000"},
                    content_type="application/json")
        assert RegistroAuditoria.objects.filter(usuario=usuario_2fa[0], acao="2FA_FALHA").exists()


@pytest.mark.django_db
class TestExpiracaoDoEstadoPre2FA:

    def test_estado_pre_2fa_web_expira(self, usuario_2fa):
        _, device = usuario_2fa
        client = Client()
        client.post(URL_LOGIN_WEB, {"username": "aval_2fa", "password": SENHA})

        sessao = client.session
        sessao["pre_2fa_em"] = timezone.now().timestamp() - 301
        sessao.save()

        resposta = client.post(URL_2FA_WEB, {"codigo": codigo_atual(device)})
        assert resposta.status_code == 302 and resposta.url.endswith("/entrar/")
        assert "_auth_user_id" not in client.session
        assert "pre_2fa_user_id" not in client.session

    def test_estado_pre_2fa_web_dentro_do_prazo_funciona(self, usuario_2fa):
        _, device = usuario_2fa
        client = Client()
        client.post(URL_LOGIN_WEB, {"username": "aval_2fa", "password": SENHA})
        resposta = client.post(URL_2FA_WEB, {"codigo": codigo_atual(device)})
        assert resposta.status_code == 302 and resposta.url.endswith("/home/")
        assert "_auth_user_id" in client.session

    def test_token_pre_2fa_da_api_expira(self, usuario_2fa):
        _, device = usuario_2fa
        client = Client()
        with patch("django.core.signing.time.time", return_value=time.time() - 301):
            token = token_2fa(client)
        resposta = client.post(URL_LOGIN_SPA_2FA, {"token_2fa": token, "codigo": codigo_atual(device)},
                               content_type="application/json")
        assert resposta.status_code == 401


@pytest.mark.django_db
class TestRecuperacaoDeSenhaExecutada:

    @pytest.fixture
    def usuario(self, db):
        return Usuario.objects.create_user(username="aval_rec", email="rec@exemplo.com",
                                           password=SENHA, consentimento_dados=True)

    def _redefinir(self, token, senha):
        return Client().post(URL_REDEFINIR, {"token": str(token), "password": senha},
                             content_type="application/json")

    def test_token_expirado_e_recusado(self, usuario):
        token = TokenRecuperacaoSenha.objects.create(usuario=usuario)
        TokenRecuperacaoSenha.objects.filter(pk=token.pk).update(expira_em=timezone.now() - timedelta(minutes=1))
        assert self._redefinir(token.token, "Nova!Senha#2026y").status_code == 400
        usuario.refresh_from_db()
        assert usuario.check_password(SENHA)

    def test_token_nao_pode_ser_reutilizado(self, usuario):
        token = TokenRecuperacaoSenha.objects.create(usuario=usuario)
        assert self._redefinir(token.token, "Nova!Senha#2026y").status_code == 200
        assert self._redefinir(token.token, "Outra!Senha#2026z").status_code == 400
        usuario.refresh_from_db()
        assert usuario.check_password("Nova!Senha#2026y")

    @pytest.mark.parametrize("senha_fraca", ["12345678", "password123", "curta"])
    def test_politica_de_senha_e_aplicada_na_redefinicao(self, usuario, senha_fraca):
        token = TokenRecuperacaoSenha.objects.create(usuario=usuario)
        assert self._redefinir(token.token, senha_fraca).status_code == 400
        usuario.refresh_from_db()
        assert usuario.check_password(SENHA)

    def test_solicitacoes_de_recuperacao_sao_limitadas(self, usuario):
        """No máximo 5 pedidos de e-mail de recuperação por hora por cliente."""
        client = Client()
        status = [client.post(URL_RECUPERAR, {"email": "rec@exemplo.com"},
                              content_type="application/json").status_code for _ in range(6)]
        assert all(s != 429 for s in status[:5])
        assert status[5] == 429


@pytest.mark.django_db
class TestTriggerAplicadoNoBanco:

    def test_banco_em_uso_e_postgresql(self):
        assert connection.vendor == "postgresql"

    def test_trigger_existe_na_tabela_de_auditoria(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tgname, tgenabled FROM pg_trigger "
                "WHERE tgrelid = 'auditoria_registroauditoria'::regclass AND NOT tgisinternal"
            )
            triggers = cursor.fetchall()
        assert triggers, "Nenhum trigger encontrado na tabela de auditoria"
        assert all(habilitado == "O" for _, habilitado in triggers)

    def test_update_e_delete_diretos_continuam_bloqueados(self):
        log = RegistroAuditoria.objects.create(acao="CREATE", modulo_afetado="Teste",
                                               descricao="original", ip_origem="127.0.0.1")
        for sql in ("UPDATE auditoria_registroauditoria SET descricao = 'alterado' WHERE id = %s",
                    "DELETE FROM auditoria_registroauditoria WHERE id = %s"):
            with pytest.raises(DatabaseError):
                with connection.cursor() as cursor:
                    cursor.execute("SAVEPOINT sp")
                    try:
                        cursor.execute(sql, [log.id])
                    finally:
                        cursor.execute("ROLLBACK TO SAVEPOINT sp")
        assert RegistroAuditoria.objects.get(id=log.id).descricao == "original"