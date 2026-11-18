"""
Prazo de retenção da auditoria: 5 anos.

O trigger continua bloqueando qualquer UPDATE (exceto o SET NULL do
usuário, como antes) e qualquer DELETE de registro com menos de 5 anos.
A única mudança é que um registro mais antigo que isso pode ser
eliminado, para que os dados pessoais da trilha (usuário, IP, descrição)
não fiquem guardados para sempre (LGPD, arts. 15 e 16).

Como o UPDATE continua bloqueado, não é possível "envelhecer" um registro
alterando a data para conseguir apagá-lo.
"""

from django.db import migrations

FUNCAO_COM_RETENCAO = """
CREATE OR REPLACE FUNCTION proteger_registro_auditoria()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        IF (OLD.usuario_id IS NOT NULL AND NEW.usuario_id IS NULL) THEN
            IF (
                OLD.id = NEW.id AND
                OLD.acao = NEW.acao AND
                OLD.modulo_afetado = NEW.modulo_afetado AND
                OLD.descricao = NEW.descricao AND
                OLD.ip_origem IS NOT DISTINCT FROM NEW.ip_origem AND
                OLD.data_hora = NEW.data_hora
            ) THEN
                RETURN NEW;
            END IF;
        END IF;
        RAISE EXCEPTION 'Modificação de logs de auditoria não é permitida.';
    END IF;

    IF (TG_OP = 'DELETE') THEN
        IF (OLD.data_hora < NOW() - INTERVAL '5 years') THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'Exclusão de logs de auditoria não é permitida antes de 5 anos.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

FUNCAO_ANTERIOR = """
CREATE OR REPLACE FUNCTION proteger_registro_auditoria()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        IF (OLD.usuario_id IS NOT NULL AND NEW.usuario_id IS NULL) THEN
            IF (
                OLD.id = NEW.id AND
                OLD.acao = NEW.acao AND
                OLD.modulo_afetado = NEW.modulo_afetado AND
                OLD.descricao = NEW.descricao AND
                OLD.ip_origem IS NOT DISTINCT FROM NEW.ip_origem AND
                OLD.data_hora = NEW.data_hora
            ) THEN
                RETURN NEW;
            END IF;
        END IF;
        RAISE EXCEPTION 'Modificação de logs de auditoria não é permitida.';
    END IF;

    IF (TG_OP = 'DELETE') THEN
        RAISE EXCEPTION 'Exclusão de logs de auditoria não é permitida.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0003_auto_20261012_1140"),
    ]

    operations = [
        migrations.RunSQL(FUNCAO_COM_RETENCAO, reverse_sql=FUNCAO_ANTERIOR),
    ]
