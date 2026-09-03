# Segurança


Esta documentação apresenta os principais recursos de segurança implementados no projeto **EmprestaCampus**. Os mecanismos descritos correspondem estritamente às funcionalidades presentes no código atual da aplicação.

---

### 1. Proteção das Senhas
* O projeto delega o gerenciamento de credenciais ao sistema de autenticação nativo do Django (`django.contrib.auth`).
* Durante o cadastro de novos usuários na classe `RegistroView` e no `RegistroSerializer`, a senha recebida em texto plano é processada pelo método `set_password()`.
* **Segurança:** O sistema aplica o algoritmo de hash **PBKDF2** com salt de forma automática, garantindo que senhas em texto puro nunca sejam persistidas na base de dados PostgreSQL.

### 2. Validação de Senhas
* O projeto utiliza os validadores de senha padrão do Django configurados no arquivo de configurações globais (`settings.py`).
* Entre as regras aplicadas para mitigar o uso de credenciais fracas estão:
  * `MinimumLengthValidator` (restrição de tamanho mínimo).
  * `CommonPasswordValidator` (bloqueio de senhas comuns baseadas em listas conhecidas).
  * `NumericPasswordValidator` (prevenção contra senhas inteiramente numéricas).

### 3. Mitigação de Ataques de Enumeração de Usuários
* O fluxo de autenticação visual implementado na função `login_view()` adota uma estratégia defensiva no tratamento de falhas.
* Quando o método `authenticate()` retorna credenciais inválidas, a aplicação emite uma mensagem genérica de erro (`messages.error`) para a interface web.
* **Segurança:** Essa prática impede que atacantes descubran quais nomes de usuário ou e-mails estão cadastrados no sistema através da variação de mensagens de erro.

### 4. Proteção da Sessão e Cookies HTTP-only
* O gerenciamento de estado da interface web utiliza sessões nativas do Django atreladas ao SGBD.
* Os cookies de sessão gerados pelo framework após o sucesso da autenticação utilizam a diretiva de segurança **`SESSION_COOKIE_HTTPONLY = True`**.
* **Segurança:** Essa configuração impede que scripts maliciosos executados no navegador (como ataques de XSS) tenham acesso direto ao identificador da sessão através de JavaScript.

### 5. Controle de Acesso e Redirecionamento Seguro
* O roteamento da aplicação (`usuarios/urls.py`) aplica o princípio de **Separação de Conceitos (SoC)**, isolando os endpoints de API REST (protegidos via SimpleJWT) das rotas baseadas em sessão HTML.
* O fluxo de login visual obriga o uso do método HTTP `POST`, blindando o envio de credenciais contra vazamento de parâmetros sigilosos na barra de endereços (via GET).
* Após o sucesso da validação, a função `login()` acopla o usuário à sessão e executa o redirecionamento controlado para a rota protegida (`home_view`).

### 6. Resumo dos Mecanismos de Segurança

| Mecanismo de Segurança | Implementação Técnica | Finalidade Principal |
| :--- | :--- | :--- |
| **Hash de Senha** | Método `set_password()` (PBKDF2) | Evitar armazenamento de senhas em texto plano no SGBD. |
| **Validação de Força** | Validadores nativos do Django | Impedir o cadastro de senhas fracas ou previsíveis. |
| **Prevenção contra Enumeração** | Mensagens genéricas via `messages.error` | Ocultar a existência de contas válidas em tentativas de login falhas. |
| **Proteção de Sessão** | `SESSION_COOKIE_HTTPONLY = True` | Bloquear o roubo de sessão por scripts JavaScript (XSS). |
| **Método de Envio HTTP** | Restrição estrita ao método `POST` | Ocultar credenciais do histórico e da URL do navegador. |

### 7. Considerações
Os mecanismos apresentados foram estruturados com o objetivo de proteger o processo de autenticação e assegurar a integridade dos dados dos usuários. As funcionalidades podem ser validadas por meio da execução local do sistema e dos testes de fluxo realizados no front-end.