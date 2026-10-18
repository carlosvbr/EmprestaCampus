# Limitações Conhecidas — EmprestaCampus

**Requisito:** 6. Documentação Técnico-Científica
**Escopo deste documento:** riscos residuais aceitos (complemento dos itens 6.7 e 6.8) e melhorias previstas

---

## 1. Objetivo

Este documento reúne as limitações conhecidas do EmprestaCampus na versão entregue. Cada limitação foi identificada durante o desenvolvimento ou a revisão técnica e mantida de forma consciente, por estar fora do escopo acadêmico do projeto ou por exigir mudanças maiores do que o prazo permitia.

Para cada item são descritos o risco que permanece, a mitigação que o sistema já aplica e a melhoria prevista. As linhas com risco residual **Médio** da análise de risco (`Ativos e Analise de Risco.md`, seção 4) estão relacionadas na seção 10.

## 2. Autenticação e credenciais

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| Os validadores de senha do Django estão configurados em `AUTH_PASSWORD_VALIDATORS`, mas não são chamados no cadastro nem na redefinição de senha | Senhas fracas, como `12345678`, são aceitas; apenas o mínimo de 8 caracteres é exigido | Bloqueio após 5 tentativas erradas; 2FA disponível; hash com 600.000 iterações | Chamar `validate_password` no `RegistroSerializer` e na `RedefinirSenhaView` |
| O 2FA é opcional | Contas sem 2FA dependem apenas da senha | O 2FA pode ser ativado por qualquer usuário em "Meu Perfil" | Tornar o 2FA obrigatório para o papel Administrador |
| O 2FA não oferece códigos de recuperação | O usuário que perde o celular com o aplicativo autenticador não consegue entrar | O administrador pode remover o dispositivo TOTP do usuário pelo Django Admin; o usuário volta a entrar só com a senha e reativa o 2FA | Códigos de uso único do plugin `otp_static` do `django-otp` |
| O bloqueio contra força bruta é pela combinação de IP e usuário | Um ataque distribuído em muitos IPs contra a mesma conta não é bloqueado pela combinação | 2FA; registro de cada falha na auditoria, que permite identificar o padrão | Limite adicional por usuário, independente do IP |
| Não há limite de requisições no cadastro e na solicitação de recuperação de senha | Criação de contas em massa e envio de muitos e-mails de recuperação | A recuperação responde igual para e-mails existentes ou não e registra cada pedido na auditoria | Throttling do Django REST Framework nesses endpoints |
| A API JWT não tem logout nem lista de bloqueio de tokens | Um token de `refresh` roubado continua válido por até 7 dias | A interface atual usa sessão, não JWT; o token de acesso expira em 1 hora | App `token_blacklist` do SimpleJWT, rotação do `refresh` e rota de logout |
| O hash de senha usa PBKDF2 em vez de Argon2 | Menor resistência a ataques com GPU | 600.000 iterações, conforme a recomendação da OWASP | Migrar para Argon2id, mantendo o PBKDF2 para as senhas antigas |
| Se a conta do usuário for excluída durante a validação do 2FA no login web, a tela de validação gera erro em vez de voltar ao login | Erro 500 em um caso raro | — | Tratar usuário inexistente redirecionando para o login |

## 3. Recuperação de senha

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| O token de recuperação é armazenado em texto puro no banco | Quem conseguir ler a tabela usa um token pendente para trocar a senha de outra pessoa | Validade de 1 hora; uso único; invalidação dos demais tokens após a redefinição; banco acessível só pela rede interna do Docker | Guardar apenas o SHA-256 do token |
| O e-mail não é obrigatório nem único na API, e a busca diferencia maiúsculas de minúsculas | Com e-mails repetidos, a recuperação pode escolher a conta errada; `Fulano@...` e `fulano@...` são tratados como diferentes | O formulário de cadastro exige o e-mail | Tornar o e-mail obrigatório e único, sem diferenciar maiúsculas, com limpeza das duplicatas existentes |
| O e-mail é enviado de forma síncrona | O tempo de resposta é maior quando o e-mail existe, o que pode revelar sua existência a quem mede o tempo; um servidor de e-mail lento atrasa a resposta | A mensagem exibida é sempre a mesma | Envio em segundo plano (fila de tarefas) |

