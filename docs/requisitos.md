# Documento de Requisitos
## Sistema de Empréstimo de Equipamentos Acadêmicos

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Data | Agosto/2026 |
| Status | Em definição |

---

## 1. Visão Geral

### 1.1 Objetivo

Substituir o controle manual (planilhas, fichas em papel e cadernos) do empréstimo de equipamentos acadêmicos por um sistema web que garanta **rastreabilidade**, **responsabilização** e **auditoria** de cada movimentação de equipamento.

### 1.2 Problema

O controle manual gera atrasos e erros, não permite histórico confiável, não identifica o responsável em caso de extravio ou dano, e não impede que um equipamento seja reservado por duas pessoas ao mesmo tempo.

### 1.3 Escopo

O sistema cobre o ciclo completo:

```
Aluno solicita → Responsável aprova → Equipamento reservado
     → Retirada → Uso → Devolução → (Penalidade, se houver atraso)
```

Tipos de equipamento atendidos: notebooks, câmeras, projetores, kits Arduino, equipamentos de laboratório e instrumentos.

### 1.4 Fora de Escopo (v1)

- Integração com sistema acadêmico da instituição (SIGA/SUAP)
- Compra, licitação ou baixa patrimonial de equipamentos
- Rastreamento por GPS/RTLS em tempo real
- Aplicativo mobile nativo (a interface web será responsiva)
- Cobrança financeira efetiva de multas (o sistema registra, não cobra)

### 1.5 Atores

| Ator | Descrição | Responsabilidade principal |
|---|---|---|
| **Aluno** | Discente da instituição | Solicita, retira e devolve equipamentos |
| **Docente** | Professor responsável | Aprova ou rejeita solicitações |
| **Técnico** | Responsável pelo laboratório | Registra retirada/devolução, avalia condição do item |
| **Administrador** | Gestor do sistema | Gerencia usuários, catálogo, políticas e relatórios |

---

## 2. Requisitos Funcionais

**Legenda de prioridade:** 🔴 Essencial (MVP) · 🟡 Importante · 🟢 Desejável

### 2.1 Autenticação e Gestão de Usuários

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF01 | O sistema deve permitir autenticação por e-mail institucional e senha | Todos | 🔴 |
| RF02 | O sistema deve associar cada usuário a exatamente um papel: Aluno, Docente, Técnico ou Administrador | Admin | 🔴 |
| RF03 | O sistema deve restringir funcionalidades e dados conforme o papel do usuário | Todos | 🔴 |
| RF04 | O sistema deve permitir ao Administrador cadastrar, editar, ativar e desativar usuários | Admin | 🔴 |
| RF05 | O sistema deve permitir ao usuário alterar a própria senha | Todos | 🔴 |
| RF06 | O sistema deve permitir recuperação de senha por e-mail | Todos | 🟡 |
| RF07 | O sistema deve encerrar a sessão automaticamente após período de inatividade | Todos | 🟡 |
| RF08 | O sistema deve permitir vincular um aluno a um curso e a um docente orientador | Admin | 🟢 |

### 2.2 Catálogo de Equipamentos

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF10 | O sistema deve permitir cadastrar equipamentos com nome, descrição, categoria, número de patrimônio, número de série e laboratório de origem | Técnico, Admin | 🔴 |
| RF11 | O sistema deve gerar e exibir um identificador único por equipamento (código/QR Code) | Técnico | 🔴 |
| RF12 | O sistema deve manter o status de cada equipamento: Disponível, Reservado, Emprestado, Em manutenção, Baixado, Perdido | Sistema | 🔴 |
| RF13 | O sistema deve permitir organizar equipamentos em categorias | Admin | 🔴 |
| RF14 | O sistema deve permitir consultar o catálogo com busca por nome, categoria, laboratório e disponibilidade | Todos | 🔴 |
| RF15 | O sistema deve permitir definir por equipamento o prazo máximo de empréstimo (em dias) | Admin | 🔴 |
| RF16 | O sistema deve permitir classificar o equipamento por criticidade/valor, definindo se exige aprovação de nível superior | Admin | 🟡 |
| RF17 | O sistema deve permitir anexar foto e manual do equipamento | Técnico | 🟢 |
| RF18 | O sistema deve permitir registrar entrada e saída de manutenção, tornando o item indisponível no período | Técnico | 🟢 |

