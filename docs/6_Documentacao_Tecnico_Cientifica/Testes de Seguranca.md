# Testes de Segurança — EmprestaCampus

**Requisito:** 6. Documentação Técnico-Científica
**Escopo deste documento:** itens 6.9 (testes de segurança realizados) e 6.10 (resultados dos testes documentados)

---

## 1. Objetivo

Este documento apresenta a suíte completa de testes automatizados do EmprestaCampus. Ela cobre os mecanismos de segurança dos requisitos 1 (Autenticação e Gestão de Credenciais), 2 (Recuperação de Senha), 3 (Criptografia), 4 (LGPD) e 5 (Auditoria), o controle de acesso por papel (RBAC) e as regras de negócio dos módulos de inventário, empréstimos e notificações. O objetivo é comprovar, de forma reproduzível e não apenas manual, que o sistema funciona e que suas proteções se comportam como projetado.

## 2. Ferramenta utilizada

Os testes usam `pytest` com o plugin `pytest-django`, que integra o `pytest` ao ambiente do Django (banco de dados de teste isolado, acesso aos models, fixtures). Essa escolha, em vez do `TestCase` nativo do Django, permite testes mais concisos e legíveis, mantendo total acesso aos recursos do framework.

**Configuração:** `backend/pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py tests_*.py testes_*.py *_tests.py
```

**Fixtures compartilhadas:** `backend/conftest.py` (usuários Aluno e Administrador, equipamento de teste e clientes já autenticados). O Aluno de teste autoriza os avisos de empréstimo por e-mail, porque, desde o consentimento por finalidade (seção 3.9), esses avisos só são enviados a quem autorizou.

**E-mails nos testes:** nenhum e-mail sai de verdade. O `pytest-django` substitui o envio por uma caixa de saída falsa (`mailoutbox`), onde os testes conferem destinatário e conteúdo.

## 3. Cobertura dos testes

A suíte tem **216 testes** em 10 arquivos. Como alguns são parametrizados, o `pytest` executa **234 casos**.

| Arquivo | Classes | Funções de teste | Casos executados | Foco |
|---|---|---|---|---|
| `usuarios/tests_seguranca.py` | 12 | 52 | 55 | Autenticação, 2FA, recuperação, RBAC, LGPD |
| `auditoria/tests.py` | 3 | 8 | 8 | Imutabilidade dos logs |
| `notificacoes/tests.py` | 7 | 18 | 18 | Notificações e e-mails |
| `inventario/tests.py` | 4 | 28 | 30 | Inventário e catálogo |
| `emprestimos/tests.py` | 8 | 38 | 38 | Ciclo do empréstimo |
| `usuarios/tests.py` | 5 | 19 | 21 | Pendências da avaliação da release 1.5.0 (1.5, 2.x e 5.3) |
| `usuarios/tests_criptografia.py` | 2 | 7 | 7 | Dados cifrados em repouso e rotação de chave (3.4) |
| `usuarios/testes_lgpd.py` | 2 | 8 | 16 | Mapeamento de dados e minimização (4.2, 4.3) |
| `usuarios/testes_consentimento.py` | 5 | 19 | 19 | Consentimento por finalidade (4.5) |
| `usuarios/testes_retencao.py` | 3 | 19 | 22 | Eliminação, anonimização e retenção (4.10) |
| **Total** | **51** | **216** | **234** | |

---

### 3.1 `usuarios/tests_seguranca.py` — Autenticação, credenciais, RBAC e LGPD

#### 3.1.1 `TestHashDeSenha` — itens 1.1, 1.2, 1.3, 1.4

| Teste | O que verifica |
|---|---|
| `test_senha_nunca_fica_em_texto_puro_no_banco` | A senha salva nunca é igual à original e usa o prefixo `pbkdf2_sha256$` |
| `test_custo_do_hash_e_600000_iteracoes` | O hash usa exatamente 600.000 iterações, o valor de `usuarios/hashers.py` |
| `test_dois_usuarios_com_mesma_senha_geram_hashes_diferentes` | A mesma senha gera hashes diferentes em contas diferentes (salt único) |

#### 3.1.2 `TestProtecaoForcaBruta` — item 1.11

| Teste | O que verifica |
|---|---|
| `test_bloqueia_apos_cinco_tentativas_erradas` | Após 5 senhas erradas, até a senha correta é recusada pelo `django-axes` |

#### 3.1.3 `TestRecuperacaoDeSenha` — itens 2.2, 2.3, 2.4

| Teste | O que verifica |
|---|---|
| `test_token_e_de_uso_unico` | O token deixa de ser válido depois de usado |
| `test_token_nao_e_previsivel` | Dois tokens seguidos são diferentes e têm comprimento de geração segura (`secrets.token_urlsafe`) |

#### 3.1.4 `TestDoisFatores` e `TestLoginSpaDoisFatores` — itens 1.5, 1.6

| Teste | O que verifica |
|---|---|
| `test_usuario_com_2fa_nao_autentica_so_com_senha` | Com 2FA ativo, a senha sozinha não dá acesso |
| `test_codigo_2fa_incorreto_nao_libera_acesso` | Um código TOTP incorreto é rejeitado |
| `test_primeira_etapa_nao_emite_jwt_nem_expoe_id` | A etapa 1 do login pela API não devolve JWT nem o id do usuário quando há 2FA |
| `test_fluxo_completo_com_codigo_correto_emite_jwt` | Senha correta + código correto emitem o par de tokens JWT |
| `test_codigo_errado_nao_emite_jwt` | Código incorreto na etapa 2 não emite token |
| `test_segunda_etapa_sem_passar_pela_senha_e_rejeitada` | A etapa 2 sem o token da etapa 1 é rejeitada |
| `test_token_forjado_ou_adulterado_e_rejeitado` | Token intermediário adulterado é rejeitado pela assinatura |
| `test_token_expirado_e_rejeitado` | Token intermediário com mais de 5 minutos é rejeitado |
| `test_usuario_sem_2fa_recebe_jwt_direto` | Sem 2FA, o JWT é emitido já na etapa 1 |

#### 3.1.5 `TestCadastroNaoPermitePapelPrivilegiado` — itens 6.7, 6.8

| Teste | O que verifica |
|---|---|
| `test_cadastro_com_papel_admin_e_recusado` | O cadastro recusa `"papel": "ADMIN"` com erro 400 |
| `test_cadastro_com_papel_inexistente_e_recusado` | Um papel inexistente é recusado |
| `test_cadastro_com_papel_aluno_e_aceito` | O papel Aluno é aceito |
| `test_cadastro_sem_papel_vira_aluno_por_padrao` | Sem o campo `papel`, a conta nasce Aluno |
| `test_aluno_nao_consegue_cadastrar_equipamento` | A permissão `IsAdmin` impede o Aluno de escrever no inventário |
| `test_admin_consegue_cadastrar_equipamento` | O Administrador cadastra equipamentos |

#### 3.1.6 `TestPapelManda` — controle de acesso por papel (RBAC)

| Teste | O que verifica |
|---|---|
| `test_admin_nasce_com_acesso_administrativo` | Papel ADMIN recebe `is_staff` e `is_superuser` |
| `test_aluno_nasce_sem_acesso_administrativo` | Papel Aluno não recebe acesso administrativo |
| `test_forcar_is_staff_em_aluno_e_revertido` | Marcar `is_staff` manualmente num Aluno é desfeito pelo `save()` |
| `test_promover_a_admin_concede_acesso` | Mudar o papel para ADMIN concede o acesso |
| `test_rebaixar_admin_remove_acesso` | Tirar o papel ADMIN remove o acesso |
| `test_save_parcial_do_papel_tambem_sincroniza` | `save(update_fields=["papel"])` também grava os privilégios |
| `test_createsuperuser_cria_conta_com_papel_admin` | O `createsuperuser` cria a conta já como ADMIN |
| `test_admin_acessa_o_django_admin_e_aluno_nao` | Só o Administrador entra no Django Admin |
| `test_notificar_admins_alcanca_so_os_administradores` | Avisos para administradores chegam só a quem é ADMIN |

#### 3.1.7 `TestRevogacaoDoisFatores` — itens 1.5, 5.2

| Teste | O que verifica |
|---|---|
| `test_revogar_remove_o_dispositivo` | Desativar o 2FA apaga o dispositivo TOTP |
| `test_depois_de_revogar_o_login_volta_a_entrar_so_com_senha` | Após desativar, o login volta a pedir só a senha |
| `test_visitante_sem_login_e_mandado_para_o_login` | Quem não está logado não desativa o 2FA |
| `test_get_nao_revoga` | `GET` não desativa; só `POST` |
| `test_revogar_grava_auditoria` | A desativação é registrada na auditoria |
| `test_revogar_avisa_o_dono_da_conta_por_email` | O dono da conta recebe e-mail de aviso |
| `test_usuario_sem_2fa_nao_gera_auditoria_nem_email` | Sem 2FA ativo, não há registro nem e-mail |
| `test_revogar_so_afeta_o_proprio_usuario` | Não afeta o 2FA de outros usuários |
| `test_ativacao_pendente_e_limpa_sem_avisar` | Ativação não concluída é descartada sem aviso |
| `test_perfil_mostra_a_confirmacao_depois_de_desativar` | O perfil exibe a confirmação |

#### 3.1.8 `TestPaginaConfigurar2FA` — item 1.5

| Teste | O que verifica |
|---|---|
| `test_com_2fa_ligado_mostra_o_botao_e_nao_mostra_o_qr_code` | Com 2FA ativo, mostra o botão de desativar e não um novo QR Code |
| `test_com_2fa_ligado_nao_cria_dispositivo_novo` | Com 2FA ativo, abrir a página não cria outro dispositivo |
| `test_com_2fa_desligado_mostra_o_qr_code_e_nao_o_botao` | Sem 2FA, mostra o QR Code para ativação |

