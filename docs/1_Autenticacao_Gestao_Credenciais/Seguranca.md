# Segurança


Esta documentação apresenta os principais recursos de segurança implementados no projeto **EmprestaCampus**. Os mecanismos descritos correspondem estritamente às funcionalidades presentes no código atual da aplicação.

## 1. Armazenamento de senhas

- As senhas são armazenadas com **PBKDF2-SHA256 com 600.000 iterações**, definidas na subclasse `PBKDF2HasherReforcado` (`usuarios/hashers.py`) e registradas em `PASSWORD_HASHERS` (`config/settings.py`).
- Cada senha recebe um **salt aleatório próprio**, então duas contas com a mesma senha geram hashes diferentes.
- O banco guarda apenas o formato `pbkdf2_sha256$600000$<salt>$<hash>`. A senha original nunca é persistida.

**Justificativa:** 600.000 iterações é o mínimo recomendado pela OWASP para PBKDF2-SHA256 (OWASP, Password Storage Cheat Sheet). O número fica fixado no código, em vez de depender do valor padrão da versão instalada do Django. O PBKDF2 foi preferido ao Argon2 por ser nativo do Django, não exigir dependência externa e ser aceito pela NIST SP 800-63B. O Argon2, por exigir muita memória, resiste melhor a ataques com GPU e é a evolução natural (ver seção 11).

## 2. Regras de senha

- O cadastro (`RegistroSerializer`) e a redefinição de senha (`RedefinirSenhaView`) exigem **no mínimo 8 caracteres**.
- O `settings.py` declara os validadores do Django em `AUTH_PASSWORD_VALIDATORS` (similaridade com dados do usuário, tamanho mínimo, senhas comuns e senhas só numéricas), mas **eles não são chamados pelas views**. Hoje uma senha como `12345678` é aceita. Essa é uma limitação conhecida (seção 11).

## 3. Autenticação de dois fatores (2FA)

- Implementada com **TOTP** (`django-otp`), opcional por usuário, ativada pela leitura de um QR Code em "Meu Perfil".
- **Login web:** a sessão só é criada depois do código TOTP correto.
- **Login pela API:** a primeira etapa (`login/spa/`) devolve apenas um token intermediário assinado com a `SECRET_KEY`, válido por 5 minutos. O JWT só é emitido na segunda etapa (`login/spa/2fa/`), com o código correto. O identificador do usuário nunca é exposto ao cliente.
- Tentativas de código erradas sofrem atraso progressivo (throttling nativo do `django-otp`).
- O usuário pode desativar o 2FA. A desativação é registrada na auditoria e o dono da conta é avisado por e-mail.

**Justificativa:** o TOTP (RFC 6238) funciona offline, não depende de operadora e não sofre com interceptação de SMS ou troca de chip, motivos pelos quais a NIST SP 800-63B restringe o SMS como segundo fator.

## 4. Proteção contra força bruta

- O `django-axes` bloqueia o login depois de **5 tentativas erradas**, por **30 minutos** (`AXES_FAILURE_LIMIT = 5`, `AXES_COOLOFF_TIME = 0.5`).
- O bloqueio é pela **combinação de IP e usuário** (`AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]`). Atrás do Nginx, um bloqueio só por IP derrubaria todos os usuários, porque todos chegariam com o mesmo endereço.
- O IP usado pelo axes é o mesmo da auditoria (`AXES_CLIENT_IP_CALLABLE`, seção 9).
- Cobre o login web e o login pela API, já que os dois usam `authenticate()`. Há uma página própria de bloqueio (`lockout.html`).

**Justificativa:** 5 tentativas equilibram usabilidade (erros de digitação) e proteção. O bloqueio temporário, em vez de permanente, evita que um atacante bloqueie contas de propósito por tempo indeterminado.

## 5. Mitigação de enumeração de usuários

