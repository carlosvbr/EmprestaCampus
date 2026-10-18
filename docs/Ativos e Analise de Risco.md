# Ativos, Ameaças e Análise de Risco — EmprestaCampus

**Requisito:** 6. Documentação Técnico-Científica
**Escopo deste documento:** itens 6.6 (ativos do sistema), 6.7 (ameaças e vulnerabilidades), 6.8 (associação risco × contramedida) e 6.11 (uso de normas técnicas)

---

## 1. Objetivo

Este documento identifica os ativos de informação do EmprestaCampus, as ameaças e vulnerabilidades relevantes para cada um, a contramedida técnica implementada no sistema para mitigar cada risco e o risco que permanece depois dela (risco residual). A análise usa como referência técnica principal o **OWASP Top 10:2025**, a lista de consenso da comunidade sobre os riscos mais críticos em aplicações web, publicada pela OWASP Foundation.

## 2. Identificação dos Ativos do Sistema

Um ativo, no contexto de segurança da informação, é qualquer recurso que tenha valor para a organização e que, se comprometido, cause dano. Os ativos do EmprestaCampus foram agrupados em três categorias.

### 2.1 Dados

| Ativo | Descrição | Classificação |
|---|---|---|
| Credenciais de usuário | Username, senha (hash PBKDF2-SHA256) e papel (RBAC) | Crítico |
| Dados pessoais do usuário | Nome, e-mail, matrícula e telefone | Dado pessoal (LGPD) |
| Telefone do usuário | Único campo pessoal armazenado com criptografia reversível (Fernet) | Dado pessoal |
| Registro de consentimento | Situação, data e versão da Política de Privacidade aceita | Dado pessoal (LGPD), prova de conformidade |
| Tokens de recuperação de senha | Tokens de uso único, com expiração de 1 hora | Crítico, temporário |
| Segredo TOTP (2FA) | Chave secreta compartilhada entre o servidor e o aplicativo autenticador do usuário | Crítico |
| Sessões web e tokens JWT | Identificam o usuário autenticado; sessão de 30 minutos, JWT de acesso de 1 hora e refresh de 7 dias | Crítico, temporário |
| Registros de auditoria | Histórico de login, falhas, 2FA, recuperação de senha, LGPD, inventário e empréstimos, com IP de origem | Íntegro, não deve ser alterável |
| Dados de catálogo e empréstimo | Equipamentos, categorias, solicitações, prazos e histórico de empréstimos | Operacional; o histórico é dado pessoal |
| Histórico de notificações | Mensagens enviadas a cada usuário | Operacional, dado pessoal |

### 2.2 Aplicações e Serviços

| Ativo | Descrição |
|---|---|
| API Django/DRF | Serviço que expõe todos os endpoints de negócio |
| Banco de dados PostgreSQL | Armazena todos os dados persistentes do sistema |
| Servidor Nginx | Termina a conexão TLS, redireciona HTTP para HTTPS e encaminha as requisições ao backend |
| Frontend (templates Django; SPA planejada) | Interface que o usuário final utiliza; a SPA consumirá a API JWT já disponível |
| Servidor de e-mail (SMTP externo) | Entrega os e-mails de recuperação de senha, avisos de segurança e notificações de empréstimo |
| Containers Docker | Isolam banco, backend e Nginx; somente o Nginx é exposto à rede externa |

### 2.3 Segredos e Chaves

| Ativo | Descrição |
|---|---|
| `SECRET_KEY` | Chave usada pelo Django para assinar sessões, tokens CSRF e o token intermediário do login com 2FA na API |
| `ENCRYPTION_KEY` | Chave Fernet usada para criptografar o campo telefone, separada da `SECRET_KEY` |
| Senha do banco de dados | Credencial do PostgreSQL (`POSTGRES_PASSWORD`) |
| Credenciais SMTP | Usuário e senha do servidor de e-mail |
| Certificado TLS | Certificado e chave privada usados pelo Nginx para servir HTTPS |
| Variáveis de ambiente (`.env`) | Local onde os segredos acima residem, fora do código-fonte, do repositório e da imagem Docker |

## 3. Identificação de Ameaças e Vulnerabilidades

As ameaças abaixo estão agrupadas segundo as categorias do **OWASP Top 10:2025**.

### 3.1 Quebra de controle de acesso

**Ameaça:** um usuário consegue acessar ou modificar dados ou funções que não deveria, seja por falha de checagem de papel (RBAC), seja por identificadores previsíveis (IDOR), seja por um fluxo que dispensa a prova de identidade.

