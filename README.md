# EdgeTrack

**Open-source crypto trade tracker for Spot & Futures.**

Track your trades, analyze performance, and monitor your portfolio across multiple exchanges — all from a single self-hosted dashboard.

EdgeTrack automatically syncs your exchange data, reconstructs trades from raw orders, and provides detailed analytics including daily PnL, equity curves, and per-trade breakdowns.

## Features

- **Multi-exchange support** — Bitget, Bitmart, Hyperliquid (more coming)
- **Futures trade reconstruction** — Automatically groups orders into trades with entry/exit prices, PnL, fees
- **Daily PnL tracking** — Track realized and unrealized PnL day by day
- **Equity history** — Monitor your account equity over time
- **Multi-account** — Manage multiple exchange accounts from one place
- **Privacy-first** — Self-hosted, your API keys are encrypted at rest
- **Invitation system** — Control who can register after the first admin user
- **Dark mode** — Easy on the eyes, always
- **Extensible** — App factory pattern with hooks for building on top of EdgeTrack

## Tech Stack

| Layer      | Technology                                             |
|------------|--------------------------------------------------------|
| Backend    | Python 3.12+, FastAPI, SQLAlchemy 2.0, PostgreSQL 16   |
| Frontend   | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui    |
| Charts     | ECharts, Lightweight Charts                            |
| Deployment | Docker Compose                                         |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/CryptoRobotFr/edgetrack-core.git
cd edgetrack-core
```

### 2. Run the init script

The init script generates a `.env` file with secure random secrets (database password, encryption keys, JWT secret, etc.).

**Linux / macOS:**

```bash
chmod +x init.sh
./init.sh
```

**Windows (PowerShell):**

```powershell
.\init.ps1
```

> **Warning:** Keep your encryption keys safe. If you lose `ENCRYPTION_KEY` or `EMAIL_ENCRYPTION_KEY`, encrypted data (API keys, emails) cannot be recovered.

### 3. Start EdgeTrack

```bash
docker compose up -d --build
```

That's it! Open [http://localhost:3000](http://localhost:3000) in your browser.

The first user to register becomes the admin. After that, registration is invitation-only by default (configurable via `REGISTRATION_ENABLED` in `.env`).

### Default Ports

| Service            | URL                                                      |
| ------------------ | -------------------------------------------------------- |
| Frontend           | [http://localhost:3000](http://localhost:3000)           |
| Backend API        | [http://localhost:8000](http://localhost:8000)           |
| API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |
| PostgreSQL         | `localhost:5432`                                         |

All ports are configurable in `.env`.

## Local Development

For a faster development workflow with hot-reload, run only the database in Docker and start the backend/frontend locally.

### Dev Prerequisites

- [Python 3.12+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js 20+](https://nodejs.org/) and [pnpm](https://pnpm.io/)
- Docker (for the database)

### 1. Start the database

```bash
docker compose -f docker-compose.dev.yml up -d
```

This starts PostgreSQL and pgAdmin.

### 2. Backend

```bash
cd backend
uv sync
uv run alembic upgrade head    # Run database migrations
uv run uvicorn src.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Useful Commands

```bash
# Run backend tests
cd backend && uv run pytest

# TypeScript type checking
cd frontend && pnpm tsc --noEmit

# Regenerate OpenAPI client types (after changing API schemas)
cd frontend && pnpm generate:api

# Lint Python code
cd backend && uv run ruff check .
```

## Configuration

All configuration is done through environment variables. See [`.env.example`](.env.example) for the full list.

Key settings:

| Variable                          | Default  | Description                          |
|-----------------------------------|----------|--------------------------------------|
| `MODE`                            | `docker` | `docker` or `local`                  |
| `REGISTRATION_ENABLED`            | `false`  | Open registration or invitation-only |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440`   | Access token lifetime (24h)          |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`   | `7`      | Refresh token lifetime               |
| `BACKEND_PORT`                    | `8000`   | Backend API port                     |
| `FRONTEND_PORT`                   | `3000`   | Frontend port                        |
| `POSTGRES_PORT`                   | `5432`   | PostgreSQL port                      |

