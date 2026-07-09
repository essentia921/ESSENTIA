# ADS Agent SP — Amazon Ads Management SaaS

Piattaforma SaaS per la gestione di campagne Amazon Advertising (SP + SB):
ottimizzazione offerte, autopilot, search-term harvesting, book economics KDP,
blog, affiliati, pagamenti.

## Stack

| Pezzo | Dove gira | Cos'è |
|---|---|---|
| **Frontend** | Vercel | React + TypeScript + Vite (`frontend/`) |
| **Backend API** | Railway | FastAPI (`backend/app/`), avviato da `run_server.py` |
| **Worker** | Railway | processi in sottofondo: `python -m backend.app.services.big_bang_worker` |
| **Database + Storage** | Supabase | Postgres + storage immagini blog |
| **Codice / versioning** | GitHub | — |

Servizi esterni: Stripe (pagamenti), Resend (email), Google OAuth (login),
Amazon Ads API, OpenAI + Oxylabs + Canopy (extractor / dati prodotto).

## Struttura del backend

```
backend/app/
  main.py            app FastAPI + registrazione route
  api/routes/        endpoint (auth, accounts, campaigns, autopilot, harvest, blog, ...)
  core/              config, security, database
  services/          logica (amazon_ads/ adapter, autopilot, harvest, ...)
  models/            modelli ORM
db/                  accesso dati (accounts_db, blog_db, harvest_db)
```

## Sviluppo in locale

```bash
# 1. dipendenze backend
uv sync                     # oppure: pip install -e .
# 2. variabili
cp .env.example .env        # e riempi i valori
# 3. avvio
python -m backend.app.services.big_bang_worker &   # worker
python run_server.py                                # API su :8000

# frontend
cd frontend && npm install && npm run dev
```

## Deploy

**Supabase**: crea il progetto → copia la connection string in `DATABASE_URL`;
crea un bucket storage `media` (pubblico) e prendi `SUPABASE_URL` + service key.

**Railway** (due servizi dallo stesso repo GitHub):
- `web`  → start: `python run_server.py`
- `worker` → start: `python -m backend.app.services.big_bang_worker`
- imposta tutte le variabili d'ambiente (vedi `.env.example`).

**Vercel**: importa il repo, Root Directory = `frontend`, framework Vite;
variabili `VITE_API_URL` (= URL backend Railway + `/api`) e `VITE_GA4_ID`.

Tutte le variabili necessarie sono documentate in [.env.example](.env.example).