**Vulnerabilidades identificadas e corrigidas:**

- **Identificador exposto no login com 2FA da API:** a primeira versão do endpoint devolvia o `id` numérico e sequencial do usuário na primeira etapa, e a segunda etapa aceitava esse `id` diretamente. Um atacante poderia tentar ids conhecidos sem nunca fornecer a senha, restando apenas adivinhar o código de 6 dígitos.
- **Escalada de privilégio no cadastro:** o cadastro público aceitava o campo `papel` enviado pelo cliente. Um cadastro com `"papel": "ADMIN"` criava uma conta de Administrador com acesso de escrita ao inventário.
- **Reativação de conta sem senha:** o login redirecionava contas inativas para a tela de reativação antes de conferir a senha. Qualquer pessoa que soubesse o nome de usuário reativava a conta e restaurava o consentimento, inclusive de contas desativadas pelo administrador.
- **Acesso a dados de outros usuários:** pedidos de prorrogação, listagem de empréstimos e exportação de dados poderiam, sem filtro pelo usuário logado, expor ou alterar registros de terceiros.

### 3.2 Falhas criptográficas

**Ameaça:** dados sensíveis (senhas, dados pessoais, tráfego de rede) protegidos com algoritmo fraco, chave exposta no código-fonte ou ausência completa de criptografia, permitindo que um atacante com acesso ao banco de dados ou à rede leia informações que deveriam estar protegidas.

### 3.3 Falhas de autenticação

**Ameaça:** um atacante assume a identidade de outro usuário através de senha fraca, ausência de segundo fator, tentativas ilimitadas de login (força bruta) ou reutilização de token de recuperação de senha.

**Vulnerabilidade identificada e corrigida:** o bloqueio contra força bruta era aplicado por IP **ou** por usuário. Atrás do Nginx, todos os usuários chegam com o mesmo IP, então cinco erros na conta de uma pessoa bloqueavam todas as outras por 30 minutos, transformando a proteção em um vetor de negação de serviço.

### 3.4 Configuração incorreta de segurança

**Ameaça:** o sistema expõe informações sensíveis por configuração inadequada do ambiente, como `DEBUG=True` em produção, cabeçalhos HTTP ausentes, cookies sem a flag `Secure` ou tráfego HTTP não redirecionado para HTTPS.

### 3.5 Tratamento inadequado de condições excepcionais

**Ameaça:** o sistema se comporta de forma insegura diante de erros ou entradas inesperadas, por exemplo revelando mensagens de erro detalhadas que ajudam um atacante, registrando eventos que não aconteceram ou falhando de um jeito que concede acesso em vez de negá-lo.

### 3.6 Injeção

**Ameaça:** dados enviados pelo usuário são interpretados como comandos, como em SQL Injection ou na injeção de scripts nas páginas (XSS).

### 3.7 Falhas de integridade de dados

**Ameaça:** dados que deveriam ser imutáveis, como os registros de auditoria, são alterados ou apagados, destruindo a prova do que aconteceu no sistema.

**Vulnerabilidade identificada e corrigida:** a proteção dos registros de auditoria existia apenas no Django Admin. Pelo ORM ou por SQL direto, os registros podiam ser alterados e apagados.

### 3.8 Falhas de registro e alerta de segurança

**Ameaça:** eventos de segurança não são registrados, são registrados com informações falsas ou registram dados que não deveriam ser guardados.

**Vulnerabilidades identificadas e corrigidas:**

- **IP forjável:** o IP gravado na auditoria vinha do primeiro valor do cabeçalho `X-Forwarded-For`, que o próprio cliente controla. Um atacante podia registrar qualquer endereço nos logs.
- **Dados pessoais nos logs:** o texto digitado no campo de login e o e-mail digitado na recuperação de senha eram gravados na auditoria, que não pode ser apagada. Uma senha digitada por engano no campo de usuário ficaria registrada permanentemente.

### 3.9 Riscos à privacidade do titular (LGPD)

**Ameaça:** o tratamento dos dados pessoais deixa de cumprir o que a Política de Privacidade promete ao titular, especialmente na exclusão dos dados.

**Vulnerabilidade identificada e corrigida:** o encerramento da conta anonimizava nome, usuário, e-mail e matrícula, mas mantinha o telefone, o dispositivo TOTP e os tokens de recuperação, embora a tela informasse que os dados haviam sido "anonimizados irreversivelmente".

## 4. Associação Risco × Contramedida

**Escala utilizada:**

