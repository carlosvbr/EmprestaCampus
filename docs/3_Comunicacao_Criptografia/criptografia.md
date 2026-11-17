# Criptografia e Comunicação Segura


Os principais arquivos relacionados à implementação são:

```
backend/
├── .env.example
├── .dockerignore
├── config/
│   └── settings.py
│
└── usuarios/
    ├── crypto.py
    ├── hashers.py
    ├── models.py
    ├── tests_criptografia.py
    ├── migrations/
    │   └── 0011_migrar_dispositivos_totp.py
    └── management/commands/
        └── rotacionar_chave_criptografia.py

nginx/
└── nginx.conf

docker-compose.yml
.gitignore
```

------------------------------------------------------------------------

## Hash e Criptografia

### Hash

O hash é utilizado para proteger as senhas dos usuários.

O fluxo pode ser representado da seguinte forma:

```
Senha informada pelo usuário
            |
            v
   PBKDF2-SHA256 (600.000 iterações + salt)
            |
            v
       Hash da senha
            |
            v
       Banco de dados
```

Durante a autenticação, a senha informada no login é processada pelo mesmo mecanismo de hash, com o mesmo salt, e o resultado é comparado com o valor armazenado.

Portanto:

```
Senha → Hash

Hash → Senha original
       NÃO É POSSÍVEL
```

Essa característica torna o hash adequado para armazenamento de senhas.

### Criptografia

A criptografia é utilizada quando o sistema precisa proteger uma informação, mas ainda precisa conseguir recuperar o valor original posteriormente.

Um exemplo é o número de telefone do usuário, que é exibido ao próprio titular em "Meu Perfil" e incluído na exportação de dados.

O fluxo é:

```
Telefone original
       |
       v
 Criptografia (Fernet + ENCRYPTION_KEY)
       |
       v
Texto cifrado
       |
       v
Banco de dados
```

Quando a aplicação precisa utilizar o telefone:

```
Texto cifrado
       |
       v
Descriptografia
       +
Chave correta
       |
       v
Telefone original
```

Dessa forma:

```
Hash:

Senha → Hash
Hash → Senha original
       NÃO É POSSÍVEL


Criptografia:

Telefone → Texto cifrado
Texto cifrado → Telefone   (somente com a chave correta)
```

A criptografia é reversível quando a chave correta está disponível.

------------------------------------------------------------------------

## Comunicação protegida por TLS/HTTPS

Utilizamos o **Nginx** como servidor responsável por receber as conexões externas e encaminhá-las para o backend Django.

O arquivo responsável por essa configuração é:

```
nginx/nginx.conf
```

A configuração do Nginx utiliza a porta `443` com SSL/TLS:

```nginx
server {
    listen 443 ssl;

    server_name localhost;

    ssl_certificate /etc/nginx/certs/localhost.crt;
    ssl_certificate_key /etc/nginx/certs/localhost.key;
}
```

A porta `443` é utilizada para conexões HTTPS.

O certificado e sua respectiva chave privada são configurados através das diretivas `ssl_certificate` e `ssl_certificate_key`. Em ambiente local, o certificado é autoassinado e fica na pasta `nginx/certs/`, que não é versionada.

O Nginx também encaminha as requisições para o backend:

```nginx
location / {
    proxy_pass http://backend:8000;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

O cabeçalho `X-Forwarded-Proto` informa ao Django que a conexão original foi feita por HTTPS. O cabeçalho `X-Real-IP`, que o Nginx preenche com o IP real do cliente, é o utilizado pela auditoria e pelo bloqueio de força bruta.

O fluxo de comunicação é:

```
Cliente
   |
   | HTTPS / TLS (porta 443)
   v
 Nginx
   |
   | HTTP (rede interna do Docker)
   v
Backend Django
   |
   v
PostgreSQL
```

Dessa forma, a comunicação externa da aplicação utiliza HTTPS/TLS para proteger os dados durante a transmissão. O trecho entre o Nginx e o Django trafega em HTTP, mas apenas dentro da rede interna do Docker: a porta `8000` do backend não é publicada para fora (`expose`, e não `ports`, no `docker-compose.yml`).

------------------------------------------------------------------------

## Bloqueio de conexões não seguras

O sistema possui uma proteção para evitar que a aplicação seja utilizada através de uma conexão HTTP não protegida.

No arquivo `nginx/nginx.conf` existe a seguinte configuração:

```nginx
server {
    listen 80;
    server_name localhost;

    return 301 https://$host$request_uri;
}
```

Quando o usuário acessa `http://localhost`, o Nginx responde com o código `301` e redireciona para `https://localhost`.

