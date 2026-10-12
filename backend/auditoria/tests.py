import pytest
from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError
from auditoria.models import RegistroAuditoria
from usuarios.models import Usuario


@pytest.mark.django_db
class TestImutabilidadeAuditoriaModel:
    @pytest.fixture(autouse=True)
    def setup_log(self):
        self.log = RegistroAuditoria.objects.create(
            acao='CREATE',
            modulo_afetado='Inventario',
            descricao='Teste de imutabilidade',
            ip_origem='127.0.0.1'
        )

    def test_nao_permite_atualizar_registro_existente_via_django(self):
        self.log.descricao = 'Alteracao'
        with pytest.raises(ValidationError):
            self.log.save()

    def test_nao_permite_excluir_registro_individual_via_django(self):
        with pytest.raises(ValidationError):
            self.log.delete()

    def test_nao_permite_atualizacao_em_lote_via_queryset(self):
        with pytest.raises(ValidationError):
            RegistroAuditoria.objects.filter(id=self.log.id).update(descricao='Lote')

    def test_nao_permite_exclusao_em_lote_via_queryset(self):
        with pytest.raises(ValidationError):
            RegistroAuditoria.objects.filter(id=self.log.id).delete()


@pytest.mark.django_db
class TestImutabilidadeAuditoriaBanco:
    @pytest.fixture(autouse=True)
    def setup_log(self):
        self.log = RegistroAuditoria.objects.create(
            acao='CREATE',
            modulo_afetado='Inventario',
            descricao='Teste trigger',
            ip_origem='127.0.0.1'
        )

    def test_trigger_postgres_bloqueia_update_direto(self):
        with pytest.raises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auditoria_registroauditoria SET descricao = 'Hack' WHERE id = %s;",
                    [self.log.id]
                )

    def test_trigger_postgres_bloqueia_delete_direto(self):
        with pytest.raises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM auditoria_registroauditoria WHERE id = %s;",
                    [self.log.id]
                )


@pytest.mark.django_db
class TestExclusaoDeUsuarioPreservaLog:
    """
    O campo 'usuario' do log usa SET_NULL: ao excluir um usuário, o log
    deve sobreviver, só perdendo a referência. Garante que a proteção de
    imutabilidade não impede essa operação legítima, e que a exceção que
    o trigger abre para ela é estreita (não serve para alterar o resto
    do registro).
    """

    def _criar_usuario_com_log(self, username):
        usuario = Usuario.objects.create_user(username=username, password="senha12345")
        log = RegistroAuditoria.objects.create(
            usuario=usuario,
            acao='LOGIN_SUCESSO',
            modulo_afetado='Autenticação',
            descricao='Log de teste.',
            ip_origem='127.0.0.1',
        )
        return usuario, log

    def test_excluir_usuario_mantem_o_log_com_usuario_nulo(self):
        usuario, log = self._criar_usuario_com_log("teste_excluir_log")

        usuario.delete()
        log.refresh_from_db()

        assert log.usuario is None
        assert log.descricao == 'Log de teste.'

    def test_trigger_nao_permite_zerar_usuario_junto_com_outra_alteracao(self):
        """
        A única alteração tolerada é usuario_id virar NULL com o resto do
        registro idêntico. Zerar o usuário E mexer na descrição é recusado.
        """
        _, log = self._criar_usuario_com_log("teste_excecao_estreita")

        with pytest.raises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auditoria_registroauditoria "
                    "SET usuario_id = NULL, descricao = 'Hack' WHERE id = %s;",
                    [log.id]
                )