- **Probabilidade** (de a ameaça ser explorada, considerando o sistema sem a contramedida): Baixa, Média ou Alta.
- **Impacto** (dano caso a ameaça se concretize): Baixo, Médio ou Alto.
- **Risco residual** (risco que permanece depois da contramedida implementada): Baixo, Médio ou Alto.

| # | Ameaça | Vulnerabilidade específica no domínio | Contramedida implementada | Onde está no código | Prob. | Impacto | Risco residual |
|---|---|---|---|---|---|---|---|
| 1 | Quebra de controle de acesso | Identificador de usuário previsível exposto na primeira etapa do login com 2FA, permitindo pular a validação de senha | Token intermediário assinado (`django.core.signing`), emitido apenas após senha correta, com expiração de 5 minutos e verificação de integridade | `usuarios/views.py` — `LoginAPIView`, `VerificarDoisFatoresLoginView` | Alta | Alto | Baixo |
| 2 | Quebra de controle de acesso | Cadastro público aceitava o papel ADMIN enviado pelo cliente | Cadastro aceita apenas Aluno e Docente; o papel é a fonte única de privilégios e sincroniza `is_staff` e `is_superuser` | `usuarios/serializers.py`, `usuarios/models.py` | Alta | Alto | Baixo |
| 3 | Quebra de controle de acesso | Reativação de conta suspensa sem conferir a senha | Senha conferida antes da reativação; só contas suspensas por revogação de consentimento podem ser reativadas; autorização de 5 minutos e uso único | `usuarios/views.py` — `login_view`, `pode_reativar`, `reativar_conta_lgpd_view` | Alta | Alto | Baixo |
| 4 | Quebra de controle de acesso | Acesso a empréstimos ou dados de outro usuário | Consultas filtradas pelo usuário logado; o cliente não define o dono nem o status do pedido; exportação restrita ao próprio titular | `emprestimos/views.py`, `emprestimos/serializers.py`, `usuarios/views.py` | Média | Médio | Baixo |
| 5 | Quebra de controle de acesso | Logout por GET permitia a um site externo encerrar a sessão do usuário (CSRF) | Logout aceita apenas `POST` com token CSRF | `usuarios/views.py` — `logout_view`, templates | Baixa | Baixo | Baixo |
| 6 | Falhas criptográficas | Senha armazenada sem proteção adequada | Hash PBKDF2-SHA256 com 600.000 iterações e salt único por senha | `usuarios/hashers.py` | Média | Alto | Baixo |
| 7 | Falhas criptográficas | Dado pessoal (telefone) armazenado sem proteção | Criptografia simétrica autenticada (Fernet) no campo `telefone`, com chave separada da `SECRET_KEY` | `usuarios/crypto.py` | Média | Médio | Médio |
| 8 | Falhas criptográficas | Chaves secretas expostas no código-fonte versionado | Segredos lidos do `.env`, que não é versionado nem copiado para a imagem Docker | `config/settings.py`, `.gitignore`, `.dockerignore` | Média | Alto | Baixo |
| 9 | Falhas criptográficas | Tráfego entre cliente e servidor sem criptografia | HTTPS via Nginx com certificado TLS e redirecionamento 301 de HTTP para HTTPS; backend acessível apenas pela rede interna do Docker | `nginx/nginx.conf`, `docker-compose.yml` | Média | Alto | Baixo |
| 10 | Falhas de autenticação | Ausência de segundo fator de autenticação | Autenticação de dois fatores (TOTP), validada antes da criação da sessão ou da emissão do JWT | `usuarios/views.py`, `django-otp` | Média | Alto | Médio |
| 11 | Falhas de autenticação | Tentativas ilimitadas de login (força bruta) | Bloqueio de 30 minutos após 5 tentativas incorretas | `django-axes`, `config/settings.py` | Alta | Alto | Médio |
| 12 | Falhas de autenticação | Bloqueio por IP derrubava todos os usuários atrás do Nginx | Bloqueio pela combinação de IP e usuário, usando o IP real do cliente | `config/settings.py` (`AXES_LOCKOUT_PARAMETERS`, `AXES_CLIENT_IP_CALLABLE`) | Alta | Médio | Baixo |
| 13 | Falhas de autenticação | Token de recuperação de senha reutilizável ou sem expiração | Token de uso único, gerado com `secrets.token_urlsafe`, com expiração de 1 hora; os demais tokens do usuário são invalidados após a redefinição | `usuarios/models.py`, `usuarios/views.py` | Média | Alto | Médio |
| 14 | Configuração incorreta de segurança | Cookies transmitidos sem proteção e navegador sem obrigação de HTTPS | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS e `SECURE_SSL_REDIRECT` ativos com `DEBUG=False`; `X_FRAME_OPTIONS` e `nosniff` sempre ativos | `config/settings.py` | Média | Médio | Médio |
| 15 | Injeção | SQL Injection e injeção de scripts nas páginas (XSS) | Consultas pelo ORM do Django (parametrizadas); escape automático nos templates; proteção CSRF nos formulários | `*/views.py`, templates | Média | Alto | Baixo |
| 16 | Falhas de integridade de dados | Registros de auditoria alteráveis ou apagáveis fora do Django Admin | Imutabilidade em três camadas: Django Admin, model/queryset e trigger no PostgreSQL | `auditoria/admin.py`, `auditoria/models.py`, `auditoria/migrations/0003_auto_20261012_1140.py` | Média | Alto | Médio |
| 17 | Falhas de registro e alerta | Registro de auditoria incompleto diante de falhas de autenticação | Cada tentativa de login, 2FA e recuperação, com sucesso ou falha, gera um registro com data, ação e IP | `usuarios/views.py`, módulo `auditoria` | Média | Médio | Baixo |
| 18 | Falhas de registro e alerta | IP de origem forjável pelo cabeçalho `X-Forwarded-For` | IP lido do cabeçalho `X-Real-IP`, preenchido pelo Nginx, e validado como endereço IP | `auditoria/utils.py` | Alta | Médio | Baixo |
| 19 | Falhas de registro e alerta | Texto digitado no login e e-mail da recuperação gravados num log imutável | A auditoria não grava o que foi digitado; registra apenas o resultado e o usuário, quando identificado | `usuarios/views.py` | Média | Médio | Baixo |
| 20 | Condições excepcionais | Erros inesperados revelando detalhes, registrando eventos falsos ou interrompendo o sistema | Exclusão protegida retorna erro claro sem log falso; falha no envio de e-mail é registrada sem interromper a operação; token de 2FA inválido ou expirado é negado | `inventario/views.py`, `notificacoes/utils.py`, `usuarios/views.py` | Média | Médio | Baixo |
| 21 | Privacidade (LGPD) | Encerramento da conta mantinha telefone, dispositivo TOTP e tokens de recuperação | Encerramento apaga o telefone, os dispositivos TOTP e os tokens, anonimiza os demais dados e torna a senha inutilizável | `usuarios/views.py` — `encerrar_conta_view` | Média | Alto | Baixo |

