# Recuperação de Senha — EmprestaCampus

## 1. Objetivo

Documentar o funcionamento da recuperação de senha do EmprestaCampus, permitindo que usuários que esqueceram suas credenciais recuperem o acesso ao sistema por meio de um link enviado ao e-mail cadastrado.

## 2. Solicitação de recuperação

A solicitação é realizada pela `SolicitarRecuperacaoSenhaView`, a partir da tela "Esqueci minha senha".

### Funcionamento

1. O usuário informa o e-mail cadastrado.
2. O backend recebe o e-mail.
3. O sistema procura o usuário com esse e-mail.
4. A solicitação é registrada no `RegistroAuditoria` com a ação `RECUPERACAO_SOLICITADA`, exista ou não uma conta com aquele e-mail.
5. Caso o usuário exista, é criado um token de recuperação.
6. O sistema envia ao e-mail do usuário um link para a tela de redefinição, contendo o token. O e-mail informa que o link vale por 1 hora e só pode ser usado uma vez.
7. A API retorna uma mensagem de confirmação.

O envio é feito pela função `enviar_email` (`notificacoes/utils.py`), por SMTP quando o servidor de e-mail está configurado no `.env` (`SMTP_HOST`), ou pelo console do servidor em ambiente de desenvolvimento. Uma falha no envio é registrada no log da aplicação e não altera a resposta da API.

### Comportamento de segurança

A API retorna a mesma mensagem ("Se o e-mail existir, um link de recuperação foi enviado.") mesmo quando o e-mail não está cadastrado. Isso evita que alguém descubra quais e-mails possuem conta no sistema.

## 3. Redefinição de senha

A redefinição é realizada pela `RedefinirSenhaView`.

### Funcionamento

1. O usuário acessa o link recebido.
2. O frontend confere se a nova senha e a confirmação são iguais e envia o token e a nova senha.
3. O backend verifica se o token existe.
4. O sistema verifica se o token ainda é válido (dentro de 1 hora).
5. O sistema verifica se o token já foi utilizado.
6. A nova senha é validada.
7. A senha é atualizada com hash (`set_password`).
8. O token utilizado e **todos os demais tokens pendentes do mesmo usuário** são marcados como utilizados.
9. O sistema registra o sucesso da operação.
10. A API retorna a confirmação.

Se qualquer verificação dos passos 3 a 6 falhar, a senha não é alterada, a falha é registrada na auditoria e a API retorna erro `400` com o motivo ("Token inválido.", "Token expirado.", "Token já utilizado." ou a regra de senha não atendida).

## 4. Requisitos funcionais

| ID   | Requisito                                                       |
| ---- | --------------------------------------------------------------- |
| RF01 | O sistema deve permitir solicitar a recuperação de senha.       |
| RF02 | O sistema deve receber o e-mail do usuário.                     |
| RF03 | O sistema deve registrar a solicitação de recuperação.          |
| RF04 | O sistema deve gerar um token de recuperação.                   |
| RF05 | O sistema deve enviar o link de recuperação por e-mail.         |
| RF06 | O sistema deve validar o token recebido.                        |
| RF07 | O sistema deve impedir o uso de token expirado ou já utilizado. |
| RF08 | O sistema deve validar a nova senha.                            |
| RF09 | O sistema deve atualizar a senha do usuário.                    |
| RF10 | O sistema deve registrar o resultado da recuperação.            |
| RF11 | O sistema deve invalidar os demais tokens pendentes do usuário após a redefinição. |

## 5. Requisitos não funcionais

| ID    | Requisito                                                       |
| ----- | --------------------------------------------------------------- |
| RNF01 | A senha deve ser armazenada utilizando hash.                    |
| RNF02 | O token deve possuir validade limitada.                         |
| RNF03 | O token deve ser utilizado apenas uma vez.                      |
| RNF04 | O sistema não deve revelar se um e-mail está cadastrado.        |
| RNF05 | O sistema deve registrar eventos de recuperação para auditoria. |
| RNF06 | O processo deve utilizar comunicação segura.                    |

## 6. Validações

### Token

O token é gerado pelo model `TokenRecuperacaoSenha` com `secrets.token_urlsafe(32)`, uma fonte criptograficamente segura que produz 256 bits aleatórios (não sequencial nem previsível). Ele expira 1 hora após a criação (`expira_em`).

O sistema verifica:

* Se o token existe.
* Se o token ainda está válido.
* Se o token já foi utilizado.

### Nova senha

A senha deve possuir pelo menos **8 caracteres**. Ela é gravada com hash PBKDF2-SHA256 (600.000 iterações), como no cadastro.

## 7. Auditoria

O sistema utiliza o modelo `RegistroAuditoria` (app `auditoria`) para registrar eventos relacionados à recuperação de senha, no módulo `Autenticação/Recuperação`. Cada registro guarda a data e hora, o usuário (quando identificado) e o IP de origem. Os registros não podem ser alterados nem excluídos.

### Eventos registrados

* `RECUPERACAO_SOLICITADA` — pedido de recuperação. A descrição indica apenas se o e-mail estava cadastrado ou não; o e-mail digitado não é gravado.
* `RECUPERACAO_FALHA` — token inexistente, expirado ou já utilizado, ou nova senha fora da regra.
* `RECUPERACAO_SUCESSO` — senha redefinida.

Os registros permitem acompanhar solicitações, falhas de recuperação e alterações concluídas. Registros anteriores à padronização dessas ações aparecem com as ações genéricas `RECUPERACAO` e `UPDATE`.

## 8. Observações

A implementação da recuperação de senha está localizada no módulo `usuarios` do backend.

| Tipo | Rota | Componente | Função |
| ---- | ---- | ---------- | ------ |
| API | `POST /api/usuarios/recuperar-senha/` | `SolicitarRecuperacaoSenhaView` | Recebe o e-mail e envia o link. |
| API | `POST /api/usuarios/redefinir-senha/` | `RedefinirSenhaView` | Recebe o token e a nova senha. |
| Tela | `/api/usuarios/esqueci-minha-senha/` | `recuperar_senha.html` | Formulário de solicitação. |
| Tela | `/api/usuarios/esqueci-minha-senha/confirmar/?token=...` | `redefinir_senha.html` | Formulário de nova senha, aberto pelo link do e-mail. |

Arquivos envolvidos: `usuarios/views.py` (views), `usuarios/models.py` (`TokenRecuperacaoSenha`), `usuarios/urls.py` (rotas), `notificacoes/utils.py` (envio do e-mail) e `config/settings.py` (configuração de e-mail em `MAILERS`).