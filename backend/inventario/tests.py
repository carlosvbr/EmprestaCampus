import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from auditoria.models import RegistroAuditoria
from emprestimos.models import Emprestimo
from inventario.models import Categoria, Equipamento

URL_CATEGORIAS = "/api/inventario/categorias/"
URL_EQUIPAMENTOS = "/api/inventario/equipamentos/"


def _chamar(metodo, usuario, url, dados=None, cliente=None):
    """
    Faz uma requisição à API como o usuário informado, autenticando com
    JWT (a API não usa sessão). Com usuario=None, vai sem token (visitante).
    """
    cliente = cliente or Client()
    extra = {}
    if usuario is not None:
        token = str(RefreshToken.for_user(usuario).access_token)
        extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    funcao = getattr(cliente, metodo)
    if dados is None:
        return funcao(url, **extra)
    return funcao(url, dados, content_type="application/json", **extra)


@pytest.fixture
def categoria(db):
    return Categoria.objects.create(nome="Notebooks")


@pytest.mark.django_db
class TestPermissoesDaAPI:
    """
    RBAC do inventário: qualquer usuário logado consulta, só o ADMIN
    cria, edita ou exclui (permissão IsAdmin).
    """

    def test_visitante_sem_token_e_recusado(self, equipamento):
        resposta = _chamar("get", None, URL_EQUIPAMENTOS)

        assert resposta.status_code == 401

    def test_aluno_lista_equipamentos(self, aluno, equipamento):
        resposta = _chamar("get", aluno, URL_EQUIPAMENTOS)

        assert resposta.status_code == 200
        item = resposta.json()[0]
        assert item["patrimonio"] == equipamento.patrimonio
        assert item["categoria_nome"] == "Tablets"

    def test_aluno_lista_categorias(self, aluno, equipamento):
        resposta = _chamar("get", aluno, URL_CATEGORIAS)

        assert resposta.status_code == 200
        assert [c["nome"] for c in resposta.json()] == ["Tablets"]

    def test_aluno_nao_cria_categoria(self, aluno):
        resposta = _chamar("post", aluno, URL_CATEGORIAS, {"nome": "Proibida"})

        assert resposta.status_code == 403
        assert not Categoria.objects.filter(nome="Proibida").exists()

    def test_aluno_nao_cria_equipamento(self, aluno, categoria):
        resposta = _chamar(
            "post", aluno, URL_EQUIPAMENTOS,
            {"nome": "Intruso", "patrimonio": "PAT-X-1", "categoria": categoria.id},
        )

        assert resposta.status_code == 403
        assert Equipamento.objects.count() == 0

    def test_aluno_nao_edita_equipamento(self, aluno, equipamento):
        resposta = _chamar(
            "patch", aluno, f"{URL_EQUIPAMENTOS}{equipamento.id}/", {"status": "INATIVO"}
        )
        equipamento.refresh_from_db()

        assert resposta.status_code == 403
        assert equipamento.status == "DISPONIVEL"

    def test_aluno_nao_exclui_equipamento(self, aluno, equipamento):
        resposta = _chamar("delete", aluno, f"{URL_EQUIPAMENTOS}{equipamento.id}/")

        assert resposta.status_code == 403
        assert Equipamento.objects.filter(id=equipamento.id).exists()


