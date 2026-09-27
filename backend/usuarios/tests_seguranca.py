import time
from unittest.mock import patch

import pytest
from django.contrib.auth import authenticate
from django.test import Client
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from usuarios.models import TokenRecuperacaoSenha, Usuario


@pytest.mark.django_db
class TestHashDeSenha:
    """
    Cobre os itens 1.1, 1.2, 1.3 e 1.4 do checklist: hash criptografico,
    custo configurado, salt unico por usuario, armazenamento correto.
    """

    def test_senha_nunca_fica_em_texto_puro_no_banco(self):
        usuario = Usuario.objects.create_user(username="teste_hash", password="senha12345")
        assert usuario.password != "senha12345"
        assert usuario.password.startswith("pbkdf2_sha256$")

    def test_custo_do_hash_e_600000_iteracoes(self):
        usuario = Usuario.objects.create_user(username="teste_custo", password="senha12345")
        # Formato do hash: algoritmo$iteracoes$salt$hash
        partes = usuario.password.split("$")
        assert partes[1] == "600000"

    def test_dois_usuarios_com_mesma_senha_geram_hashes_diferentes(self):
        """
        Prova que o salt e unico por usuario (item 1.3): a mesma senha
        nunca deve gerar o mesmo hash em contas diferentes.
        """
        u1 = Usuario.objects.create_user(username="teste_salt_1", password="senha12345")
        u2 = Usuario.objects.create_user(username="teste_salt_2", password="senha12345")
        assert u1.password != u2.password


@pytest.mark.django_db
class TestProtecaoForcaBruta:
    """
    Cobre o item 1.11: bloqueio apos numero limite de tentativas erradas.
    """

    def test_bloqueia_apos_cinco_tentativas_erradas(self):
        Usuario.objects.create_user(
            username="teste_bruteforce",
            password="senhacerta123",
            consentimento_dados=True,
        )
        client = Client()

        for _ in range(5):
            client.post(
                "/api/usuarios/entrar/",
                {"username": "teste_bruteforce", "password": "senhaerrada"},
            )

        resposta = client.post(
            "/api/usuarios/entrar/",
            {"username": "teste_bruteforce", "password": "senhacerta123"},
        )

        # Apos o limite, ate a senha CERTA deve ser rejeitada pelo axes
        assert b"muitas tentativas" in resposta.content.lower() or resposta.status_code == 429


@pytest.mark.django_db
class TestRecuperacaoDeSenha:
    """
    Cobre os itens 2.2, 2.3, 2.4: token seguro, com expiracao,
    invalidado apos uso.
    """

    def test_token_e_de_uso_unico(self):
        usuario = Usuario.objects.create_user(username="teste_token", password="senhaantiga123")
        token = TokenRecuperacaoSenha.objects.create(usuario=usuario)

        assert token.esta_valido() is True

        token.usado = True
        token.save()

        assert token.esta_valido() is False

    def test_token_nao_e_previsivel(self):
        """
        Dois tokens seguidos nunca devem ter relacao sequencial visivel,
        confirmando uso de secrets.token_urlsafe (criptograficamente
        seguro) em vez de contador ou id incremental.
        """
        usuario = Usuario.objects.create_user(username="teste_token_2", password="senhaantiga123")
        token1 = TokenRecuperacaoSenha.objects.create(usuario=usuario)
        token2 = TokenRecuperacaoSenha.objects.create(usuario=usuario)

        assert token1.token != token2.token
        assert len(token1.token) >= 32


@pytest.mark.django_db
class TestDoisFatores:
    """
    Cobre os itens 1.5 e 1.6: 2FA implementado e validado apos a
    autenticacao primaria, antes de liberar a sessao.
    """

    def test_usuario_com_2fa_nao_autentica_so_com_senha(self):
        usuario = Usuario.objects.create_user(
            username="teste_2fa",
            password="senha12345",
            consentimento_dados=True,
        )
        TOTPDevice.objects.create(user=usuario, name="dispositivo-padrao", confirmed=True)

        client = Client()
        resposta = client.post(
            "/api/usuarios/entrar/",
            {"username": "teste_2fa", "password": "senha12345"},
            follow=True,
        )

        # Usuario com 2FA deve cair na tela de codigo, nao direto na home
        assert resposta.wsgi_request.path != "/api/usuarios/home/"

    def test_codigo_2fa_incorreto_nao_libera_acesso(self):
        usuario = Usuario.objects.create_user(username="teste_2fa_falha", password="senha12345")
        device = TOTPDevice.objects.create(user=usuario, name="dispositivo-padrao", confirmed=True)

        assert device.verify_token("000000") is False


