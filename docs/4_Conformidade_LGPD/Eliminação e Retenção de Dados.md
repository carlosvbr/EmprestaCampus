# Eliminação, Anonimização e Retenção de Dados — EmprestaCampus

**Fonte no código:** `backend/usuarios/retencao.py`, comando `aplicar_retencao` e migração `auditoria/0004_retencao_da_auditoria`
**Testes:** `backend/usuarios/testes_retencao.py`

---

## 1. Objetivo

Este documento descreve o que acontece com os dados pessoais quando:

- o titular encerra a conta;
- a conta fica suspensa por muito tempo;
- cada dado atinge o fim do seu prazo de retenção.

Também trata dos backups e justifica por que alguns registros continuam guardados depois do encerramento da conta (LGPD, arts. 15 e 16).

## 2. Encerramento da conta (art. 18, IV e VI)

O titular encerra a conta em **Meu Perfil → Encerrar Minha Conta**. A operação é irreversível e é feita pela função `anonimizar_usuario`, numa única transação.

### 2.1 O que é anonimizado ou eliminado

| Dado | O que acontece |
|---|---|
| Nome, sobrenome, nome de usuário, e-mail e matrícula | Substituídos por valores anônimos (`Usuário Anonimizado`, `anon_<id>`, `anon_<id>@emprestacampus.local`) |
| Telefone | Apagado |
| Senha | Tornada inutilizável; não é possível entrar nem reativar a conta |
| Data do último login | Apagada |
| Chave do 2FA | Apagada |
| Links de recuperação de senha | Apagados |
| Notificações | Apagadas, porque o texto pode citar o nome do titular |
| Observações dos empréstimos | Apagadas, porque são texto livre e podem conter dado pessoal |
| Tentativas de login no `django-axes` | Apagadas (usuário e IP) |
| Sessões abertas em qualquer navegador | Encerradas |

### 2.2 Empréstimo em aberto bloqueia o encerramento

Se o titular tem um empréstimo **solicitado, aprovado, retirado ou atrasado**, o encerramento é recusado com uma mensagem explicando o motivo. Enquanto a pessoa está com um equipamento da instituição, ou pode vir a estar, a instituição precisa saber quem ela é. Anonimizar nesse momento apagaria a responsabilidade pelo bem. Depois da devolução ou da decisão sobre a solicitação, o encerramento fica disponível.

### 2.3 O que permanece, e por quê

| Dado que permanece | Base legal para manter (art. 16) | Até quando |
|---|---|---|
| Histórico de empréstimos (equipamento, datas, situação), ligado à conta **já anônima** | Art. 16, I: cumprimento de obrigação legal ou regulatória pelo controlador, no caso o controle patrimonial dos bens da instituição. Sem a identidade, o histórico deixa de ser dado pessoal | 5 anos após a devolução |
| Histórico de consentimento (aceites e recusas, com data e versão) | Art. 8º, § 2º: cabe ao controlador provar que o consentimento foi obtido | Junto com a conta anônima |
| Trilha de auditoria | Art. 16, I, e art. 37 (registro das operações de tratamento); legítimo interesse na segurança (art. 7º, IX) | 5 anos (seção 4) |
| Histórico de ações dos administradores (`/admin/`) | Mesma base da auditoria | 5 anos |

**O conflito com os logs imutáveis.** A trilha de auditoria não pode ser alterada nem apagada (item 5.3), então os registros antigos de um titular continuam com o nome de usuário e o IP da época, mesmo depois do encerramento. Isso é permitido pelo art. 16, I, mas não por tempo indeterminado. Por isso a imutabilidade agora vale **durante o prazo de retenção de 5 anos**. Depois disso, o registro pode ser eliminado (seção 4).

## 3. Conta suspensa por revogação do consentimento

Quando o titular revoga o consentimento geral, o acesso é suspenso e a data fica registrada (`consentimento_revogado_em`). Os dados ficam guardados para que ele mesmo possa reativar a conta com a senha.

Depois de **12 meses** sem reativação, a rotina de retenção anonimiza a conta automaticamente, do mesmo jeito que no encerramento. A exceção é a conta que ainda tem empréstimo em aberto: ela fica de fora até a devolução, pelo mesmo motivo da seção 2.2.

Contas desativadas pelo administrador, sem revogação do consentimento, não entram nessa regra.