### 2.3 Solicitação de Empréstimo

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF20 | O sistema deve permitir ao aluno solicitar um ou mais equipamentos em uma única solicitação | Aluno | 🔴 |
| RF21 | O sistema deve exigir na solicitação a finalidade de uso, a data prevista de retirada e a data prevista de devolução | Aluno | 🔴 |
| RF22 | O sistema deve validar a disponibilidade do equipamento no período solicitado antes de aceitar a solicitação | Sistema | 🔴 |
| RF23 | O sistema deve impedir a solicitação por usuário com pendência ativa (atraso ou penalidade) | Sistema | 🔴 |
| RF24 | O sistema deve permitir ao solicitante cancelar a própria solicitação enquanto ela não tiver sido retirada | Aluno | 🔴 |
| RF25 | O sistema deve permitir ao aluno consultar o status atual de suas solicitações | Aluno | 🔴 |
| RF26 | O sistema deve limitar a quantidade de itens simultâneos por usuário conforme política configurável | Sistema | 🟡 |
| RF27 | O sistema deve exigir antecedência mínima configurável entre a solicitação e a retirada | Sistema | 🟢 |

### 2.4 Aprovação (Autorização)

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF30 | O sistema deve encaminhar cada solicitação a um responsável habilitado para aprovação | Sistema | 🔴 |
| RF31 | O sistema deve permitir ao responsável aprovar ou rejeitar a solicitação | Docente, Técnico | 🔴 |
| RF32 | O sistema deve exigir justificativa obrigatória na rejeição | Docente, Técnico | 🔴 |
| RF33 | O sistema deve impedir que o solicitante aprove a própria solicitação, em qualquer circunstância | Sistema | 🔴 |
| RF34 | O sistema deve registrar o aprovador, a data/hora e a decisão de cada aprovação | Sistema | 🔴 |
| RF35 | O sistema deve exigir aprovação adicional (segundo nível) para equipamentos classificados como críticos | Sistema | 🟡 |
| RF36 | O sistema deve listar ao responsável as solicitações pendentes de sua decisão | Docente, Técnico | 🔴 |
| RF37 | O sistema deve cancelar automaticamente solicitações não aprovadas dentro do prazo configurado | Sistema | 🟢 |

### 2.5 Reserva

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF40 | O sistema deve reservar o equipamento no período aprovado, tornando-o indisponível para outros usuários | Sistema | 🔴 |
| RF41 | O sistema deve impedir a existência de duas reservas com sobreposição de período para o mesmo equipamento | Sistema | 🔴 |
| RF42 | O sistema deve liberar automaticamente a reserva se a retirada não ocorrer até o prazo limite | Sistema | 🟡 |
| RF43 | O sistema deve exibir um calendário de disponibilidade por equipamento | Todos | 🟢 |

### 2.6 Retirada

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF50 | O sistema deve permitir ao técnico registrar a retirada apenas de empréstimos previamente aprovados | Técnico | 🔴 |
| RF51 | O sistema deve exigir a identificação do retirante e validar que corresponde ao solicitante | Técnico | 🔴 |
| RF52 | O sistema deve gerar um termo de responsabilidade e exigir o aceite eletrônico antes de concluir a retirada | Aluno | 🔴 |
| RF53 | O sistema deve registrar a condição do equipamento na retirada por meio de checklist | Técnico | 🔴 |
| RF54 | O sistema deve calcular e registrar a data prevista de devolução no momento da retirada | Sistema | 🔴 |
| RF55 | O sistema deve permitir identificar o equipamento por leitura de QR Code/código de barras na retirada | Técnico | 🟢 |
| RF56 | O sistema deve permitir anexar foto do equipamento no momento da retirada | Técnico | 🟢 |

