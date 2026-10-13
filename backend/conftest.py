import pytest
from django.test import Client

from inventario.models import Categoria, Equipamento
from usuarios.models import Usuario

# Com mais de um backend de autenticação configurado (Axes + ModelBackend),
# o force_login exige dizer qual usar.
BACKEND_SESSAO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def aluno(db):
    # Sem senha de propósito: o teste usa force_login ou JWT, e criar
    # usuário sem senha evita o custo do hash PBKDF2 (600.000 iterações).
    return Usuario.objects.create_user(
        username="aluno_teste", email="aluno@exemplo.com", papel="ALUNO"
    )


@pytest.fixture
def outro_aluno(db):
    return Usuario.objects.create_user(
        username="outro_aluno_teste", email="outro@exemplo.com", papel="ALUNO"
    )


@pytest.fixture
def administrador(db):
    return Usuario.objects.create_user(
        username="admin_teste", email="admin@exemplo.com", papel="ADMIN"
    )


@pytest.fixture
def equipamento(db):
    categoria = Categoria.objects.create(nome="Tablets")
    return Equipamento.objects.create(
        nome="Tablet de teste", patrimonio="PAT-T-001", categoria=categoria
    )


@pytest.fixture
def cliente_aluno(aluno):
    cliente = Client()
    cliente.force_login(aluno, backend=BACKEND_SESSAO)
    return cliente


@pytest.fixture
def cliente_admin(administrador):
    cliente = Client()
    cliente.force_login(administrador, backend=BACKEND_SESSAO)
    return cliente