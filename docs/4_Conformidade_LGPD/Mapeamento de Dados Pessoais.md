# Mapeamento de Dados Pessoais — EmprestaCampus

**Fonte no código:** `backend/usuarios/lgpd.py`
**Testes:** `backend/usuarios/testes_lgpd.py`

---

## 1. Objetivo

Este documento associa **cada campo** gravado pelo sistema que se refere a uma pessoa a uma ou mais **finalidades**, a uma **base legal** da LGPD (art. 7º) e a um **prazo de retenção**. Também registra as decisões de **minimização**: o que o sistema deixou de coletar ou de guardar e por quê.

O mapeamento não existe só neste documento. Ele está no código, em `usuarios/lgpd.py`, e um teste automatizado compara esse mapeamento com os campos reais do banco (seção 6). Se alguém criar um campo novo sem classificá-lo, o teste falha e a mudança não entra na `main`.

## 2. Finalidades e bases legais

| Código | Finalidade | Base legal |
|---|---|---|
| `acesso` | Identificar o titular e permitir o login com segurança | Execução de contrato (art. 7º, V) |
| `emprestimo` | Registrar quem solicitou, retirou e devolveu cada equipamento | Execução de contrato (art. 7º, V) |
| `comunicacao` | Avisar o titular sobre a segurança da conta e permitir a recuperação de senha | Execução de contrato (art. 7º, V) |
| `avisos_emprestimo` | Avisar por e-mail sobre o andamento dos empréstimos (aprovação, recusa, devolução, prorrogação) | Consentimento (art. 7º, I); opcional |
| `contato_alternativo` | Contato da equipe com o titular, por telefone, sobre um equipamento emprestado | Consentimento (art. 7º, I); opcional |
| `consentimento` | Comprovar quando e qual versão da política o titular aceitou | Cumprimento de obrigação legal (art. 7º, II; art. 8º, § 2º) |
| `seguranca` | Proteger as contas, investigar incidentes e manter a trilha de auditoria | Legítimo interesse (art. 7º, IX; art. 10, § 3º) |

**Por que nem tudo é consentimento.** O empréstimo de um equipamento da instituição não acontece sem saber quem o retirou. Esses dados são condição do próprio serviço, e a base legal adequada é a execução de contrato (art. 7º, V). Se fossem tratados como consentimento, revogar o consentimento teria que apagar o registro de quem está com um equipamento, o que inviabilizaria o controle patrimonial. O consentimento fica reservado para o que é **opcional**: os avisos por e-mail sobre os empréstimos e o contato por telefone. Cada um tem aceite próprio.

**Legítimo interesse e segurança.** Os registros de segurança (auditoria, tentativas de login) protegem o próprio titular, e o art. 10, § 3º, exige transparência sobre esse uso. Por isso eles estão descritos na Política de Privacidade.

## 3. Mapeamento campo a campo

Os prazos marcados com **(automático)** são aplicados pela rotina de retenção do item 4.10. Os demais acompanham a vida da conta.

### 3.1 Conta do usuário (`usuarios.Usuario`)

| Campo | Dado | Finalidade | Retenção |
|---|---|---|---|
| `username` | Nome de usuário | `acesso` | Enquanto a conta existir; anonimizado no encerramento |
| `password` | Hash da senha (PBKDF2-SHA256) | `acesso` | Enquanto a conta existir; invalidado no encerramento |
| `first_name`, `last_name` | Nome e sobrenome | `acesso` | Enquanto a conta existir; anonimizados no encerramento |
| `email` | E-mail institucional | `comunicacao`; `avisos_emprestimo` (só com consentimento) | Enquanto a conta existir; anonimizado no encerramento |
| `matricula` | Matrícula (RA/SIAPE) | `emprestimo` | Enquanto a conta existir; anonimizada no encerramento |
| `papel` | Vínculo (aluno, docente, administrador) | `acesso` | Enquanto a conta existir |
| `telefone` | Telefone, **cifrado** (Fernet) | `contato_alternativo` | Enquanto houver consentimento; apagado no encerramento |
| `is_active` | Conta ativa ou suspensa | `acesso` | Enquanto a conta existir |
| `date_joined` | Data de criação da conta | `acesso` | Enquanto a conta existir |
| `last_login` | Data do último login | `seguranca` | Enquanto a conta existir |
| `consentimento_dados`, `data_consentimento`, `versao_documento_aceito` | Registro do aceite da política | `consentimento` | Mantido junto à conta, inclusive após a anonimização, como prova do consentimento (art. 8º, § 2º) |

