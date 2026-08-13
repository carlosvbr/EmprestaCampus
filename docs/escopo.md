# Documento de Escopo

**Projeto:** Sistema de Empréstimo de Equipamentos Acadêmicos
**Disciplina:** Projeto Integrador, turma 7ºB, 2026.02
**Versão:** 1.0

---

## 1. Objetivo do Projeto

Desenvolver um sistema web que controle o empréstimo de equipamentos acadêmicos em universidades (notebooks, câmeras, projetores, kits Arduino, equipamentos de laboratório e instrumentos), cobrindo todo o ciclo: solicitação pelo aluno, aprovação pelo responsável, reserva, retirada e devolução.

## 2. Justificativa

O controle manual desse tipo de empréstimo, feito por planilhas ou fichas em papel, não garante rastreabilidade nem identifica o responsável em caso de atraso, dano ou extravio. Também permite que um mesmo equipamento seja reservado por duas pessoas ao mesmo tempo. O sistema proposto resolve essas falhas por meio de um fluxo de aprovação controlado, trilha de auditoria e prevenção de conflito de reserva.

## 3. Escopo Incluído

O projeto contempla:

- Cadastro e autenticação de usuários com quatro papéis: Aluno, Docente, Técnico e Administrador
- Cadastro e consulta do catálogo de equipamentos
- Fluxo completo de empréstimo: solicitação, aprovação (com segregação entre solicitante e aprovador), reserva, retirada e devolução
- Termo de responsabilidade digital, aceito no momento da retirada
- Controle de atraso, com notificações automáticas e bloqueio de novas solicitações para usuários inadimplentes
- Trilha de auditoria de todos os eventos do empréstimo
- Painel com indicadores e relatórios básicos (empréstimos por período, atrasos por usuário)
- API REST documentada, consumida por uma interface web

O detalhamento funcional e não funcional de cada item está no documento `docs/requisitos.md`.

## 4. Fora de Escopo

Não fazem parte deste projeto:

- Integração com o sistema acadêmico da instituição (SIGA, SUAP ou similar)
- Processos de compra, licitação ou baixa patrimonial de equipamentos
- Rastreamento por GPS ou RTLS em tempo real
- Aplicativo mobile nativo (a interface web será responsiva, mas não haverá app para lojas de aplicativo)
- Cobrança financeira efetiva de multas (o sistema registra a penalidade, não processa pagamento)
- Leitura de QR Code/código de barras via hardware dedicado (fica como possível extensão futura)

## 5. Entregáveis do Projeto

| Entregável | Descrição |
|---|---|
| Repositório no GitHub | Público, com todos os membros como proprietários |
| `docs/escopo.md` | Este documento |
| `docs/requisitos.md` | Requisitos funcionais, não funcionais e regras de negócio |
| `docs/arquitetura.md` | Arquitetura, módulos e decisões técnicas |
| `docs/stack.md` | Tecnologias adotadas e justificativa |
| Kanban no GitHub Projects | Etapas do projeto com responsáveis |
| README.md | Apresentação do projeto e instruções de execução |
| Código-fonte do backend | API REST em Django/DRF |
| Código-fonte do frontend | Interface web em React |
| Ambiente containerizado | Execução completa via Docker Compose |
| Apresentação final | Conforme critério a ser definido pela disciplina |

## 6. Partes Interessadas

| Parte interessada | Papel no projeto |
|---|---|
| Professor da disciplina | Avalia o projeto e define os critérios de entrega |
| Grupo (2 a 3 alunos) | Desenvolve o sistema e documenta as decisões |
| Aluno (persona do sistema) | Usuário final que solicita equipamentos |
| Docente/Técnico (persona do sistema) | Usuário final que aprova e controla o empréstimo |

## 7. Divisão de Responsabilidades no Grupo

| Membro | Frente |
|---|---|
| André | Backend (API, banco de dados, regras de negócio) |
| Demais membros | A definir no kanban |

## 8. Premissas

- O grupo já está definido e não será alterado após o início da atividade
- Os dados de exemplo do catálogo (equipamentos, laboratórios) serão fictícios, criados para fins de demonstração
- O ambiente de desenvolvimento e de apresentação será local, via Docker Compose, sem necessidade de hospedagem em nuvem

## 9. Restrições

- Prazo definido pelo cronograma da disciplina
- Tecnologias fixadas em `docs/stack.md`; qualquer mudança de stack após o início do desenvolvimento deve ser acordada entre os membros do grupo
- Tamanho do grupo entre 2 e 3 alunos, conforme regra da disciplina

## 10. Critérios de Aceite do MVP

O projeto é considerado no mínimo entregável quando:

- O fluxo completo (solicitar, aprovar, reservar, retirar, devolver) funciona de ponta a ponta
- Um usuário não pode aprovar a própria solicitação
- O sistema impede duas reservas sobrepostas para o mesmo equipamento
- Toda ação relevante fica registrada na trilha de auditoria
- O projeto sobe por completo com `docker compose up`

Os critérios detalhados de cada requisito estão em `docs/requisitos.md`, seção 8 (Escopo do MVP).
