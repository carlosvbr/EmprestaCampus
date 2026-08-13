# Arquitetura do Sistema

**Projeto:** Sistema de Empréstimo de Equipamentos Acadêmicos
**Versão do documento:** 1.0

---

## 1. Estilo Arquitetural

O sistema adota o estilo **monolito modular em camadas**, com separação entre cliente e servidor:

- **Backend**: aplicação Django que expõe uma **API REST** e concentra toda a regra de negócio
- **Frontend**: aplicação React independente, que consome a API via HTTP/JSON
- Comunicação exclusivamente por **API REST**, sem renderização de templates no servidor

### 1.1 Justificativa

**Por que monolito e não microsserviços?**

O sistema possui domínio único e coeso, equipe reduzida e ausência de necessidade de escalar módulos de forma independente. Uma arquitetura de microsserviços introduziria complexidade operacional (comunicação entre serviços, consistência distribuída, orquestração) sem benefício correspondente. Além disso, transações que envolvem múltiplas entidades (como aprovar um empréstimo, reservar os equipamentos e registrar o evento de auditoria) são naturalmente atômicas em um monolito.

**Por que modular?**

A separação em módulos com fronteiras claras mantém o código organizado, facilita o trabalho paralelo entre os membros do grupo e permite uma eventual extração de serviços no futuro, caso necessário.

**Por que separar frontend e backend?**

Permite que as camadas evoluam de forma independente, viabiliza o consumo da mesma API por outros clientes futuros e possibilita a divisão de trabalho na equipe. Atende também ao RNF40.

---

## 2. Visão de Contexto

```
┌───────────────────────────────────────────────────────────┐
│                        USUÁRIOS                           │
│      Aluno · Docente · Técnico · Administrador            │
└──────────────────────────┬────────────────────────────────┘
                           │ HTTPS
                           ▼
              ┌────────────────────────┐
              │       FRONTEND         │
              │  React + TypeScript    │
              └───────────┬────────────┘
                          │ REST / JSON (JWT)
                          ▼
              ┌────────────────────────┐        ┌──────────────┐
              │       BACKEND          │───────▶│   PostgreSQL │
              │   Django + DRF         │        └──────────────┘
              │                        │
              │  accounts · catalog    │        ┌──────────────┐
              │  loans · audit         │───────▶│    Redis     │
              │  notifications         │        └──────┬───────┘
              └────────────────────────┘               │
                                                       ▼
                                            ┌────────────────────┐
                                            │  Celery Worker     │
                                            │  Celery Beat       │
                                            └─────────┬──────────┘
                                                      │ SMTP
                                                      ▼
                                            ┌────────────────────┐
                                            │  Servidor de       │
                                            │  E-mail            │
                                            └────────────────────┘
```

---

## 3. Módulos do Backend

Cada módulo corresponde a um *app* Django, com fronteira de responsabilidade definida.

| Módulo | Responsabilidade | Entidades principais |
|---|---|---|
| `core` | Classes base, exceções de domínio, permissões compartilhadas, mixins | - |
| `accounts` | Usuários, papéis, autenticação e autorização | `Usuario` |
| `catalog` | Catálogo de equipamentos e sua organização | `Laboratorio`, `Categoria`, `Equipamento` |
| `loans` | Ciclo de vida do empréstimo: solicitação, aprovação, reserva, retirada, devolução, penalidades | `Emprestimo`, `ItemEmprestimo`, `Reserva`, `TermoResponsabilidade`, `Penalidade` |
| `audit` | Trilha de auditoria imutável | `EventoEmprestimo` |
| `notifications` | Composição e envio assíncrono de notificações | `Notificacao` |

### 3.1 Regra de dependência

Os módulos dependem apenas em uma direção:

```
notifications ──┐
                ├──▶ loans ──▶ catalog ──▶ accounts ──▶ core
audit ──────────┘
```

O módulo `accounts` não conhece `loans`. O módulo `catalog` não conhece `loans`. Dependências circulares entre módulos não são permitidas.

