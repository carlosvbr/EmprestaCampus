3. Criptografia e Comunicação Segura

Os principais arquivos relacionados à implementação são:


backend/
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


------------------------------------------------------------------------

Hash e Criptografia

## Hash
o hash é utilizado para proteger as senhas dos
usuários.

O fluxo pode ser representado da seguinte forma:


Senha informada pelo usuário
            |
            v
      PBKDF2-SHA256
            |
            v
       Hash da senha
            |
            v
       Banco de dados

Durante a autenticação, a senha informada no login é processada pelo
mecanismo de hash e comparada com o valor armazenado.

Portanto:


Senha → Hash

Hash → Senha original
       NÃO É POSSÍVEL

Essa característica torna o hash adequado para armazenamento de senhas.

## Criptografia

A criptografia é utilizada quando o sistema precisa proteger uma
informação, mas ainda precisa conseguir recuperar o valor original
posteriormente.

Um exemplo é o número de telefone do usuário.

O fluxo é:


Telefone original
       |
       v
   Criptografia
       |
       v
Texto cifrado
       |
       v
Banco de dados


Quando a aplicação precisa utilizar o telefone:


Texto cifrado
       |
       v
Descriptografia
       +
Chave correta
       |
       v
Telefone original


Dessa forma:


Hash:

Senha → Hash
Hash → Senha original
       NÃO É POSSÍVEL


Criptografia:

Telefone → Texto cifrado
Texto cifrado → Telefone


A criptografia é reversível quando a chave correta está disponível.

------------------------------------------------------------------------

# Comunicação protegida por TLS/HTTPS

utilizamos o **Nginx** como servidor responsável por
receber as conexões externas e encaminhá-las para o backend Django.

O arquivo responsável por essa configuração é:


nginx/nginx.conf


A configuração do Nginx utiliza a porta `443` com SSL/TLS:


server {
    listen 443 ssl;

    server_name localhost;

    ssl_certificate /etc/nginx/certs/localhost.crt;
    ssl_certificate_key /etc/nginx/certs/localhost.key;
}


A porta `443` é utilizada para conexões HTTPS.

O certificado e sua respectiva chave privada são configurados através
das diretivas:


ssl_certificate
ssl_certificate_key


O Nginx também encaminha as requisições para o backend:


location / {
    proxy_pass http://backend:8000;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}


O fluxo de comunicação é:

Cliente
   |
   | HTTPS / TLS
   v
 Nginx
   |
   v
Backend Django
   |
   v
PostgreSQL


Dessa forma, a comunicação externa da aplicação utiliza HTTPS/TLS para
proteger os dados durante a transmissão.

------------------------------------------------------------------------

# Bloqueio de conexões não seguras

O sistema possui uma proteção para evitar que a aplicação seja utilizada
através de uma conexão HTTP não protegida.

No arquivo:


nginx/nginx.conf


existe a seguinte configuração:


server {
    listen 80;
    server_name localhost;

    return 301 https://$host$request_uri;
}


Quando o usuário acessa:


http://localhost


o Nginx realiza um redirecionamento para:


https://localhost


Dessa forma, o acesso à aplicação é direcionado para uma conexão
protegida por TLS.

Além da configuração do Nginx, o Django possui uma camada adicional de
proteção.

No arquivo:


backend/config/settings.py


está configurado:


SECURE_SSL_REDIRECT = not DEBUG


Também existe:


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


A configuração `SECURE_SSL_REDIRECT` permite que, em ambiente de
produção (`DEBUG = False`), o Django também redirecione requisições HTTP
para HTTPS.

------------------------------------------------------------------------

# Evidência de tráfego cifrado

A evidência de utilização de tráfego cifrado está presente na
configuração do Nginx.

No arquivo:


nginx/nginx.conf


a porta HTTPS está configurada através de:


listen 443 ssl;


Também são utilizados:


ssl_certificate /etc/nginx/certs/localhost.crt;
ssl_certificate_key /etc/nginx/certs/localhost.key;


Essas configurações demonstram que o servidor está preparado para
estabelecer conexões HTTPS utilizando TLS.

O `docker-compose.yml` também disponibiliza as portas HTTP e HTTPS:


ports:
  - "80:80"
  - "443:443"

## Proteções adicionais

O Django também possui configurações relacionadas à proteção de cookies.

No arquivo:


backend/config/settings.py


existem:


SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


Quando o sistema está em produção com `DEBUG = False`, essas
configurações fazem com que os cookies sejam enviados somente através de
conexões HTTPS.

Também existe configuração de HSTS:


SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if not DEBUG else 0


Em produção, isso instrui o navegador a utilizar HTTPS para o domínio
durante o período configurado.

------------------------------------------------------------------------

# Dados sensíveis criptografados em repouso

Além de proteger os dados durante o tráfego, o EmprestaCampus também
possui proteção para determinados dados pessoais armazenados no banco de
dados.

Um exemplo é o campo de telefone do usuário.

O arquivo responsável pelo modelo é:


backend/usuarios/models.py


No modelo `Usuario`, o telefone é definido utilizando a classe:


telefone = CampoCriptografado(
    max_length=255,
    null=True,
    blank=True,
    help_text="Telefone pessoal, armazenado criptografado com Fernet (item 3.4).",
)


A classe `CampoCriptografado` está implementada em:


backend/usuarios/crypto.py


Essa classe utiliza o Fernet:


from cryptography.fernet import Fernet


A chave é obtida através da configuração:


return Fernet(settings.ENCRYPTION_KEY.encode())


Quando o valor é preparado para ser armazenado no banco, ele é
criptografado:


valor_cifrado = _fernet().encrypt(value.encode())

return valor_cifrado.decode()


Quando o valor é recuperado do banco, ocorre a descriptografia:


valor_original = _fernet().decrypt(value.encode())

return valor_original.decode()

------------------------------------------------------------------------

# Uso de algoritmo criptográfico adequado

O mecanismos diferentes para senhas e dados pessoais.

## Senhas

As senhas utilizam um algoritimo de proteção **PBKDF2-SHA256**.

O arquivo responsável:


backend/usuarios/hashers.py


O projeto possui uma implementação personalizada:


class PBKDF2HasherReforcado(PBKDF2PasswordHasher):
    iterations = 600_000


Foi definido um número elevado de iterações:


600.000 iterações


O objetivo é aumentar o custo computacional necessário para realizar
tentativas de descoberta de senhas.

No arquivo:


backend/config/settings.py


esse hasher é registrado:


PASSWORD_HASHERS = [
    "usuarios.hashers.PBKDF2HasherReforcado",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher"
]

## Dados pessoais - Fernet

Para dados pessoais que precisam ser recuperados posteriormente, o
projeto utiliza **Fernet**.

A implementação está em:


backend/usuarios/crypto.py


A biblioteca utilizada é:


from cryptography.fernet import Fernet


O mecanismo é inicializado utilizando a chave de criptografia:


Fernet(settings.ENCRYPTION_KEY.encode())

A escolha dos mecanismos ocorre de acordo com a finalidade:

-   **Senha:** hash PBKDF2-SHA256, pois a senha original não precisa ser
    recuperada;
-   **Telefone:** criptografia Fernet, pois o sistema pode precisar
    recuperar o valor original.

------------------------------------------------------------------------

# Chaves criptográficas protegidas

As chaves criptográficas não devem ser armazenadas diretamente no
código-fonte.

A chave utilizada para criptografar os dados pessoais
é obtida através de uma variável de ambiente.

No arquivo:


backend/config/settings.py


está definido:


ENCRYPTION_KEY = env("ENCRYPTION_KEY")


A biblioteca utilizada para carregar as configurações do ambiente é:


from decouple import config as env


Dessa forma, a chave de criptografia pode ser mantida fora do
código-fonte.

A chave utilizada pelo Fernet é diferente da `SECRET_KEY` do Django:


SECRET_KEY = env("SECRET_KEY")

ENCRYPTION_KEY = env("ENCRYPTION_KEY")


Essa separação é importante porque as chaves possuem finalidades
diferentes.

### SECRET_KEY

É utilizada pelo Django para operações internas de segurança, como
assinatura de dados e mecanismos relacionados às sessões.

### ENCRYPTION_KEY

É utilizada especificamente para criptografar os dados pessoais
protegidos pelo Fernet.

------------------------------------------------------------------------

# Proteção das variáveis de ambiente

O arquivo:


.gitignore


possui regras para impedir que arquivos de variáveis de ambiente sejam
enviados ao repositório:


.env
.env.local


Também existe uma regra para os certificados locais:


nginx/certs/
------------------------------------------------------------------------

# 4. Tabela de atendimento aos requisitos

  ------------------------------------------------------------------------------
  Requisito         Implementação      Arquivo principal       Situação
  ----------------- ------------------ ----------------------- -----------------
  3.1 TLS/HTTPS     Nginx com SSL/TLS  `nginx/nginx.conf`      Implementado
                    na porta 443                               

  3.2 Bloqueio de   Redirecionamento   `nginx/nginx.conf`      Implementado
  conexões não      HTTP → HTTPS                               
  seguras                                                      

  3.3 Evidência de  HTTPS/TLS, cookies `nginx/nginx.conf` /    Implementado
  tráfego cifrado   seguros e HSTS em  `settings.py`           
                    produção                                   

  3.4 Dados         Telefone           `usuarios/crypto.py` /  Implementado
  sensíveis em      criptografado com  `usuarios/models.py`    
  repouso           Fernet                                     

  3.5 Algoritmo     PBKDF2-SHA256 para `usuarios/hashers.py` / Implementado
  adequado          senhas e Fernet    `usuarios/crypto.py`    
                    para dados                                 
                    pessoais                                   

  3.6 Chaves        `ENCRYPTION_KEY` e `settings.py` /         Implementado
  protegidas        `SECRET_KEY`       `.gitignore`            
                    obtidas por                                
                    variável de                                
                    ambiente                                   
  -----------------------------------------------------------------------------
  
# Conclusão

O EmprestaCampus utiliza mecanismos distintos de segurança de acordo com
a necessidade de cada informação.

Para senhas, é utilizado **hash PBKDF2-SHA256**, pois a aplicação não
precisa recuperar a senha original.

Para dados pessoais que precisam ser recuperados posteriormente, como o
telefone, é utilizada **criptografia simétrica através do Fernet**.

Na comunicação entre cliente e servidor, o sistema utiliza **HTTPS/TLS
através do Nginx**, além de configurações adicionais de segurança no
Django.

As chaves utilizadas pela aplicação são obtidas através de variáveis de
ambiente, evitando que sejam definidas diretamente na implementação da
lógica de criptografia.

Dessa forma, o projeto apresenta mecanismos de proteção para:

-   Dados em trânsito;
-   Dados armazenados;
-   Senhas;
-   Dados pessoais;
-   Chaves criptográficas;
-   Cookies e sessões;
-   Conexões HTTP não seguras.

A combinação dessas medidas contribui para a proteção da
confidencialidade e integridade das informações processadas pelo
EmprestaCampus.
