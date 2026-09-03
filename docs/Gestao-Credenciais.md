# Gestao-Credenciais


Este documento detalha a implementação das funcionalidades de autenticação, gerenciamento de credenciais e segurança do sistema **EmprestaCampus**. A estrutura descreve as escolhas arquiteturais e a relação direta com os arquivos e funções desenvolvidos no código-fonte.

---

### 1. Cadastro de Usuários (API REST)
* O cadastro inicial de novos usuários é processado pela classe `RegistroView`, localizada em `usuarios/views.py`.
* A view herda de `generics.CreateAPIView` e possui permissão pública (`permissions.AllowAny`), permitindo o registro de contas de forma externa ou via front-end.
* A senha enviada em texto plano na requisição é interceptada pelo `RegistroSerializer`, que delega a criptografia ao método nativo `set_password()`.
* **Segurança:** O Django aplica automaticamente o algoritmo de hash **PBKDF2** com salt, garantindo que credenciais em texto puro nunca sejam persistidas no banco de dados PostgreSQL.

### 2. Autenticação Web (Stateful)
* O fluxo de login visual é implementado pela função `login_view()` em `usuarios/views.py`, voltada para a interface HTML da disciplina.
* A submissão é restrita estritamente ao método HTTP `POST`, blindando o payload contra vazamento de parâmetros sensíveis na URL.
* O sistema utiliza a função `authenticate()` do Django para validar o usuário e a senha informados. Essa camada abstrai a verificação de hash e previne ataques de **SQL Injection** nas consultas ao banco de dados.
* Quando as credenciais são validadas com sucesso, a função `login()` acopla o usuário à sessão ativa, gerando um cookie HTTP-only seguro. Caso contrário, o sistema emite uma mensagem genérica de erro via `messages.error` para mitigar vulnerabilidades de enumeração de contas.

### 3. Gerenciamento de Sessão e Controle de Acesso
* O gerenciamento do estado de login da interface web utiliza sessões nativas gerenciadas pelo SGBD e controladas por cookies protegidos.
* As rotas protegidas validam o estado do usuário, redirecionando fluxos não autorizados para o endpoint de login.
* O redirecionamento pós-autenticação aponta para a `home_view()`, servindo como evidência visual do sucesso no ciclo de login (Caminho Feliz).

### 4. Isolamento de Rotas e Separação de Conceitos (SoC)
* O roteamento do módulo (`usuarios/urls.py`) aplica o princípio de separação arquitetural ao isolar dois paradigmas distintos:
  * **APIs Stateless:** Endpoints dedicados a clientes modernos utilizando o padrão SimpleJWT (`TokenObtainPairView` e `TokenRefreshView`), além da rota de registro.
  * **APIs Stateful:** Endpoints visuais voltados para o template HTML de login (`/entrar/`) e a página de destino (`/home/`).
* A nomenclatura das rotas foi isolada de forma explícita (separando `login_api` e `login_web`) para evitar colisões no roteamento reverso do framework.

### 5. Estrutura de Arquivos Envolvidos
* **`usuarios/views.py`**: Centraliza a lógica de controle do endpoint de registro (`RegistroView`), da validação visual de sessão (`login_view`) e da rota de validação pós-login (`home_view`).
* **`usuarios/urls.py`**: Gerencia o mapeamento de URLs, dividindo os endpoints de API REST (JWT) das rotas baseadas em sessão HTML.
* **`usuarios/serializers.py`**: Gerencia a serialização dos dados de entrada do usuário e aplica as regras de transformação e hash de senha.
* **`templates/usuarios/login.html`**: Interface visual de acesso que implementa proteções nativas contra falsificação de solicitações entre sites por meio da tag `{% csrf_token %}`.

### 6. Considerações Finais
As funcionalidades descritas correspondem estritamente à implementação técnica entregue no repositório. O funcionamento do sistema é comprovado através da validação dos fluxos de falha e sucesso diretamente pela interface web e pelos testes de endpoints da API.