Dessa forma, o acesso à aplicação é direcionado para uma conexão protegida por TLS.

Além da configuração do Nginx, o Django possui uma camada adicional de proteção. No arquivo `backend/config/settings.py` está configurado:

```python
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

A configuração `SECURE_SSL_REDIRECT` faz com que, em produção (`DEBUG=False`), o próprio Django também redirecione requisições HTTP para HTTPS. Essa camada é redundante de propósito: protege a aplicação mesmo que algum dia ela seja exposta sem o Nginx na frente. O `SECURE_PROXY_SSL_HEADER` permite ao Django reconhecer, pelo cabeçalho enviado pelo Nginx, que a conexão original já era HTTPS.

O valor de `DEBUG` vem do arquivo `.env`. O `.env.example` traz `DEBUG=True` para facilitar o desenvolvimento local; em produção ou na demonstração das proteções, o valor deve ser `DEBUG=False`.

------------------------------------------------------------------------

## Evidência de tráfego cifrado

A evidência de utilização de tráfego cifrado está presente na configuração do Nginx (`listen 443 ssl`, com `ssl_certificate` e `ssl_certificate_key`) e nos prints da pasta `docs/Evidencias/3_Comunicacao_Criptografia/`, que mostram o acesso por HTTPS, o certificado e o redirecionamento.

O `docker-compose.yml` disponibiliza as portas HTTP e HTTPS do Nginx:

```yaml
ports:
  - "80:80"
  - "443:443"
```

### Proteções adicionais

O Django também possui configurações relacionadas à proteção de cookies e cabeçalhos. No arquivo `backend/config/settings.py` existem:

```python
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```

Com `DEBUG=False`:

- os cookies de sessão e de CSRF só são enviados por conexões HTTPS;
- o cabeçalho HSTS instrui o navegador a usar apenas HTTPS para o domínio durante 30 dias.

Em qualquer modo, o `nosniff` impede que o navegador interprete um arquivo com tipo diferente do declarado, e o `X-Frame-Options: DENY` impede que o sistema seja carregado dentro de um `<iframe>` (clickjacking).

------------------------------------------------------------------------

## Dados sensíveis criptografados em repouso

Além de proteger os dados durante o tráfego, o EmprestaCampus também protege os dados sensíveis armazenados no banco. A proteção escolhida depende de o sistema precisar ou não recuperar o valor original.

### Inventário dos dados armazenados

A tabela abaixo cobre **todos** os campos com dado pessoal ou segredo gravados pelo sistema, e mostra como cada um é protegido.

| Dado | Onde fica | Proteção em repouso | Por quê |
| --- | --- | --- | --- |
| Senha | `Usuario.password` | Hash PBKDF2-SHA256, 600.000 iterações, salt próprio | O sistema só precisa comparar, nunca recuperar a senha |
| Telefone | `Usuario.telefone` | **Cifrado com Fernet** (`CampoCriptografado`) | Dado de contato pessoal, que não é usado em buscas e precisa ser exibido ao dono |
| Chave secreta do 2FA (TOTP) | `DispositivoTOTP.key` | **Cifrada com Fernet** (`CampoCriptografado`) | Com essa chave, qualquer pessoa geraria os códigos de 2FA do usuário |
| Token de recuperação de senha | `TokenRecuperacaoSenha.token` | Texto aleatório de 256 bits (`secrets.token_urlsafe(32)`), válido por 1 hora e de uso único | Precisa ser buscado pelo valor exato; a validade curta e o uso único limitam o risco |
| Nome, e-mail, usuário (login) e matrícula | `Usuario` | Não cifrados; protegidos pelo controle de acesso (papéis) e pela rede do banco | São usados no login, em buscas, na unicidade (`unique`) e na identificação do usuário nas telas. Um campo cifrado com Fernet gera um texto diferente a cada gravação e não pode ser buscado nem ter `unique` |
| IP e usuário informado nos logs | `RegistroAuditoria`, tabelas do `django-axes` | Não cifrados; tabela de auditoria imutável (trigger) e acesso só para o administrador | São usados para investigar incidentes e bloquear força bruta, o que exige consulta por IP e por usuário |
| Dados dos empréstimos e notificações | `Emprestimo`, `Notificacao` | Não cifrados; acesso filtrado por papel e por dono | Não são dados sensíveis no sentido do art. 5º, II, da LGPD; são a operação do sistema |

Os campos cifrados são os que guardam um segredo (2FA) ou um dado de contato pessoal que não é usado em buscas (telefone). Os demais ficam em claro por necessidade de funcionamento, e a proteção deles vem do controle de acesso e do isolamento do banco: a porta do PostgreSQL só é publicada em `127.0.0.1`.

### Como o campo cifrado funciona

A classe `CampoCriptografado` está em `backend/usuarios/crypto.py`. Antes de gravar no banco, o valor é cifrado; ao ler, é decifrado:

```python
def get_prep_value(self, value):
    if value is None or value == "":
        return value
    valor_cifrado = _fernet().encrypt(value.encode())
    return valor_cifrado.decode()