#### 3.1.9 `TestLoginObrigatorio` — páginas protegidas

| Teste | O que verifica |
|---|---|
| `test_visitante_vai_para_o_login` (4 casos) | Perfil, configuração do 2FA, exportação de dados e revogação do 2FA redirecionam visitantes para o login |

#### 3.1.10 `TestPerfil` — itens 3.4, 4.8

| Teste | O que verifica |
|---|---|
| `test_mostra_todos_os_dados_do_usuario` | O perfil exibe os dados pessoais do titular |
| `test_campos_vazios_mostram_aviso` | Campos vazios aparecem com aviso |
| `test_telefone_fica_criptografado_no_banco_mas_aparece_na_tela` | O telefone no banco é texto cifrado (Fernet), mas aparece correto na tela |

#### 3.1.11 `TestExportacaoDeDados` — item 4.9

| Teste | O que verifica |
|---|---|
| `test_exporta_todos_os_dados_do_perfil` | O JSON contém todos os dados do perfil, incluindo consentimento e versão da política |
| `test_baixa_como_arquivo` | A exportação é entregue como arquivo para download |
| `test_so_exporta_os_dados_do_proprio_usuario` | O arquivo só contém dados do titular logado |
| `test_campos_vazios_saem_com_texto_padrao` | Campos vazios saem com texto padrão |
| `test_arquivo_nao_vaza_a_senha` | O arquivo não contém a senha nem o hash |

---

### 3.2 `auditoria/tests.py` — Imutabilidade dos logs (item 5.3)

#### 3.2.1 `TestImutabilidadeAuditoriaModel`

| Teste | O que verifica |
|---|---|
| `test_nao_permite_atualizar_registro_existente_via_django` | O model recusa alterar um registro salvo |
| `test_nao_permite_excluir_registro_individual_via_django` | O model recusa excluir um registro |
| `test_nao_permite_atualizacao_em_lote_via_queryset` | `update()` em lote é recusado |
| `test_nao_permite_exclusao_em_lote_via_queryset` | `delete()` em lote é recusado |

#### 3.2.2 `TestImutabilidadeAuditoriaBanco`

| Teste | O que verifica |
|---|---|
| `test_trigger_postgres_bloqueia_update_direto` | A trigger do PostgreSQL bloqueia `UPDATE` feito direto por SQL |
| `test_trigger_postgres_bloqueia_delete_direto` | A trigger bloqueia `DELETE` feito direto por SQL |

#### 3.2.3 `TestExclusaoDeUsuarioPreservaLog`

| Teste | O que verifica |
|---|---|
| `test_excluir_usuario_mantem_o_log_com_usuario_nulo` | Excluir um usuário mantém o log, só com o usuário nulo |
| `test_trigger_nao_permite_zerar_usuario_junto_com_outra_alteracao` | A trigger só tolera zerar o usuário; zerar e alterar outro campo é recusado |

---

### 3.3 `notificacoes/tests.py` — Notificações e e-mails

#### 3.3.1 `TestNotificar`

| Teste | O que verifica |
|---|---|
| `test_grava_o_registro_no_banco` | Toda notificação fica registrada no banco |
| `test_envia_o_email_para_o_usuario` | Notificações do tipo e-mail são enviadas ao usuário |
| `test_tipo_sistema_grava_mas_nao_envia_email` | Notificações internas são gravadas sem envio de e-mail |
| `test_usuario_sem_email_grava_mas_nao_envia` | Usuário sem e-mail tem a notificação gravada, sem tentativa de envio |

#### 3.3.2 `TestNotificarAdmins`

| Teste | O que verifica |
|---|---|
| `test_avisa_todos_os_administradores_ativos` | Todos os administradores ativos são avisados |
| `test_nao_avisa_aluno_nem_admin_inativo` | Alunos e administradores inativos não recebem o aviso |
| `test_sem_administradores_nao_da_erro` | Sem administradores, o envio não gera erro |

#### 3.3.3 `TestNotificacaoEUsuarioExcluido`

| Teste | O que verifica |
|---|---|
| `test_excluir_usuario_apaga_as_notificacoes_dele` | Excluir um usuário apaga as notificações dele |

#### 3.3.4 `TestAdminDeNotificacoes`

| Teste | O que verifica |
|---|---|
| `test_listagem_resume_mensagens_longas` | A listagem do admin resume mensagens longas |

#### 3.3.5 `TestEmailsDoFluxoDeEmprestimo`

| Teste | O que verifica |
|---|---|
| `test_solicitacao_avisa_o_admin_por_email` | Uma nova solicitação avisa o administrador por e-mail |
| `test_aprovacao_avisa_o_aluno_com_o_prazo` | A aprovação avisa o aluno, informando o prazo de devolução (o aluno de teste autorizou os avisos; ver seção 3.9.4) |
| `test_rejeicao_avisa_o_aluno` | A rejeição avisa o aluno |
| `test_devolucao_avisa_o_aluno` | A devolução registrada avisa o aluno |

#### 3.3.6 `TestFalhaNoEnvioNaoQuebraNada`

| Teste | O que verifica |
|---|---|
| `test_erro_de_smtp_e_registrado_e_a_notificacao_continua_gravada` | Uma falha do servidor de e-mail é registrada no log e não interrompe a operação |

#### 3.3.7 `TestRecuperacaoDeSenhaPorEmail` — itens 2.1, 2.6

| Teste | O que verifica |
|---|---|
| `test_envia_o_link_por_email` | A recuperação envia o link com o token por e-mail |
| `test_email_inexistente_responde_igual_e_nao_envia` | E-mail não cadastrado recebe a mesma resposta e nenhum e-mail é enviado |
| `test_o_token_nao_fica_gravado_nas_notificacoes` | O token não fica gravado no histórico de notificações |
| `test_o_link_do_email_redefine_a_senha` | O link recebido por e-mail redefine a senha de ponta a ponta |

---

### 3.4 `inventario/tests.py` — Inventário e catálogo

#### 3.4.1 `TestPermissoesDaAPI` — RBAC do inventário

| Teste | O que verifica |
|---|---|
| `test_visitante_sem_token_e_recusado` | A API recusa quem não está autenticado |
| `test_aluno_lista_equipamentos` | O Aluno consulta os equipamentos |
| `test_aluno_lista_categorias` | O Aluno consulta as categorias |
| `test_aluno_nao_cria_categoria` | O Aluno não cria categorias |
| `test_aluno_nao_cria_equipamento` | O Aluno não cria equipamentos |
| `test_aluno_nao_edita_equipamento` | O Aluno não edita equipamentos |
| `test_aluno_nao_exclui_equipamento` | O Aluno não exclui equipamentos |

#### 3.4.2 `TestAdminGerenciaInventario`

| Teste | O que verifica |
|---|---|
| `test_admin_cria_categoria` | O Administrador cria categorias |
| `test_nome_de_categoria_duplicado_e_recusado` | Categoria com nome repetido é recusada |
| `test_admin_cria_equipamento_e_registra_auditoria` | Criar equipamento gera registro na auditoria |
| `test_patrimonio_duplicado_e_recusado` | Número de patrimônio repetido é recusado |
| `test_status_invalido_e_recusado` | Status de equipamento inválido é recusado |
| `test_categoria_inexistente_e_recusada` | Categoria inexistente é recusada |
| `test_admin_edita_equipamento_e_registra_auditoria` | Editar equipamento gera registro na auditoria |
| `test_data_de_cadastro_nao_pode_ser_alterada` | A data de cadastro do equipamento não pode ser alterada |
| `test_admin_exclui_equipamento_sem_historico_e_registra_auditoria` | Excluir equipamento sem histórico gera registro na auditoria |

#### 3.4.3 `TestExclusaoProtegida`

| Teste | O que verifica |
|---|---|
| `test_equipamento_com_historico_nao_e_excluido_nem_gera_log_falso` | Equipamento com empréstimos não é excluído, a API responde com erro claro e nenhum log falso de exclusão é gravado |
| `test_categoria_em_uso_nao_e_excluida` | Categoria com equipamentos não é excluída |

#### 3.4.4 `TestCatalogoTela`

| Teste | O que verifica |
|---|---|
| `test_visitante_e_mandado_para_o_login` | O catálogo exige login |
| `test_lista_os_equipamentos_cadastrados` | O catálogo lista os equipamentos |
| `test_equipamento_disponivel_tem_botao_de_solicitar` | Equipamento disponível exibe o botão "Solicitar" |
| `test_equipamento_emprestado_nao_tem_botao` | Equipamento emprestado não exibe o botão |
| `test_mostra_ja_solicitado_no_lugar_do_botao` (2 casos) | Pedido do próprio aluno em aberto (Solicitado ou Aprovado) mostra "Já solicitado" |
| `test_pedido_de_outro_aluno_nao_marca_ja_solicitado` | Pedido de outro aluno não altera a tela |
| `test_pedido_encerrado_nao_marca_ja_solicitado` (2 casos) | Pedido rejeitado ou devolvido libera um novo pedido |
| `test_catalogo_vazio_mostra_aviso` | Catálogo vazio exibe aviso |
| `test_status_aparece_por_extenso` | O status aparece por extenso |
| `test_nao_faz_uma_consulta_por_equipamento` | O número de consultas ao banco não cresce com a quantidade de equipamentos (sem N+1) |

---

### 3.5 `emprestimos/tests.py` — Ciclo do empréstimo

#### 3.5.1 `TestSolicitacaoPelaTela`

