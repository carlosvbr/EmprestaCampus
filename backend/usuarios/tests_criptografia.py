"""
Criptografia em repouso e rotação de chaves.

Os testes leem o valor gravado direto no banco, por SQL puro, para provar
que o que está guardado é o texto cifrado, e não o dado original.
"""

import importlib
import io
import time

import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from usuarios.models import DispositivoTOTP, Usuario

TELEFONE = "(00) 00000-0000"


# Consultas fixas, sem montar SQL com variáveis (evita alerta de SQL injection).
CONSULTAS = {
    "telefone": "SELECT telefone FROM usuarios_usuario WHERE id = %s",
    "chave_2fa": "SELECT key FROM usuarios_dispositivototp WHERE id = %s",
}


def valor_no_banco(campo, pk):
    with connection.cursor() as cursor:
        cursor.execute(CONSULTAS[campo], [pk])
        return cursor.fetchone()[0]


def codigo_atual(device):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time()
    return f"{totp.token():06d}"


@pytest.fixture
def usuario(db):
    return Usuario.objects.create_user(
        username="cripto", password="Emp!Campus#2026x", email="cripto@exemplo.com",
        telefone=TELEFONE, consentimento_dados=True,
    )


@pytest.mark.django_db
class TestDadosCifradosNoBanco:

    def test_telefone_fica_cifrado_no_banco(self, usuario):
        gravado = valor_no_banco("telefone", usuario.pk)
        assert TELEFONE not in gravado
        assert gravado.startswith("gAAAAA")  # prefixo de um token Fernet
        assert Usuario.objects.get(pk=usuario.pk).telefone == TELEFONE

    def test_chave_do_2fa_fica_cifrada_no_banco(self, usuario):
        device = DispositivoTOTP.objects.create(user=usuario, name="padrao", confirmed=True)
        chave = DispositivoTOTP.objects.get(pk=device.pk).key

        gravado = valor_no_banco("chave_2fa", device.pk)
        assert chave not in gravado
        assert gravado.startswith("gAAAAA")
        assert len(chave) == 40 and int(chave, 16) >= 0  # decifrada, volta a ser hexadecimal

    def test_2fa_continua_funcionando_com_a_chave_cifrada(self, usuario):
        device = DispositivoTOTP.objects.create(user=usuario, name="padrao", confirmed=True)
        device = DispositivoTOTP.objects.get(pk=device.pk)
        assert device.verify_token(codigo_atual(device)) is True
        assert device.verify_token("000000") is False

    def test_mesmo_valor_gera_cifras_diferentes(self, db):
        a = Usuario.objects.create_user(username="a", password="x", telefone=TELEFONE)
        b = Usuario.objects.create_user(username="b", password="x", telefone=TELEFONE)
        assert valor_no_banco("telefone", a.pk) != valor_no_banco("telefone", b.pk)

    def test_migracao_tira_as_chaves_do_texto_puro(self, usuario):
        antigo = TOTPDevice.objects.create(user=usuario, name="antigo", confirmed=True)
        chave_antiga = antigo.key

        migracao = importlib.import_module("usuarios.migrations.0011_migrar_dispositivos_totp")
        migracao.migrar(apps, None)

        assert not TOTPDevice.objects.exists()
        novo = DispositivoTOTP.objects.get(user=usuario)
        assert novo.key == chave_antiga  # o app autenticador continua valendo
        assert novo.name == "antigo" and novo.confirmed
        assert chave_antiga not in valor_no_banco("chave_2fa", novo.pk)


@pytest.mark.django_db
class TestRotacaoDeChave:

    @pytest.fixture
    def chaves(self):
        return Fernet.generate_key().decode(), Fernet.generate_key().decode()

    def test_rotacao_completa(self, settings, chaves):
        antiga, nova = chaves
        settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEYS_ANTIGAS = antiga, []
        usuario = Usuario.objects.create_user(username="rot", password="x", telefone=TELEFONE)
        device = DispositivoTOTP.objects.create(user=usuario, name="padrao", confirmed=True)
        chave_totp = DispositivoTOTP.objects.get(pk=device.pk).key

        # Passo 1: chave nova em uso, antiga ainda aceita para leitura.
        settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEYS_ANTIGAS = nova, [antiga]
        assert Usuario.objects.get(pk=usuario.pk).telefone == TELEFONE

        # Passo 2: recifra tudo com a chave nova.
        call_command("rotacionar_chave_criptografia", stdout=io.StringIO())

        # Passo 3: a chave antiga sai, e os dados continuam legíveis.
        settings.ENCRYPTION_KEYS_ANTIGAS = []
        assert Usuario.objects.get(pk=usuario.pk).telefone == TELEFONE
        assert DispositivoTOTP.objects.get(pk=device.pk).key == chave_totp

        # O que está no banco só abre com a chave nova.
        gravado = valor_no_banco("telefone", usuario.pk)
        assert Fernet(nova.encode()).decrypt(gravado.encode()).decode() == TELEFONE
        with pytest.raises(InvalidToken):
            Fernet(antiga.encode()).decrypt(gravado.encode())

    def test_sem_a_chave_certa_o_dado_nao_e_lido(self, settings, chaves):
        antiga, nova = chaves
        settings.ENCRYPTION_KEY, settings.ENCRYPTION_KEYS_ANTIGAS = antiga, []
        usuario = Usuario.objects.create_user(username="semchave", password="x", telefone=TELEFONE)

        settings.ENCRYPTION_KEY = nova  # troca sem guardar a antiga
        with pytest.raises(InvalidToken):
            Usuario.objects.get(pk=usuario.pk)