---

## 4. Camadas Internas

Dentro de cada módulo, a organização segue quatro camadas com responsabilidades distintas:

```
loans/
├── models.py              # Entidades e constraints de banco
├── services/              # Regra de negócio (escrita)
│   ├── solicitacao.py
│   ├── aprovacao.py
│   ├── retirada.py
│   └── devolucao.py
├── selectors.py           # Consultas complexas (leitura)
├── serializers.py         # Validação de entrada e formatação de saída
├── permissions.py         # Regras de acesso por papel
├── views.py               # Endpoints HTTP
├── urls.py                # Rotas
├── tasks.py               # Tarefas assíncronas (Celery)
└── tests/                 # Testes automatizados
```

### 4.1 Responsabilidade de cada camada

| Camada | Faz | Não faz |
|---|---|---|
| **View** | Recebe a requisição, aplica permissão, delega ao service, devolve resposta | Não contém regra de negócio; não altera estado diretamente |
| **Serializer** | Valida formato e tipo dos dados de entrada; formata a saída | Não decide regra de negócio |
| **Service** | Aplica a regra de negócio, controla a transação, altera estado, registra o evento de auditoria | Não conhece HTTP |
| **Selector** | Consultas de leitura otimizadas | Não altera estado |
| **Model** | Estrutura dos dados, constraints e invariantes de banco | Não orquestra fluxos |

### 4.2 Regra fundamental

> **A view nunca altera o estado de um empréstimo diretamente. Toda transição passa por um service.**

Essa regra existe porque as regras críticas do sistema (RN01, RN03, RN04, RN08) precisam valer independentemente do ponto de entrada: API, Django Admin, comando de terminal ou tarefa agendada. Se a validação estivesse na view, o Admin conseguiria burlá-la.

---

## 5. Modelo de Dados

### 5.1 Diagrama de entidades

```
  Usuario ──────┬────< Emprestimo >────┬──── Usuario
 (solicitante)  │                      │   (aprovador)
                │                      │
                │                      ├────< EventoEmprestimo
                │                      ├────< TermoResponsabilidade
                │                      │
                │                      └────< ItemEmprestimo >──── Equipamento
                │                                                      │
                └────< Penalidade                                      │
                                                                       │
   Laboratorio ────< Equipamento >──── Categoria                       │
                                                                       │
                              Reserva >───────────────────────────────-┘
```

### 5.2 Entidades principais

**`Usuario`**: estende o modelo de usuário do Django.
`nome`, `email` (login), `matricula`, `papel` (ALUNO · DOCENTE · TECNICO · ADMIN), `ativo`

**`Equipamento`**
`nome`, `descricao`, `patrimonio` (único), `numero_serie`, `categoria`, `laboratorio`, `status` (DISPONIVEL · RESERVADO · EMPRESTADO · MANUTENCAO · BAIXADO · PERDIDO), `critico` (booleano), `prazo_maximo_dias`

**`Emprestimo`**: agrega um ou mais equipamentos em uma única solicitação (RF20).
`solicitante`, `aprovador`, `status`, `finalidade`, `data_prevista_retirada`, `data_prevista_devolucao`, `data_retirada`, `data_devolucao`, `justificativa_rejeicao`

**`ItemEmprestimo`**: cada equipamento dentro de um empréstimo, permitindo devolução parcial (RF61).
`emprestimo`, `equipamento`, `condicao_retirada`, `condicao_devolucao`, `devolvido_em`, `ocorrencia`

**`Reserva`**: bloqueio do equipamento em um intervalo de tempo. Existe como entidade separada justamente para receber a constraint de exclusão.
`equipamento`, `emprestimo`, `periodo` (intervalo de datas)

**`TermoResponsabilidade`**: comprovação de aceite (RNF62).
`emprestimo`, `usuario`, `versao_texto`, `aceito_em`, `ip_origem`