| Teste | O que verifica |
|---|---|
| `test_aluno_logado_cria_solicitacao` | O aluno logado cria uma solicitação, que nasce como Solicitado |
| `test_solicitacao_notifica_o_administrador` | A solicitação avisa os administradores |
| `test_solicitacao_gera_registro_de_auditoria` | A solicitação é registrada na auditoria |
| `test_visitante_sem_login_e_mandado_para_o_login` | Solicitar exige login |
| `test_get_nao_cria_solicitacao` | `GET` não cria solicitação; só `POST` |
| `test_equipamento_indisponivel_nao_pode_ser_solicitado` | Equipamento indisponível não pode ser solicitado |
| `test_segunda_solicitacao_em_aberto_e_barrada` | Uma segunda solicitação em aberto do mesmo equipamento é barrada |
| `test_pedido_rejeitado_nao_impede_nova_solicitacao` | Um pedido rejeitado não impede um novo pedido |

#### 3.5.2 `TestSolicitacaoPelaAPI`

| Teste | O que verifica |
|---|---|
| `test_cria_solicitacao` | A API cria a solicitação |
| `test_cliente_nao_consegue_escolher_status_nem_dono` | O cliente não consegue definir o status nem o dono do pedido (proteção contra *mass assignment*) |
| `test_sem_token_e_recusado` | A API recusa quem não está autenticado |
| `test_equipamento_indisponivel_e_recusado` | Equipamento indisponível é recusado |
| `test_segunda_solicitacao_em_aberto_e_recusada` | Segunda solicitação em aberto é recusada |
| `test_solicitacao_notifica_o_administrador` | A solicitação avisa os administradores |
| `test_meus_emprestimos_lista_so_os_do_proprio_usuario` | Cada usuário vê apenas os próprios empréstimos |

#### 3.5.3 `TestAprovacao`

| Teste | O que verifica |
|---|---|
| `test_aprovar_define_status_prazo_e_marca_equipamento` | Aprovar define o status, o prazo de 7 dias e marca o equipamento como emprestado |
| `test_aprovar_notifica_o_aluno_e_registra_auditoria` | A aprovação avisa o aluno e é registrada na auditoria |
| `test_aprovar_ignora_equipamento_indisponivel` | Pedido de equipamento indisponível não é aprovado |
| `test_aprovar_so_afeta_pedidos_solicitados` | Só pedidos em Solicitado são aprovados |
| `test_dois_pedidos_do_mesmo_equipamento_so_um_e_aprovado` | Com dois pedidos para o mesmo equipamento, só um é aprovado |
| `test_aluno_nao_consegue_executar_acao_do_admin` | O aluno não executa ações de administrador |

#### 3.5.4 `TestRejeicao`

| Teste | O que verifica |
|---|---|
| `test_rejeitar_muda_status_notifica_e_nao_mexe_no_equipamento` | Rejeitar muda o status, avisa o aluno e não altera o equipamento |
| `test_rejeitar_nao_afeta_emprestimo_ja_aprovado` | Empréstimo já aprovado não é rejeitado |

#### 3.5.5 `TestDevolucao`

| Teste | O que verifica |
|---|---|
| `test_devolver_libera_o_equipamento_e_registra_a_data` | A devolução libera o equipamento e grava a data |
| `test_devolver_nao_afeta_pedido_que_nao_foi_aprovado` | Pedido não aprovado não pode ser devolvido |

#### 3.5.6 `TestPedidoDeProrrogacao`

| Teste | O que verifica |
|---|---|
| `test_aluno_solicita_prorrogacao` | O aluno pede a prorrogação do prazo |
| `test_so_emprestimo_aprovado_pode_ser_prorrogado` | Só empréstimos aprovados podem ser prorrogados |
| `test_pedido_repetido_nao_avisa_o_admin_de_novo` | Pedido repetido não gera novo aviso ao administrador |
| `test_aluno_nao_pede_prorrogacao_do_emprestimo_de_outro` | O aluno não pede prorrogação de empréstimo de outra pessoa |

#### 3.5.7 `TestDecisaoDeProrrogacao`

| Teste | O que verifica |
|---|---|
| `test_admin_aprova_e_o_prazo_aumenta` | Aprovar a prorrogação estende o prazo |
| `test_admin_rejeita_e_o_prazo_continua` | Rejeitar mantém o prazo original |
| `test_aprovar_prorrogacao_sem_pedido_nao_altera_o_prazo` | Sem pedido do aluno, o prazo não muda |

#### 3.5.8 `TestAtraso`

| Teste | O que verifica |
|---|---|
| `test_emprestimo_vencido_esta_atrasado` | Empréstimo aprovado, não devolvido e com prazo vencido está atrasado |
| `test_emprestimo_no_prazo_nao_esta_atrasado` | Empréstimo dentro do prazo não está atrasado |
| `test_pedido_sem_prazo_nao_esta_atrasado` | Pedido ainda sem prazo não está atrasado |
| `test_emprestimo_devolvido_nao_esta_atrasado` | Empréstimo devolvido não está atrasado |
| `test_prorrogacao_aprovada_tira_o_atraso` | A prorrogação aprovada retira o atraso |
| `test_tela_so_marca_atrasado_quando_vencido` | A tela só indica atraso quando o prazo venceu |

### 3.6 `usuarios/tests.py` — Pendências da avaliação da release 1.5.0

Testes criados para comprovar, com execução real, os pontos que o parecer da avaliação da release 1.5.0 pediu para demonstrar (itens 1.5, Recuperação de Senha e 5.3).

#### 3.6.1 `TestNenhumaRotaContornaO2FA` — item 1.5

| Teste | O que verifica |
|---|---|
| `test_nenhuma_rota_expoe_emissao_direta_de_jwt` | Percorre **todas** as URLs do projeto e confirma que nenhuma usa `TokenObtainPairView` ou `TokenObtainSlidingView`, que emitiriam JWT sem passar pelo 2FA |
| `test_renovacao_nao_emite_jwt_sem_refresh_valido` | A rota de renovação não emite token de acesso sem um refresh token válido |
| `test_senha_correta_sozinha_nao_gera_jwt_nem_sessao` | Com 2FA ativo, a senha correta não gera JWT nem sessão autenticada |
| `test_login_web_com_2fa_nao_autentica_antes_do_codigo` | No login web, a senha correta só leva à tela do código, sem autenticar |

#### 3.6.2 `TestCodigosTOTP` — item 1.5

| Teste | O que verifica |
|---|---|
| `test_codigo_invalido_e_recusado` | Código TOTP inválido é recusado e não emite token |
| `test_replay_o_mesmo_codigo_nao_vale_duas_vezes` | Um código já usado com sucesso é recusado na segunda vez (proteção contra replay do `django-otp`) |
| `test_apos_erro_o_dispositivo_fica_bloqueado_por_um_tempo` | Logo após um código errado, nem o código certo passa (atraso progressivo do `django-otp`) |
| `test_tentativas_repetidas_sao_limitadas_por_ip` | Na 11ª tentativa em um minuto, a API responde HTTP 429 (limite `login_2fa`) |
| `test_falhas_de_2fa_ficam_registradas_na_auditoria` | Cada código errado gera registro `2FA_FALHA` na auditoria |

#### 3.6.3 `TestExpiracaoDoEstadoPre2FA` — item 1.5

| Teste | O que verifica |
|---|---|
| `test_estado_pre_2fa_web_expira` | No login web, o estado "senha correta, aguardando código" expira em 5 minutos; depois disso, a sessão é limpa e o código não é mais aceito |
| `test_estado_pre_2fa_web_dentro_do_prazo_funciona` | Dentro do prazo, o código correto conclui o login normalmente |
| `test_token_pre_2fa_da_api_expira` | No login JWT, o token intermediário com mais de 5 minutos é recusado |

#### 3.6.4 `TestRecuperacaoDeSenhaExecutada` — itens 2.3, 2.4 e 1.11

| Teste | O que verifica |
|---|---|
| `test_token_expirado_e_recusado` | Token de recuperação vencido é recusado e a senha antiga continua valendo |
| `test_token_nao_pode_ser_reutilizado` | O token funciona uma vez e é recusado na segunda tentativa |
| `test_politica_de_senha_e_aplicada_na_redefinicao` | Senhas fracas (`12345678`, `password123`, `curta`) são recusadas pela política de senhas (3 casos) |
| `test_solicitacoes_de_recuperacao_sao_limitadas` | No 6º pedido de e-mail de recuperação na mesma hora, a API responde HTTP 429 (limite `recuperacao_senha`) |

#### 3.6.5 `TestTriggerAplicadoNoBanco` — item 5.3

| Teste | O que verifica |
|---|---|
| `test_banco_em_uso_e_postgresql` | Os testes rodam contra PostgreSQL, e não contra outro banco |
| `test_trigger_existe_na_tabela_de_auditoria` | Consulta o catálogo `pg_trigger` e confirma que o trigger está instalado e **ativo** na tabela de auditoria do banco em uso |
| `test_update_e_delete_diretos_continuam_bloqueados` | `UPDATE` e `DELETE` em SQL puro, direto no banco, são recusados e o registro permanece intacto |

### 3.7 `usuarios/tests_criptografia.py` — Dados cifrados em repouso (item 3.4)

Os testes leem o valor gravado direto no banco, por SQL puro, para provar que o que está guardado é o texto cifrado, e não o dado original.

#### 3.7.1 `TestDadosCifradosNoBanco`

| Teste | O que verifica |
|---|---|
| `test_telefone_fica_cifrado_no_banco` | O banco guarda um token Fernet (`gAAAA...`), e não o número |
| `test_chave_do_2fa_fica_cifrada_no_banco` | A chave secreta do 2FA também fica cifrada e, ao ser lida, volta a ser a chave hexadecimal original |
| `test_2fa_continua_funcionando_com_a_chave_cifrada` | O código certo é aceito e o errado é recusado, com a chave cifrada |
| `test_mesmo_valor_gera_cifras_diferentes` | Dois telefones iguais geram textos cifrados diferentes |
| `test_migracao_tira_as_chaves_do_texto_puro` | A migração `0011` move as chaves do `TOTPDevice` (texto puro) para o `DispositivoTOTP` (cifrado), sem invalidar o aplicativo autenticador |

