# Ativos, Ameaças e Análise de Risco — EmprestaCampus

**Requisito:** 6. Documentação Técnico-Científica
**Escopo deste documento:** itens 6.6 (ativos do sistema), 6.7 (ameaças e vulnerabilidades), 6.8 (associação risco × contramedida) e 6.11 (uso de normas técnicas)

---

## 1. Objetivo

Este documento identifica os ativos de informação do EmprestaCampus, as ameaças e vulnerabilidades relevantes para cada um, e a contramedida técnica já implementada no sistema para mitigar cada risco. A análise usa como referência técnica o **OWASP Top 10:2025**, a lista de consenso da comunidade sobre os riscos mais críticos em aplicações web, publicada pela OWASP Foundation.

## 2. Identificação dos Ativos do Sistema

Um ativo, no contexto de segurança da informação, é qualquer recurso que tenha valor para a organização e que, se comprometido, cause dano. Os ativos do EmprestaCampus foram agrupados em três categorias.

### 2.1 Dados

| Ativo | Descrição | Classificação |
|---|---|---|
| Credenciais de usuário | Username, senha (hash), papel (RBAC) | Crítico |
| Dados pessoais do usuário | Nome, e-mail, matrícula, telefone | Dado pessoal (LGPD) |
| Telefone do usuário | Único campo pessoal armazenado com criptografia reversível (Fernet) | Dado pessoal sensível ao contexto |
| Tokens de recuperação de senha | Tokens de uso único, com prazo de expiração | Crítico, temporário |
| Segredo TOTP (2FA) | Chave secreta compartilhada entre o servidor e o aplicativo autenticador do usuário | Crítico |
| Registros de auditoria | Histórico de login, falhas, eventos de 2FA e LGPD | Íntegro, não deve ser alterável |
| Dados de catálogo e empréstimo | Equipamentos, categorias, solicitações de empréstimo | Operacional |

### 2.2 Aplicações e Serviços

| Ativo | Descrição |
|---|---|
| API Django/DRF | Serviço que expõe todos os endpoints de negócio |
| Banco de dados PostgreSQL | Armazena todos os dados persistentes do sistema |
| Servidor Nginx | Termina a conexão TLS e encaminha requisições ao backend |
| Frontend (templates Django e SPA React) | Interfaces que o usuário final utiliza |

### 2.3 Segredos e Chaves

| Ativo | Descrição |
|---|---|
| `SECRET_KEY` | Chave usada pelo Django para assinar sessões, tokens CSRF e (no fluxo de login da SPA) o token intermediário de 2FA |
| `ENCRYPTION_KEY` | Chave Fernet usada para criptografar o campo telefone |
| Certificado TLS | Certificado e chave privada usados pelo Nginx para servir HTTPS |
| Variáveis de ambiente (`.env`) | Local onde as chaves acima residem, fora do código-fonte |

## 3. Identificação de Ameaças e Vulnerabilidades

Cada ameaça abaixo é referenciada à categoria correspondente do **OWASP Top 10:2025**.

### 3.1 Quebra de controle de acesso (A01:2025 — Broken Access Control)

**Ameaça:** um usuário autenticado consegue acessar ou modificar dados ou funções que não deveria, seja por falha de checagem de papel (RBAC), seja por identificadores previsíveis (IDOR) que permitem adivinhar recursos de outros usuários.

**Vulnerabilidade identificada durante o desenvolvimento:** a primeira versão do endpoint de login com 2FA para a SPA React devolvia o `id` numérico e sequencial do usuário na primeira etapa da autenticação, e a segunda etapa aceitava esse `id` diretamente para validar o código TOTP. Como identificadores de banco de dados costumam ser sequenciais, um atacante poderia tentar ids conhecidos ou próximos sem nunca ter fornecido a senha correta, restando apenas adivinhar o código de 6 dígitos.

### 3.2 Falhas criptográficas (A04:2025 — Cryptographic Failures)

**Ameaça:** dados sensíveis (senhas, dados pessoais, tráfego de rede) protegidos com algoritmo fraco, chave exposta no código-fonte, ou ausência completa de criptografia, permitindo que um atacante com acesso ao banco de dados ou à rede leia informações que deveriam estar protegidas.

### 3.3 Falhas de identificação e autenticação (mapeada em Broken Access Control / Cryptographic Failures no OWASP 2025, tratada aqui separadamente por relevância ao domínio do sistema)

**Ameaça:** um atacante assume a identidade de outro usuário através de senha fraca, ausência de segundo fator, tentativas ilimitadas de login (força bruta), ou reutilização de token de recuperação de senha já usado ou expirado.

### 3.4 Configuração incorreta de segurança (A02:2025 — Security Misconfiguration)

