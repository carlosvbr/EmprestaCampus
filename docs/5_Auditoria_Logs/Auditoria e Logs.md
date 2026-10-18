# Análise de Logs e Auditoria

## 1. Objetivo
O objetivo deste documento é demonstrar como o módulo de Auditoria acompanha e registra eventos críticos de autenticação, recuperação de credenciais, segundo fator, privacidade, inventário e empréstimos. Essa rastreabilidade garante a prestação de contas e o cumprimento de normas de segurança e da LGPD.

Todos os eventos são gravados no model `RegistroAuditoria` (app `auditoria`), com os campos:

| Campo | Conteúdo |
| :--- | :--- |
| `data_hora` | Data e hora do evento, preenchida automaticamente |
| `usuario` | Usuário que realizou a ação, quando identificado |
| `acao` | Tipo do evento (ver seção 2) |
| `modulo_afetado` | Área do sistema em que o evento ocorreu |
| `descricao` | Descrição do que aconteceu |
| `ip_origem` | Endereço IP de origem da requisição |

## 2. Eventos Registrados
O sistema registra automaticamente os seguintes eventos:

| Ação | Módulo | Quando é registrada |
| :--- | :--- | :--- |
| `LOGIN_SUCESSO` | Autenticação, Autenticação/API | Login concluído com senha correta, em usuário sem 2FA |
| `LOGIN_FALHA` | Autenticação, Autenticação/API | Credenciais inválidas no login web ou na API |
| `2FA_SUCESSO` | Autenticação, Autenticação/API | Código TOTP correto no login |
| `2FA_FALHA` | Autenticação, Autenticação/API | Código TOTP incorreto no login |
| `RECUPERACAO_SOLICITADA` | Autenticação/Recuperação | Pedido de recuperação de senha, com e-mail cadastrado ou não |
| `RECUPERACAO_SUCESSO` | Autenticação/Recuperação | Senha redefinida com sucesso |
| `RECUPERACAO_FALHA` | Autenticação/Recuperação | Token inexistente, expirado ou já utilizado, ou nova senha fora da regra |
| `UPDATE` | Segurança/2FA | Ativação do 2FA, falha de código na ativação (web e API) e desativação pelo usuário |
| `UPDATE` | Privacidade/LGPD | Revogação do consentimento, restauração do consentimento e reativação da conta |
| `DELETE` | Privacidade/LGPD | Encerramento da conta com anonimização dos dados |
| `CREATE` / `UPDATE` / `DELETE` | Inventário | Cadastro, edição e exclusão de equipamentos pela API |
| `CREATE` | Empréstimos | Nova solicitação de empréstimo, pela tela ou pela API |
| `UPDATE` | Empréstimos | Pedido de prorrogação pelo usuário; aprovação, rejeição, devolução e decisão de prorrogação pelo administrador |

Dois cuidados com o conteúdo dos registros:

- **O IP de origem** é lido do cabeçalho `X-Real-IP`, preenchido pelo Nginx com o endereço real do cliente, e validado como endereço IP (`auditoria/utils.py`). O cabeçalho `X-Forwarded-For`, que o próprio cliente pode forjar, não é utilizado.
- **O texto digitado não é gravado.** Nas falhas de login, a descrição é apenas "Credenciais inválidas", vinculada ao usuário quando a conta existe. Na recuperação, a descrição informa somente se o e-mail estava cadastrado. Assim, nenhum dado pessoal digitado, nem uma senha digitada por engano no campo de usuário, fica guardado em um registro que não pode ser apagado.

## 3. Exemplo de Análise
Abaixo, um recorte real da base de dados demonstrando a rastreabilidade de diferentes usuários no dia 20/09/2026:

| Data/Hora | Nome do Usuário | Ação | Módulo Afetado | IP de Origem |
| :--- | :--- | :--- | :--- | :--- |
| 20/09/2026 19:07:07 | TesteT | UPDATE | Privacidade/LGPD | 127.0.0.1 |
| 20/09/2026 19:06:11 | TesteT | RECUPERACAO | Autenticação/Recuperação | 127.0.0.1 |
| 20/09/2026 18:58:09 | Lucas | LOGIN_SUCESSO | Autenticação | 127.0.0.1 |
| 20/09/2026 18:56:00 | usuarioteste | 2FA_SUCESSO | Autenticação | 127.0.0.1 |
| 20/09/2026 18:55:55 | usuarioteste | 2FA_FALHA | Autenticação | 127.0.0.1 |
| 20/09/2026 18:55:23 | usuarioteste | LOGIN_FALHA | Autenticação | 127.0.0.1 |

O recorte foi obtido em ambiente local, por isso todos os acessos aparecem com o IP `127.0.0.1`. Ele é anterior à padronização das ações de recuperação de senha: o evento que aparece como `RECUPERACAO` é registrado hoje como `RECUPERACAO_SOLICITADA` ou `RECUPERACAO_SUCESSO`. Como os registros de auditoria são imutáveis, os registros antigos permanecem com a ação original.

