# Insulinet Backend

API REST do **Insulinet**, uma aplicação para controle de estoque de insulina, registro de doses e estimativa de autonomia com base no histórico de consumo.

## Tecnologias

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT
- Argon2
- Resend

## Funcionalidades

- Cadastro e autenticação de usuários
- Recuperação e redefinição de senha
- Cadastro e edição de insulinas
- Controle de entradas e ajustes de estoque
- Registro individual e em lote de doses
- Histórico de movimentações
- Cálculo do estoque atual
- Estimativa de consumo médio
- Projeção de dias restantes
- Isolamento dos dados por usuário

## Estrutura

```text
app/
├── api/
│   └── routes/
│       ├── auth.py
│       ├── doses.py
│       ├── health.py
│       ├── insulins.py
│       ├── stock.py
│       └── users.py
├── core/
│   ├── config.py
│   └── security.py
├── services/
│   ├── dose_service.py
│   ├── email_service.py
│   ├── insulin_service.py
│   ├── projection_service.py
│   └── stock_service.py
├── database.py
├── main.py
├── models.py
└── schemas.py
```

A aplicação separa as responsabilidades entre rotas HTTP, regras de negócio, segurança, configuração e persistência.

## Configuração local

Clone o repositório:

```bash
git clone https://github.com/fernanndp/insulinet-backend.git
cd insulinet-backend
```

Crie um ambiente virtual:

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` a partir do `.env.example`.

Exemplo:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/insulinet
APP_TIMEZONE=America/Fortaleza
JWT_SECRET_KEY=troque-por-uma-chave-secreta-forte
ACCESS_TOKEN_EXPIRE_MINUTES=1440
PASSWORD_RESET_EXPIRE_MINUTES=30
RESEND_API_KEY=
EMAIL_FROM=Insulinet <onboarding@resend.dev>
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Nunca versione o arquivo `.env`.

## Banco de dados

O projeto utiliza PostgreSQL e Alembic para controle de migrations.

Verifique a migration atual:

```bash
alembic current
```

Verifique a migration mais recente disponível:

```bash
alembic heads
```

Para aplicar migrations pendentes:

```bash
alembic upgrade head
```

## Executando

```bash
uvicorn app.main:app --reload
```

API local:

```text
http://127.0.0.1:8000
```

Documentação interativa:

```text
http://127.0.0.1:8000/docs
```

## Principais endpoints

### Autenticação

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/forgot-password
POST /api/auth/reset-password
```

### Usuário

```text
GET /api/users/me
```

### Insulinas

```text
POST  /api/insulins
GET   /api/insulins
PATCH /api/insulins/{insulin_id}
GET   /api/insulins/{insulin_id}/history
GET   /api/insulins/{insulin_id}/summary
```

### Estoque

```text
POST  /api/insulins/{insulin_id}/stock
GET   /api/insulins/{insulin_id}/stock
POST  /api/insulins/{insulin_id}/adjustments
PATCH /api/insulins/{insulin_id}/stock/{movement_id}
```

### Doses

```text
POST  /api/insulins/{insulin_id}/doses
PATCH /api/insulins/{insulin_id}/doses/{dose_id}
POST  /api/insulins/{insulin_id}/dose-batches
```

## Segurança

O backend utiliza:

- Hash de senhas com Argon2
- Tokens JWT para autenticação
- Associação dos registros ao usuário autenticado
- Variáveis sensíveis fora do controle de versão
- Configuração explícita de CORS

## Roadmap

Entre as funcionalidades planejadas para evolução do Insulinet estão:

- Alertas de estoque baixo com base na autonomia estimada
- Definição de um nível mínimo de segurança para reposição
- Previsão da data recomendada para aquisição de uma nova unidade de insulina
- Controle do processo de reposição diretamente pela plataforma
- Busca de opções de compra em farmácias
- Redirecionamento do usuário para farmácias ou páginas de compra compatíveis com a insulina cadastrada
- Possibilidade futura de integração com serviços de disponibilidade e preços de farmácias

A proposta é evoluir o Insulinet de um sistema de controle de estoque para uma ferramenta capaz de antecipar a necessidade de reposição e facilitar o acesso do usuário ao medicamento.

## Frontend

O frontend do projeto está em:

https://github.com/fernanndp/insulinet-frontend

## Status

Projeto em desenvolvimento.
