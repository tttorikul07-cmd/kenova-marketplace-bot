# KENOVA SHOP — Telegram Shop Bot Foundation

A modular Python Telegram bot foundation with SQLAlchemy, PostgreSQL-ready configuration, SQLite local development, deposit review, a wallet ledger, product browsing, balance purchases, order history, and basic support tickets.

> This is a tested starting release, not a claim that every commercial/business requirement is complete. Before selling it, complete the commercial checklist below, test against your actual hosting environment, and have payment and security flows independently reviewed.

## Stack
- Python 3.12+
- `python-telegram-bot` asynchronous framework
- SQLAlchemy 2
- Alembic migrations
- SQLite locally; PostgreSQL in production
- pytest

## Windows local setup
1. Install Python 3.12 or newer.
2. Extract this folder and open a terminal in `kenova-shop`.
3. Create an environment: `py -3.12 -m venv .venv`
4. Activate it in PowerShell: `Set-ExecutionPolicy -Scope Process Bypass` then `\.venv\Scripts\Activate.ps1`
5. Install: `python -m pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and add your BotFather token. Set your Telegram numeric ID in `ADMIN_IDS`.
7. For local SQLite, use `DATABASE_URL=sqlite:///./kenova_shop.db`.
8. Initialize the database: `alembic upgrade head`
9. Add demo products: `python -m scripts.seed_demo`
10. Run tests: `python -m pytest -q`
11. Start bot: `python -m app.main`

Do not include the backticks in terminal commands. Never share `.env` or your bot token.

## Database migrations
For a fresh database, run `alembic upgrade head`. For a future schema release, generate a migration with `alembic revision --autogenerate -m "describe change"`, inspect the generated migration carefully, then run `alembic upgrade head`. Back up production data before every migration. Do not delete the database to resolve a schema mismatch.

The convenience `init_db()` helper is used by local tests; production deployment should use Alembic migrations.

## Admin use
Set `ADMIN_IDS` to comma-separated numeric Telegram IDs, e.g. `ADMIN_IDS=123456789,987654321`. In Telegram, send `/admin` to the bot, then select pending deposits. Every review callback checks the administrator's Telegram ID. Do not set a public/group ID as an admin.

## Deposits and wallet
Deposits remain pending until an authorized admin approves them. A screenshot or reference is not proof of payment. Configure `PAYMENT_BKASH_NUMBER`, `PAYMENT_NAGAD_NUMBER`, and `PAYMENT_ROCKET_NUMBER` only with payment destinations you control and are permitted to use. No payment gateway is integrated in this release.

## Production notes
- Set `DATABASE_URL` to a managed PostgreSQL URL, and use a cloud host that supports a persistent background process.
- Use secrets management rather than committing `.env`.
- Configure backups, uptime alerts, error monitoring, and access control.
- Free hosting tiers may sleep, terminate long-running processes, or lose local storage. Do not rely on ephemeral SQLite storage for production.
- Run migrations as a release step before starting the bot.
- The included Docker Compose file is a deployment starting point; set a strong `POSTGRES_PASSWORD` in your local `.env` and validate the target host's networking/secrets configuration.

## Known scope limits before commercial resale
This release includes customer product browsing, one-item immediate purchase, balance display, manual deposit requests, admin deposit review, order/transaction history, profiles, and basic support tickets. A full web admin dashboard, cart quantity management, product CRUD interface, broadcast preview workflow, refund interface, support ticket replies, advanced roles, rate limiting, and a real payment gateway are not implemented in this release. Do not advertise those as available until built and tested.

## Backup (SQLite local development)
Stop the bot, copy `kenova_shop.db` to a secure backup location, and keep the backup outside source control. For PostgreSQL, use your provider's backup service or `pg_dump`; test restores periodically.