### 2.7 Devolução

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF60 | O sistema deve permitir ao técnico registrar a devolução, validando que os itens pertencem ao empréstimo ativo | Técnico | 🔴 |
| RF61 | O sistema deve permitir devolução parcial, mantendo o empréstimo aberto para os itens não devolvidos | Técnico | 🔴 |
| RF62 | O sistema deve exigir o registro da condição do equipamento na devolução | Técnico | 🔴 |
| RF63 | O sistema deve permitir registrar ocorrência de dano, avaria ou perda na devolução | Técnico | 🔴 |
| RF64 | O sistema deve retornar o equipamento ao status Disponível após devolução sem ocorrência | Sistema | 🔴 |
| RF65 | O sistema deve encaminhar automaticamente para manutenção o equipamento devolvido com avaria | Sistema | 🟡 |
| RF66 | O sistema deve permitir solicitar prorrogação do prazo, sujeita a aprovação e à inexistência de reserva concorrente | Aluno | 🟢 |

### 2.8 Controle de Atraso e Penalidades

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF70 | O sistema deve alterar automaticamente para "Atrasado" o empréstimo não devolvido após a data prevista | Sistema | 🔴 |
| RF71 | O sistema deve bloquear novas solicitações de usuário com empréstimo em atraso | Sistema | 🔴 |
| RF72 | O sistema deve registrar penalidade com data de início, data de término e motivo | Sistema | 🟡 |
| RF73 | O sistema deve aplicar suspensão automática conforme política configurável de reincidência | Sistema | 🟡 |
| RF74 | O sistema deve marcar o equipamento como Perdido após período configurável de atraso | Sistema | 🟡 |
| RF75 | O sistema deve permitir ao Administrador remover manualmente uma penalidade, com justificativa registrada | Admin | 🟡 |

### 2.9 Notificações

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF80 | O sistema deve notificar o responsável quando houver solicitação pendente de aprovação | Sistema | 🔴 |
| RF81 | O sistema deve notificar o solicitante sobre aprovação ou rejeição da solicitação | Sistema | 🔴 |
| RF82 | O sistema deve enviar lembrete de devolução com antecedência configurável | Sistema | 🔴 |
| RF83 | O sistema deve notificar o usuário no dia do vencimento e em intervalos escalonados após o atraso | Sistema | 🔴 |
| RF84 | O sistema deve notificar o técnico responsável sobre empréstimos em atraso no seu laboratório | Sistema | 🟡 |
| RF85 | O sistema deve manter histórico das notificações enviadas | Sistema | 🟢 |

### 2.10 Auditoria e Histórico

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF90 | O sistema deve registrar todo evento relevante do empréstimo, contendo autor, ação, data/hora e dados de contexto | Sistema | 🔴 |
| RF91 | O sistema deve impedir alteração ou exclusão de registros de auditoria | Sistema | 🔴 |
| RF92 | O sistema deve permitir consultar o histórico completo de custódia de um equipamento | Técnico, Admin | 🔴 |
| RF93 | O sistema deve permitir consultar o histórico completo de empréstimos de um usuário | Docente, Admin | 🔴 |
| RF94 | O sistema deve registrar exclusões lógicas como eventos, sem remoção física de dados | Sistema | 🔴 |
| RF95 | O sistema deve permitir filtrar a trilha de auditoria por período, usuário e tipo de ação | Admin | 🟡 |

### 2.11 Relatórios e Dashboard

| ID | Requisito | Ator | Prior. |
|---|---|---|---|
| RF100 | O sistema deve exibir painel com totais de equipamentos disponíveis, emprestados e em atraso | Técnico, Admin | 🔴 |
| RF101 | O sistema deve gerar relatório de empréstimos por período | Admin | 🔴 |
| RF102 | O sistema deve gerar relatório de atrasos por usuário | Admin | 🔴 |
| RF103 | O sistema deve gerar relatório de utilização por equipamento e por categoria | Admin | 🟡 |
| RF104 | O sistema deve permitir exportar relatórios em CSV | Admin | 🟡 |
| RF105 | O sistema deve exibir ranking de equipamentos mais demandados, como apoio a decisões de aquisição | Admin | 🟢 |

---

## 3. Requisitos Não Funcionais

### 3.1 Desempenho

