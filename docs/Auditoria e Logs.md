# Análise de Logs e Auditoria

## 1. Objetivo
O objetivo deste documento é demonstrar como o módulo de Auditoria acompanha e regista eventos críticos de autenticação, recuperação de credenciais e privacidade. Esta rastreabilidade garante a prestação de contas e o cumprimento de normas de segurança e da LGPD.

## 2. Eventos Registados
O sistema monitoriza e regista automaticamente eventos como:
- **LOGIN_SUCESSO / LOGIN_FALHA:** Sucesso ou falha na autenticação primária.
- **2FA_SUCESSO / 2FA_FALHA:** Validação de segundo fator (TOTP).
- **RECUPERACAO:** Ações relacionadas com a recuperação de palavra-passe.
- **UPDATE (Privacidade/LGPD):** Alterações no estado de consentimento de dados por parte do utilizador.

## 3. Exemplo de Análise
Abaixo, um recorte real da base de dados demonstrando a rastreabilidade de diferentes utilizadores no dia 20/09/2026[cite: 3]:

| Data/Hora | Nome do Utilizador | Ação | Módulo Afetado | IP de Origem |
| :--- | :--- | :--- | :--- | :--- |
| 20/09/2026 19:07:07 | TesteT | UPDATE | Privacidade/LGPD | 127.0.0.1 |
| 20/09/2026 19:06:11 | TesteT | RECUPERACAO | Autenticação/Recuperação | 127.0.0.1 |
| 20/09/2026 18:58:09 | Lucas | LOGIN_SUCESSO | Autenticação | 127.0.0.1 |
| 20/09/2026 18:56:00 | usuarioteste | 2FA_SUCESSO | Autenticação | 127.0.0.1 |
| 20/09/2026 18:55:55 | usuarioteste | 2FA_FALHA | Autenticação | 127.0.0.1 |
| 20/09/2026 18:55:23 | usuarioteste | LOGIN_FALHA | Autenticação | 127.0.0.1 |

## 4. Interpretação dos Eventos
A tabela ilustra três cenários distintos capturados com precisão pelo sistema de auditoria:
1. **Resiliência de Acesso:** Às 18:55:23, o usuário usuarioteste falhou a autenticação primária. Logo de seguida, falhou a inserção do código 2FA (18:55:55), mas obteve sucesso segundos depois (18:56:00), demonstrando a eficácia da barreira de segundo fator contra erros ou tentativas de acesso indevido[cite: 3].
2. **Acesso Normal:** O usuário Lucas autenticou-se de forma direta e bem-sucedida às 18:58:09[cite: 3].
3. **Recuperação e Privacidade:** O usuário TesteT realizou um processo de recuperação de credenciais às 19:06:11[cite: 3]. Menos de um minuto depois (19:07:07), o sistema registou um `UPDATE` no módulo `Privacidade/LGPD`, evidenciando que o usuário atualizou o consentimento dos seus dados após recuperar a senha.

## 5. Identificação de Comportamentos Sensíveis
Através desta tabela, o administrador de sistemas consegue auditar não só a segurança de quem entra e como entra, mas também as ações legais. Se um IP malicioso tentasse forçar o login do utilizador `TesteT`, os logs evidenciariam uma anomalia em contraste com o comportamento normal verificado acima.

## 6. Integridade dos Registos
Para que os logs tenham validade legal e técnica, a sua integridade é garantida ao nível da aplicação. As definições no ficheiro `auditoria/admin.py` removem as permissões de adicionar, editar ou excluir (`has_add_permission`, `has_change_permission`, `has_delete_permission`). O sistema opera em modo **Append-Only**, garantindo a imutabilidade do histórico.

## 7. Conclusão
A centralização da auditoria provou ser eficaz a mapear todo o ciclo de vida da identidade do usuário. Os logs são gerados com associação exata ao ID do utilizador e ao IP de origem, permitindo diagnósticos rápidos e auditorias de conformidade transparentes.