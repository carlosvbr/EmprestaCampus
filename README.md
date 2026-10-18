# EmprestaCampus
 
Sistema web para gerenciamento de empréstimos de equipamentos acadêmicos, desenvolvido com foco em segurança da informação e conformidade com a LGPD.
 
## Escopo
 
Desenvolver um sistema de gerenciamento seguro do ciclo de empréstimo de equipamentos acadêmicos, contemplando solicitação,reserva, aprovação, retirada, devolução, histórico, controle de acesso, notificações e auditoria das operações.
 
## Stack Tecnológico
 
### Frontend

- **Atual:** Django Templates
- **Planejado:** React com JavaScript
 
### Backend
 
- Python 3.14.7
- Django 6.1.1
- Django REST Framework 3.18
 
### Banco de Dados
 
- PostgreSQL 16.2
 
### Ferramentas
 
- Git
- GitHub
- GitHub Projects
- Docker
 
 
## Arquitetura

O projeto utiliza uma arquitetura monolítica modular, com interface web e API REST.

O frontend atual utiliza Django Templates. Futuramente, será desenvolvido utilizando React e JavaScript, consumindo a API REST já disponível no backend.

O backend é desenvolvido utilizando Python, Django e Django REST Framework.

O PostgreSQL é utilizado para armazenamento e persistência dos dados.

O Nginx recebe as conexões externas por HTTPS e as encaminha ao backend, e toda a aplicação é executada em containers Docker.


### Estrutura do projeto

```
EmprestaCampus/
├── backend/
│   ├── manage.py
│   ├── config/             # Configurações centrais (settings, urls, wsgi/asgi) e middleware de fuso horário
│   ├── usuarios/           # Cadastro, login, 2FA, recuperação de senha, perfil e funcionalidades da LGPD
│   │   ├── hashers.py      # Hasher PBKDF2-SHA256 com 600.000 iterações
│   │   ├── crypto.py       # Campo criptografado com Fernet (telefone)
│   │   ├── templates/      # Telas de login, cadastro, 2FA, perfil, política de privacidade e reativação
│   │   └── tests_seguranca.py  # Testes de segurança
│   ├── inventario/         # Equipamentos, categorias e tela do catálogo
│   ├── emprestimos/        # Solicitação, aprovação, prorrogação e devolução de empréstimos
│   ├── notificacoes/       # Envio de e-mails e histórico de notificações
│   ├── auditoria/          # Registro imutável dos eventos (model, trigger no PostgreSQL e captura do IP real)
│   ├── conftest.py         # Fixtures compartilhadas pelos testes
│   ├── pytest.ini          # Configuração do pytest
│   ├── Dockerfile          # Imagem do backend (python:3.14-slim)
│   ├── requirements.txt    # Dependências do projeto
│   ├── .dockerignore       # Impede que o .env entre na imagem Docker
│   ├── .env                # Variáveis de ambiente (não versionado)
│   └── .env.example        # Exemplo de variáveis de ambiente
├── nginx/
│   ├── nginx.conf          # TLS na porta 443, redirecionamento HTTP → HTTPS e proxy para o Django
│   └── certs/              # Certificado TLS local (não versionado)
├── docs/                   # Documentação técnico-científica
│   └── Evidencias/         # Capturas de tela que comprovam cada requisito
├── docker-compose.yml      # Serviços db (PostgreSQL), backend (Django) e nginx
├── .gitignore
├── LICENSE
└── README.md
```

## Como executar

### Pré-requisitos

- Docker e Docker Compose
- Git
- OpenSSL, para gerar o certificado local (no Windows, já vem com o Git)

### 1. Clonar o repositório

```bash
git clone <URL do repositório>
cd EmprestaCampus
```

### 2. Configurar as variáveis de ambiente

Copie o arquivo de exemplo:

```powershell
# Windows (PowerShell)
Copy-Item backend/.env.example backend/.env
```

```bash
# Linux / macOS
cp backend/.env.example backend/.env
```

Edite o `backend/.env` e preencha, no mínimo:

| Variável | Como obter |
| --- | --- |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `POSTGRES_PASSWORD` | Uma senha à sua escolha para o banco |

As variáveis `SMTP_*` são opcionais: se `SMTP_HOST` ficar vazio, os e-mails são exibidos no log do container em vez de enviados. Para demonstrar as proteções de produção (cookies `Secure`, HSTS e redirecionamento HTTPS do Django), use `DEBUG=False`.

O arquivo `.env` nunca deve ser enviado ao repositório.

### 3. Gerar o certificado TLS local

O Nginx precisa de um certificado em `nginx/certs/` para iniciar. Gere um certificado autoassinado:

```powershell
# Windows (PowerShell), usando o OpenSSL que acompanha o Git
New-Item -ItemType Directory -Force nginx/certs
& "C:\Program Files\Git\usr\bin\openssl.exe" req -x509 -nodes -newkey rsa:2048 -days 365 `
  -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj "/CN=localhost"
```

```bash
# Linux / macOS
mkdir -p nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout nginx/certs/localhost.key -out nginx/certs/localhost.crt -subj "/CN=localhost"
```

A pasta `nginx/certs/` não é versionada.

### 4. Subir os containers

```bash
docker compose up --build
```

As migrações do banco são aplicadas automaticamente na inicialização do backend.

### 5. Criar o usuário administrador

Em outro terminal:

```bash
docker compose exec backend python manage.py createsuperuser
```

A conta criada recebe o papel de Administrador.

O banco de dados começa vazio. Para carregar categorias e equipamentos de exemplo no catálogo:

```bash
docker compose exec backend python manage.py loaddata dados_exemplo
```

### 6. Acessar o sistema

| Página | Endereço |
| --- | --- |
| Login | https://localhost/api/usuarios/entrar/ |
| Administração (aprovação de empréstimos, inventário e auditoria) | https://localhost/admin/ |

Como o certificado é autoassinado, o navegador exibirá um aviso de segurança na primeira vez; basta prosseguir. O acesso por `http://localhost` é redirecionado automaticamente para HTTPS.

Para encerrar, use `docker compose down`. Os dados do banco ficam guardados em um volume do Docker.

## Testes

Com os containers em execução:

```bash
docker compose exec backend python -m pytest -v
```

A suíte tem 149 casos de teste, cobrindo autenticação, 2FA, recuperação de senha, controle de acesso, LGPD, auditoria, inventário, empréstimos e notificações. A descrição de cada teste e o resultado da execução estão em docs.

### Executar sem Docker (desenvolvimento)

Também é possível rodar o backend e os testes direto na máquina, mantendo apenas o banco no Docker:

```powershell
# Na raiz do repositório
docker compose up -d db
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
python -m pip install -r requirements.txt
```

No `backend/.env`, ajuste `POSTGRES_HOST=localhost` e `POSTGRES_PORT=5433` (porta publicada pelo container do banco). Depois:

```bash
python manage.py migrate
python manage.py runserver
python -m pytest
```
