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

## Administration and settlement

Create an administrator with `.venv/bin/python manage.py createsuperuser`, then use http://localhost:8000/admin to add people and markets. Market resolution is available through `POST /api/markets/<id>/settle/` to a staff token with an `outcome_id` JSON body.

Payouts are parimutuel: the complete market pool is distributed among winning bets in proportion to each winning stake. This project uses fictional play credits only.

## Checks

```bash
.venv/bin/python manage.py test
cd frontend && npm run build
```