- O login responde sempre "Credenciais inválidas", exista a conta ou não.
- A recuperação de senha responde sempre "Se o e-mail existir, um link de recuperação foi enviado".
- A tela de reativação de conta só aparece depois da senha correta. Ela não revela a existência da conta a quem não sabe a senha.

## 6. Sessão, cookies e logout

- Sessão web expira após **30 minutos de inatividade** (`SESSION_COOKIE_AGE = 1800`, renovada a cada requisição) e ao fechar o navegador.
- O cookie de sessão é `HttpOnly` (padrão do Django), o que impede sua leitura por JavaScript.
- Com `DEBUG=False`, os cookies de sessão e CSRF só trafegam por HTTPS (`SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE`).
- Formulários protegidos por token CSRF (`CsrfViewMiddleware`).
- O **logout só aceita POST**, com token CSRF. Um site externo não consegue deslogar o usuário com um simples link ou imagem.
- JWT: token de acesso válido por 1 hora e refresh por 7 dias.

## 7. Controle de acesso (RBAC)

- O campo `papel` do usuário (Aluno, Docente ou Administrador) é a fonte única de privilégios. O `save()` do model sincroniza `is_staff` e `is_superuser` com o papel ADMIN, e só com ele.
- O cadastro público só aceita os papéis Aluno e Docente. Um pedido com `"papel": "ADMIN"` é recusado com erro 400.
- A escrita no inventário pela API exige o papel ADMIN (permissão `IsAdmin`). A leitura exige apenas estar autenticado.
- Aprovação de empréstimos e prorrogações é feita pelo Django Admin, acessível apenas ao ADMIN.

## 8. Recuperação de senha

- Token gerado com `secrets.token_urlsafe(32)` (256 bits), válido por 1 hora e de uso único.
- Ao redefinir a senha, **todos os tokens pendentes do usuário são invalidados**.
- O link é enviado por e-mail (SMTP, ou console em desenvolvimento). Detalhes em `RecSenha.md`.

## 9. Auditoria

- Eventos de autenticação, 2FA, recuperação, LGPD, inventário e empréstimos são registrados em `RegistroAuditoria`.
- Os registros são **imutáveis em três camadas**: Django Admin, model/queryset e trigger no PostgreSQL.
- O IP vem do cabeçalho `X-Real-IP`, preenchido pelo Nginx, validado como endereço IP. O cabeçalho `X-Forwarded-For`, que o cliente pode forjar, não é usado.
- O texto digitado no login e o e-mail digitado na recuperação não são gravados, evitando dados pessoais (ou senhas digitadas no campo errado) num log que não pode ser apagado.

Detalhes em `Auditoria e Logs.md`.

## 10. Criptografia, comunicação e configuração

- **Em trânsito:** HTTPS/TLS no Nginx (porta 443), com redirecionamento 301 da porta 80. Com `DEBUG=False`, o Django também força HTTPS (`SECURE_SSL_REDIRECT`) e envia HSTS por 30 dias.
- **Em repouso:** o telefone é cifrado com **Fernet** (AES-128-CBC com HMAC-SHA256), com chave própria (`ENCRYPTION_KEY`), separada da `SECRET_KEY`.
- **Cabeçalhos:** `X-Frame-Options: DENY` (clickjacking) e `X-Content-Type-Options: nosniff` (MIME sniffing).
- **Segredos:** `SECRET_KEY`, `ENCRYPTION_KEY`, senha do banco e credenciais SMTP vêm do `.env`, que não é versionado. `DEBUG` e `ALLOWED_HOSTS` também vêm do `.env`.
- **LGPD:** consentimento obrigatório no cadastro, revogação com suspensão da conta, reativação apenas com a senha do titular, exportação dos dados em JSON e encerramento com anonimização (nome, username, e-mail, matrícula, telefone, dispositivo 2FA e tokens de recuperação).

Detalhes em `criptografia.md` e na Política de Privacidade.