**`EventoEmprestimo`**: trilha de auditoria (RF90).
`emprestimo`, `autor`, `tipo`, `dados` (JSONB), `criado_em`

**`Penalidade`**
`usuario`, `motivo`, `inicio`, `fim`, `ativa`, `removida_por`, `justificativa_remocao`

---

## 6. Decisões Arquiteturais

### AD-01: Máquina de estados explícita para o empréstimo

**Contexto:** o empréstimo percorre múltiplos estados e transições inválidas causariam inconsistência (por exemplo, registrar retirada de algo não aprovado).

**Decisão:** as transições válidas são declaradas explicitamente e validadas no service. Qualquer transição não declarada é rejeitada com exceção de domínio.

```python
TRANSICOES_VALIDAS = {
    "SOLICITADO": {"APROVADO", "REJEITADO", "CANCELADO"},
    "APROVADO":   {"RESERVADO", "CANCELADO"},
    "RESERVADO":  {"RETIRADO", "CANCELADO"},
    "RETIRADO":   {"DEVOLVIDO", "ATRASADO"},
    "ATRASADO":   {"DEVOLVIDO", "PERDIDO"},
    "DEVOLVIDO":  set(),
    "REJEITADO":  set(),
    "CANCELADO":  set(),
    "PERDIDO":    set(),
}
```

**Consequência:** o fluxo fica documentado no próprio código e protegido contra erro de programação em qualquer ponto de entrada.

---

### AD-02: Prevenção de reserva concorrente no banco de dados

**Contexto:** validar disponibilidade apenas na aplicação cria uma condição de corrida: dois usuários podem consultar "disponível" no mesmo instante e ambos reservarem o mesmo equipamento.

**Decisão:** a restrição é imposta pelo PostgreSQL por meio de uma `ExclusionConstraint`.

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators

class Reserva(models.Model):
    equipamento = models.ForeignKey(Equipamento, on_delete=models.PROTECT)
    emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE)
    periodo = DateTimeRangeField()

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="reserva_sem_sobreposicao",
                expressions=[
                    ("equipamento", RangeOperators.EQUAL),
                    ("periodo", RangeOperators.OVERLAPS),
                ],
            ),
        ]
```

**Consequência:** a violação é impossível mesmo sob concorrência. A aplicação continua fazendo a verificação prévia para exibir mensagem amigável, mas a garantia real está no banco. Atende ao RF41, ao RNF14 e à RN02.

---

### AD-03: Segregação de funções na aprovação (*maker-checker*)

**Contexto:** permitir que o solicitante aprove a própria solicitação elimina o controle e abre espaço para uso indevido.

**Decisão:** a validação `solicitante != aprovador` é implementada no service de aprovação, não apenas na camada de permissão da API. Equipamentos marcados como críticos exigem aprovação de nível superior.

```python
def aprovar(emprestimo, aprovador):
    if emprestimo.solicitante_id == aprovador.id:
        raise RegraDeNegocioError("O solicitante não pode aprovar a própria solicitação.")
    if emprestimo.exige_aprovacao_superior and aprovador.papel != Papel.ADMIN:
        raise RegraDeNegocioError("Este equipamento exige aprovação de nível superior.")
    ...
```

**Consequência:** a regra vale para qualquer ponto de entrada, inclusive o Django Admin. Atende ao RF33, ao RF35 e à RN01.

---

### AD-04: Trilha de auditoria imutável (*append-only*)

**Contexto:** o sistema precisa responder "quem estava com este equipamento em determinada data" e "quem aprovou esta solicitação", mesmo após alterações posteriores.

**Decisão:** `EventoEmprestimo` é somente-inserção. Não há operações de `UPDATE` nem `DELETE` sobre a tabela. Exclusões de outras entidades são registradas como eventos, nunca como remoção física.

**Consequência:** o histórico é reconstruível e confiável. Atende aos RF90, RF91, RF94 e à RN08.

---

### AD-05: Processamento assíncrono de notificações e atrasos

**Contexto:** o envio de e-mail é lento e sujeito a falha; a marcação de atraso precisa ocorrer periodicamente, sem intervenção do usuário.

**Decisão:** notificações são enfileiradas no Redis e processadas por um *worker* Celery. Uma tarefa periódica do Celery Beat verifica diariamente os empréstimos vencidos e altera seu status para `ATRASADO`.

**Consequência:** falha no envio de e-mail não impede a conclusão da operação principal (RNF33) e o tempo de resposta da API não depende do SMTP (RNF04).

---

## 7. Fluxo de uma Requisição

Exemplo: **aprovação de uma solicitação**

```
1. POST /api/emprestimos/{id}/aprovar/
                 │