## 4. Interpretação dos Eventos
A tabela ilustra três cenários distintos capturados com precisão pelo sistema de auditoria:
1. **Resiliência de Acesso:** às 18:55:23, o usuário usuarioteste falhou na autenticação primária. Logo em seguida, errou o código 2FA (18:55:55), mas obteve sucesso segundos depois (18:56:00), demonstrando a eficácia da barreira de segundo fator contra erros ou tentativas de acesso indevido.
2. **Acesso Normal:** o usuário Lucas autenticou-se de forma direta e bem-sucedida às 18:58:09.
3. **Recuperação e Privacidade:** o usuário TesteT realizou um processo de recuperação de credenciais às 19:06:11. Menos de um minuto depois (19:07:07), o sistema registrou um `UPDATE` no módulo `Privacidade/LGPD`, evidenciando que o usuário alterou o consentimento dos seus dados após recuperar a senha.

## 5. Identificação de Comportamentos Sensíveis
Por meio desses registros, o administrador do sistema consegue auditar não só quem entra e como entra, mas também as ações legais e operacionais. No Django Admin, os registros podem ser filtrados por ação, módulo e data, e pesquisados por nome de usuário, IP e descrição.

Alguns padrões que indicam comportamento anômalo:

- **Vários `LOGIN_FALHA` seguidos do mesmo IP**, em uma ou mais contas: tentativa de força bruta. Após 5 falhas na mesma combinação de IP e usuário, o `django-axes` bloqueia novas tentativas por 30 minutos.
- **`LOGIN_FALHA` em contas diferentes a partir do mesmo IP**: tentativa de descobrir senhas comuns em várias contas.
- **Sequência de `2FA_FALHA`** depois de um login com senha correta: a senha da conta pode ter sido comprometida.
- **Vários `RECUPERACAO_FALHA` por token inexistente**: tentativa de adivinhar tokens de recuperação.
- **`UPDATE` em `Segurança/2FA` com a desativação do 2FA** sem que o titular reconheça a ação: possível uso indevido da sessão. O titular também recebe um e-mail de aviso.
- **`DELETE` em `Inventário`** fora do padrão da equipe: exclusão indevida de equipamentos.

Se um IP malicioso tentasse forçar o login do usuário `TesteT`, por exemplo, os logs evidenciariam uma sequência de falhas em contraste com o comportamento normal verificado acima.

## 6. Integridade dos Registros
Para que os logs tenham validade legal e técnica, a sua integridade é protegida em **três camadas independentes**. O sistema opera em modo **append-only**: novos registros podem ser incluídos, mas os existentes não podem ser alterados nem excluídos.

1. **Django Admin** (`auditoria/admin.py`): as permissões de adicionar, editar e excluir são removidas (`has_add_permission`, `has_change_permission` e `has_delete_permission` retornam `False`), e todos os campos são somente leitura. O administrador pode consultar os registros, mas não modificá-los.
2. **Model e QuerySet** (`auditoria/models.py`): o método `save()` recusa salvar um registro que já existe, o método `delete()` recusa a exclusão, e um QuerySet próprio recusa as operações em lote `update()` e `delete()`. Isso protege os registros contra alterações feitas pelo código da aplicação, fora do Admin.
3. **Trigger no PostgreSQL** (migração `auditoria/migrations/0003_auto_20261012_1140.py`): uma trigger `BEFORE UPDATE OR DELETE` na tabela de auditoria levanta um erro em qualquer tentativa de alteração ou exclusão, inclusive por SQL direto, pelo pgAdmin ou pelo `psql`, contornando totalmente a aplicação.

A trigger abre uma única exceção, estreita: quando um usuário é excluído, o campo `usuario` do log passa a ser nulo (`on_delete=SET_NULL`), para que o registro sobreviva à exclusão da conta. A trigger só aceita essa mudança se todos os outros campos do registro permanecerem idênticos. Zerar o usuário e, ao mesmo tempo, alterar a descrição, a ação ou o IP é recusado.

As três camadas são verificadas pelos testes automatizados em `auditoria/tests.py`, descritos em `Testes de Seguranca.md`. Os limites residuais dessa proteção estão descritos em `Limitacoes.md`.

## 7. Conclusão
A centralização da auditoria se mostrou eficaz para mapear todo o ciclo de vida da identidade do usuário e as operações sobre o inventário e os empréstimos. Os logs são gerados com associação ao usuário, quando identificado, e ao IP real de origem, sem guardar dados digitados que não deveriam ser armazenados. Protegidos contra alteração e exclusão em três camadas, eles permitem diagnósticos rápidos e auditorias de conformidade transparentes.