## Project Structure

```text
edgetrack-core/
├── backend/
│   ├── src/
│   │   ├── api/v1/           # REST API routes & Pydantic schemas
│   │   ├── core/             # Config, security, logging, hooks
│   │   ├── models/           # SQLAlchemy models
│   │   │   └── futures/      # Futures-specific models
│   │   ├── exchanges/        # Exchange connectors
│   │   │   ├── bitget/
│   │   │   ├── bitmart/
│   │   │   └── hyperliquid/
│   │   ├── futures/          # Trade reconstruction & analytics
│   │   └── main.py           # create_app() factory
│   ├── alembic/              # Database migrations
│   ├── tests/
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── components/       # React components (shadcn/ui)
│   │   ├── pages/            # Feature pages
│   │   ├── api/              # Generated OpenAPI client
│   │   ├── hooks/            # React Query hooks
│   │   ├── contexts/         # Auth, Account, User contexts
│   │   └── lib/              # Utilities & formatters
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml        # Full stack (DB + Backend + Frontend)
├── docker-compose.dev.yml    # Database only (for local dev)
├── init.sh                   # Setup script (Linux/macOS)
├── init.ps1                  # Setup script (Windows)
├── .env.example              # Environment template
└── LICENSE                   # AGPL-3.0
```

## Extensibility

EdgeTrack is designed to be extended. The `create_app()` factory accepts additional routers, middleware, and startup hooks:

```python
from src.main import create_app
from src.core.hooks import register_hook

app = create_app(
    extra_routers=[your_router],
    extra_middleware=[your_middleware],
    on_startup=your_startup_callback,
    settings_override=your_settings,
)

# Hook into lifecycle events
register_hook("on_user_registered", your_callback)
register_hook("on_sync_completed", your_callback)
register_hook("on_exception", your_error_handler)
```

Available hooks: `on_user_registered`, `on_sync_completed`, `on_exception`, and more.

## Contributing

Contributions are welcome! Here's how to get started:

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Set up local development (see [Local Development](#local-development))
4. Make your changes
5. Run tests (`cd backend && uv run pytest`)
6. Commit your changes with a descriptive message
7. Push to your fork and open a Pull Request

### Guidelines

- **Language**: All code, comments, and commit messages must be in **English**
- **Python style**: Follow [Ruff](https://docs.astral.sh/ruff/) defaults (`ruff check .` to verify)
- **TypeScript style**: `camelCase` for variables/functions, `PascalCase` for components/types
- **Dates**: UTC timestamps in milliseconds (never ISO strings in API responses)
- **Errors**: Follow RFC 7807 format with custom exceptions
- **Logging**: Use `structlog` — never log PII (emails, passwords, API secrets)
- **Tests**: Add or update tests for any code changes
- **Scope**: Keep PRs focused — one feature or fix per PR

### Architecture Rules

- `core/` is a leaf module — it must not import from other modules
- `models/` can only import from `core/`
- Business logic stays out of API routes
- Spot (`s_*` tables) and Futures (`f_*` tables) logic must never be mixed
- All trading data is scoped by `account_id`, never directly by `user_id`

### Contributor License Agreement

By submitting a pull request, you agree to the terms of our [CLA](CLA.md). Please include this statement in your first PR:

> I have read the CLA and I agree to its terms.

## Supported Exchanges

| Exchange    | Futures | Spot    |
|-------------|---------|---------|
| Bitget      | Yes     | Planned |
| Bitmart     | Yes     | Planned |
| Hyperliquid | Yes     | Planned |

Want to add an exchange? Check the [exchange connector interface](backend/src/exchanges/base.py) and open an issue to discuss.

## License

EdgeTrack is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE).

This means you can freely use, modify, and distribute EdgeTrack, but if you run a modified version as a network service, you must make the source code available to your users.

For commercial/proprietary licensing options, contact the maintainer.

---

Built by [ROBOTSOLUTIONS](https://github.com/CryptoRobotFr)
