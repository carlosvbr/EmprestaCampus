# Testes de Segurança — EmprestaCampus

**Requisito:** 6. Documentação Técnico-Científica
**Escopo deste documento:** itens 6.9 (testes de segurança realizados) e 6.10 (resultados dos testes documentados)

---

## 1. Objetivo

Este documento apresenta os testes automatizados de segurança implementados no EmprestaCampus, cobrindo os mecanismos críticos descritos nos requisitos 1 (Autenticação e Gestão de Credenciais) e 2 (Recuperação de Senha). O objetivo é comprovar, de forma reproduzível e não apenas manual, que essas proteções funcionam como projetado.

## 2. Ferramenta utilizada

Os testes usam `pytest` com o plugin `pytest-django`, que integra o `pytest` ao ambiente do Django (banco de dados de teste isolado, acesso aos models, fixtures). Essa escolha, em vez do `TestCase` nativo do Django, permite testes mais concisos e legíveis, mantendo total acesso aos recursos do framework.

**Configuração:** `backend/pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py tests_*.py
```

**Arquivo de testes:** `backend/usuarios/tests_seguranca.py`

## 3. Cobertura dos testes

Os 15 testes estão organizados em 4 classes, cada uma cobrindo um mecanismo de segurança específico.

### 3.1 `TestHashDeSenha` — cobre os itens 1.1, 1.2, 1.3, 1.4

| Teste | O que verifica |
|---|---|
| `test_senha_nunca_fica_em_texto_puro_no_banco` | A senha salva no campo `password` nunca é igual à senha original, e usa o prefixo `pbkdf2_sha256$`, confirmando o algoritmo de hash em uso |
| `test_custo_do_hash_e_600000_iteracoes` | O número de iterações do PBKDF2 embutido no hash é exatamente 600.000, o valor configurado em `usuarios/hashers.py` |
| `test_dois_usuarios_com_mesma_senha_geram_hashes_diferentes` | Dois usuários com a senha idêntica produzem hashes diferentes, provando que o salt é único por usuário |

### 3.2 `TestProtecaoForcaBruta` — cobre o item 1.11

| Teste | O que verifica |
|---|---|
| `test_bloqueia_apos_cinco_tentativas_erradas` | Depois de 5 tentativas de login com senha errada, mesmo a senha correta é rejeitada pelo `django-axes`, confirmando o bloqueio temporário |

### 3.3 `TestRecuperacaoDeSenha` — cobre os itens 2.2, 2.3, 2.4

| Teste | O que verifica |
|---|---|
| `test_token_e_de_uso_unico` | Um token de recuperação válido se torna inválido assim que marcado como usado |
| `test_token_nao_e_previsivel` | Dois tokens gerados em sequência para o mesmo usuário são diferentes entre si e têm comprimento compatível com geração criptograficamente segura (`secrets.token_urlsafe`) |

### 3.4 `TestDoisFatores` e `TestLoginSpaDoisFatores` — cobrem os itens 1.5, 1.6

| Teste | O que verifica |
|---|---|
| `test_usuario_com_2fa_nao_autentica_so_com_senha` | Um usuário com 2FA confirmado não recebe acesso completo enviando apenas a senha correta |
| `test_codigo_2fa_incorreto_nao_libera_acesso` | Um código TOTP incorreto (`000000`) é rejeitado pela verificação do dispositivo |
| `test_primeira_etapa_nao_emite_jwt_nem_expoe_id` | A primeira etapa do login via API (`/api/usuarios/login/spa/`) não devolve token de acesso nem o identificador interno do usuário quando há 2FA pendente |
| `test_fluxo_completo_com_codigo_correto_emite_jwt` | O fluxo completo (senha correta seguida do código TOTP correto) emite o par de tokens JWT |
| `test_codigo_errado_nao_emite_jwt` | Um código incorreto na segunda etapa não emite token nenhum |
| `test_segunda_etapa_sem_passar_pela_senha_e_rejeitada` | Tentar acessar a segunda etapa sem ter completado a primeira (sem token de sessão de 2FA válido) é rejeitado |
| `test_token_forjado_ou_adulterado_e_rejeitado` | Um token de sessão de 2FA adulterado manualmente é rejeitado pela verificação de assinatura |
| `test_token_expirado_e_rejeitado` | Um token de sessão de 2FA emitido há mais tempo que o limite configurado (5 minutos) é rejeitado |
| `test_usuario_sem_2fa_recebe_jwt_direto` | Um usuário sem 2FA configurado recebe o token diretamente na primeira etapa, sem exigir segunda etapa |

## 4. Achado de segurança corrigido durante os testes

