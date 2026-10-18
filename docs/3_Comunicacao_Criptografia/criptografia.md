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
    └── models.py

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

Além de proteger os dados durante o tráfego, o EmprestaCampus também cifra dados pessoais armazenados no banco de dados. Atualmente, o campo cifrado é o **telefone** do usuário.

O arquivo responsável pelo modelo é `backend/usuarios/models.py`. No modelo `Usuario`, o telefone é definido utilizando a classe:

```python
telefone = CampoCriptografado(
    max_length=255,
    null=True,
    blank=True,
    help_text="Telefone pessoal, armazenado criptografado com Fernet (item 3.4).",
)
```

A classe `CampoCriptografado` está implementada em `backend/usuarios/crypto.py` e utiliza o Fernet:

```python
from cryptography.fernet import Fernet
```

A chave é obtida através da configuração:

```python
return Fernet(settings.ENCRYPTION_KEY.encode())
```

Quando o valor é preparado para ser armazenado no banco, ele é criptografado:

```python
valor_cifrado = _fernet().encrypt(value.encode())
return valor_cifrado.decode()
```

Quando o valor é recuperado do banco, ocorre a descriptografia:

```python
valor_original = _fernet().decrypt(value.encode())
return valor_original.decode()
```

No banco, o telefone aparece como um texto iniciado por `gAAAA...`, e não como o número original. Como o Fernet usa um vetor de inicialização aleatório a cada cifragem, o mesmo telefone gera um texto cifrado diferente a cada gravação.

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

O mecanismo é inicializado utilizando a chave de criptografia:

```python
Fernet(settings.ENCRYPTION_KEY.encode())
```

**Por que Fernet, e não AES-GCM diretamente:**

| Opção | Característica | Decisão |
| --- | --- | --- |
| Fernet (AES-128-CBC + HMAC-SHA256) | Receita de alto nível: gera o vetor de inicialização, calcula o HMAC e codifica o resultado automaticamente, reduzindo o risco de uso incorreto | **Adotado** |
| AES-GCM | Também autenticado e mais rápido, com opção de chave de 256 bits, mas exige que a aplicação gerencie o nonce; reutilizar um nonce compromete a segurança | Não adotado |

Para o volume e o tipo de dado do sistema (um campo curto por usuário), a facilidade de uso correto do Fernet pesou mais do que o desempenho do AES-GCM.

A escolha dos mecanismos ocorre de acordo com a finalidade:

-   **Senha:** hash PBKDF2-SHA256, pois a senha original não precisa ser recuperada;
-   **Telefone:** criptografia Fernet, pois o sistema precisa recuperar o valor original.

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
| 3.4 Dados sensíveis em repouso | Telefone cifrado com Fernet | `usuarios/crypto.py`, `usuarios/models.py` | Implementado |
| 3.5 Algoritmo adequado | PBKDF2-SHA256 (600.000 iterações) para senhas; Fernet (AES-128-CBC + HMAC-SHA256) para dados pessoais | `usuarios/hashers.py`, `usuarios/crypto.py` | Implementado |
| 3.6 Chaves protegidas | `SECRET_KEY` e `ENCRYPTION_KEY` separadas, lidas do `.env`; `.env` fora do Git e da imagem Docker | `settings.py`, `.gitignore`, `.dockerignore` | Implementado |
| 3.7 Estratégia documentada | Este documento | `docs/criptografia.md` | Implementado |
| 3.8 Justificativa técnica | Comparações PBKDF2 × bcrypt × Argon2 e Fernet × AES-GCM | `docs/criptografia.md` | Implementado |

------------------------------------------------------------------------

## Conclusão

O EmprestaCampus utiliza mecanismos distintos de segurança de acordo com a necessidade de cada informação.

Para senhas, é utilizado **hash PBKDF2-SHA256 com 600.000 iterações e salt**, pois a aplicação não precisa recuperar a senha original.

Para dados pessoais que precisam ser recuperados posteriormente, como o telefone, é utilizada **criptografia simétrica autenticada com Fernet** (AES-128-CBC com HMAC-SHA256).

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