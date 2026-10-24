# FitLifeGuide

Django fitness app for planning workouts and meals, tracking progress, and sharing with the community.

## Setup

```powershell
cd fitlifeguide
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `fitlifeguide/.env` and set `DJANGO_SECRET_KEY`, `EMAIL_HOST_PASSWORD`, and `YOUTUBE_DATA_API_KEY`. Keep `DJANGO_DEBUG=True` for local development.

```powershell
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

## Tests

```powershell
python manage.py test
```

The test suite uses Django's in-memory email backend, so it does not send real email.
