"""
Mapeamento dos dados pessoais tratados pelo sistema.

Cada campo gravado no banco que se refere a uma pessoa está associado a
uma ou mais finalidades, e cada finalidade a uma base legal do art. 7º da
LGPD. As finalidades com base em consentimento são opcionais e têm aceite
próprio.
Os campos puramente técnicos, que não identificam nem descrevem ninguém,
ficam listados à parte, para que nenhum campo fique sem classificação.

O teste test_todo_campo_esta_mapeado (usuarios/testes_lgpd.py) falha se
alguém criar um campo novo nesses modelos sem registrá-lo aqui. Assim o
mapeamento não fica desatualizado em relação ao código.

A tabela legível deste mapeamento, com os prazos de retenção, está em
docs/4_Conformidade_LGPD/Mapeamento de Dados Pessoais.md.
"""

FINALIDADES = {
    "acesso": {
        "descricao": "Identificar o titular e permitir o login com segurança",
        "base_legal": "Execução de contrato (art. 7º, V)",
    },
    "emprestimo": {
        "descricao": "Registrar quem solicitou, retirou e devolveu cada equipamento",
        "base_legal": "Execução de contrato (art. 7º, V)",
    },
    "comunicacao": {
        "descricao": "Avisar o titular sobre a segurança da conta e permitir a recuperação de senha",
        "base_legal": "Execução de contrato (art. 7º, V)",
    },
    "avisos_emprestimo": {
        "descricao": "Avisar por e-mail sobre o andamento dos empréstimos (aprovação, recusa, devolução, prorrogação)",
        "base_legal": "Consentimento (art. 7º, I); opcional",
    },
    "contato_alternativo": {
        "descricao": "Contato da equipe com o titular, por telefone, sobre um equipamento emprestado",
        "base_legal": "Consentimento (art. 7º, I); opcional",
    },
    "consentimento": {
        "descricao": "Comprovar quando e qual versão da política o titular aceitou",
        "base_legal": "Cumprimento de obrigação legal (art. 7º, II; art. 8º, § 2º)",
    },
    "seguranca": {
        "descricao": "Proteger as contas, investigar incidentes e manter a trilha de auditoria",
        "base_legal": "Legítimo interesse (art. 7º, IX; art. 10, § 3º)",
    },
}

# Campos com dado pessoal: {modelo: {campo: finalidade ou (finalidades, ...)}}
MAPEAMENTO = {
    "usuarios.Usuario": {
        "username": "acesso",
        "password": "acesso",
        "first_name": "acesso",
        "last_name": "acesso",
                "email": ("comunicacao", "avisos_emprestimo"),
        "matricula": "emprestimo",
        "papel": "acesso",
        "telefone": "contato_alternativo",
        "is_active": "acesso",
        "date_joined": "acesso",
        "last_login": "seguranca",
        "consentimento_dados": "consentimento",
        "data_consentimento": "consentimento",
        "versao_documento_aceito": "consentimento",
        "consentimento_revogado_em": "consentimento",
    },
    "usuarios.DispositivoTOTP": {
        "user": "acesso",
        "key": "acesso",
        "confirmed": "acesso",
        "last_t": "seguranca",
        "throttling_failure_timestamp": "seguranca",
        "throttling_failure_count": "seguranca",
        "created_at": "seguranca",
        "last_used_at": "seguranca",
    },
    "usuarios.TokenRecuperacaoSenha": {
        "usuario": "acesso",
        "token": "acesso",
        "criado_em": "acesso",
        "expira_em": "acesso",
        "usado": "acesso",
    },
    "emprestimos.Emprestimo": {
        "usuario": "emprestimo",
        "equipamento": "emprestimo",
        "data_solicitacao": "emprestimo",
        "data_retirada": "emprestimo",
        "data_devolucao_prevista": "emprestimo",
        "data_devolucao_real": "emprestimo",
        "status": "emprestimo",
        "observacoes": "emprestimo",
        "prorrogacao_solicitada": "emprestimo",
    },
    "usuarios.ConsentimentoFinalidade": {
        "usuario": "consentimento",
        "finalidade": "consentimento",
        "aceito": "consentimento",
        "data_hora": "consentimento",
        "versao_politica": "consentimento",
    },
    "notificacoes.Notificacao": {
        # Guarda tanto avisos de segurança quanto avisos de empréstimo;
        # estes só são gravados com o consentimento do titular.
        "usuario": ("comunicacao", "avisos_emprestimo"),
        "mensagem": ("comunicacao", "avisos_emprestimo"),
        "tipo": ("comunicacao", "avisos_emprestimo"),
        "lida": ("comunicacao", "avisos_emprestimo"),
        "data_criacao": ("comunicacao", "avisos_emprestimo"),
    },
    "auditoria.RegistroAuditoria": {
        "usuario": "seguranca",
        "acao": "seguranca",
        "modulo_afetado": "seguranca",
        "descricao": "seguranca",
        "ip_origem": "seguranca",
        "data_hora": "seguranca",
    },
    "admin.LogEntry": {
        # Histórico das alterações feitas pelos administradores no /admin/.
        "user": "seguranca",
        "action_time": "seguranca",
        "content_type": "seguranca",
        "object_id": "seguranca",
        "object_repr": "seguranca",
        "action_flag": "seguranca",
        "change_message": "seguranca",
    },
    "axes.AccessAttempt": {
        "username": "seguranca",
        "ip_address": "seguranca",
        "user_agent": "seguranca",
        "http_accept": "seguranca",
        "path_info": "seguranca",
        "attempt_time": "seguranca",
        "get_data": "seguranca",
        "post_data": "seguranca",
        "failures_since_start": "seguranca",
    },
}

# Campos técnicos, sem dado pessoal: {modelo: {campo, ...}}
CAMPOS_TECNICOS = {
    "usuarios.Usuario": {
        # Derivados do papel no save(); não descrevem o titular.
        "is_staff", "is_superuser",
    },
    "usuarios.DispositivoTOTP": {
        # Parâmetros do algoritmo TOTP, iguais para todos os usuários.
        "name", "step", "t0", "digits", "tolerance", "drift",
    },
}

def finalidades_do_campo(valor):
    """Normaliza o valor do MAPEAMENTO: sempre devolve uma tupla de finalidades."""
    return (valor,) if isinstance(valor, str) else tuple(valor)
