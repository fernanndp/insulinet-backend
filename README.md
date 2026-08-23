# Insulinet Backend

API REST do **Insulinet**, uma aplicação para controle de estoque de insulina, registro de doses e estimativa de autonomia com base no histórico de consumo.

## Produção

- Frontend: https://insulinet-frontend-production.up.railway.app
- API: https://insulinet-backend-production.up.railway.app
- Documentação Swagger: https://insulinet-backend-production.up.railway.app/docs

## Tecnologias

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT
- Argon2
- Resend
- Railway

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

```bash
alembic current
alembic heads
alembic upgrade head
```

## Executando localmente

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

## Deploy

O backend está hospedado no Railway com PostgreSQL gerenciado.

Configurações principais de produção:

```text
Start Command:
uvicorn app.main:app --host 0.0.0.0 --port $PORT

Pre-deploy Command:
alembic upgrade head
```

As credenciais e demais valores sensíveis são configurados exclusivamente como variáveis de ambiente no Railway.

## Segurança

- Hash de senhas com Argon2
- Tokens JWT para autenticação
- Associação dos registros ao usuário autenticado
- Variáveis sensíveis fora do controle de versão
- Configuração explícita de CORS

## Roadmap

- Alertas de estoque baixo com base na autonomia estimada
- Definição de nível mínimo de segurança para reposição
- Previsão da data recomendada para aquisição de nova unidade de insulina
- Controle do processo de reposição diretamente pela plataforma
- Busca de opções de compra em farmácias
- Redirecionamento para farmácias ou páginas de compra compatíveis
- Possível integração futura com serviços de disponibilidade e preços

A proposta é evoluir o Insulinet de um sistema de controle de estoque para uma ferramenta capaz de antecipar a necessidade de reposição e facilitar o acesso do usuário ao medicamento.

## Frontend

Código-fonte:

https://github.com/fernanndp/insulinet-frontend

Aplicação:

https://insulinet-frontend-production.up.railway.app

## Status

Projeto em desenvolvimento e disponível em ambiente de produção no Railway.
