# Autenticação

Esta documentação detalha os fluxos, as estratégias e a implementação prática dos mecanismos de autenticação do projeto EmprestaCampus, abrangendo tanto o consumo via API REST quanto a interface web tradicional.

---

### 1. Arquitetura Híbrida de Autenticação (SoC)

A aplicação adota o princípio de Separação de Conceitos (SoC) para atender a diferentes tipos de clientes:

- **API REST (Stateless):** destinada a integrações externas e a um futuro front-end desacoplado (SPA planejada), utilizando tokens de acesso baseados em JSON Web Tokens (JWT).
- **Interface Web (Stateful):** interface atual do sistema, construída com templates do Django, utilizando o sistema nativo de sessões e cookies.

Nos dois casos, a autenticação passa pela função `authenticate()` do Django, que é interceptada pelo `django-axes` (proteção contra força bruta) e, quando o usuário tem 2FA ativo, exige o código TOTP antes de conceder acesso.

### 2. Fluxo de Autenticação Web (Stateful)

Implementado na função `login_view` e associado à rota web (`entrar/`), gerencia o acesso de usuários à interface HTML:

- **Restrição de Método HTTP:** a requisição `GET` apenas exibe o formulário. As credenciais só são processadas em requisições `POST`, garantindo que trafeguem no corpo da requisição e não na URL.
- **Validação de Credenciais (`authenticate`):** o Django compara o hash da senha enviada com o armazenado no PostgreSQL. A tentativa é contabilizada pelo `django-axes`, que bloqueia a combinação de IP e usuário por 30 minutos após 5 erros e exibe a página `lockout.html`.
- **Segundo Fator (2FA):** se o usuário tem um dispositivo TOTP confirmado, a sessão ainda não é criada. O sistema guarda o usuário de forma provisória e redireciona para `2fa/validar/` (`validar_dois_fatores_view`), onde o código de 6 dígitos é conferido.
- **Criação de Sessão (`login`):** só depois da senha correta (e do código TOTP, quando houver), a função `login()` acopla o usuário à sessão e emite o cookie de sessão (`HttpOnly`). A sessão expira após 30 minutos de inatividade ou ao fechar o navegador.
- **Redirecionamento Pós-Login:** o sistema executa um redirecionamento controlado via `redirect('home')` para o endpoint protegido (`home_view`), que renderiza o painel inicial do usuário.
- **Conta Suspensa por Revogação de Consentimento (LGPD):** quando o titular revogou o consentimento, a conta fica inativa e o `authenticate()` não a aceita. Nesse caso, e somente se a senha digitada estiver correta, o usuário é levado à tela `reativar-conta/`, onde pode restaurar o consentimento. A autorização para reativar vale 5 minutos e é de uso único. Contas desativadas pelo administrador ou anonimizadas não têm acesso a essa tela.
- **Encerramento de Sessão (`logout`):** a rota `sair/` só aceita `POST` com token CSRF. Uma requisição `GET` apenas redireciona para a página inicial, sem deslogar, o que impede que um site externo encerre a sessão do usuário.

### 3. Fluxo de Autenticação via API REST (Stateless - JWT)

Utiliza a biblioteca `djangorestframework-simplejwt` para gerar os tokens, com um fluxo próprio em duas etapas para suportar o 2FA:

- **Primeira Etapa (`login_spa`):** mapeada na rota `login/spa/` (`LoginAPIView`), valida usuário e senha enviados via JSON.
  - Usuário **sem** 2FA: recebe diretamente o par de tokens (`access` e `refresh`).
  - Usuário **com** 2FA: recebe apenas `requer_2fa: true` e um token intermediário (`token_2fa`), assinado com a `SECRET_KEY` e válido por 5 minutos. Nenhum JWT é emitido nesta etapa, e o identificador do usuário não é exposto.
- **Segunda Etapa (`login_spa_2fa`):** mapeada na rota `login/spa/2fa/` (`VerificarDoisFatoresLoginView`), recebe o `token_2fa` e o código TOTP. Só com o token íntegro, dentro do prazo, e o código correto, emite o par de tokens JWT.
- **Renovação de Token (`login_renovar`):** mapeada na rota `login/renovar/` (`TokenRefreshView`), permite que o cliente obtenha um novo token de acesso utilizando o `refresh`, sem reenviar a senha.
- **Validade dos Tokens:** o token de acesso vale 1 hora e o `refresh` vale 7 dias.