**Histórico de consentimento por finalidade (`usuarios.ConsentimentoFinalidade`):** os campos `usuario`, `finalidade`, `aceito`, `data_hora` e `versao_politica` registram cada aceite e cada recusa das finalidades opcionais. Finalidade: `consentimento`. Retenção: igual à do registro do aceite. Os registros nunca são alterados; cada mudança vira uma linha nova.

**Conta suspensa por revogação do consentimento:** os dados ficam guardados para que o próprio titular possa reativar a conta. Depois de **12 meses** sem reativação, a conta é anonimizada **(automático)**.

### 3.2 Autenticação

| Modelo | Campo | Dado | Finalidade | Retenção |
|---|---|---|---|---|
| `DispositivoTOTP` | `user`, `key`, `confirmed` | Chave secreta do 2FA, **cifrada** (Fernet) | `acesso` | Até o titular desativar o 2FA ou encerrar a conta |
| `DispositivoTOTP` | `last_t`, `throttling_failure_*`, `created_at`, `last_used_at` | Controle de replay, tentativas erradas e uso | `seguranca` | Junto com o dispositivo |
| `TokenRecuperacaoSenha` | `usuario`, `token`, `criado_em`, `expira_em`, `usado` | Link de redefinição de senha | `acesso` | Válido por 1 hora; apagado 7 dias depois de expirar **(automático)** e no encerramento |

### 3.3 Empréstimos e notificações

| Modelo | Campo | Dado | Finalidade | Retenção |
|---|---|---|---|---|
| `Emprestimo` | `usuario`, `equipamento`, datas, `status`, `prorrogacao_solicitada` | Histórico de empréstimos | `emprestimo` | **5 anos** após a devolução, para o controle patrimonial; após o encerramento da conta, fica ligado à conta anonimizada |
| `Emprestimo` | `observacoes` | Texto livre do titular | `emprestimo` | Apagado no encerramento da conta, porque pode conter dado pessoal |
| `Notificacao` | `usuario`, `mensagem`, `tipo`, `lida`, `data_criacao` | Avisos enviados ao titular | `comunicacao`; `avisos_emprestimo` (só gravados com consentimento) | Lidas: **90 dias** **(automático)**; todas: apagadas no encerramento |

### 3.4 Segurança e auditoria

| Modelo | Campo | Dado | Finalidade | Retenção |
|---|---|---|---|---|
| `RegistroAuditoria` | `usuario`, `acao`, `modulo_afetado`, `descricao`, `ip_origem`, `data_hora` | Trilha de auditoria, com IP | `seguranca` | **5 anos**; imutável (trigger no PostgreSQL). A justificativa para mantê-la após o encerramento da conta está no item 4.10 |
| `admin.LogEntry` | `user`, `action_time`, `object_repr`, `change_message` etc. | Alterações feitas pelos administradores no `/admin/` | `seguranca` | **5 anos** |
| `axes.AccessAttempt` | `username`, `ip_address`, `user_agent`, `post_data` etc. | Tentativas de login erradas, para o bloqueio contra força bruta | `seguranca` | **30 dias** após a tentativa **(automático)**. A senha digitada **não** é guardada: o `django-axes` a substitui por `********` |
| Sessão (`django_session`) | Identificador da sessão e do usuário | Manter o titular logado | `acesso` | 30 minutos de inatividade; sessões expiradas apagadas diariamente **(automático)** |
| Cookie `fuso_horario_usuario` | Fuso horário do navegador | Exibir datas no horário local | `acesso` | 1 ano, **só no navegador**; não é gravado no servidor |

### 3.5 Campos técnicos (sem dado pessoal)

| Modelo | Campos | Por que não são dado pessoal |
|---|---|---|
| `Usuario` | `is_staff`, `is_superuser` | Derivados automaticamente do `papel`; não acrescentam informação sobre o titular |
| `DispositivoTOTP` | `name`, `step`, `t0`, `digits`, `tolerance`, `drift` | Parâmetros do algoritmo TOTP, iguais para todos os usuários |

Também ficam fora do mapeamento:

- os modelos de catálogo (`Equipamento`, `Categoria`), que descrevem bens da instituição, e não pessoas;
- a tabela `otp_totp_totpdevice`, do `django-otp`, que fica vazia desde a migração `0011_migrar_dispositivos_totp`;
- as tabelas `axes_accesslog` e `axes_accessfailurelog`, que ficam vazias por configuração (seção 4).

## 4. Minimização de dados (item 4.3)

### 4.1 O que o sistema não coleta

O cadastro pede apenas nome, e-mail, usuário, senha, matrícula, vínculo e, opcionalmente, telefone. O sistema **não coleta** CPF, RG, endereço, data de nascimento, foto, gênero, dados de saúde, dados financeiros nem qualquer dado sensível do art. 5º, II.

Isso não depende só do formulário. A API de cadastro aceita somente os campos listados no `RegistroSerializer`. Qualquer outro campo enviado, como `cpf` ou `endereco`, é **descartado** sem ser gravado. Também é recusada qualquer tentativa de se cadastrar com privilégios (`is_staff`, `is_superuser` ou papel de administrador).

### 4.2 Decisões de minimização tomadas nesta revisão

| Antes | Problema | Mudança |
|---|---|---|
| O formulário de cadastro **exigia** o telefone | Nenhuma função do sistema depende do telefone: as notificações são enviadas por e-mail. Exigir o dado contrariava o art. 6º, III | Telefone **opcional** no formulário; campo vazio é gravado como nulo, e não como texto vazio |
| O `django-axes` gravava **cada login bem-sucedido** numa tabela própria (`AccessLog`), com IP e navegador, sem prazo | Cópia duplicada do registro `LOGIN_SUCESSO` da auditoria, com um dado a mais (o navegador) e sem finalidade própria | `AXES_DISABLE_ACCESS_LOG = True`. As tentativas **erradas** continuam registradas, porque são necessárias para o bloqueio |

### 4.3 Medidas de minimização já existentes

- **Senha:** guardada só como hash; nunca é devolvida em resposta da API (`write_only`).
- **Telefone e chave do 2FA:** cifrados no banco (item 3.4).
- **Auditoria:** os registros novos não guardam o texto digitado no login (usuário ou e-mail informado), apenas o resultado e o IP.
- **Visibilidade:** a API de empréstimos devolve a cada titular só os próprios empréstimos; os dados dos demais usuários e o histórico de notificações ficam restritos aos administradores, no `/admin/`.
- **Exportação (art. 18, V):** devolve apenas os dados do próprio titular.

## 5. Relação com os demais itens

- **4.5 — Consentimento por finalidade:** as finalidades `avisos_emprestimo` e `contato_alternativo` dependem de consentimento próprio, separado do aceite da política (modelo `ConsentimentoFinalidade`; testes em `usuarios/testes_consentimento.py`).
- **4.10 — Eliminação e retenção:** os prazos marcados como **(automático)** na seção 3 são aplicados pela rotina de retenção, e o encerramento da conta passa a cobrir todos os campos indicados como "apagado no encerramento".

## 6. Como a completude do mapeamento é verificada

O arquivo `backend/usuarios/testes_lgpd.py` contém estes testes:

| Teste | O que garante |
|---|---|
| `test_todo_campo_esta_mapeado` | Para cada modelo, os campos mapeados mais os campos técnicos são **exatamente** os campos do banco: nenhum fica sem classificação e nenhum aparece duas vezes |
| `test_todo_modelo_ligado_a_um_usuario_esta_mapeado` | Qualquer modelo do projeto com vínculo a um usuário precisa estar no mapeamento |
| `test_toda_finalidade_usada_existe_e_tem_base_legal` | Toda finalidade usada está descrita e tem base legal do art. 7º |
| `test_cadastro_funciona_sem_telefone` | O telefone é de fato opcional na API |
| `test_formulario_de_cadastro_nao_exige_telefone` | O formulário web não marca o telefone como obrigatório |
| `test_cadastro_descarta_dados_nao_previstos` | CPF, endereço, data de nascimento e flags de privilégio enviados no cadastro não são gravados nem devolvidos |
| `test_login_nao_grava_copia_no_axes` | O login bem-sucedido fica só na auditoria, sem cópia na tabela do `django-axes` |
| `test_tentativa_errada_continua_registrada_para_o_bloqueio` | As tentativas erradas continuam registradas, sem a senha digitada |