As linhas com risco residual **Médio** (7, 10, 11, 13, 14 e 16) têm a justificativa e a melhoria prevista descritas em `Limitacoes.md`.

## 5. Fundamentação Técnica e Normativa

As decisões de segurança do EmprestaCampus se apoiam em normas e guias reconhecidos, aplicados da seguinte forma:

1. **OWASP Top 10:2025** — usado para organizar as ameaças da seção 3 e as linhas da tabela da seção 4. As categorias de cadeia de suprimentos de software e de design inseguro não receberam linha própria: a primeira depende da gestão das dependências do projeto, e a segunda é tratada transversalmente pelas decisões de arquitetura descritas nos demais documentos (OWASP, 2025).

2. **OWASP Password Storage Cheat Sheet** — define o número de iterações do PBKDF2-SHA256 (600.000) adotado em `usuarios/hashers.py` (OWASP, 2023).

3. **NIST SP 800-63B** — orienta as decisões de autenticação: armazenamento de senhas com função de derivação de chave, limitação de tentativas e uso de TOTP em vez de SMS como segundo fator (NIST, 2017).

4. **Lei nº 13.709/2018 (LGPD)** — base legal para a classificação dos dados pessoais (seção 2.1) e para os riscos à privacidade do titular (seção 3.9), incluindo consentimento, exportação e anonimização dos dados (BRASIL, 2018).

5. **ISO/IEC 27001** — a estrutura deste documento segue a lógica de gestão de riscos da norma: identificação dos ativos, das ameaças e vulnerabilidades, avaliação de probabilidade e impacto, escolha de controles e registro do risco residual aceito (ISO, 2022).

As referências completas estão em `referencias.md`.

## 6. Rastreabilidade com o Checklist

| Item do checklist | Onde está atendido |
|---|---|
| 6.6 — Identificação dos ativos do sistema | Seção 2 |
| 6.7 — Identificação de ameaças e vulnerabilidades | Seção 3 |
| 6.8 — Associação risco × contramedida | Seção 4 |
| 6.11 — Uso de normas técnicas | Seção 5 |