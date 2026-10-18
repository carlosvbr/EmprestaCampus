# Gestao-Credenciais


Este documento detalha a implementação das funcionalidades de gerenciamento de credenciais do sistema **EmprestaCampus**: como a credencial é criada, armazenada, verificada, trocada, revogada e encerrada. A estrutura descreve as escolhas arquiteturais e a relação direta com os arquivos e funções desenvolvidos no código-fonte. Os fluxos de login, passo a passo, estão descritos em `Autenticacao.md`.

---

### 1. Cadastro de Usuários (API REST)
* O cadastro inicial de novos usuários é processado pela classe `RegistroView`, localizada em `usuarios/views.py`, e consumido pela tela `cadastrar/`.
* A view herda de `generics.CreateAPIView` e possui permissão pública (`permissions.AllowAny`), permitindo o registro de contas sem autenticação prévia.
* A senha enviada na requisição é recebida pelo `RegistroSerializer`, que exige no mínimo 8 caracteres, marca o campo como `write_only` (a senha nunca aparece em respostas da API) e delega o hash ao método nativo `set_password()`.
* **Segurança:** o hash é feito com **PBKDF2-SHA256 com 600.000 iterações**, definidas na subclasse `PBKDF2HasherReforcado` (`usuarios/hashers.py`) e registradas em `PASSWORD_HASHERS`. Cada senha recebe um salt aleatório próprio, e o banco guarda apenas o formato `pbkdf2_sha256$600000$<salt>$<hash>`. A senha em texto puro nunca é persistida no PostgreSQL.
* **Papel restrito:** o cadastro público só aceita os papéis Aluno e Docente. Um pedido com o papel Administrador é recusado com erro 400.
* **Consentimento:** a conta só é criada com o aceite da Política de Privacidade; a data e a versão do aceite são gravadas automaticamente.

### 2. Autenticação Web (Stateful)
* O fluxo de login visual é implementado pela função `login_view()` em `usuarios/views.py`, voltada para a interface HTML do sistema.
* As credenciais só são processadas em requisições `POST`; a requisição `GET` apenas exibe o formulário. Isso evita o vazamento de parâmetros sensíveis na URL.
* O sistema utiliza a função `authenticate()` do Django para validar o usuário e a senha. Essa camada compara o hash da senha digitada com o armazenado e usa o ORM, que impede **SQL Injection** nas consultas.
* Cada tentativa passa pelo `django-axes`, que bloqueia a combinação de IP e usuário por 30 minutos após 5 erros.
* Quando o usuário tem 2FA ativo, a senha correta não basta: o código TOTP é exigido antes da criação da sessão. Caso as credenciais estejam erradas, o sistema emite uma mensagem genérica via `messages.error`, para não revelar se a conta existe.
* **Segundo fator como credencial adicional:**
  * **Ativação:** em "Meu Perfil" (`perfil/2fa/`, `configurar_2fa_view`), o sistema gera um dispositivo TOTP e exibe o QR Code. O dispositivo só passa a valer depois que o usuário confirma um código correto. Códigos errados na ativação são registrados na auditoria. A API oferece o mesmo fluxo em `2fa/ativar/` e `2fa/confirmar/`.
  * **Revogação:** o usuário pode desativar o 2FA (`perfil/2fa/revogar/`, somente `POST`). Todos os dispositivos TOTP dele são apagados, a ação é registrada na auditoria e o dono da conta recebe um aviso por e-mail.