## 4. Criptografia e dados em repouso

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| Apenas o telefone é cifrado; nome, e-mail, matrícula e o segredo TOTP ficam em claro no banco | Exposição desses dados em caso de vazamento do banco | Banco acessível apenas pela rede interna do Docker; porta publicada somente em `127.0.0.1`; senha do banco no `.env` | Cifrar o segredo TOTP e avaliar a cifragem dos demais campos |
| Não há rotação da `ENCRYPTION_KEY` | Uma chave vazada compromete todos os telefones cifrados | Chave separada da `SECRET_KEY`, fora do código e da imagem Docker | `MultiFernet` para cifrar com a chave nova e ler com as antigas |
| Não há captura do handshake TLS nas evidências | A evidência de tráfego cifrado se baseia na configuração e em prints do navegador | Configuração do Nginx documentada em `criptografia.md` | Registrar a saída de `openssl s_client` e de `curl -I` |

## 5. Configuração e implantação

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| Cookies `Secure`, HSTS e redirecionamento HTTPS do Django só são ativados com `DEBUG=False`, e o `.env.example` traz `DEBUG=True` | Em um ambiente configurado a partir do exemplo sem ajuste, essas proteções ficam desligadas | O Nginx sempre redireciona HTTP para HTTPS; `DEBUG` é lido do `.env` | `.env.example` com `DEBUG=False` e um arquivo separado para desenvolvimento |
| O container do backend usa o servidor de desenvolvimento do Django (`runserver`), sem `collectstatic` | Desempenho e robustez inadequados para produção | Uso restrito a ambiente local e demonstração | Gunicorn e WhiteNoise, com `STATIC_ROOT` configurado |
| A aplicação conecta ao banco com o usuário `postgres`, que é superusuário | Uma falha na aplicação teria privilégios totais no banco, inclusive para desativar a trigger da auditoria | Banco acessível apenas pela rede interna do Docker | Usuário de banco próprio, sem privilégios de superusuário |
| O IP real vem do cabeçalho `X-Real-IP`, confiável apenas com o Nginx na frente | Se o Django for exposto diretamente, o cliente pode informar um IP falso | No Docker, o backend só é acessível pelo Nginx (`expose`, e não `ports`) | Aceitar o cabeçalho apenas de IPs de proxies conhecidos |
| As versões das dependências não são fixas no `requirements.txt` | Uma instalação futura pode receber versões diferentes das testadas | Suíte de 149 testes para detectar quebras | Fixar as versões (`==`) |
| O `LANGUAGE_CODE` está em `en-us` | Mensagens geradas pelo próprio Django aparecem em inglês | As mensagens do sistema foram escritas em português | Alterar para `pt-br` |
| Três templates carregam o Tailwind por CDN | Dependência de um serviço externo para o estilo das páginas | — | Gerar o CSS localmente |

## 6. Auditoria

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| A trigger de imutabilidade não impede um `TRUNCATE` e pode ser desativada por um superusuário do banco | Um administrador do banco consegue apagar ou alterar os registros | Imutabilidade em três camadas contra a aplicação e contra SQL de usuários comuns | Usuário de banco sem privilégios e hash encadeado com HMAC entre os registros, que permite detectar qualquer alteração |
| As ações do administrador sobre empréstimos (aprovar, rejeitar, devolver, decidir prorrogação) são registradas sem IP | Rastreabilidade parcial dessas ações | O registro identifica o administrador e o empréstimo | Gravar o IP também nas ações do Django Admin |
| O formulário de edição de empréstimos no Django Admin permite alterar o status e a data prevista sem registro na auditoria | Alterações administrativas fora das ações previstas não ficam registradas | As ações próprias (aprovar, rejeitar, devolver) são auditadas | Tornar esses campos somente leitura ou auditar no `save_model` |
| As categorias do inventário não geram registro de auditoria, apenas os equipamentos | Criação e exclusão de categorias não ficam rastreadas | Exclusão de categoria em uso é bloqueada | Auditar também as categorias |
| Registros anteriores à remoção do texto digitado podem conter o login ou o e-mail informados | Dados pessoais em registros que não podem ser apagados | Os novos registros não guardam o texto digitado | — (a imutabilidade impede a correção dos registros antigos) |