#### 3.7.2 `TestRotacaoDeChave`

| Teste | O que verifica |
|---|---|
| `test_rotacao_completa` | Com a chave nova e a antiga configuradas, os dados continuam legíveis; depois do comando `rotacionar_chave_criptografia` e da retirada da chave antiga, o dado só abre com a chave nova |
| `test_sem_a_chave_certa_o_dado_nao_e_lido` | Sem a chave correta, a leitura falha (`InvalidToken`) em vez de devolver um valor errado |

### 3.8 `usuarios/testes_lgpd.py` — Mapeamento e minimização (itens 4.2 e 4.3)

#### 3.8.1 `TestMapeamentoDosDados`

| Teste | O que verifica |
|---|---|
| `test_todo_campo_esta_mapeado` | Para cada modelo com dado pessoal (9 casos), os campos mapeados em `usuarios/lgpd.py` mais os técnicos são **exatamente** os campos do banco |
| `test_todo_modelo_ligado_a_um_usuario_esta_mapeado` | Nenhum modelo do projeto com vínculo a um usuário fica fora do mapeamento |
| `test_toda_finalidade_usada_existe_e_tem_base_legal` | Toda finalidade usada está descrita e tem base legal do art. 7º |

#### 3.8.2 `TestMinimizacao`

| Teste | O que verifica |
|---|---|
| `test_cadastro_funciona_sem_telefone` | O telefone é opcional na API |
| `test_formulario_de_cadastro_nao_exige_telefone` | O formulário web não marca o telefone como obrigatório |
| `test_cadastro_descarta_dados_nao_previstos` | CPF, endereço, data de nascimento e flags de privilégio enviados no cadastro não são gravados nem devolvidos |
| `test_login_nao_grava_copia_no_axes` | O login bem-sucedido fica só na auditoria, sem cópia na tabela do `django-axes` |
| `test_tentativa_errada_continua_registrada_para_o_bloqueio` | As tentativas erradas continuam registradas, sem a senha digitada |

### 3.9 `usuarios/testes_consentimento.py` — Consentimento por finalidade (item 4.5)

#### 3.9.1 `TestFinalidadesOpcionais`

| Teste | O que verifica |
|---|---|
| `test_finalidades_opcionais_estao_no_mapeamento_com_base_no_consentimento` | As finalidades opcionais existem no mapeamento e têm o consentimento como base legal |

#### 3.9.2 `TestConsentimentoNoCadastro`

| Teste | O que verifica |
|---|---|
| `test_cadastro_sem_marcar_nada_registra_as_duas_recusas` | A recusa também fica registrada, com data e versão da política |
| `test_cada_finalidade_e_escolhida_separadamente` | Autorizar uma finalidade não autoriza a outra |
| `test_telefone_sem_autorizacao_e_recusado` | O telefone só é aceito com a autorização correspondente |
| `test_telefone_com_autorizacao_e_guardado` | Com a autorização, o telefone é gravado |
| `test_aceite_da_politica_continua_obrigatorio` | O aceite da política continua obrigatório para criar a conta |

#### 3.9.3 `TestConsentimentoNoPerfil`

| Teste | O que verifica |
|---|---|
| `test_perfil_mostra_uma_opcao_para_cada_finalidade` | "Minhas Autorizações" tem uma opção para cada finalidade |
| `test_autorizar_uma_finalidade_nao_muda_a_outra` | As finalidades são independentes |
| `test_autorizar_telefone_exige_o_numero` | Autorizar o telefone sem informar o número não tem efeito |
| `test_autorizar_telefone_guarda_o_numero` | Com o número, a autorização e o telefone são gravados |
| `test_retirar_autorizacao_do_telefone_apaga_o_numero` | Retirar a autorização apaga o telefone |
| `test_retirar_autorizacao_nao_bloqueia_o_acesso` | Retirar uma autorização opcional não suspende a conta |
| `test_cada_mudanca_fica_no_historico_e_na_auditoria` | Cada mudança vira uma linha nova no histórico e um registro na auditoria |
| `test_historico_nao_pode_ser_alterado` | Um registro de consentimento não pode ser alterado depois de gravado |
| `test_exportacao_inclui_o_historico` | A exportação JSON inclui o histórico por finalidade |

#### 3.9.4 `TestEfeitoDoConsentimento`

| Teste | O que verifica |
|---|---|
| `test_sem_consentimento_o_aviso_de_emprestimo_nao_e_enviado` | Sem autorização, o aviso de empréstimo não é enviado nem gravado |
| `test_com_consentimento_o_aviso_de_emprestimo_e_enviado` | Com autorização, o aviso é enviado |
| `test_aviso_de_seguranca_nao_depende_de_consentimento` | Alertas de segurança da conta são sempre enviados |

#### 3.9.5 `TestMigracaoDosUsuariosExistentes`

| Teste | O que verifica |
|---|---|
| `test_mantem_o_que_cada_usuario_ja_recebia` | A migração `0013` registra, para quem já tinha conta, as autorizações que correspondem ao que a pessoa já recebia na v1.0 |

### 3.10 `usuarios/testes_retencao.py` — Eliminação, anonimização e retenção (item 4.10)

A rotina de retenção recebe a data "de agora" como parâmetro, então os testes simulam a passagem do tempo sem envelhecer os registros. Na auditoria, como o trigger usa o relógio do PostgreSQL, os registros antigos são inseridos já com a data no passado.

#### 3.10.1 `TestEncerramentoDaConta`

| Teste | O que verifica |
|---|---|
| `test_elimina_todos_os_vinculos_do_titular` | O encerramento anonimiza a conta e apaga 2FA, links de recuperação, notificações, observações dos empréstimos e tentativas de login; o empréstimo fica ligado à conta anônima |
| `test_mantem_o_historico_de_consentimento_como_prova` | O histórico de consentimento continua depois do encerramento |
| `test_encerra_as_sessoes_em_outros_navegadores` | As sessões abertas em outros navegadores são encerradas |
| `test_bloqueia_com_emprestimo_em_aberto` | Com empréstimo solicitado, aprovado, retirado ou atrasado (4 casos), o encerramento é recusado |
| `test_encerramento_fica_na_auditoria` | O encerramento é registrado na auditoria |

#### 3.10.2 `TestRotinaDeRetencao`

| Teste | O que verifica |
|---|---|
| `test_token_de_recuperacao_some_7_dias_depois_de_expirar` | Um dia antes do prazo o token continua; um dia depois, é apagado |
| `test_notificacao_some_depois_de_90_dias` | O mesmo para as notificações (90 dias) |
| `test_tentativa_de_login_some_depois_de_30_dias` | O mesmo para as tentativas de login (30 dias) |
| `test_sessoes_expiradas_sao_apagadas` | Sessões expiradas são apagadas |
| `test_conta_suspensa_e_anonimizada_depois_de_12_meses` | A conta suspensa por revogação é anonimizada depois de 12 meses, e não antes |
| `test_conta_suspensa_com_equipamento_nao_e_anonimizada` | Quem ainda está com um equipamento não é anonimizado |
| `test_conta_desativada_pelo_admin_nao_entra_na_rotina` | A desativação pelo administrador não é tratada como revogação |
| `test_emprestimo_devolvido_some_depois_de_5_anos` | O empréstimo devolvido é eliminado depois de 5 anos, e não antes |
| `test_emprestimo_em_aberto_nunca_e_apagado` | Empréstimo em aberto nunca é eliminado |
| `test_auditoria_com_mais_de_5_anos_e_eliminada` | Só o registro de auditoria com mais de 5 anos é eliminado |
| `test_comando_agendavel_executa_a_rotina` | O comando `aplicar_retencao` executa a rotina |

#### 3.10.3 `TestTriggerDaAuditoriaComRetencao`

| Teste | O que verifica |
|---|---|
| `test_registro_dentro_do_prazo_continua_sem_poder_ser_apagado` | `DELETE` em SQL puro de um registro com menos de 5 anos continua bloqueado pelo trigger |
| `test_nao_da_para_envelhecer_um_registro_para_apaga_lo` | Não é possível alterar a data de um registro para conseguir apagá-lo |
| `test_registro_antigo_continua_sem_poder_ser_alterado` | Mesmo um registro antigo não pode ser alterado |

## 4. Achados de segurança corrigidos durante os testes

### 4.1 Identificador exposto no login com 2FA da API

Durante a escrita dos testes de `TestLoginSpaDoisFatores`, foi identificada uma falha real na primeira versão do endpoint de login via API: a etapa 1 devolvia o `user_id` do usuário autenticado, e a etapa 2 aceitava esse id diretamente para validar o código de 2FA. Como identificadores de usuário no banco são sequenciais e previsíveis, isso permitiria que alguém pulasse a etapa da senha e tentasse adivinhar apenas o código de 6 dígitos de um usuário conhecido.

**Correção aplicada:** a etapa 1 passou a emitir um token assinado (usando `django.core.signing`, que utiliza a `SECRET_KEY` do projeto), gerado apenas após a senha correta. A etapa 2 exige esse token, rejeitando tokens forjados, adulterados ou emitidos há mais de 5 minutos. O identificador do usuário não é mais exposto em nenhuma resposta da API.

Essa correção está coberta pelos testes `test_primeira_etapa_nao_emite_jwt_nem_expoe_id`, `test_token_forjado_ou_adulterado_e_rejeitado` e `test_token_expirado_e_rejeitado`.

### 4.2 Escalada de privilégio no cadastro público

O cadastro público aceitava o campo `papel` enviado pelo cliente, permitindo criar uma conta de Administrador. **Correção aplicada:** o `RegistroSerializer` passou a aceitar apenas os papéis Aluno e Docente, e o papel passou a ser a fonte única de privilégios (`is_staff` e `is_superuser` sincronizados no `save()`). Coberto por `TestCadastroNaoPermitePapelPrivilegiado` e `TestPapelManda`.

