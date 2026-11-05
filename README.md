# Heartstake

A play-credit social prediction market built with Django and React. Users register with only a username and password, receive 1,000 signup credits and can claim 250 credits once per calendar month.

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to Django on port 8000.

If the frontend is hosted separately from Django, set `VITE_API_URL` to the API base before building, for example `VITE_API_URL=https://example.com/api npm run build`.

## Docker Compose deployment

The production compose setup runs Django, the built React frontend, and an Nginx reverse proxy. The proxy serves the frontend at `/` and forwards `/api/` to Django.

```bash
cp .env.example .env
# Set DJANGO_SECRET_KEY in .env
docker compose up --build -d
```

Open `http://localhost` (or `http://localhost:${APP_PORT}` if you changed `APP_PORT`). The SQLite database is persisted in the `backend_data` Docker volume. Put TLS termination in front of the `proxy` service, or extend `deploy/nginx.conf` with your certificate configuration.

## Administration and settlement

Create an administrator with `.venv/bin/python manage.py createsuperuser`, then use http://localhost:8000/admin to add people and markets. Market resolution is available through `POST /api/markets/<id>/settle/` to a staff token with an `outcome_id` JSON body.

Payouts are parimutuel: the complete market pool is distributed among winning bets in proportion to each winning stake. This project uses fictional play credits only.

## Checks

```bash
.venv/bin/python manage.py test
cd frontend && npm run build
```