| ID | Requisito | Métrica |
|---|---|---|
| RNF01 | Operações de solicitação, aprovação, retirada e devolução devem responder em até 2 segundos | p95 < 2s |
| RNF02 | Consultas ao catálogo devem responder em até 1 segundo | p95 < 1s |
| RNF03 | O sistema deve suportar ao menos 100 usuários simultâneos sem degradação perceptível | — |
| RNF04 | Notificações devem ser processadas de forma assíncrona, sem bloquear a requisição do usuário | — |

### 3.2 Segurança

| ID | Requisito |
|---|---|
| RNF10 | Senhas devem ser armazenadas com hash criptográfico (bcrypt ou Argon2), nunca em texto puro |
| RNF11 | A autenticação deve usar tokens com expiração (JWT ou sessão segura) |
| RNF12 | Toda comunicação deve ocorrer sobre HTTPS |
| RNF13 | O controle de acesso deve ser validado no servidor, nunca apenas na interface |
| RNF14 | Regras críticas (não auto-aprovação, conflito de reserva) devem ser garantidas na camada de serviço e/ou no banco de dados, não apenas na interface |
| RNF15 | O sistema deve ser protegido contra SQL Injection, XSS e CSRF |
| RNF16 | Tentativas de login devem ser limitadas por taxa (rate limiting) |

### 3.3 Usabilidade

| ID | Requisito |
|---|---|
| RNF20 | A interface deve ser responsiva, utilizável em desktop e celular |
| RNF21 | Um aluno deve conseguir concluir uma solicitação em no máximo 3 telas |
| RNF22 | Mensagens de erro devem ser claras e orientar a ação corretiva |
| RNF23 | O estado atual de cada empréstimo deve ser visualmente distinguível |
| RNF24 | A interface deve seguir diretrizes básicas de acessibilidade (contraste, navegação por teclado, labels) |

### 3.4 Confiabilidade e Disponibilidade

| ID | Requisito |
|---|---|
| RNF30 | O sistema deve estar disponível 24/7, com janela de manutenção comunicada |
| RNF31 | Operações que alteram estado devem ser transacionais (tudo ou nada) |
| RNF32 | O banco de dados deve ter rotina de backup diário |
| RNF33 | Falhas de envio de notificação não devem impedir a conclusão da operação principal |

### 3.5 Manutenibilidade

| ID | Requisito |
|---|---|
| RNF40 | O código deve ser organizado em camadas, com a regra de negócio isolada da camada de apresentação |
| RNF41 | A API deve ser documentada (OpenAPI/Swagger) |
| RNF42 | O projeto deve ter testes automatizados cobrindo as regras de negócio críticas |
| RNF43 | O projeto deve executar com um único comando via containerização |
| RNF44 | Alterações no esquema do banco devem ser versionadas por migrations |

### 3.6 Escalabilidade e Portabilidade

| ID | Requisito |
|---|---|
| RNF50 | A arquitetura deve permitir adicionar novos tipos de equipamento e novos laboratórios sem alteração de código |
| RNF51 | Políticas (prazos, limites, penalidades) devem ser configuráveis, não fixas no código |
| RNF52 | O sistema deve funcionar nos navegadores modernos (Chrome, Firefox, Edge, Safari) |

### 3.7 Legais e de Conformidade

| ID | Requisito |
|---|---|
| RNF60 | O tratamento de dados pessoais deve estar em conformidade com a LGPD (Lei 13.709/2018) |
| RNF61 | Devem ser coletados apenas os dados necessários à finalidade do empréstimo |
| RNF62 | O termo de responsabilidade aceito deve ser preservado com data, hora e identificação do aceite |
| RNF63 | O usuário deve ser informado sobre quais dados são coletados e com qual finalidade |

---

## 4. Regras de Negócio