2. Autenticação  │  JWT validado, usuário identificado
                 ▼
3. Permissão     │  IsDocenteOuTecnico → papel autorizado?
                 ▼
4. Serializer    │  valida formato dos dados de entrada
                 ▼
5. Service       │  ┌─ abre transação atômica
   aprovacao.py  │  ├─ verifica transição de estado válida (AD-01)
                 │  ├─ verifica solicitante ≠ aprovador (AD-03)
                 │  ├─ verifica necessidade de aprovação superior
                 │  ├─ cria Reserva → constraint do banco valida (AD-02)
                 │  ├─ altera status para APROVADO
                 │  ├─ registra EventoEmprestimo (AD-04)
                 │  └─ enfileira notificação (AD-05)
                 ▼
6. Resposta      │  200 OK com o empréstimo atualizado
```

Qualquer exceção de domínio levantada no passo 5 desfaz a transação inteira e retorna `400` com mensagem tratada.

---

## 8. Segurança

| Aspecto | Implementação |
|---|---|
| Autenticação | JWT com token de acesso de curta duração e token de renovação |
| Senhas | Hash PBKDF2 (padrão do Django), configurável para Argon2 |
| Autorização | RBAC por papel, validado em classes de permissão do DRF e reforçado nos services |
| Escopo de dados | Docente acessa apenas seus orientandos; Técnico apenas seu laboratório |
| Transporte | HTTPS obrigatório em produção |
| Proteções nativas | Django ORM (SQL Injection), escape automático (XSS), token CSRF |
| Limitação de taxa | Throttling do DRF nos endpoints de autenticação |

---

## 9. Estrutura do Frontend

```
src/
├── api/            # cliente HTTP e funções por recurso
├── components/     # componentes reutilizáveis
├── features/       # organizados por domínio
│   ├── auth/
│   ├── catalogo/
│   ├── emprestimos/
│   └── relatorios/
├── hooks/
├── routes/         # rotas e proteção por papel
├── types/          # tipos TypeScript espelhando a API
└── utils/
```

A proteção de rota no frontend é apenas experiência de uso. **A autorização real é sempre validada no servidor** (RNF13).

---

## 10. Implantação

```
┌──────────────────── docker compose ────────────────────┐
│                                                        │
│   frontend ──▶ backend ──┬──▶ db (PostgreSQL)          │
│                          │                             │
│                          └──▶ redis ──┬──▶ worker      │
│                                       └──▶ beat        │
└────────────────────────────────────────────────────────┘
```

Cada serviço possui seu próprio `Dockerfile`. Volumes persistentes são utilizados para o banco de dados e para os arquivos enviados. Variáveis sensíveis são carregadas de `.env`, versionado apenas como `.env.example`.

---

## 11. Rastreabilidade

| Decisão | Requisitos atendidos |
|---|---|
| AD-01: Máquina de estados | RF70, RN03, RN11 |
| AD-02: Constraint de exclusão | RF41, RNF14, RN02 |
| AD-03: Maker-checker | RF33, RF34, RF35, RN01 |
| AD-04: Auditoria append-only | RF90, RF91, RF94, RN08 |
| AD-05: Processamento assíncrono | RF82, RF83, RNF04, RNF33 |
| Camadas (service layer) | RNF40, RNF14 |
| Containerização | RNF43 |