### 4.3 Estado pré-2FA sem prazo no login web

Ao escrever `TestExpiracaoDoEstadoPre2FA`, a equipe verificou que o login JWT já expirava o token intermediário em 5 minutos, mas o login **web** guardava o estado "senha correta, aguardando código" na sessão **sem prazo**: a pessoa podia digitar o código muito tempo depois da senha. **Correção aplicada:** o `login_view` passou a gravar o horário da autenticação primária (`pre_2fa_em`), e o `validar_dois_fatores_view` recusa o código depois de `TOKEN_2FA_VALIDADE_SEGUNDOS` (5 minutos), limpando a sessão. Coberto por `test_estado_pre_2fa_web_expira`.

### 4.4 Política de senha não aplicada pela API

A análise estática da esteira (Semgrep, regra `unvalidated-password`, CWE-521) apontou que o cadastro e a redefinição de senha aceitavam qualquer senha com 8 caracteres, como `12345678`, embora o `settings.py` declare quatro validadores. **Correção aplicada:** `validate_password()` passou a ser chamado antes de `set_password()` no `RegistroSerializer` e na `RedefinirSenhaView`. Coberto por `test_politica_de_senha_e_aplicada_na_redefinicao`.

### 4.5 API sem limite de requisições

A mesma análise (regra `missing-throttle-config`, CWE-770) apontou que a API REST não limitava o número de requisições, o que permitiria disparar e-mails de recuperação em massa ou testar códigos 2FA sem limite. **Correção aplicada:** rate limiting do Django REST Framework para toda a API (60/min anônimo, 300/min autenticado) e limites mais rígidos para as rotas sensíveis (5 pedidos de recuperação por hora e 10 tentativas de código 2FA por minuto). Coberto por `test_solicitacoes_de_recuperacao_sao_limitadas` e `test_tentativas_repetidas_sao_limitadas_por_ip`.

### 4.6 Chave secreta do 2FA em texto puro

Ao levantar todos os dados sensíveis guardados no banco (item 3.4), a equipe verificou que o `TOTPDevice` do `django-otp` guarda a chave secreta do 2FA em texto puro. Quem lesse essa tabela, por um backup vazado ou uma injeção de SQL, conseguiria gerar os códigos de 2FA de qualquer usuário. **Correção aplicada:** modelo próprio `DispositivoTOTP`, com a chave no mesmo campo cifrado do telefone, e migração dos dispositivos existentes. Coberto pela seção 3.7.

### 4.7 Dados coletados sem finalidade

Ao montar o mapeamento campo a campo (item 4.2), a equipe encontrou dois casos sem finalidade: o formulário de cadastro **exigia** o telefone, embora nenhuma função do sistema dependa dele, e o `django-axes` guardava uma cópia de cada login bem-sucedido, com IP e navegador, sem prazo. **Correção aplicada:** telefone opcional e `AXES_DISABLE_ACCESS_LOG = True`. Coberto pela seção 3.8.2.

### 4.8 Testes que não estavam sendo executados

Na revisão do CI, a equipe notou que um arquivo de testes chamado `testes_lgpd.py` não era coletado pelo `pytest`, porque a configuração só reconhecia nomes começando com `tests`. Os testes existiam, mas não rodavam, e o CI continuava verde. **Correção aplicada:** o `pytest.ini` passou a reconhecer também o padrão `testes_*.py` (seção 2). A lição registrada é conferir o **número de casos executados** em cada execução do CI, e não só se ela passou.

## 5. Como executar os testes

Dentro da pasta `backend/`, para a suíte completa:

```bash
python -m pytest -v
```

Ou, com o Docker em execução:

```bash
docker compose exec backend python -m pytest -v
```

Para executar apenas um módulo, informe o arquivo, por exemplo `python -m pytest usuarios/tests_seguranca.py -v`.

**Execução automática (CI).** A suíte também roda no GitHub Actions a cada push e Pull Request para a `main`, pelo workflow `.github/workflows/testes-postgresql.yml` ("Testes automatizados"). O job sobe um **PostgreSQL 16 real** como serviço, instala as dependências com as versões fixadas no `requirements.txt`, gera segredos descartáveis e executa `python -m pytest -v`. Cada execução publica o artefato `resultado-testes`, com três arquivos:

| Arquivo | Conteúdo |
|---|---|
| `ambiente.txt` | Data, commit, sistema, versões do Python e do PostgreSQL e lista de pacotes instalados |
| `resultado-testes.txt` | Saída completa do `pytest` |
| `junit.xml` | Resultado de cada caso no formato JUnit |

Assim, qualquer pessoa consegue verificar qual versão do código foi testada, em qual ambiente e com qual resultado, sem depender de uma execução manual.

## 6. Resultado da execução