| ID | Regra |
|---|---|
| RN01 | O solicitante nunca pode ser o aprovador da mesma solicitação |
| RN02 | Um equipamento não pode ter duas reservas com sobreposição de período |
| RN03 | Nenhuma retirada pode ocorrer sem aprovação prévia registrada |
| RN04 | Nenhuma retirada pode ocorrer sem aceite do termo de responsabilidade |
| RN05 | Usuário com empréstimo em atraso ou penalidade ativa não pode iniciar nova solicitação |
| RN06 | O prazo de devolução é contado a partir da data efetiva de retirada, não da solicitação |
| RN07 | Equipamento com avaria registrada não retorna ao status Disponível automaticamente |
| RN08 | Registros de auditoria são somente-inserção: nunca alterados nem excluídos |
| RN09 | Toda rejeição de solicitação exige justificativa |
| RN10 | Equipamentos classificados como críticos exigem aprovação de nível superior |
| RN11 | O cancelamento só é permitido antes da retirada |
| RN12 | Prorrogação só é concedida se não houver reserva concorrente no período estendido |

---

## 5. Máquina de Estados do Empréstimo

```
                    ┌─────────────┐
                    │ SOLICITADO  │
                    └──────┬──────┘
              ┌────────────┼────────────┐
        rejeita       aprova        cancela
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌───────────┐
        │REJEITADO │ │ APROVADO │ │ CANCELADO │
        └──────────┘ └────┬─────┘ └───────────┘
                          │ reserva confirmada
                          ▼
                    ┌──────────┐
                    │RESERVADO │──── prazo expirado ──▶ CANCELADO
                    └────┬─────┘
                         │ retirada registrada
                         ▼
                    ┌──────────┐
                    │ RETIRADO │
                    └────┬─────┘
              ┌──────────┼──────────┐
          devolve   vence prazo     │
              ▼          ▼          │
        ┌──────────┐ ┌──────────┐   │
        │DEVOLVIDO │ │ ATRASADO │───┘ devolve
        └──────────┘ └────┬─────┘
                          │ prazo limite excedido
                          ▼
                    ┌──────────┐
                    │ PERDIDO  │
                    └──────────┘
```

**Regra:** toda transição não representada no diagrama deve ser rejeitada pelo sistema.

---

## 6. Matriz de Permissões

| Ação | Aluno | Docente | Técnico | Admin |
|---|:---:|:---:|:---:|:---:|
| Consultar catálogo | ✅ | ✅ | ✅ | ✅ |
| Solicitar empréstimo | ✅ | ✅ | — | — |
| Aprovar/rejeitar solicitação | — | ✅ | ✅ | ✅ |
| Registrar retirada | — | — | ✅ | ✅ |
| Registrar devolução | — | — | ✅ | ✅ |
| Registrar avaria/perda | — | — | ✅ | ✅ |
| Cadastrar/editar equipamento | — | — | ✅ | ✅ |
| Ver próprio histórico | ✅ | ✅ | ✅ | ✅ |
| Ver histórico de terceiros | — | ✅¹ | ✅² | ✅ |
| Gerenciar usuários e papéis | — | — | — | ✅ |
| Configurar políticas | — | — | — | ✅ |
| Consultar trilha de auditoria | — | — | — | ✅ |
| Gerar relatórios | — | ✅¹ | ✅² | ✅ |

¹ Restrito aos alunos sob sua orientação · ² Restrito ao seu laboratório

---

## 7. Rastreabilidade: Problema → Requisito

| Problema identificado | Requisitos que o resolvem |
|---|---|
| Ausência de histórico e rastreabilidade | RF90, RF92, RF93, RF11 |
| Atraso e não-devolução | RF70, RF71, RF82, RF83, RF74 |
| Extravio/dano sem responsável identificável | RF52, RF53, RF62, RF63, RNF62 |
| Aprovação fraudulenta / auto-aprovação | RF33, RF34, RF35, RN01 |
| Retirada sem autorização | RF50, RF51, RN03 |
| Conflito de reserva (double-booking) | RF41, RNF14, RN02 |
| Dependência de atendimento presencial | RF20, RF25, RNF20 |
| Registro item a item inviabilizando relatórios | RF20, RF61 |

---

## 8. Escopo do MVP

Entram no MVP todos os requisitos marcados como 🔴 **Essencial**, o que corresponde ao fluxo completo:

**solicitar → aprovar → reservar → retirar → devolver**, com controle de acesso, termo de responsabilidade, prevenção de double-booking, trilha de auditoria e notificação de vencimento.

Requisitos 🟡 e 🟢 compõem as iterações seguintes.
