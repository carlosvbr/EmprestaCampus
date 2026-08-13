# Stack Tecnológica

**Projeto:** Sistema de Empréstimo de Equipamentos Acadêmicos
**Versão do documento:** 1.0

---

## 1. Visão Geral

| Camada | Tecnologia | Versão |
|---|---|---|
| Linguagem (backend) | Python | 3.12 |
| Framework web | Django | 5.x |
| API REST | Django REST Framework | 3.15 |
| Banco de dados | PostgreSQL | 16 |
| Fila / cache | Redis | 7 |
| Processamento assíncrono | Celery + Celery Beat | 5.x |
| Linguagem (frontend) | TypeScript | 5.x |
| Biblioteca de UI | React | 18 |
| Build tool | Vite | 5.x |
| Estilização | Tailwind CSS | 3.x |
| Containerização | Docker + Docker Compose | - |
| Controle de versão | Git + GitHub | - |
| CI | GitHub Actions | - |

---

## 2. Backend

### 2.1 Python + Django + Django REST Framework

**Decisão:** o backend será desenvolvido em Python com Django e Django REST Framework (DRF).

**Justificativa:**

O sistema é caracterizado por operações de CRUD, fluxo de aprovação com múltiplos papéis, controle de acesso, auditoria e relatórios. Não é um sistema de alto volume de requisições concorrentes nem de processamento assíncrono intensivo.

O Django atende diretamente a esse perfil, fornecendo de forma nativa:

- **ORM com migrations versionadas**, atendendo ao RNF44
- **Sistema de autenticação e permissões**, base para o RBAC exigido pelos RF02 e RF03
- **Django Admin**, que fornece uma interface administrativa funcional desde as primeiras iterações, útil para cadastro inicial de equipamentos e usuários
- **Proteções de segurança nativas** contra SQL Injection, XSS e CSRF, atendendo ao RNF15
- **Django REST Framework**, que padroniza serialização, validação, paginação, filtros e documentação automática da API (RNF41)

### 2.2 Alternativas avaliadas

| Alternativa | Motivo da não adoção |
|---|---|
| **FastAPI** | Excelente desempenho em cargas assíncronas e tipagem nativa, porém exige construir manualmente ORM, autenticação, permissões e painel administrativo. O ganho de performance não é relevante para o perfil de carga deste sistema (RNF03: ~100 usuários simultâneos). |
| **Flask** | Microframework sem estrutura imposta. Traria liberdade desnecessária e maior risco de inconsistência em um projeto desenvolvido em equipe e com prazo definido. |
| **Spring Boot (Java)** | Tecnicamente adequado, mas com maior verbosidade e tempo de configuração inicial para o escopo e o cronograma deste projeto. |

### 2.3 Bibliotecas principais

| Biblioteca | Finalidade |
|---|---|
| `djangorestframework` | Construção da API REST |
| `djangorestframework-simplejwt` | Autenticação por token JWT (RNF11) |
| `django-filter` | Filtros de consulta no catálogo (RF14) |
| `drf-spectacular` | Geração de documentação OpenAPI/Swagger (RNF41) |
| `psycopg[binary]` | Driver PostgreSQL |
| `celery` + `redis` | Tarefas assíncronas e agendadas (RNF04) |
| `python-decouple` | Gestão de variáveis de ambiente |
| `pytest-django` + `factory-boy` | Testes automatizados (RNF42) |
| `ruff` | Linter e formatador |

---

## 3. Banco de Dados

### 3.1 PostgreSQL 16

**Decisão:** PostgreSQL como sistema gerenciador de banco de dados relacional.

**Justificativa:**

O modelo de dados é fortemente relacional (usuários, equipamentos, empréstimos, itens, eventos) e exige integridade referencial e transações, o que descarta bancos não relacionais.

Entre os bancos relacionais, o PostgreSQL foi escolhido por dois recursos que atendem diretamente a requisitos críticos do sistema:

1. **`ExclusionConstraint` com tipos de intervalo (`tstzrange`)**: permite garantir, no nível do banco de dados, que um mesmo equipamento não tenha duas reservas com sobreposição de período. Isso atende ao RF41 e ao RNF14 de forma segura contra condições de corrida, o que não seria possível validando apenas na aplicação.