@pytest.mark.django_db
class TestAdminGerenciaInventario:
    def test_admin_cria_categoria(self, administrador):
        resposta = _chamar(
            "post", administrador, URL_CATEGORIAS,
            {"nome": "Notebooks", "descricao": "Portáteis"},
        )

        assert resposta.status_code == 201
        assert Categoria.objects.filter(nome="Notebooks").exists()

    def test_nome_de_categoria_duplicado_e_recusado(self, administrador, equipamento):
        resposta = _chamar("post", administrador, URL_CATEGORIAS, {"nome": "Tablets"})

        assert resposta.status_code == 400
        assert Categoria.objects.filter(nome="Tablets").count() == 1

    def test_admin_cria_equipamento_e_registra_auditoria(self, administrador, categoria):
        resposta = _chamar(
            "post", administrador, URL_EQUIPAMENTOS,
            {"nome": "Notebook Novo", "patrimonio": "PAT-N-100", "categoria": categoria.id},
        )

        assert resposta.status_code == 201
        # Todo equipamento novo nasce disponível (default do model).
        assert resposta.json()["status"] == "DISPONIVEL"
        registro = RegistroAuditoria.objects.get(
            usuario=administrador, acao="CREATE", modulo_afetado="Inventário"
        )
        assert "PAT-N-100" in registro.descricao

    def test_patrimonio_duplicado_e_recusado(self, administrador, equipamento):
        resposta = _chamar(
            "post", administrador, URL_EQUIPAMENTOS,
            {
                "nome": "Clone",
                "patrimonio": equipamento.patrimonio,
                "categoria": equipamento.categoria.id,
            },
        )

        assert resposta.status_code == 400
        assert Equipamento.objects.count() == 1

    def test_status_invalido_e_recusado(self, administrador, categoria):
        resposta = _chamar(
            "post", administrador, URL_EQUIPAMENTOS,
            {
                "nome": "Quebrado",
                "patrimonio": "PAT-Q-1",
                "categoria": categoria.id,
                "status": "QUEBRADO",
            },
        )

        assert resposta.status_code == 400
        assert Equipamento.objects.count() == 0

    def test_categoria_inexistente_e_recusada(self, administrador):
        resposta = _chamar(
            "post", administrador, URL_EQUIPAMENTOS,
            {"nome": "Sem categoria", "patrimonio": "PAT-S-1", "categoria": 999999},
        )

        assert resposta.status_code == 400
        assert Equipamento.objects.count() == 0

    def test_admin_edita_equipamento_e_registra_auditoria(self, administrador, equipamento):
        resposta = _chamar(
            "patch", administrador, f"{URL_EQUIPAMENTOS}{equipamento.id}/",
            {"status": "MANUTENCAO"},
        )
        equipamento.refresh_from_db()

        assert resposta.status_code == 200
        assert equipamento.status == "MANUTENCAO"
        assert RegistroAuditoria.objects.filter(
            usuario=administrador, acao="UPDATE", modulo_afetado="Inventário"
        ).exists()

    def test_data_de_cadastro_nao_pode_ser_alterada(self, administrador, equipamento):
        antes = equipamento.data_cadastro

        resposta = _chamar(
            "patch", administrador, f"{URL_EQUIPAMENTOS}{equipamento.id}/",
            {"data_cadastro": "2000-01-01T00:00:00Z"},
        )
        equipamento.refresh_from_db()

        assert resposta.status_code == 200
        assert equipamento.data_cadastro == antes

    def test_admin_exclui_equipamento_sem_historico_e_registra_auditoria(
        self, administrador, equipamento
    ):
        patrimonio = equipamento.patrimonio

        resposta = _chamar("delete", administrador, f"{URL_EQUIPAMENTOS}{equipamento.id}/")

        assert resposta.status_code == 204
        assert not Equipamento.objects.filter(patrimonio=patrimonio).exists()
        registro = RegistroAuditoria.objects.get(
            usuario=administrador, acao="DELETE", modulo_afetado="Inventário"
        )
        assert patrimonio in registro.descricao


@pytest.mark.django_db
class TestExclusaoProtegida:
    """
    O model usa on_delete=PROTECT: equipamento com empréstimo no histórico
    e categoria em uso não podem ser apagados. A API deve responder com um
    erro claro (não com 500) e não pode registrar na auditoria uma
    exclusão que não aconteceu.
    """

    def _excluir(self, usuario, url):
        # raise_request_exception=False devolve o 500 como resposta, em vez
        # de estourar a exceção dentro do teste.
        return _chamar("delete", usuario, url, cliente=Client(raise_request_exception=False))

    def test_equipamento_com_historico_nao_e_excluido_nem_gera_log_falso(
        self, administrador, aluno, equipamento
    ):
        Emprestimo.objects.create(usuario=aluno, equipamento=equipamento, status="DEVOLVIDO")

        resposta = self._excluir(administrador, f"{URL_EQUIPAMENTOS}{equipamento.id}/")

        assert resposta.status_code in (400, 409)
        assert Equipamento.objects.filter(id=equipamento.id).exists()
        assert not RegistroAuditoria.objects.filter(acao="DELETE").exists()

    def test_categoria_em_uso_nao_e_excluida(self, administrador, equipamento):
        resposta = self._excluir(administrador, f"{URL_CATEGORIAS}{equipamento.categoria.id}/")

        assert resposta.status_code in (400, 409)
        assert Categoria.objects.filter(id=equipamento.categoria.id).exists()