Durante a escrita dos testes de `TestLoginSpaDoisFatores`, foi identificada uma falha real na primeira versão do endpoint de login via API: a etapa 1 devolvia o `user_id` do usuário autenticado, e a etapa 2 aceitava esse id diretamente para validar o código de 2FA. Como identificadores de usuário no banco são sequenciais e previsíveis, isso permitiria que alguém pulasse a etapa da senha e tentasse adivinhar apenas o código de 6 dígitos de um usuário conhecido.

**Correção aplicada:** a etapa 1 passou a emitir um token assinado (usando `django.core.signing`, que utiliza a `SECRET_KEY` do projeto), gerado apenas após a senha correta. A etapa 2 exige esse token, rejeitando tokens forjados, adulterados ou emitidos há mais de 5 minutos. O identificador do usuário não é mais exposto em nenhuma resposta da API.

Essa correção está coberta pelos testes `test_primeira_etapa_nao_emite_jwt_nem_expoe_id`, `test_token_forjado_ou_adulterado_e_rejeitado` e `test_token_expirado_e_rejeitado`.

## 5. Como executar os testes

```bash
docker compose exec backend python -m pytest -v
```

## 6. Resultado da execução

Execução realizada em 27/09/2026, ambiente local (Docker), banco de dados de teste isolado gerado automaticamente pelo `pytest-django`.

```
================================================= test session starts ==================================================
platform linux -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /usr/local/bin/python
cachedir: .pytest_cache
django: version: 6.1.1, settings: config.settings (from ini)
rootdir: /app
configfile: pytest.ini
plugins: django-4.14.0
collected 15 items

usuarios/tests_seguranca.py::TestHashDeSenha::test_senha_nunca_fica_em_texto_puro_no_banco PASSED                [  6%]
usuarios/tests_seguranca.py::TestHashDeSenha::test_custo_do_hash_e_600000_iteracoes PASSED                       [ 13%]
usuarios/tests_seguranca.py::TestHashDeSenha::test_dois_usuarios_com_mesma_senha_geram_hashes_diferentes PASSED  [ 20%]
usuarios/tests_seguranca.py::TestProtecaoForcaBruta::test_bloqueia_apos_cinco_tentativas_erradas PASSED          [ 26%]
usuarios/tests_seguranca.py::TestRecuperacaoDeSenha::test_token_e_de_uso_unico PASSED                            [ 33%]
usuarios/tests_seguranca.py::TestRecuperacaoDeSenha::test_token_nao_e_previsivel PASSED                          [ 40%]
usuarios/tests_seguranca.py::TestDoisFatores::test_usuario_com_2fa_nao_autentica_so_com_senha PASSED             [ 46%]
usuarios/tests_seguranca.py::TestDoisFatores::test_codigo_2fa_incorreto_nao_libera_acesso PASSED                 [ 53%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_primeira_etapa_nao_emite_jwt_nem_expoe_id PASSED      [ 60%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_fluxo_completo_com_codigo_correto_emite_jwt PASSED    [ 66%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_codigo_errado_nao_emite_jwt PASSED                    [ 73%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_segunda_etapa_sem_passar_pela_senha_e_rejeitada PASSED [ 80%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_token_forjado_ou_adulterado_e_rejeitado PASSED        [ 86%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_token_expirado_e_rejeitado PASSED                     [ 93%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_usuario_sem_2fa_recebe_jwt_direto PASSED              [100%]

============================================ 15 passed, 1 warning in 9.75s =============================================
```

**Resultado:** 15 de 15 testes aprovados. O único aviso presente (`RemovedInDjango70Warning`, sobre a futura descontinuação de `EMAIL_BACKEND` em favor de `MAILERS`) é informativo, relacionado a uma mudança planejada para versões futuras do Django, sem impacto na versão atual em uso.

## 7. Rastreabilidade com o checklist

| Item do checklist | Onde está atendido |
|---|---|
| 1.1 a 1.4 — Hash, custo, salt, armazenamento | `TestHashDeSenha`, seção 3.1 |
| 1.5, 1.6 — 2FA implementado e validado após autenticação primária | `TestDoisFatores`, `TestLoginSpaDoisFatores`, seção 3.4 |
| 1.11 — Proteção contra força bruta | `TestProtecaoForcaBruta`, seção 3.2 |
| 2.2, 2.3, 2.4 — Token de recuperação seguro, com expiração, uso único | `TestRecuperacaoDeSenha`, seção 3.3 |
| 6.9 — Testes de segurança realizados | Este documento inteiro |
| 6.10 — Resultados dos testes documentados | Seção 6 (saída real da execução) |