A rota `login/` (`TokenObtainPairView`), que existia em versões anteriores, foi removida por emitir JWT sem passar pelo segundo fator.

### 4. Registro e Acesso Público (`RegistroView`)

O cadastro inicial de novos usuários é tratado pelo endpoint público `RegistroView` (herdando de `generics.CreateAPIView`), consumido pela tela `cadastrar/`:

- **Permissão Aberta (`AllowAny`):** configurado explicitamente para permitir o acesso de novos usuários sem a exigência de um token prévio.
- **Segurança na Criação:** a requisição delega a persistência ao `RegistroSerializer`, que exige senha de no mínimo 8 caracteres e invoca o método `set_password()` (hash PBKDF2-SHA256) antes de gravar o usuário. A senha é `write_only` e nunca aparece nas respostas da API.
- **Papel Restrito:** o cadastro público só aceita os papéis Aluno e Docente. Uma tentativa de se cadastrar como Administrador é recusada com erro 400; esse papel só é atribuído por um administrador.
- **Consentimento Obrigatório (LGPD):** o cadastro só é concluído com o aceite da Política de Privacidade (`consentimento_dados`). A data e a versão do aceite são registradas automaticamente.

### 5. Tratamento de Erros e Feedback Visual

O sistema utiliza o Django Messages Framework para gerenciar o feedback ao usuário na interface web:

- Em caso de falha na autenticação, a aplicação injeta a mensagem genérica `messages.error(request, 'Credenciais inválidas...')` no template `login.html`, sem indicar se o erro foi no usuário ou na senha.
- Código 2FA incorreto gera a mensagem "Código incorreto." na tela de validação.
- Na API, as falhas retornam mensagens igualmente genéricas, com status `401` (credenciais ou token intermediário inválidos) ou `400` (código TOTP incorreto).
- Todas as tentativas, com sucesso ou falha, são registradas na auditoria (`LOGIN_SUCESSO`, `LOGIN_FALHA`, `2FA_SUCESSO`, `2FA_FALHA`), com o IP de origem e sem gravar o texto digitado.

O front-end exibe dinamicamente o alerta visual em caso de erro, guiando o usuário sem expor detalhes que ajudem um atacante.

### 6. Resumo dos Fluxos de Autenticação

| Tipo de Fluxo | Endpoint / Rota | Tecnologia / Componente | Finalidade Principal |
| :--- | :--- | :--- | :--- |
| Autenticação Web | `/api/usuarios/entrar/` | `login_view` + `authenticate()` + `login()` | Acesso via navegador com sessão e cookies. |
| Validação 2FA (Web) | `/api/usuarios/2fa/validar/` | `validar_dois_fatores_view` (`django-otp`) | Conferir o código TOTP antes de criar a sessão. |
| Reativação de Conta | `/api/usuarios/reativar-conta/` | `reativar_conta_lgpd_view` | Restaurar o consentimento, somente após senha correta. |
| Encerramento de Sessão | `/api/usuarios/sair/` | `logout_view` (somente `POST`) | Encerrar a sessão web com proteção CSRF. |
| Login JWT — Etapa 1 | `/api/usuarios/login/spa/` | `LoginAPIView` | Validar a senha e emitir JWT ou token intermediário de 2FA. |
| Login JWT — Etapa 2 | `/api/usuarios/login/spa/2fa/` | `VerificarDoisFatoresLoginView` | Validar o código TOTP e emitir o par de tokens JWT. |
| Renovação de Token | `/api/usuarios/login/renovar/` | `TokenRefreshView` (SimpleJWT) | Estender a sessão da API sem reenvio de credenciais. |
| Cadastro Público | `/api/usuarios/registro/` | `RegistroView` (`AllowAny`) | Porta de entrada para novos cadastros de usuários. |
| Página Inicial | `/api/usuarios/home/` | `home_view` (template `home.html`) | Painel do usuário após o login. |

### 7. Considerações

Os mecanismos de autenticação implementados combinam a flexibilidade de uma API baseada em tokens com a robustez de uma aplicação web baseada em sessões do Django. Em ambos os caminhos, a senha é validada por hash, as tentativas são limitadas pelo `django-axes`, o segundo fator é exigido antes de qualquer acesso quando ativado, e cada tentativa fica registrada na auditoria.