## 7. LGPD e privacidade

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| O consentimento é único para toda a política, sem aceite por finalidade | O titular não escolhe finalidades separadamente | Política com a finalidade de cada dado | Consentimento por finalidade |
| O sistema guarda apenas o último aceite, sem histórico de aceites e revogações | O histórico completo depende dos registros de auditoria | A data e a versão do último aceite são preservadas na revogação; as revogações ficam na auditoria | Tabela de histórico de consentimento |
| A versão da política (`v1.0`) aparece escrita também nos templates | Uma nova versão exige atualizar a constante e os templates juntos | Constante única `VERSAO_POLITICA_PRIVACIDADE` no código | Exibir nos templates o valor da constante |
| O titular não edita os próprios dados | A correção (Art. 18, III) depende do encarregado | Canal do encarregado descrito na política | Edição de nome e telefone pelo titular; troca de e-mail com confirmação da senha |
| Durante a suspensão por revogação, os dados permanecem intactos, e a conta suspensa não pode ser encerrada diretamente | O titular precisa reativar a conta para depois encerrá-la | O encerramento está disponível assim que a conta é reativada | Permitir o encerramento a partir da tela de reativação |
| Se o administrador desativar uma conta que já estava suspensa por revogação, o titular ainda consegue reativá-la | A desativação administrativa pode ser desfeita pelo titular nesse caso específico | Contas desativadas pelo administrador com consentimento ativo não podem ser reativadas | Campo próprio para a desativação administrativa |

## 8. Controle de acesso e administração

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| O model `Usuario` não está registrado no Django Admin | Promover administradores ou desativar contas exige o shell do Django ou o banco | O papel ADMIN do primeiro usuário é atribuído pelo `createsuperuser` | Registrar `Usuario` com um `UserAdmin` próprio |
| Atualizações em massa (`.update()`) não passam pelo `save()` que sincroniza o papel com `is_staff` e `is_superuser` | Uma alteração em massa feita por código pode deixar privilégios dessincronizados | Nenhuma parte do sistema altera papéis em massa | Sincronizar também por sinal ou restrição no banco |

## 9. Notificações, testes e evidências

| Limitação | Risco | Mitigação atual | Melhoria futura |
|---|---|---|---|
| O histórico de notificações registra o tipo "e-mail" mesmo quando o envio falha | O histórico pode indicar um envio que não aconteceu | A falha é registrada no log da aplicação | Registrar a situação do envio |
| O envio usa um servidor SMTP externo sujeito a limite diário de mensagens | Notificações podem deixar de ser entregues em picos de uso | Falhas de envio não interrompem as operações | Serviço de e-mail transacional |
| Não há testes de regressão específicos para a reativação de conta, a anonimização completa, o bloqueio combinado de IP e usuário, o IP real na auditoria, a expiração da sessão e o logout | Uma alteração futura pode reintroduzir esses problemas sem que a suíte detecte | Correções verificadas manualmente; suíte de 149 testes cobre os demais mecanismos | Testes automatizados para cada um desses cenários |

## 10. Relação com a análise de risco

| Linha da análise de risco (seção 4) | Motivo do risco residual Médio | Seção deste documento |
|---|---|---|
| 7 — Telefone cifrado com Fernet | Demais dados pessoais e segredo TOTP em claro; sem rotação de chave | 4 |
| 10 — Segundo fator de autenticação | 2FA opcional, sem códigos de recuperação; senhas fracas aceitas | 2 |
| 11 — Força bruta | Ataque distribuído não bloqueado pela combinação de IP e usuário; sem limite no cadastro e na recuperação | 2 |
| 13 — Token de recuperação de senha | Token em texto puro no banco; e-mail não único | 3 |
| 14 — Cookies e HTTPS | Proteções dependem de `DEBUG=False`, e o exemplo traz `DEBUG=True` | 5 |
| 16 — Imutabilidade da auditoria | `TRUNCATE` e superusuário do banco; ações do Admin sem IP | 6 |
