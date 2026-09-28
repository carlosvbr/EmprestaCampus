# Fluxos de autenticação e dados documentados

##  Login web por sessão (`/api/usuarios/entrar/`)

**Fluxo:** usuário/senha → `authenticate()` → se o usuário tem 2FA confirmado, redireciona para validação TOTP → só então `login()` de sessão é efetivado.

Usado pela interface HTML (Django Templates).

## Login via API/JWT, fluxo em duas etapas com 2FA (`/api/usuarios/login/spa/` + `/api/usuarios/login/spa/2fa/`)

A primeira etapa valida usuário/senha. Se houver 2FA confirmado, retorna um token intermediário assinado (`django.core.signing`, com expiração de 300 segundos), sem emitir JWT ainda.

A segunda etapa exige esse token + o código TOTP válido para, só então, emitir o par de tokens JWT (`access/refresh`).

O usuário nunca é identificado por ID exposto ao cliente — apenas pelo token assinado, o que impede um atacante de pular a etapa de senha enviando um ID de usuário diretamente.

## Login via API/JWT sem 2FA (rota legada)

**Path:** `path("login/", TokenObtainPairView.as_view())`, do `djangorestframework-simplejwt`.

Essa rota foi identificada, durante a revisão técnica do projeto, como uma inconsistência de segurança: permitia obter um JWT válido sem passar pelo segundo fator, mesmo para usuários com 2FA ativado.

Após confirmação de que nenhuma view, teste automatizado ou template do projeto dependia dela, a rota foi removida, eliminando esse caminho alternativo que contornava o 2FA.

## Fluxo de recuperação de senha

**Solicitação de e-mail** → geração de token criptograficamente seguro (`secrets.token_urlsafe(32)`) com validade de 1 hora e uso único → envio do link (hoje simulado via console em ambiente de desenvolvimento, ver 6.4) → validação do token → redefinição de senha → token marcado como usado.