**Ameaça:** o sistema expõe informações sensíveis por configuração inadequada do ambiente, como `DEBUG=True` em produção, cabeçalhos HTTP ausentes, cookies sem a flag `Secure`, ou tráfego HTTP não redirecionado para HTTPS.

### 3.5 Tratamento inadequado de condições excepcionais (A10:2025 — Mishandling of Exceptional Conditions, categoria nova na edição 2025)

**Ameaça:** o sistema se comporta de forma insegura diante de erros ou entradas inesperadas, por exemplo revelando mensagens de erro detalhadas que ajudam um atacante, ou falhando de um jeito que concede acesso em vez de negá-lo.

## 4. Associação Risco × Contramedida

| # | Ameaça (OWASP 2025) | Vulnerabilidade específica no domínio | Contramedida implementada | Onde está no código |
|---|---|---|---|---|
| 1 | A01 — Broken Access Control | Identificador de usuário previsível exposto na primeira etapa do login com 2FA, permitindo pular a validação de senha | Token intermediário assinado (`django.core.signing`), emitido apenas após senha correta, com expiração de 5 minutos e verificação de integridade contra adulteração | `usuarios/views.py` — `LoginAPIView`, `VerificarDoisFatoresLoginView` |
| 2 | A04 — Cryptographic Failures | Senha armazenada sem proteção adequada | Hash PBKDF2-SHA256 com 600.000 iterações, valor acima do mínimo recomendado pela OWASP | `usuarios/hashers.py` |
| 3 | A04 — Cryptographic Failures | Dado pessoal (telefone) armazenado sem proteção | Criptografia simétrica autenticada (Fernet) no campo `telefone`, com chave separada da `SECRET_KEY` | `usuarios/crypto.py` |
| 4 | A04 — Cryptographic Failures | Chaves secretas expostas no código-fonte versionado | `SECRET_KEY` e `ENCRYPTION_KEY` lidas de variáveis de ambiente (`.env`), nunca commitadas | `config/settings.py`, `.gitignore` |
| 5 | A04 — Cryptographic Failures | Tráfego entre cliente e servidor sem criptografia | HTTPS obrigatório via Nginx com certificado TLS, com redirecionamento automático de HTTP para HTTPS | `nginx/nginx.conf`, `config/settings.py` (`SECURE_SSL_REDIRECT`) |
| 6 | Falha de identificação e autenticação | Ausência de segundo fator de autenticação | Autenticação de dois fatores (TOTP) implementada e obrigatoriamente validada antes da emissão do token de acesso | `usuarios/views.py`, `django-otp` |
| 7 | Falha de identificação e autenticação | Tentativas ilimitadas de login (força bruta) | Bloqueio temporário após 5 tentativas de login incorretas | `django-axes`, `config/settings.py` |
| 8 | Falha de identificação e autenticação | Token de recuperação de senha reutilizável ou sem expiração | Token de uso único, gerado com `secrets.token_urlsafe` (não previsível), com expiração de 1 hora | `usuarios/models.py` — `TokenRecuperacaoSenha` |
| 9 | A02 — Security Misconfiguration | Cookies transmitidos sem proteção adequada | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` e `X_FRAME_OPTIONS` configurados | `config/settings.py` |
| 10 | A10 — Mishandling of Exceptional Conditions | Registro de auditoria poderia ser incompleto diante de falhas de autenticação | Cada tentativa de login, sucesso ou falha, gera um registro de auditoria, mesmo quando a autenticação falha | `usuarios/views.py`, módulo `auditoria` |

## 5. Fundamentação Técnica e Normativa

Este documento e as decisões de segurança do EmprestaCampus se apoiam nas seguintes referências:

1. **OWASP (Open Worldwide Application Security Project). OWASP Top 10:2025** — lista de consenso da comunidade de segurança sobre os dez riscos mais críticos em aplicações web, utilizada como referência principal para a categorização de ameaças neste documento.

2. **OWASP Password Storage Cheat Sheet** — referência utilizada para a definição do número de iterações do PBKDF2 (600.000), adotado em `usuarios/hashers.py`.

3. **Lei nº 13.709/2018 (Lei Geral de Proteção de Dados Pessoais — LGPD)** — base legal para a classificação de dados pessoais e para as funcionalidades de consentimento, exportação e exclusão de dados implementadas no sistema.

## 6. Rastreabilidade com o Checklist

| Item do checklist | Onde está atendido |
|---|---|
| 6.6 — Identificação dos ativos do sistema | Seção 2 |
| 6.7 — Identificação de ameaças e vulnerabilidades | Seção 3 |
| 6.8 — Associação risco × contramedida | Seção 4 |
| 6.11 — Uso de normas técnicas | Seção 5 |