def from_db_value(self, value, expression, connection):
    if value is None or value == "":
        return value
    valor_original = _fernet().decrypt(value.encode())
    return valor_original.decode()
```

No banco, o valor aparece como um texto iniciado por `gAAAA...`, e não como o dado original. Como o Fernet usa um vetor de inicialização aleatório a cada cifragem, o mesmo valor gera um texto cifrado diferente a cada gravação.

O telefone usa o campo no modelo `Usuario`:

```python
telefone = CampoCriptografado(
    max_length=255,
    null=True,
    blank=True,
    help_text="Telefone pessoal, armazenado criptografado com Fernet (item 3.4).",
)
```

### Chave secreta do 2FA

O `TOTPDevice` padrão do `django-otp` guarda a chave secreta do 2FA em texto puro (hexadecimal). Quem lesse essa tabela, por um backup vazado ou uma injeção de SQL, conseguiria gerar os códigos de 2FA de qualquer usuário e anularia o segundo fator.

Por isso o projeto usa o modelo próprio `DispositivoTOTP`, em `backend/usuarios/models.py`. Ele tem os mesmos campos do `TOTPDevice`, mas a chave usa o `CampoCriptografado`:

```python
key = CampoCriptografado(
    max_length=255,
    default=default_key,
    help_text="Chave secreta do TOTP, cifrada com Fernet (item 3.4).",
)
```

A verificação do código é reaproveitada do `django-otp`, sem reescrever a lógica já testada pela biblioteca (atraso progressivo após erros e proteção contra reuso do mesmo código). Só muda onde a chave fica guardada.

A migração `0011_migrar_dispositivos_totp` copia os dispositivos que já existiam para o novo modelo, com a chave cifrada, e apaga as linhas antigas da tabela do `django-otp`. Quem já tinha o 2FA configurado continua usando o mesmo aplicativo autenticador.

### Rotação de chaves

A função `_fernet()` monta um `MultiFernet` com a chave atual e as chaves antigas:

```python
chaves = [settings.ENCRYPTION_KEY, *settings.ENCRYPTION_KEYS_ANTIGAS]
return MultiFernet([Fernet(chave.encode()) for chave in chaves])
```

O `MultiFernet` cifra sempre com a primeira chave (a atual) e, para decifrar, tenta cada chave da lista. Assim, a chave pode ser trocada sem perder os dados já gravados:

1. A chave atual vai para `ENCRYPTION_KEYS_ANTIGAS`, e uma chave nova vai para `ENCRYPTION_KEY`. Os dados antigos continuam legíveis.
2. O comando `python manage.py rotacionar_chave_criptografia` recifra todos os telefones e chaves de 2FA com a chave nova. Ele roda numa única transação: se algum valor não puder ser decifrado, nada é alterado.
3. A chave antiga é retirada de `ENCRYPTION_KEYS_ANTIGAS`.

A rotação é indicada periodicamente e, obrigatoriamente, sempre que houver suspeita de vazamento da chave.

### Testes

Os testes de `backend/usuarios/tests_criptografia.py` leem o valor gravado direto no banco, por SQL puro, e comprovam que:

- o telefone e a chave do 2FA ficam cifrados, e não em texto puro;
- o 2FA continua funcionando com a chave cifrada;
- o mesmo valor gera textos cifrados diferentes;
- a migração tira as chaves de 2FA do texto puro sem invalidar o aplicativo autenticador;
- depois da rotação, os dados só abrem com a chave nova, e sem a chave certa o dado não é lido.

------------------------------------------------------------------------

## Uso de algoritmo criptográfico adequado

O projeto usa mecanismos diferentes para senhas e para dados pessoais.

### Senhas

As senhas utilizam o algoritmo **PBKDF2-SHA256**. O arquivo responsável é `backend/usuarios/hashers.py`, com uma implementação personalizada:

```python
class PBKDF2HasherReforcado(PBKDF2PasswordHasher):
    iterations = 600_000