2. **Campo `JSONB` com indexação**: permite armazenar o contexto variável de cada evento da trilha de auditoria (RF90) sem criar uma tabela por tipo de evento.

Adicionalmente: transações ACID completas, integração madura com o ORM do Django e ampla disponibilidade em ambientes de hospedagem.

### 3.2 Extensões necessárias

| Extensão | Finalidade |
|---|---|
| `btree_gist` | Pré-requisito para a `ExclusionConstraint` que combina igualdade (equipamento) com sobreposição (período) |

### 3.3 Alternativas avaliadas

| Alternativa | Motivo da não adoção |
|---|---|
| **MySQL / MariaDB** | Não oferece constraints de exclusão com tipos de intervalo, o que exigiria resolver a prevenção de reserva concorrente apenas na aplicação, solução mais frágil. |
| **SQLite** | Adequado apenas para desenvolvimento local. Não suporta acesso concorrente adequado nem os recursos citados acima. |
| **MongoDB** | Modelo de dados do projeto é relacional e exige integridade referencial e transações multi-tabela. |

---

## 4. Frontend

### 4.1 React + TypeScript + Vite

**Decisão:** interface web em React com TypeScript, empacotada com Vite.

**Justificativa:**

- **React**: maior ecossistema e maior disponibilidade de material de apoio; interface baseada em componentes reutilizáveis (tabelas, formulários, cards de status), adequada ao perfil do sistema
- **TypeScript**: tipagem estática reduz erros de integração com a API e documenta os contratos de dados
- **Vite**: build e servidor de desenvolvimento rápidos, com configuração mínima

### 4.2 Bibliotecas principais

| Biblioteca | Finalidade |
|---|---|
| `react-router-dom` | Roteamento e proteção de rotas por papel |
| `@tanstack/react-query` | Gerenciamento de estado do servidor, cache e revalidação |
| `axios` | Cliente HTTP com interceptadores para o token JWT |
| `react-hook-form` + `zod` | Formulários e validação no cliente |
| `tailwindcss` | Estilização utilitária |
| `lucide-react` | Ícones |
| `date-fns` | Manipulação de datas |

---

## 5. Infraestrutura e Ferramentas

### 5.1 Containerização

Todo o ambiente é orquestrado via **Docker Compose**, atendendo ao RNF43 (execução com um único comando).

| Serviço | Descrição |
|---|---|
| `db` | PostgreSQL 16 com volume persistente |
| `redis` | Redis 7, broker do Celery |
| `backend` | Django + DRF |
| `worker` | Celery worker (envio de notificações) |
| `beat` | Celery Beat (verificação periódica de atrasos) |
| `frontend` | React servido pelo Vite (dev) ou Nginx (produção) |

### 5.2 Integração Contínua

**GitHub Actions**, executando a cada `push` e `pull request`:

1. Verificação de estilo e lint (`ruff`)
2. Execução da suíte de testes (`pytest`)
3. Verificação de migrations pendentes

### 5.3 Convenções de desenvolvimento

| Item | Convenção |
|---|---|
| Mensagens de commit | Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`) |
| Branches | `main` (estável) · `develop` (integração) · `feature/<nome>` |
| Integração | Via Pull Request, com revisão de outro membro do grupo |
| Idioma do código | Nomes de entidades e campos em português; palavras-chave e bibliotecas em inglês |

---

## 6. Requisitos de Ambiente

Para executar o projeto localmente é necessário apenas:

- Docker Engine 24+
- Docker Compose v2

Não é necessário instalar Python, Node.js ou PostgreSQL na máquina do desenvolvedor.

```bash
git clone <url-do-repositorio>
cd <pasta-do-projeto>
cp .env.example .env
docker compose up
```

| Serviço | Endereço local |
|---|---|
| API | http://localhost:8000/api/ |
| Documentação da API | http://localhost:8000/api/docs/ |
| Painel administrativo | http://localhost:8000/admin/ |
| Interface web | http://localhost:5173/ |
