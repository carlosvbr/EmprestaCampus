## Política de Privacidade e Transparência de Dados

Esta política descreve como o sistema EmprestaCampus realiza o tratamento dos seus dados pessoais, em estrita conformidade com a Lei Geral de Proteção de Dados (LGPD - Lei nº 13.709/2018). Cada uso dos seus dados tem uma base legal própria (Art. 7º): os dados necessários ao cadastro e aos empréstimos são tratados para a execução do serviço (Art. 7º, V); os registros de segurança, por legítimo interesse (Art. 7º, IX); e os usos opcionais, somente com o seu consentimento (Art. 7º, I), dado separadamente para cada um. O mapeamento completo, campo a campo, está em `Mapeamento de Dados Pessoais.md`.

A mesma política é exibida aos usuários na página `/api/usuarios/privacidade/` (template `usuarios/politica_privacidade.html`), cujo aceite é obrigatório no cadastro.

### 1. Dados Pessoais Coletados e Finalidade

* **Nome e Sobrenome:** Utilizados para a identificação do titular nas reservas e retiradas de equipamentos.
* **Nome de Usuário:** Utilizado para o acesso ao sistema (login).
* **Senha:** Utilizada para autenticar o titular. É armazenada apenas na forma de hash irreversível; a senha original nunca é guardada.
* **E-mail Institucional:** Utilizado para alertas de segurança da conta e recuperação de senha e, somente se você autorizar, para avisos sobre o andamento dos seus empréstimos.
* **Telefone:** Opcional. Guardado somente se você autorizar o contato da equipe por telefone sobre os seus empréstimos. Ao retirar a autorização, o telefone é apagado.
* **Matrícula (RA/SIAPE):** Utilizada para vincular o titular à instituição e garantir a responsabilidade patrimonial sobre os itens emprestados.
* **Vínculo (Aluno, Docente):** Utilizado para identificar a relação do titular com a instituição. As permissões de administração do sistema são atribuídas separadamente, apenas pela equipe responsável.
* **Histórico de Empréstimos:** Equipamentos solicitados, situação e datas de solicitação, retirada e devolução. Utilizado para a gestão dos empréstimos e o controle patrimonial.
* **Registro do Consentimento:** Data e versão desta política aceitas pelo titular e o histórico das autorizações opcionais (cada aceite e cada recusa, com data e versão). Utilizado para comprovar o consentimento.
* **Segredo da Autenticação em Dois Fatores (2FA):** Coletado somente se o titular ativar o 2FA. Utilizado exclusivamente para validar os códigos do aplicativo autenticador.
* **Logs de Acesso e IP:** Data, hora, ação realizada e endereço IP, coletados automaticamente para auditoria de segurança, prevenção a fraudes e rastreabilidade de ações no sistema.
* **Cookie de Fuso Horário:** Cookie técnico com o fuso horário do navegador, utilizado apenas para exibir datas e horários no horário local do titular. Não é usado para rastreamento.

**Usos opcionais (consentimento por finalidade):** cada um é autorizado separadamente, no cadastro ou em "Meu Perfil → Minhas Autorizações", e pode ser retirado a qualquer momento, sem perder o acesso ao sistema. Recusar não impede o uso do EmprestaCampus.

* **Avisos por e-mail sobre os empréstimos:** aprovação, recusa, devolução e prorrogação. Sem a autorização, esses avisos não são enviados; a situação dos empréstimos continua visível no sistema.
* **Contato por telefone:** o telefone só é guardado com a autorização e é apagado quando ela é retirada.

### 2. Princípio da Minimização de Dados

O EmprestaCampus adota estritamente o princípio da minimização (Art. 6º, III da LGPD). O sistema coleta e trata apenas os dados adequados, pertinentes e limitados ao mínimo necessário para a realização da gestão de empréstimos. Não coletamos dados sensíveis (como etnia, religião ou dados de saúde), CPF, endereço residencial ou informações financeiras.

### 3. Segurança e Compartilhamento dos Dados

* **Proteção técnica:** A comunicação com o sistema é feita por conexão criptografada (HTTPS). O telefone e o segredo do 2FA são armazenados criptografados, e a senha, apenas como hash (Art. 46 da LGPD).
* **Acesso restrito:** Somente a equipe administradora do sistema tem acesso aos dados dos titulares, para a gestão dos empréstimos.
* **Compartilhamento:** Os dados não são vendidos nem compartilhados com terceiros para outras finalidades. O endereço de e-mail é repassado apenas ao provedor de e-mail utilizado para entregar as mensagens do sistema.

### 4. Fluxo de Atendimento aos Direitos do Titular

Os titulares podem exercer seus direitos de forma automatizada:

* **Autoatendimento:** Através da aba "Meu Perfil", o usuário pode consultar ativamente seus dados (Art. 18, II), exportar um relatório estruturado JSON com seus dados cadastrais, o registro do consentimento e o histórico de empréstimos (Art. 18, V), autorizar ou retirar cada uso opcional dos dados em "Minhas Autorizações" (Art. 8º, § 5º), revogar o consentimento (Art. 18, IX) e solicitar o encerramento da conta com anonimização irreversível dos dados (Art. 18, IV e VI).
* **Revogação do consentimento:** Ao revogar, o acesso ao sistema é suspenso imediatamente. Os dados permanecem armazenados enquanto a conta estiver suspensa, para permitir que o próprio titular reative a conta, o que exige a sua senha. Para a eliminação dos dados, deve ser utilizado o encerramento da conta.
* **Encerramento da conta:** Nome, nome de usuário, e-mail, matrícula e telefone são substituídos por valores anônimos; a senha, o segredo do 2FA e os links de recuperação de senha são invalidados. A operação não pode ser desfeita.
* **Demais solicitações:** A correção de dados (Art. 18, III) e qualquer outro pedido que não esteja disponível em "Meu Perfil" devem ser feitos pelo canal do encarregado (seção 6). A resposta completa é fornecida em até 15 dias (Art. 19, II).

| Direito (Art. 18) | Como é atendido | Onde no sistema |
| --- | --- | --- |
| II — Acesso | Consulta dos dados em tela | Meu Perfil |
| III — Correção | Solicitação ao encarregado | Canal da seção 6 |
| IV e VI — Anonimização e eliminação | Encerramento da conta | Meu Perfil → Encerrar Minha Conta |
| V — Portabilidade | Download em JSON | Meu Perfil → Exportar dados |
| IX — Revogação do consentimento | Revogação com suspensão do acesso | Meu Perfil → Revogar consentimento |
| VIII e IX — Recusa ou revogação por finalidade, sem perder o acesso | Uma opção para cada uso opcional | Meu Perfil → Minhas Autorizações |

### 5. Retenção dos Dados

* Os dados são mantidos enquanto a conta estiver ativa ou suspensa.
* Após o encerramento da conta, permanecem apenas o histórico de empréstimos e os registros de auditoria, vinculados à conta já anonimizada. Eles são mantidos para o controle patrimonial dos equipamentos e para a segurança do sistema (Art. 16 da LGPD). Os registros de auditoria são protegidos contra alteração e exclusão.

### 6. Contato do Encarregado

O encarregado pelo tratamento de dados pessoais (Art. 41 da LGPD) é o administrador do sistema EmprestaCampus. Dúvidas, solicitações e reclamações sobre o tratamento dos seus dados podem ser enviadas pelo e-mail institucional da coordenação responsável pelo sistema.

---

Última atualização: Novembro de 2026 | Versão do Documento: v1.1