```

Foram definidas **600.000 iterações**, o mínimo recomendado pela OWASP para PBKDF2-SHA256 (OWASP, 2023). O objetivo é aumentar o custo computacional de cada tentativa de descoberta de senha. Cada senha recebe um salt aleatório próprio.

No arquivo `backend/config/settings.py`, esse hasher é registrado:

```python
PASSWORD_HASHERS = [
    "usuarios.hashers.PBKDF2HasherReforcado",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher"
]
```

**Por que PBKDF2, e não bcrypt ou Argon2:**

| Algoritmo | Característica | Decisão |
| --- | --- | --- |
| PBKDF2-SHA256 | Nativo do Django, sem dependência externa, aceito pelas diretrizes do NIST (NIST, 2017) | **Adotado** |
| bcrypt | Bom custo computacional, mas limita a senha a 72 bytes e exige biblioteca externa | Não adotado |
| Argon2id | Exige muita memória, o que dificulta ataques com GPU; é a primeira opção da OWASP (OWASP, 2023) | Evolução futura |

O PBKDF2 foi escolhido por equilibrar segurança reconhecida, ausência de dependências e suporte nativo do framework. O número de iterações fica declarado no código, em vez de depender do valor padrão da versão instalada do Django.

### Dados pessoais - Fernet

Para dados pessoais que precisam ser recuperados posteriormente, o projeto utiliza **Fernet**, da biblioteca `cryptography`, implementado em `backend/usuarios/crypto.py`.

O Fernet é uma receita de **criptografia simétrica autenticada**: cifra os dados com **AES-128 em modo CBC** e garante a integridade com **HMAC-SHA256**. Se o texto cifrado for alterado no banco, a descriptografia falha em vez de devolver um valor adulterado.

O mecanismo é inicializado com a chave atual e as chaves antigas, por meio do `MultiFernet` (ver "Rotação de chaves"):

```python
MultiFernet([Fernet(chave.encode()) for chave in chaves])
```

**Por que Fernet, e não AES-GCM diretamente:**

| Opção | Característica | Decisão |
| --- | --- | --- |
| Fernet (AES-128-CBC + HMAC-SHA256) | Receita de alto nível: gera o vetor de inicialização, calcula o HMAC e codifica o resultado automaticamente, reduzindo o risco de uso incorreto | **Adotado** |
| AES-GCM | Também autenticado e mais rápido, com opção de chave de 256 bits, mas exige que a aplicação gerencie o nonce; reutilizar um nonce compromete a segurança | Não adotado |

Para o volume e o tipo de dado do sistema (um campo curto por usuário), a facilidade de uso correto do Fernet pesou mais do que o desempenho do AES-GCM.

A escolha dos mecanismos ocorre de acordo com a finalidade:

-   **Senha:** hash PBKDF2-SHA256, pois a senha original não precisa ser recuperada;
-   **Telefone e chave do 2FA:** criptografia Fernet, pois o sistema precisa recuperar o valor original.

------------------------------------------------------------------------

## Chaves criptográficas protegidas

As chaves criptográficas não são armazenadas no código-fonte. Elas são obtidas através de variáveis de ambiente, carregadas do arquivo `.env` pela biblioteca `python-decouple`:

```python
from decouple import config as env
```

No arquivo `backend/config/settings.py` está definido:

```python
SECRET_KEY = env("SECRET_KEY")
ENCRYPTION_KEY = env("ENCRYPTION_KEY")
```

A chave utilizada pelo Fernet é diferente da `SECRET_KEY` do Django. Essa separação é importante porque as chaves possuem finalidades diferentes: se uma delas vazar, a outra continua protegendo a sua função.

### SECRET_KEY

É utilizada pelo Django para operações internas de segurança: assinatura das sessões, dos tokens CSRF e do token intermediário do login com 2FA na API.

### ENCRYPTION_KEY

É utilizada especificamente para criptografar os dados pessoais protegidos pelo Fernet. Deve ser uma chave Fernet válida (32 bytes codificados em base64).

### ENCRYPTION_KEYS_ANTIGAS

Opcional. Lista, separada por vírgulas, das chaves anteriores à `ENCRYPTION_KEY` atual. Só é usada durante a rotação, para decifrar os dados gravados antes da troca. Fica vazia no uso normal.

------------------------------------------------------------------------

## Proteção das variáveis de ambiente

O arquivo `.gitignore` possui regras para impedir que arquivos de variáveis de ambiente e certificados sejam enviados ao repositório:

```
.env
.env.local
nginx/certs/
```

O arquivo `backend/.dockerignore` impede que o `.env` seja copiado para dentro da imagem Docker durante o build:

```
.env
.env.*
!.env.example
```

O arquivo `backend/.env.example` é versionado e lista todas as variáveis necessárias, com valores de exemplo, sem nenhum segredo real. Cada ambiente cria o seu próprio `.env` a partir dele.

A senha do banco de dados também vem do `.env` (`POSTGRES_PASSWORD`), e não fica escrita no `docker-compose.yml`. A porta do PostgreSQL só é publicada na interface local da máquina (`127.0.0.1:5433`), sem acesso a partir de outras máquinas da rede.

------------------------------------------------------------------------

## Tabela de atendimento aos requisitos

| Requisito | Implementação | Arquivo principal | Situação |
| --- | --- | --- | --- |
| 3.1 TLS/HTTPS | Nginx com SSL/TLS na porta 443 | `nginx/nginx.conf` | Implementado |
| 3.2 Bloqueio de conexões não seguras | Redirecionamento 301 de HTTP para HTTPS no Nginx; `SECURE_SSL_REDIRECT` no Django com `DEBUG=False` | `nginx/nginx.conf`, `settings.py` | Implementado |
| 3.3 Evidência de tráfego cifrado | Configuração TLS e prints do acesso por HTTPS | `nginx/nginx.conf`, `docs/Evidencias/` | Parcial: configurado, sem captura do handshake TLS |
| 3.4 Dados sensíveis em repouso | Inventário de todos os dados armazenados; telefone e chave do 2FA cifrados com Fernet; rotação de chaves com `MultiFernet` e comando de recifragem; testes por SQL puro | `usuarios/crypto.py`, `usuarios/models.py`, `usuarios/tests_criptografia.py` | Implementado |
| 3.5 Algoritmo adequado | PBKDF2-SHA256 (600.000 iterações) para senhas; Fernet (AES-128-CBC + HMAC-SHA256) para dados pessoais | `usuarios/hashers.py`, `usuarios/crypto.py` | Implementado |
| 3.6 Chaves protegidas | `SECRET_KEY` e `ENCRYPTION_KEY` separadas, lidas do `.env`; `.env` fora do Git e da imagem Docker | `settings.py`, `.gitignore`, `.dockerignore` | Implementado |
| 3.7 Estratégia documentada | Este documento | `docs/criptografia.md` | Implementado |
| 3.8 Justificativa técnica | Comparações PBKDF2 × bcrypt × Argon2 e Fernet × AES-GCM | `docs/criptografia.md` | Implementado |

------------------------------------------------------------------------

## Conclusão

O EmprestaCampus utiliza mecanismos distintos de segurança de acordo com a necessidade de cada informação.

Para senhas, é utilizado **hash PBKDF2-SHA256 com 600.000 iterações e salt**, pois a aplicação não precisa recuperar a senha original.

Para dados que precisam ser recuperados posteriormente, como o telefone e a chave secreta do 2FA, é utilizada **criptografia simétrica autenticada com Fernet** (AES-128-CBC com HMAC-SHA256), com rotação de chaves pelo `MultiFernet`.

Na comunicação entre cliente e servidor, o sistema utiliza **HTTPS/TLS através do Nginx**, com redirecionamento obrigatório de HTTP para HTTPS e configurações adicionais de segurança no Django.

As chaves utilizadas pela aplicação são separadas por finalidade e obtidas através de variáveis de ambiente, fora do código-fonte, do repositório e da imagem Docker.

Dessa forma, o projeto apresenta mecanismos de proteção para:

-   Dados em trânsito;
-   Dados armazenados;
-   Senhas;
-   Dados pessoais;
-   Chaves criptográficas;
-   Cookies e sessões;
-   Conexões HTTP não seguras.

A combinação dessas medidas contribui para a proteção da confidencialidade e da integridade das informações processadas pelo EmprestaCampus.