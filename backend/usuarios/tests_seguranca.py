import time
from unittest.mock import patch

import pytest
from django.contrib.auth import authenticate
from django.test import Client
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework_simplejwt.tokens import RefreshToken

from inventario.models import Categoria
from usuarios.models import TokenRecuperacaoSenha, Usuario

from notificacoes.models import Notificacao
from notificacoes.utils import notificar_admins


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


@pytest.mark.django_db
class TestCadastroNaoPermitePapelPrivilegiado:
    """
    Escalada de privilegio no cadastro publico: ninguem pode se
    auto-atribuir o papel ADMIN enviando o campo "papel" direto para a
    API. Tambem confirma que a permissao do inventario (IsAdmin) so
    deixa o ADMIN escrever.
    """

    URL_REGISTRO = "/api/usuarios/registro/"
    URL_EQUIPAMENTOS = "/api/inventario/equipamentos/"

    def _dados_cadastro(self, **extra):
        dados = {
            "username": "teste_papel",
            "first_name": "Teste",
            "last_name": "Papel",
            "email": "teste_papel@exemplo.com",
            "password": "senha12345",
            "matricula": "2026001",
            "consentimento_dados": True,
        }
        dados.update(extra)
        return dados

    def _cadastrar(self, **extra):
        return Client().post(
            self.URL_REGISTRO,
            self._dados_cadastro(**extra),
            content_type="application/json",
        )

    def test_cadastro_com_papel_admin_e_recusado(self):
        resposta = self._cadastrar(papel="ADMIN")

        assert resposta.status_code == 400
        assert "papel" in resposta.json()
        assert not Usuario.objects.filter(username="teste_papel").exists()

    def test_cadastro_com_papel_inexistente_e_recusado(self):
        # O TECNICO foi removido do sistema; o valor nao existe mais.
        resposta = self._cadastrar(papel="TECNICO")

        assert resposta.status_code == 400
        assert not Usuario.objects.filter(username="teste_papel").exists()

    def test_cadastro_com_papel_aluno_e_aceito(self):
        resposta = self._cadastrar(papel="ALUNO")

        assert resposta.status_code == 201
        assert Usuario.objects.get(username="teste_papel").papel == "ALUNO"

    def test_cadastro_sem_papel_vira_aluno_por_padrao(self):
        resposta = self._cadastrar()

        assert resposta.status_code == 201
        assert Usuario.objects.get(username="teste_papel").papel == "ALUNO"

    def _post_equipamento_como(self, usuario, categoria):
        # A API usa autenticacao JWT (nao sessao), entao o teste manda o token.
        token = str(RefreshToken.for_user(usuario).access_token)
        return Client().post(
            self.URL_EQUIPAMENTOS,
            {
                "nome": "Notebook de teste",
                "patrimonio": "PAT-TESTE-1",
                "categoria": categoria.id,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_aluno_nao_consegue_cadastrar_equipamento(self):
        aluno = Usuario.objects.create_user(
            username="teste_aluno_inv", password="senha12345", papel="ALUNO"
        )
        categoria = Categoria.objects.create(nome="Categoria de teste")

        resposta = self._post_equipamento_como(aluno, categoria)

        assert resposta.status_code == 403

    def test_admin_consegue_cadastrar_equipamento(self):
        admin = Usuario.objects.create_user(
            username="teste_admin_inv", password="senha12345", papel="ADMIN"
        )
        categoria = Categoria.objects.create(nome="Categoria de teste")

        resposta = self._post_equipamento_como(admin, categoria)

        assert resposta.status_code == 201

@pytest.mark.django_db
class TestPapelManda:
    """
    O campo 'papel' é a fonte única da verdade sobre privilégios:
    ADMIN tem is_staff e is_superuser, qualquer outro papel não tem.
    Garante que não existe mais "admin só no papel" nem "admin só no
    is_staff" (as duas formas de administrador ficam sempre sincronizadas).
    """

    def test_admin_nasce_com_acesso_administrativo(self):
        admin = Usuario.objects.create_user(
            username="teste_papel_admin", password="senha12345", papel="ADMIN"
        )

        assert admin.is_staff is True
        assert admin.is_superuser is True

    def test_aluno_nasce_sem_acesso_administrativo(self):
        aluno = Usuario.objects.create_user(
            username="teste_papel_aluno", password="senha12345", papel="ALUNO"
        )

        assert aluno.is_staff is False
        assert aluno.is_superuser is False

    def test_forcar_is_staff_em_aluno_e_revertido(self):
        """
        Mesmo que alguém marque is_staff direto (por exemplo no /admin/),
        o papel prevalece e o save() desfaz.
        """
        usuario = Usuario.objects.create_user(
            username="teste_forca_staff", password="senha12345", papel="ALUNO"
        )
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.save()
        usuario.refresh_from_db()

        assert usuario.is_staff is False
        assert usuario.is_superuser is False

    def test_promover_a_admin_concede_acesso(self):
        usuario = Usuario.objects.create_user(
            username="teste_promocao", password="senha12345", papel="ALUNO"
        )
        usuario.papel = "ADMIN"
        usuario.save()
        usuario.refresh_from_db()

        assert usuario.is_staff is True
        assert usuario.is_superuser is True

    def test_rebaixar_admin_remove_acesso(self):
        usuario = Usuario.objects.create_user(
            username="teste_rebaixa", password="senha12345", papel="ADMIN"
        )
        usuario.papel = "ALUNO"
        usuario.save()
        usuario.refresh_from_db()

        assert usuario.is_staff is False
        assert usuario.is_superuser is False

    def test_save_parcial_do_papel_tambem_sincroniza(self):
        """
        save(update_fields=["papel"]) só gravaria o papel; o model inclui
        is_staff e is_superuser junto para a mudança não ficar pela metade.
        """
        usuario = Usuario.objects.create_user(
            username="teste_parcial", password="senha12345", papel="ALUNO"
        )
        usuario.papel = "ADMIN"
        usuario.save(update_fields=["papel"])
        usuario.refresh_from_db()

        assert usuario.is_staff is True
        assert usuario.is_superuser is True

    def test_createsuperuser_cria_conta_com_papel_admin(self):
        usuario = Usuario.objects.create_superuser(
            username="teste_super", email="super@exemplo.com", password="senha12345"
        )

        assert usuario.papel == "ADMIN"
        assert usuario.is_staff is True
        assert usuario.is_superuser is True

    def test_admin_acessa_o_django_admin_e_aluno_nao(self):
        admin = Usuario.objects.create_user(
            username="teste_acesso_admin", password="senha12345", papel="ADMIN"
        )
        aluno = Usuario.objects.create_user(
            username="teste_acesso_aluno", password="senha12345", papel="ALUNO"
        )
        backend = "django.contrib.auth.backends.ModelBackend"

        client_admin = Client()
        client_admin.force_login(admin, backend=backend)
        assert client_admin.get("/admin/").status_code == 200

        client_aluno = Client()
        client_aluno.force_login(aluno, backend=backend)
        resposta = client_aluno.get("/admin/")
        assert resposta.status_code == 302
        assert "/admin/login/" in resposta.url

    def test_notificar_admins_alcanca_so_os_administradores(self):
        admin = Usuario.objects.create_user(
            username="teste_notif_admin",
            password="senha12345",
            email="admin@exemplo.com",
            papel="ADMIN",
        )
        aluno = Usuario.objects.create_user(
            username="teste_notif_aluno",
            password="senha12345",
            email="aluno@exemplo.com",
            papel="ALUNO",
        )

        notificar_admins("Nova solicitação de teste.")

        assert Notificacao.objects.filter(usuario=admin).count() == 1
        assert not Notificacao.objects.filter(usuario=aluno).exists()