def _codigo_totp_atual(device):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time()
    return str(totp.token()).zfill(device.digits)


@pytest.mark.django_db
class TestLoginSpaDoisFatores:
    """
    Login JWT da SPA em duas etapas: a segunda etapa so aceita o token
    assinado emitido pela primeira, nunca um id de usuario solto.
    """

    URL_LOGIN = "/api/usuarios/login/spa/"
    URL_2FA = "/api/usuarios/login/spa/2fa/"

    @pytest.fixture
    def usuario_com_2fa(self):
        usuario = Usuario.objects.create_user(
            username="teste_spa_2fa",
            password="senha12345",
            consentimento_dados=True,
        )
        device = TOTPDevice.objects.create(user=usuario, name="dispositivo-padrao", confirmed=True)
        return usuario, device

    def _login(self, client):
        return client.post(
            self.URL_LOGIN,
            {"username": "teste_spa_2fa", "password": "senha12345"},
            content_type="application/json",
        )

    def test_primeira_etapa_nao_emite_jwt_nem_expoe_id(self, usuario_com_2fa):
        resposta = self._login(Client())

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["requer_2fa"] is True
        assert corpo["token_2fa"]
        assert "access" not in corpo
        assert "refresh" not in corpo
        assert "user_id" not in corpo

    def test_fluxo_completo_com_codigo_correto_emite_jwt(self, usuario_com_2fa):
        _, device = usuario_com_2fa
        client = Client()
        token = self._login(client).json()["token_2fa"]

        resposta = client.post(
            self.URL_2FA,
            {"token_2fa": token, "codigo": _codigo_totp_atual(device)},
            content_type="application/json",
        )

        assert resposta.status_code == 200
        assert "access" in resposta.json()
        assert "refresh" in resposta.json()

    def test_codigo_errado_nao_emite_jwt(self, usuario_com_2fa):
        client = Client()
        token = self._login(client).json()["token_2fa"]

        resposta = client.post(
            self.URL_2FA,
            {"token_2fa": token, "codigo": "000000"},
            content_type="application/json",
        )

        assert resposta.status_code == 400
        assert "access" not in resposta.json()

    def test_segunda_etapa_sem_passar_pela_senha_e_rejeitada(self, usuario_com_2fa):
        """
        O ataque antigo: mandar direto o id do usuario com um codigo
        valido, sem nunca ter acertado a senha.
        """
        usuario, device = usuario_com_2fa

        resposta = Client().post(
            self.URL_2FA,
            {"user_id": usuario.id, "codigo": _codigo_totp_atual(device)},
            content_type="application/json",
        )

        assert resposta.status_code == 401
        assert "access" not in resposta.json()

    def test_token_forjado_ou_adulterado_e_rejeitado(self, usuario_com_2fa):
        _, device = usuario_com_2fa
        client = Client()
        token = self._login(client).json()["token_2fa"]

        for token_ruim in [str(usuario_com_2fa[0].id), token[:-1] + ("A" if token[-1] != "A" else "B")]:
            resposta = client.post(
                self.URL_2FA,
                {"token_2fa": token_ruim, "codigo": _codigo_totp_atual(device)},
                content_type="application/json",
            )
            assert resposta.status_code == 401

    def test_token_expirado_e_rejeitado(self, usuario_com_2fa):
        _, device = usuario_com_2fa
        client = Client()

        # Emite o token "10 minutos atras", alem da validade de 5 minutos
        with patch("django.core.signing.time.time", return_value=time.time() - 600):
            token = self._login(client).json()["token_2fa"]

        resposta = client.post(
            self.URL_2FA,
            {"token_2fa": token, "codigo": _codigo_totp_atual(device)},
            content_type="application/json",
        )

        assert resposta.status_code == 401
        assert "access" not in resposta.json()

    def test_usuario_sem_2fa_recebe_jwt_direto(self):
        Usuario.objects.create_user(
            username="teste_spa_sem_2fa",
            password="senha12345",
            consentimento_dados=True,
        )

        resposta = Client().post(
            self.URL_LOGIN,
            {"username": "teste_spa_sem_2fa", "password": "senha12345"},
            content_type="application/json",
        )

        assert resposta.status_code == 200
        assert resposta.json()["requer_2fa"] is False
        assert "access" in resposta.json()