### 3. Gerenciamento de Sessão e Controle de Acesso
* O estado de login da interface web utiliza sessões nativas do Django, armazenadas no banco de dados e identificadas por um cookie `HttpOnly`. Com `DEBUG=False`, o cookie só trafega por HTTPS.
* A sessão expira após **30 minutos de inatividade** (`SESSION_COOKIE_AGE = 1800`, renovada a cada requisição) e também ao fechar o navegador.
* O logout (`sair/`) só aceita `POST` com token CSRF, o que impede que um site externo encerre a sessão do usuário.
* As rotas protegidas usam `@login_required` e redirecionam quem não está autenticado para o login (`LOGIN_URL`).
* **Controle de acesso por papel (RBAC):** o campo `papel` é a fonte única de privilégios. O `save()` do model `Usuario` sincroniza `is_staff` e `is_superuser` com o papel Administrador, e só com ele. O comando `createsuperuser` cria a conta já com esse papel (`UsuarioManager`).
* **Troca de senha (recuperação):** o usuário solicita um link por e-mail (`recuperar-senha/`). O token é gerado com `secrets.token_urlsafe(32)`, vale 1 hora e é de uso único. Ao redefinir a senha (`redefinir-senha/`), a nova senha passa por `set_password()` e **todos os tokens pendentes do usuário são invalidados**. Detalhes em `RecSenha.md`.
* **Suspensão por revogação de consentimento:** ao revogar o consentimento, a conta fica inativa e a credencial deixa de ser aceita. O titular só consegue reativá-la informando a senha correta no login.
* **Encerramento da conta:** em "Encerrar Minha Conta" (`perfil/encerrar-conta/`, somente `POST`), a senha se torna inutilizável (`set_unusable_password()`), os dispositivos TOTP e os tokens de recuperação são apagados, e o username e o e-mail são anonimizados. A credencial deixa de existir de forma irreversível.

### 4. Isolamento de Rotas e Separação de Conceitos (SoC)
* O roteamento do módulo (`usuarios/urls.py`) aplica o princípio de separação arquitetural ao isolar dois paradigmas distintos:
  * **APIs Stateless (JSON):** registro (`registro/`), login JWT em duas etapas com 2FA (`login/spa/` e `login/spa/2fa/`), renovação do token (`login/renovar/`, `TokenRefreshView`), recuperação de senha (`recuperar-senha/` e `redefinir-senha/`) e ativação do 2FA (`2fa/ativar/` e `2fa/confirmar/`).
  * **Rotas Stateful (HTML):** login (`entrar/`), validação do 2FA (`2fa/validar/`), página inicial (`home/`), logout (`sair/`), cadastro (`cadastrar/`), telas de recuperação (`esqueci-minha-senha/`), perfil e suas ações (`perfil/...`) e reativação de conta (`reativar-conta/`).
* A nomenclatura das rotas foi isolada de forma explícita (por exemplo, `login_spa`, `login_spa_2fa` e `login_web`) para evitar colisões no roteamento reverso do framework.
* A rota `login/` (`TokenObtainPairView`), de versões anteriores, foi removida porque emitia JWT sem passar pelo segundo fator.

### 5. Estrutura de Arquivos Envolvidos
* **`usuarios/views.py`**: cadastro (`RegistroView`), login web (`login_view`) e via API (`LoginAPIView`, `VerificarDoisFatoresLoginView`), 2FA (ativação, validação e revogação), recuperação de senha, logout, reativação e encerramento de conta.
* **`usuarios/urls.py`**: mapeamento das rotas, separando as APIs JSON das rotas baseadas em sessão HTML.
* **`usuarios/serializers.py`**: validação dos dados de cadastro, restrição de papel, consentimento obrigatório e hash da senha.
* **`usuarios/models.py`**: model `Usuario` (papel, sincronização de privilégios, consentimento) e `TokenRecuperacaoSenha` (token, expiração e uso único).
* **`usuarios/hashers.py`**: hasher `PBKDF2HasherReforcado`, com as 600.000 iterações.
* **`config/settings.py`**: hashers, sessão, cookies, `django-axes` e SimpleJWT.
* **`templates/usuarios/`**: `login.html`, `validar_2fa.html`, `configurar_2fa.html`, `perfil.html`, `reativar_conta.html` e `lockout.html`. Todos os formulários usam a tag `{% csrf_token %}` contra falsificação de solicitações entre sites.

### 6. Considerações Finais
As funcionalidades descritas correspondem à implementação técnica entregue no repositório. A credencial do usuário é protegida em todo o seu ciclo de vida: criada com hash forte, verificada com limite de tentativas e segundo fator opcional, trocada por um token de uso único e encerrada de forma irreversível. O funcionamento é comprovado pela interface web e pelos testes automatizados em `usuarios/tests_seguranca.py`.