As contas que já estavam suspensas antes desta versão receberam como data de revogação a data da migração `0014`. Assim, o prazo de 12 meses só pode ser adiado, nunca antecipado.

## 4. Rotina de retenção

O comando abaixo aplica todos os prazos de uma vez:

```bash
python manage.py aplicar_retencao
```

Ele deve ser **agendado uma vez por dia**, no cron do servidor ou no agendador da plataforma de hospedagem. No Docker, por exemplo:

```bash
docker compose exec backend python manage.py aplicar_retencao
```

| O que é eliminado | Prazo |
|---|---|
| Links de recuperação de senha | 7 dias depois de expirar |
| Notificações | 90 dias |
| Tentativas de login erradas (`django-axes`) | 30 dias |
| Sessões | Logo depois de expirar |
| Contas suspensas por revogação | Anonimizadas depois de 12 meses (seção 3) |
| Empréstimos devolvidos ou rejeitados | 5 anos |
| Histórico de ações dos administradores | 5 anos |
| Trilha de auditoria | 5 anos |

Empréstimos em aberto **nunca** são eliminados pela rotina.

### 4.1 Retenção da auditoria sem abrir brecha na imutabilidade

A auditoria é protegida em três camadas: o modelo Django, o QuerySet e um trigger no PostgreSQL. A migração `auditoria/0004_retencao_da_auditoria` muda apenas uma regra do trigger: o `DELETE` passa a ser aceito **só** para registros com mais de 5 anos. O restante continua igual:

- qualquer `UPDATE` continua bloqueado, inclusive em registros antigos;
- qualquer `DELETE` de registro com menos de 5 anos continua bloqueado;
- como a data não pode ser alterada, não é possível "envelhecer" um registro para conseguir apagá-lo.

A rotina elimina os registros vencidos com um `DELETE` em SQL, porque o ORM recusa qualquer exclusão na auditoria. O prazo é conferido pelo próprio banco, com o relógio do PostgreSQL.

## 5. Backups

O EmprestaCampus não faz backups automáticos na versão entregue. Fazê-los é responsabilidade de quem opera o servidor. Para que um backup não desfaça a eliminação, a política para quem for operar o sistema é esta:

| Regra | Motivo |
|---|---|
| Os backups do banco são guardados por no máximo **35 dias**, em rodízio | Um dado eliminado do banco deixa de existir em todas as cópias em, no máximo, 35 dias |
| Os backups são cifrados e ficam em local com acesso restrito à equipe responsável | Um backup contém os mesmos dados pessoais do banco (art. 46) |
| Depois de restaurar um backup, roda-se `python manage.py aplicar_retencao` antes de liberar o acesso | Reaplica os prazos que venceram depois da data do backup |
| Contas encerradas entre a data do backup e a restauração são anonimizadas de novo, a partir dos registros `DELETE / Privacidade/LGPD` da auditoria | O encerramento não pode ser desfeito por uma restauração |

O telefone e a chave do 2FA continuam cifrados dentro do backup, porque são gravados cifrados no banco (item 3.4). Sem a `ENCRYPTION_KEY`, que não fica no banco, eles não podem ser lidos.

## 6. Testes

O arquivo `backend/usuarios/testes_retencao.py` simula a passagem do tempo passando a data "de agora" para a rotina, sem precisar envelhecer os registros. As exceções são os testes da auditoria: como o trigger usa o relógio do PostgreSQL, eles inserem registros já com a data no passado.

| Grupo | O que comprova |
|---|---|
| `TestEncerramentoDaConta` | Todos os vínculos da seção 2.1 são eliminados; o histórico patrimonial e o de consentimento ficam ligados à conta anônima; as sessões em outros navegadores são encerradas; empréstimo em aberto bloqueia o encerramento (4 situações) |
| `TestRotinaDeRetencao` | Cada prazo da seção 4: o dado continua um dia antes do prazo e some um dia depois; a conta suspensa é anonimizada depois de 12 meses, mas não se estiver com um equipamento; a conta desativada pelo administrador não entra na rotina; empréstimo em aberto nunca é apagado |
| `TestTriggerDaAuditoriaComRetencao` | Um registro com menos de 5 anos continua sem poder ser apagado; nenhum registro pode ser alterado, nem para mudar a data |