Execução automática no GitHub Actions, workflow **Testes automatizados**, no commit `cdc2dc9` da `main` (merge do Pull Request #59), em **17/11/2026 às 21:25 (horário de Brasília)**. Os arquivos abaixo foram copiados do artefato `resultado-testes` dessa execução, disponível na aba **Actions** do repositório.

### 6.1 Ambiente (`ambiente.txt`)

```
Data (UTC): 2026-11-18 00:25:09
Commit: cdc2dc9eb93374b0168240a041a54930da0cccc9
Runner: Ubuntu 26.04.1 LTS
Python: Python 3.14.10
PostgreSQL: PostgreSQL 16.16 (Debian 16.16-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit

Pacotes instalados:
asgiref==3.13.0
cffi==2.1.1
cryptography==50.0.2
Django==6.1.3
django-axes==9.0.0
django-otp==1.7.5
djangorestframework==3.18.3
djangorestframework_simplejwt==5.5.1
iniconfig==2.3.1
packaging==26.3
pillow==13.0.0
pluggy==1.7.0
psycopg==3.3.8
psycopg-binary==3.3.8
pycparser==3.12
Pygments==2.21.0
PyJWT==2.15.1
pytest==9.2.0
pytest-django==4.14.0
python-decouple==3.8
qrcode==8.2
sqlparse==0.6.1
```

### 6.2 Resumo (`junit.xml`)

| Casos | Aprovados | Falhas | Erros | Ignorados | Duração |
|---|---|---|---|---|---|
| 234 | 234 | 0 | 0 | 0 | 13,4 s |

### 6.3 Saída completa (`resultado-testes.txt`)

```
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- /opt/hostedtoolcache/Python/3.14.10/x64/bin/python
django: version: 6.1.3, settings: config.settings (from ini)
rootdir: /home/runner/work/EmprestaCampus/EmprestaCampus/backend
configfile: pytest.ini
plugins: django-4.14.0
collecting ... collected 234 items

auditoria/tests.py::TestImutabilidadeAuditoriaModel::test_nao_permite_atualizar_registro_existente_via_django PASSED [  0%]
auditoria/tests.py::TestImutabilidadeAuditoriaModel::test_nao_permite_excluir_registro_individual_via_django PASSED [  0%]
auditoria/tests.py::TestImutabilidadeAuditoriaModel::test_nao_permite_atualizacao_em_lote_via_queryset PASSED [  1%]
auditoria/tests.py::TestImutabilidadeAuditoriaModel::test_nao_permite_exclusao_em_lote_via_queryset PASSED [  1%]
auditoria/tests.py::TestImutabilidadeAuditoriaBanco::test_trigger_postgres_bloqueia_update_direto PASSED [  2%]
auditoria/tests.py::TestImutabilidadeAuditoriaBanco::test_trigger_postgres_bloqueia_delete_direto PASSED [  2%]
auditoria/tests.py::TestExclusaoDeUsuarioPreservaLog::test_excluir_usuario_mantem_o_log_com_usuario_nulo PASSED [  2%]
auditoria/tests.py::TestExclusaoDeUsuarioPreservaLog::test_trigger_nao_permite_zerar_usuario_junto_com_outra_alteracao PASSED [  3%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_aluno_logado_cria_solicitacao PASSED [  3%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_solicitacao_notifica_o_administrador PASSED [  4%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_solicitacao_gera_registro_de_auditoria PASSED [  4%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_visitante_sem_login_e_mandado_para_o_login PASSED [  5%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_get_nao_cria_solicitacao PASSED [  5%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_equipamento_indisponivel_nao_pode_ser_solicitado PASSED [  5%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_segunda_solicitacao_em_aberto_e_barrada PASSED [  6%]
emprestimos/tests.py::TestSolicitacaoPelaTela::test_pedido_rejeitado_nao_impede_nova_solicitacao PASSED [  6%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_cria_solicitacao PASSED [  7%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_cliente_nao_consegue_escolher_status_nem_dono PASSED [  7%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_sem_token_e_recusado PASSED [  8%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_equipamento_indisponivel_e_recusado PASSED [  8%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_segunda_solicitacao_em_aberto_e_recusada PASSED [  8%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_solicitacao_notifica_o_administrador PASSED [  9%]
emprestimos/tests.py::TestSolicitacaoPelaAPI::test_meus_emprestimos_lista_so_os_do_proprio_usuario PASSED [  9%]
emprestimos/tests.py::TestAprovacao::test_aprovar_define_status_prazo_e_marca_equipamento PASSED [ 10%]
emprestimos/tests.py::TestAprovacao::test_aprovar_notifica_o_aluno_e_registra_auditoria PASSED [ 10%]
emprestimos/tests.py::TestAprovacao::test_aprovar_ignora_equipamento_indisponivel PASSED [ 11%]
emprestimos/tests.py::TestAprovacao::test_aprovar_so_afeta_pedidos_solicitados PASSED [ 11%]
emprestimos/tests.py::TestAprovacao::test_dois_pedidos_do_mesmo_equipamento_so_um_e_aprovado PASSED [ 11%]
emprestimos/tests.py::TestAprovacao::test_aluno_nao_consegue_executar_acao_do_admin PASSED [ 12%]
emprestimos/tests.py::TestRejeicao::test_rejeitar_muda_status_notifica_e_nao_mexe_no_equipamento PASSED [ 12%]
emprestimos/tests.py::TestRejeicao::test_rejeitar_nao_afeta_emprestimo_ja_aprovado PASSED [ 13%]
emprestimos/tests.py::TestDevolucao::test_devolver_libera_o_equipamento_e_registra_a_data PASSED [ 13%]
emprestimos/tests.py::TestDevolucao::test_devolver_nao_afeta_pedido_que_nao_foi_aprovado PASSED [ 14%]
emprestimos/tests.py::TestPedidoDeProrrogacao::test_aluno_solicita_prorrogacao PASSED [ 14%]
emprestimos/tests.py::TestPedidoDeProrrogacao::test_so_emprestimo_aprovado_pode_ser_prorrogado PASSED [ 14%]
emprestimos/tests.py::TestPedidoDeProrrogacao::test_pedido_repetido_nao_avisa_o_admin_de_novo PASSED [ 15%]
emprestimos/tests.py::TestPedidoDeProrrogacao::test_aluno_nao_pede_prorrogacao_do_emprestimo_de_outro PASSED [ 15%]
emprestimos/tests.py::TestDecisaoDeProrrogacao::test_admin_aprova_e_o_prazo_aumenta PASSED [ 16%]
emprestimos/tests.py::TestDecisaoDeProrrogacao::test_admin_rejeita_e_o_prazo_continua PASSED [ 16%]
emprestimos/tests.py::TestDecisaoDeProrrogacao::test_aprovar_prorrogacao_sem_pedido_nao_altera_o_prazo PASSED [ 17%]
emprestimos/tests.py::TestAtraso::test_emprestimo_vencido_esta_atrasado PASSED [ 17%]
emprestimos/tests.py::TestAtraso::test_emprestimo_no_prazo_nao_esta_atrasado PASSED [ 17%]
emprestimos/tests.py::TestAtraso::test_pedido_sem_prazo_nao_esta_atrasado PASSED [ 18%]
emprestimos/tests.py::TestAtraso::test_emprestimo_devolvido_nao_esta_atrasado PASSED [ 18%]
emprestimos/tests.py::TestAtraso::test_prorrogacao_aprovada_tira_o_atraso PASSED [ 19%]
emprestimos/tests.py::TestAtraso::test_tela_so_marca_atrasado_quando_vencido PASSED [ 19%]
inventario/tests.py::TestPermissoesDaAPI::test_visitante_sem_token_e_recusado PASSED [ 20%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_lista_equipamentos PASSED [ 20%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_lista_categorias PASSED [ 20%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_nao_cria_categoria PASSED [ 21%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_nao_cria_equipamento PASSED [ 21%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_nao_edita_equipamento PASSED [ 22%]
inventario/tests.py::TestPermissoesDaAPI::test_aluno_nao_exclui_equipamento PASSED [ 22%]
inventario/tests.py::TestAdminGerenciaInventario::test_admin_cria_categoria PASSED [ 23%]
inventario/tests.py::TestAdminGerenciaInventario::test_nome_de_categoria_duplicado_e_recusado PASSED [ 23%]
inventario/tests.py::TestAdminGerenciaInventario::test_admin_cria_equipamento_e_registra_auditoria PASSED [ 23%]
inventario/tests.py::TestAdminGerenciaInventario::test_patrimonio_duplicado_e_recusado PASSED [ 24%]
inventario/tests.py::TestAdminGerenciaInventario::test_status_invalido_e_recusado PASSED [ 24%]
inventario/tests.py::TestAdminGerenciaInventario::test_categoria_inexistente_e_recusada PASSED [ 25%]
inventario/tests.py::TestAdminGerenciaInventario::test_admin_edita_equipamento_e_registra_auditoria PASSED [ 25%]
inventario/tests.py::TestAdminGerenciaInventario::test_data_de_cadastro_nao_pode_ser_alterada PASSED [ 26%]
inventario/tests.py::TestAdminGerenciaInventario::test_admin_exclui_equipamento_sem_historico_e_registra_auditoria PASSED [ 26%]
inventario/tests.py::TestExclusaoProtegida::test_equipamento_com_historico_nao_e_excluido_nem_gera_log_falso PASSED [ 26%]
inventario/tests.py::TestExclusaoProtegida::test_categoria_em_uso_nao_e_excluida PASSED [ 27%]
inventario/tests.py::TestCatalogoTela::test_visitante_e_mandado_para_o_login PASSED [ 27%]
inventario/tests.py::TestCatalogoTela::test_lista_os_equipamentos_cadastrados PASSED [ 28%]
inventario/tests.py::TestCatalogoTela::test_equipamento_disponivel_tem_botao_de_solicitar PASSED [ 28%]
inventario/tests.py::TestCatalogoTela::test_equipamento_emprestado_nao_tem_botao PASSED [ 29%]
inventario/tests.py::TestCatalogoTela::test_mostra_ja_solicitado_no_lugar_do_botao[SOLICITADO] PASSED [ 29%]
inventario/tests.py::TestCatalogoTela::test_mostra_ja_solicitado_no_lugar_do_botao[APROVADO] PASSED [ 29%]
inventario/tests.py::TestCatalogoTela::test_pedido_de_outro_aluno_nao_marca_ja_solicitado PASSED [ 30%]
inventario/tests.py::TestCatalogoTela::test_pedido_encerrado_nao_marca_ja_solicitado[REJEITADO] PASSED [ 30%]
inventario/tests.py::TestCatalogoTela::test_pedido_encerrado_nao_marca_ja_solicitado[DEVOLVIDO] PASSED [ 31%]
inventario/tests.py::TestCatalogoTela::test_catalogo_vazio_mostra_aviso PASSED [ 31%]
inventario/tests.py::TestCatalogoTela::test_status_aparece_por_extenso PASSED [ 32%]
inventario/tests.py::TestCatalogoTela::test_nao_faz_uma_consulta_por_equipamento PASSED [ 32%]
notificacoes/tests.py::TestNotificar::test_grava_o_registro_no_banco PASSED [ 32%]
notificacoes/tests.py::TestNotificar::test_envia_o_email_para_o_usuario PASSED [ 33%]
notificacoes/tests.py::TestNotificar::test_tipo_sistema_grava_mas_nao_envia_email PASSED [ 33%]
notificacoes/tests.py::TestNotificar::test_usuario_sem_email_grava_mas_nao_envia PASSED [ 34%]
notificacoes/tests.py::TestNotificarAdmins::test_avisa_todos_os_administradores_ativos PASSED [ 34%]
notificacoes/tests.py::TestNotificarAdmins::test_nao_avisa_aluno_nem_admin_inativo PASSED [ 35%]
notificacoes/tests.py::TestNotificarAdmins::test_sem_administradores_nao_da_erro PASSED [ 35%]
notificacoes/tests.py::TestNotificacaoEUsuarioExcluido::test_excluir_usuario_apaga_as_notificacoes_dele PASSED [ 35%]
notificacoes/tests.py::TestAdminDeNotificacoes::test_listagem_resume_mensagens_longas PASSED [ 36%]
notificacoes/tests.py::TestEmailsDoFluxoDeEmprestimo::test_solicitacao_avisa_o_admin_por_email PASSED [ 36%]
notificacoes/tests.py::TestEmailsDoFluxoDeEmprestimo::test_aprovacao_avisa_o_aluno_com_o_prazo PASSED [ 37%]
notificacoes/tests.py::TestEmailsDoFluxoDeEmprestimo::test_rejeicao_avisa_o_aluno PASSED [ 37%]
notificacoes/tests.py::TestEmailsDoFluxoDeEmprestimo::test_devolucao_avisa_o_aluno PASSED [ 38%]
notificacoes/tests.py::TestFalhaNoEnvioNaoQuebraNada::test_erro_de_smtp_e_registrado_e_a_notificacao_continua_gravada PASSED [ 38%]
notificacoes/tests.py::TestRecuperacaoDeSenhaPorEmail::test_envia_o_link_por_email PASSED [ 38%]
notificacoes/tests.py::TestRecuperacaoDeSenhaPorEmail::test_email_inexistente_responde_igual_e_nao_envia PASSED [ 39%]
notificacoes/tests.py::TestRecuperacaoDeSenhaPorEmail::test_o_token_nao_fica_gravado_nas_notificacoes PASSED [ 39%]
notificacoes/tests.py::TestRecuperacaoDeSenhaPorEmail::test_o_link_do_email_redefine_a_senha PASSED [ 40%]
usuarios/testes_consentimento.py::TestConsentimentoNoCadastro::test_cadastro_sem_marcar_nada_registra_as_duas_recusas PASSED [ 40%]
usuarios/testes_consentimento.py::TestConsentimentoNoCadastro::test_cada_finalidade_e_escolhida_separadamente PASSED [ 41%]
usuarios/testes_consentimento.py::TestConsentimentoNoCadastro::test_telefone_sem_autorizacao_e_recusado PASSED [ 41%]
usuarios/testes_consentimento.py::TestConsentimentoNoCadastro::test_telefone_com_autorizacao_e_guardado PASSED [ 41%]
usuarios/testes_consentimento.py::TestConsentimentoNoCadastro::test_aceite_da_politica_continua_obrigatorio PASSED [ 42%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_perfil_mostra_uma_opcao_para_cada_finalidade PASSED [ 42%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_autorizar_uma_finalidade_nao_muda_a_outra PASSED [ 43%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_autorizar_telefone_exige_o_numero PASSED [ 43%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_autorizar_telefone_guarda_o_numero PASSED [ 44%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_retirar_autorizacao_do_telefone_apaga_o_numero PASSED [ 44%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_retirar_autorizacao_nao_bloqueia_o_acesso PASSED [ 44%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_cada_mudanca_fica_no_historico_e_na_auditoria PASSED [ 45%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_historico_nao_pode_ser_alterado PASSED [ 45%]
usuarios/testes_consentimento.py::TestConsentimentoNoPerfil::test_exportacao_inclui_o_historico PASSED [ 46%]
usuarios/testes_consentimento.py::TestEfeitoDoConsentimento::test_sem_consentimento_o_aviso_de_emprestimo_nao_e_enviado PASSED [ 46%]
usuarios/testes_consentimento.py::TestEfeitoDoConsentimento::test_com_consentimento_o_aviso_de_emprestimo_e_enviado PASSED [ 47%]
usuarios/testes_consentimento.py::TestEfeitoDoConsentimento::test_aviso_de_seguranca_nao_depende_de_consentimento PASSED [ 47%]
usuarios/testes_consentimento.py::TestMigracaoDosUsuariosExistentes::test_mantem_o_que_cada_usuario_ja_recebia PASSED [ 47%]
usuarios/testes_lgpd.py::TestMinimizacao::test_cadastro_funciona_sem_telefone PASSED [ 48%]
usuarios/testes_lgpd.py::TestMinimizacao::test_formulario_de_cadastro_nao_exige_telefone PASSED [ 48%]
usuarios/testes_lgpd.py::TestMinimizacao::test_cadastro_descarta_dados_nao_previstos PASSED [ 49%]
usuarios/testes_lgpd.py::TestMinimizacao::test_login_nao_grava_copia_no_axes PASSED [ 49%]
usuarios/testes_lgpd.py::TestMinimizacao::test_tentativa_errada_continua_registrada_para_o_bloqueio PASSED [ 50%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_elimina_todos_os_vinculos_do_titular PASSED [ 50%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_mantem_o_historico_de_consentimento_como_prova PASSED [ 50%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_encerra_as_sessoes_em_outros_navegadores PASSED [ 51%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_bloqueia_com_emprestimo_em_aberto[SOLICITADO] PASSED [ 51%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_bloqueia_com_emprestimo_em_aberto[APROVADO] PASSED [ 52%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_bloqueia_com_emprestimo_em_aberto[RETIRADO] PASSED [ 52%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_bloqueia_com_emprestimo_em_aberto[ATRASADO] PASSED [ 52%]
usuarios/testes_retencao.py::TestEncerramentoDaConta::test_encerramento_fica_na_auditoria PASSED [ 53%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_token_de_recuperacao_some_7_dias_depois_de_expirar PASSED [ 53%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_notificacao_some_depois_de_90_dias PASSED [ 54%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_tentativa_de_login_some_depois_de_30_dias PASSED [ 54%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_sessoes_expiradas_sao_apagadas PASSED [ 55%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_conta_suspensa_e_anonimizada_depois_de_12_meses PASSED [ 55%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_conta_suspensa_com_equipamento_nao_e_anonimizada PASSED [ 55%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_conta_desativada_pelo_admin_nao_entra_na_rotina PASSED [ 56%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_emprestimo_devolvido_some_depois_de_5_anos PASSED [ 56%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_emprestimo_em_aberto_nunca_e_apagado PASSED [ 57%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_auditoria_com_mais_de_5_anos_e_eliminada PASSED [ 57%]
usuarios/testes_retencao.py::TestRotinaDeRetencao::test_comando_agendavel_executa_a_rotina PASSED [ 58%]
usuarios/testes_retencao.py::TestTriggerDaAuditoriaComRetencao::test_registro_dentro_do_prazo_continua_sem_poder_ser_apagado PASSED [ 58%]
usuarios/testes_retencao.py::TestTriggerDaAuditoriaComRetencao::test_nao_da_para_envelhecer_um_registro_para_apaga_lo PASSED [ 58%]
usuarios/testes_retencao.py::TestTriggerDaAuditoriaComRetencao::test_registro_antigo_continua_sem_poder_ser_alterado PASSED [ 59%]
usuarios/tests.py::TestNenhumaRotaContornaO2FA::test_nenhuma_rota_expoe_emissao_direta_de_jwt PASSED [ 59%]
usuarios/tests.py::TestNenhumaRotaContornaO2FA::test_renovacao_nao_emite_jwt_sem_refresh_valido PASSED [ 60%]
usuarios/tests.py::TestNenhumaRotaContornaO2FA::test_senha_correta_sozinha_nao_gera_jwt_nem_sessao PASSED [ 60%]
usuarios/tests.py::TestNenhumaRotaContornaO2FA::test_login_web_com_2fa_nao_autentica_antes_do_codigo PASSED [ 61%]
usuarios/tests.py::TestCodigosTOTP::test_codigo_invalido_e_recusado PASSED [ 61%]
usuarios/tests.py::TestCodigosTOTP::test_replay_o_mesmo_codigo_nao_vale_duas_vezes PASSED [ 61%]
usuarios/tests.py::TestCodigosTOTP::test_apos_erro_o_dispositivo_fica_bloqueado_por_um_tempo PASSED [ 62%]
usuarios/tests.py::TestCodigosTOTP::test_tentativas_repetidas_sao_limitadas_por_ip PASSED [ 62%]
usuarios/tests.py::TestCodigosTOTP::test_falhas_de_2fa_ficam_registradas_na_auditoria PASSED [ 63%]
usuarios/tests.py::TestExpiracaoDoEstadoPre2FA::test_estado_pre_2fa_web_expira PASSED [ 63%]
usuarios/tests.py::TestExpiracaoDoEstadoPre2FA::test_estado_pre_2fa_web_dentro_do_prazo_funciona PASSED [ 64%]
usuarios/tests.py::TestExpiracaoDoEstadoPre2FA::test_token_pre_2fa_da_api_expira PASSED [ 64%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_token_expirado_e_recusado PASSED [ 64%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_token_nao_pode_ser_reutilizado PASSED [ 65%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_politica_de_senha_e_aplicada_na_redefinicao[12345678] PASSED [ 65%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_politica_de_senha_e_aplicada_na_redefinicao[password123] PASSED [ 66%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_politica_de_senha_e_aplicada_na_redefinicao[curta] PASSED [ 66%]
usuarios/tests.py::TestRecuperacaoDeSenhaExecutada::test_solicitacoes_de_recuperacao_sao_limitadas PASSED [ 67%]
usuarios/tests.py::TestTriggerAplicadoNoBanco::test_banco_em_uso_e_postgresql PASSED [ 67%]
usuarios/tests.py::TestTriggerAplicadoNoBanco::test_trigger_existe_na_tabela_de_auditoria PASSED [ 67%]
usuarios/tests.py::TestTriggerAplicadoNoBanco::test_update_e_delete_diretos_continuam_bloqueados PASSED [ 68%]
usuarios/tests_criptografia.py::TestDadosCifradosNoBanco::test_telefone_fica_cifrado_no_banco PASSED [ 68%]
usuarios/tests_criptografia.py::TestDadosCifradosNoBanco::test_chave_do_2fa_fica_cifrada_no_banco PASSED [ 69%]
usuarios/tests_criptografia.py::TestDadosCifradosNoBanco::test_2fa_continua_funcionando_com_a_chave_cifrada PASSED [ 69%]
usuarios/tests_criptografia.py::TestDadosCifradosNoBanco::test_mesmo_valor_gera_cifras_diferentes PASSED [ 70%]
usuarios/tests_criptografia.py::TestDadosCifradosNoBanco::test_migracao_tira_as_chaves_do_texto_puro PASSED [ 70%]
usuarios/tests_criptografia.py::TestRotacaoDeChave::test_rotacao_completa PASSED [ 70%]
usuarios/tests_criptografia.py::TestRotacaoDeChave::test_sem_a_chave_certa_o_dado_nao_e_lido PASSED [ 71%]
usuarios/tests_seguranca.py::TestHashDeSenha::test_senha_nunca_fica_em_texto_puro_no_banco PASSED [ 71%]
usuarios/tests_seguranca.py::TestHashDeSenha::test_custo_do_hash_e_600000_iteracoes PASSED [ 72%]
usuarios/tests_seguranca.py::TestHashDeSenha::test_dois_usuarios_com_mesma_senha_geram_hashes_diferentes PASSED [ 72%]
usuarios/tests_seguranca.py::TestProtecaoForcaBruta::test_bloqueia_apos_cinco_tentativas_erradas PASSED [ 73%]
usuarios/tests_seguranca.py::TestRecuperacaoDeSenha::test_token_e_de_uso_unico PASSED [ 73%]
usuarios/tests_seguranca.py::TestRecuperacaoDeSenha::test_token_nao_e_previsivel PASSED [ 73%]
usuarios/tests_seguranca.py::TestDoisFatores::test_usuario_com_2fa_nao_autentica_so_com_senha PASSED [ 74%]
usuarios/tests_seguranca.py::TestDoisFatores::test_codigo_2fa_incorreto_nao_libera_acesso PASSED [ 74%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_primeira_etapa_nao_emite_jwt_nem_expoe_id PASSED [ 75%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_fluxo_completo_com_codigo_correto_emite_jwt PASSED [ 75%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_codigo_errado_nao_emite_jwt PASSED [ 76%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_segunda_etapa_sem_passar_pela_senha_e_rejeitada PASSED [ 76%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_token_forjado_ou_adulterado_e_rejeitado PASSED [ 76%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_token_expirado_e_rejeitado PASSED [ 77%]
usuarios/tests_seguranca.py::TestLoginSpaDoisFatores::test_usuario_sem_2fa_recebe_jwt_direto PASSED [ 77%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_cadastro_com_papel_admin_e_recusado PASSED [ 78%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_cadastro_com_papel_inexistente_e_recusado PASSED [ 78%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_cadastro_com_papel_aluno_e_aceito PASSED [ 79%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_cadastro_sem_papel_vira_aluno_por_padrao PASSED [ 79%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_aluno_nao_consegue_cadastrar_equipamento PASSED [ 79%]
usuarios/tests_seguranca.py::TestCadastroNaoPermitePapelPrivilegiado::test_admin_consegue_cadastrar_equipamento PASSED [ 80%]
usuarios/tests_seguranca.py::TestPapelManda::test_admin_nasce_com_acesso_administrativo PASSED [ 80%]
usuarios/tests_seguranca.py::TestPapelManda::test_aluno_nasce_sem_acesso_administrativo PASSED [ 81%]
usuarios/tests_seguranca.py::TestPapelManda::test_forcar_is_staff_em_aluno_e_revertido PASSED [ 81%]
usuarios/tests_seguranca.py::TestPapelManda::test_promover_a_admin_concede_acesso PASSED [ 82%]
usuarios/tests_seguranca.py::TestPapelManda::test_rebaixar_admin_remove_acesso PASSED [ 82%]
usuarios/tests_seguranca.py::TestPapelManda::test_save_parcial_do_papel_tambem_sincroniza PASSED [ 82%]
usuarios/tests_seguranca.py::TestPapelManda::test_createsuperuser_cria_conta_com_papel_admin PASSED [ 83%]
usuarios/tests_seguranca.py::TestPapelManda::test_admin_acessa_o_django_admin_e_aluno_nao PASSED [ 83%]
usuarios/tests_seguranca.py::TestPapelManda::test_notificar_admins_alcanca_so_os_administradores PASSED [ 84%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_revogar_remove_o_dispositivo PASSED [ 84%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_depois_de_revogar_o_login_volta_a_entrar_so_com_senha PASSED [ 85%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_visitante_sem_login_e_mandado_para_o_login PASSED [ 85%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_get_nao_revoga PASSED [ 85%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_revogar_grava_auditoria PASSED [ 86%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_revogar_avisa_o_dono_da_conta_por_email PASSED [ 86%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_usuario_sem_2fa_nao_gera_auditoria_nem_email PASSED [ 87%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_revogar_so_afeta_o_proprio_usuario PASSED [ 87%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_ativacao_pendente_e_limpa_sem_avisar PASSED [ 88%]
usuarios/tests_seguranca.py::TestRevogacaoDoisFatores::test_perfil_mostra_a_confirmacao_depois_de_desativar PASSED [ 88%]
usuarios/tests_seguranca.py::TestPaginaConfigurar2FA::test_com_2fa_ligado_mostra_o_botao_e_nao_mostra_o_qr_code PASSED [ 88%]
usuarios/tests_seguranca.py::TestPaginaConfigurar2FA::test_com_2fa_ligado_nao_cria_dispositivo_novo PASSED [ 89%]
usuarios/tests_seguranca.py::TestPaginaConfigurar2FA::test_com_2fa_desligado_mostra_o_qr_code_e_nao_o_botao PASSED [ 89%]
usuarios/tests_seguranca.py::TestLoginObrigatorio::test_visitante_vai_para_o_login[perfil-get] PASSED [ 90%]
usuarios/tests_seguranca.py::TestLoginObrigatorio::test_visitante_vai_para_o_login[configurar_2fa-get] PASSED [ 90%]
usuarios/tests_seguranca.py::TestLoginObrigatorio::test_visitante_vai_para_o_login[exportar_dados-get] PASSED [ 91%]
usuarios/tests_seguranca.py::TestLoginObrigatorio::test_visitante_vai_para_o_login[revogar_2fa-post] PASSED [ 91%]
usuarios/tests_seguranca.py::TestPerfil::test_mostra_todos_os_dados_do_usuario PASSED [ 91%]
usuarios/tests_seguranca.py::TestPerfil::test_campos_vazios_mostram_aviso PASSED [ 92%]
usuarios/tests_seguranca.py::TestPerfil::test_telefone_fica_criptografado_no_banco_mas_aparece_na_tela PASSED [ 92%]
usuarios/tests_seguranca.py::TestExportacaoDeDados::test_exporta_todos_os_dados_do_perfil PASSED [ 93%]
usuarios/tests_seguranca.py::TestExportacaoDeDados::test_baixa_como_arquivo PASSED [ 93%]
usuarios/tests_seguranca.py::TestExportacaoDeDados::test_so_exporta_os_dados_do_proprio_usuario PASSED [ 94%]
usuarios/tests_seguranca.py::TestExportacaoDeDados::test_campos_vazios_saem_com_texto_padrao PASSED [ 94%]
usuarios/tests_seguranca.py::TestExportacaoDeDados::test_arquivo_nao_vaza_a_senha PASSED [ 94%]
usuarios/testes_consentimento.py::TestFinalidadesOpcionais::test_finalidades_opcionais_estao_no_mapeamento_com_base_no_consentimento PASSED [ 95%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[admin.LogEntry] PASSED [ 95%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[auditoria.RegistroAuditoria] PASSED [ 96%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[axes.AccessAttempt] PASSED [ 96%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[emprestimos.Emprestimo] PASSED [ 97%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[notificacoes.Notificacao] PASSED [ 97%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[usuarios.ConsentimentoFinalidade] PASSED [ 97%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[usuarios.DispositivoTOTP] PASSED [ 98%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[usuarios.TokenRecuperacaoSenha] PASSED [ 98%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_campo_esta_mapeado[usuarios.Usuario] PASSED [ 99%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_todo_modelo_ligado_a_um_usuario_esta_mapeado PASSED [ 99%]
usuarios/testes_lgpd.py::TestMapeamentoDosDados::test_toda_finalidade_usada_existe_e_tem_base_legal PASSED [100%]

- generated xml file: /home/runner/work/EmprestaCampus/EmprestaCampus/backend/junit.xml -
============================= 234 passed in 13.36s =============================
```

**Resultado:** 234 de 234 casos aprovados, contra PostgreSQL 16.16, no commit `cdc2dc9`.

## 7. Rastreabilidade com o checklist

| Item do checklist | Onde está atendido |
|---|---|
| 1.1 a 1.4 — Hash, custo, salt, armazenamento | `TestHashDeSenha`, seção 3.1.1 |
| 1.5, 1.6 — 2FA implementado e validado após autenticação primária | `TestDoisFatores`, `TestLoginSpaDoisFatores`, `TestRevogacaoDoisFatores`, `TestPaginaConfigurar2FA`, seções 3.1.4, 3.1.7 e 3.1.8; nenhuma rota emite JWT sem 2FA, replay, tentativas repetidas e expiração do pré-2FA em `TestNenhumaRotaContornaO2FA`, `TestCodigosTOTP` e `TestExpiracaoDoEstadoPre2FA`, seções 3.6.1 a 3.6.3 |
| 1.11 — Proteção contra força bruta | `TestProtecaoForcaBruta`, seção 3.1.2; limites de requisição em `test_tentativas_repetidas_sao_limitadas_por_ip` e `test_solicitacoes_de_recuperacao_sao_limitadas`, seções 3.6.2 e 3.6.4 |
| 2.1 — Recuperação de senha implementada | `TestRecuperacaoDeSenhaPorEmail`, seção 3.3.7 |
| 2.2, 2.3, 2.4 — Token seguro, com expiração, uso único | `TestRecuperacaoDeSenha`, seção 3.1.3; expiração, reutilização e política de senha em `TestRecuperacaoDeSenhaExecutada`, seção 3.6.4 |
| 2.6 — Resposta igual para e-mail inexistente | `test_email_inexistente_responde_igual_e_nao_envia`, seção 3.3.7 |
| 3.4 — Dados sensíveis cifrados em repouso | `test_telefone_fica_criptografado_no_banco_mas_aparece_na_tela`, seção 3.1.10; telefone e chave do 2FA cifrados e rotação de chave em `tests_criptografia.py`, seção 3.7 |
| 4.2, 4.3 — Associação a finalidades e minimização | `testes_lgpd.py`, seção 3.8 |
| 4.5 — Consentimento associado à finalidade | `testes_consentimento.py`, seção 3.9 |
| 4.8 — Consulta aos dados do titular | `TestPerfil`, seção 3.1.10 |
| 4.9 — Exportação dos dados | `TestExportacaoDeDados`, seção 3.1.11; histórico de consentimento na exportação, `test_exportacao_inclui_o_historico`, seção 3.9.3 |
| 4.10 — Eliminação, anonimização e retenção | `testes_retencao.py`, seção 3.10 |
| 5.1, 5.2 — Registro de eventos na auditoria | `test_revogar_grava_auditoria` (3.1.7), testes de auditoria do inventário (3.4.2) e dos empréstimos (3.5.1 e 3.5.3) |
| 5.3 — Proteção contra alteração dos logs | `auditoria/tests.py`, seção 3.2; trigger instalado e ativo no PostgreSQL em uso, `TestTriggerAplicadoNoBanco`, seção 3.6.5; imutabilidade mantida com a retenção de 5 anos, `TestTriggerDaAuditoriaComRetencao`, seção 3.10.3 |
| 6.7, 6.8 — Ameaças e contramedidas (controle de acesso) | `TestCadastroNaoPermitePapelPrivilegiado`, `TestPapelManda`, `TestLoginObrigatorio`, `TestPermissoesDaAPI`, `TestSolicitacaoPelaAPI`, seções 3.1.5, 3.1.6, 3.1.9, 3.4.1 e 3.5.2 |
| 6.9 — Testes de segurança realizados | Este documento inteiro |
| 6.10 — Resultados dos testes documentados | Seção 6 (execução automática no CI, com ambiente, versões e saída real) e artefato `resultado-testes` de cada execução do workflow "Testes automatizados" |