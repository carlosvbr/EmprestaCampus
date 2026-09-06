# Recuperação de Senha — EmprestaCampus

## 1. Objetivo

Documentar o funcionamento da recuperação de senha do EmprestaCampus, permitindo que usuários que esqueceram suas credenciais recuperem o acesso ao sistema por meio de um link enviado ao e-mail cadastrado.

## 2. Solicitação de recuperação

A solicitação é realizada pela `SolicitarRecuperacaoSenhaView`.

### Funcionamento

1. O usuário informa o e-mail cadastrado.
2. O backend recebe o e-mail.
3. O sistema procura o usuário.
4. A solicitação é registrada no `LogAutenticacao`.
5. Caso o usuário exista, é criado um token de recuperação.
6. O sistema envia um link para redefinição de senha.
7. A API retorna uma mensagem de confirmação.

### Comportamento de segurança

A API retorna a mesma mensagem mesmo quando o e-mail não está cadastrado. Isso evita que alguém descubra quais e-mails possuem conta no sistema.

## 3. Redefinição de senha

A redefinição é realizada pela `RedefinirSenhaView`.

### Funcionamento

1. O usuário acessa o link recebido.
2. O frontend envia o token e a nova senha.
3. O backend verifica se o token existe.
4. O sistema verifica se o token ainda é válido.
5. O sistema verifica se o token já foi utilizado.
6. A nova senha é validada.
7. A senha é atualizada.
8. O token é marcado como utilizado.
9. O sistema registra o sucesso da operação.
10. A API retorna a confirmação.

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

O sistema verifica:

* Se o token existe.
* Se o token ainda está válido.
* Se o token já foi utilizado.

### Nova senha

A senha deve possuir pelo menos **8 caracteres**.

## 7. Auditoria

O sistema utiliza o modelo `LogAutenticacao` para registrar eventos relacionados à recuperação de senha.

### Eventos registrados

* `SOLICITACAO_RECUPERACAO`
* `RECUPERACAO_FALHA`
* `RECUPERACAO_SUCESSO`

Os registros permitem acompanhar solicitações, falhas de recuperação e alterações concluídas.

## 8. Observações

A implementação da recuperação de senha está localizada no módulo `usuarios` do backend.

Os endpoints e os detalhes de integração com o frontend devem ser documentados conforme as rotas definidas no arquivo `urls.py`.