@pytest.mark.django_db
class TestCatalogoTela:
    """Tela HTML do catálogo (botão "Ver Catálogo" da home)."""

    def _html(self, cliente):
        return cliente.get(reverse("catalogo_web")).content.decode()

    def _url_solicitar(self, equipamento):
        return reverse("solicitar_emprestimo_web", args=[equipamento.id])

    def test_visitante_e_mandado_para_o_login(self):
        resposta = Client().get(reverse("catalogo_web"))

        assert resposta.status_code == 302
        assert "/api/usuarios/entrar/" in resposta.url

    def test_lista_os_equipamentos_cadastrados(self, cliente_aluno, equipamento):
        html = self._html(cliente_aluno)

        assert equipamento.nome in html
        assert equipamento.patrimonio in html
        assert "Tablets" in html

    def test_equipamento_disponivel_tem_botao_de_solicitar(self, cliente_aluno, equipamento):
        assert self._url_solicitar(equipamento) in self._html(cliente_aluno)

    def test_equipamento_emprestado_nao_tem_botao(self, cliente_aluno, equipamento):
        equipamento.status = "EMPRESTADO"
        equipamento.save()

        html = self._html(cliente_aluno)

        assert "Emprestado" in html
        assert self._url_solicitar(equipamento) not in html

    @pytest.mark.parametrize("status", ["SOLICITADO", "APROVADO"])
    def test_mostra_ja_solicitado_no_lugar_do_botao(
        self, cliente_aluno, aluno, equipamento, status
    ):
        Emprestimo.objects.create(usuario=aluno, equipamento=equipamento, status=status)

        html = self._html(cliente_aluno)

        assert "Já solicitado" in html
        assert self._url_solicitar(equipamento) not in html

    def test_pedido_de_outro_aluno_nao_marca_ja_solicitado(
        self, cliente_aluno, outro_aluno, equipamento
    ):
        Emprestimo.objects.create(usuario=outro_aluno, equipamento=equipamento)

        html = self._html(cliente_aluno)

        assert "Já solicitado" not in html
        assert self._url_solicitar(equipamento) in html

    @pytest.mark.parametrize("status", ["REJEITADO", "DEVOLVIDO"])
    def test_pedido_encerrado_nao_marca_ja_solicitado(
        self, cliente_aluno, aluno, equipamento, status
    ):
        Emprestimo.objects.create(usuario=aluno, equipamento=equipamento, status=status)

        html = self._html(cliente_aluno)

        assert "Já solicitado" not in html
        assert self._url_solicitar(equipamento) in html

    def test_catalogo_vazio_mostra_aviso(self, cliente_aluno):
        assert "Nenhum equipamento cadastrado ainda." in self._html(cliente_aluno)

    def test_status_aparece_por_extenso(self, cliente_aluno, equipamento):
        equipamento.status = "MANUTENCAO"
        equipamento.save()

        assert "Em Manutenção" in self._html(cliente_aluno)

    def test_nao_faz_uma_consulta_por_equipamento(self, cliente_aluno, equipamento):
        """
        Prova do select_related('categoria'): com 6 equipamentos, a página
        faz o mesmo número de consultas que com 1 (sem N+1).
        """
        url = reverse("catalogo_web")

        with CaptureQueriesContext(connection) as com_um:
            cliente_aluno.get(url)

        for i in range(5):
            Equipamento.objects.create(
                nome=f"Extra {i}", patrimonio=f"PAT-E-{i}", categoria=equipamento.categoria
            )

        with CaptureQueriesContext(connection) as com_seis:
            cliente_aluno.get(url)

        assert len(com_seis) == len(com_um)