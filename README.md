# Closet Intelligence

A private digital wardrobe and rule-based outfit recommendation studio built with Flask, SQLite and SQLAlchemy. It helps users catalogue real clothing, generate explainable outfits, plan a week and understand wardrobe gaps without relying on paid services or machine learning.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`. The SQLite database is created automatically on first launch. Set a strong `SECRET_KEY` in `.env` before using the app beyond local development.

## Test

```bash
pytest -q
```

## Architecture

`closet_intelligence/__init__.py` creates the Flask application and extensions. `models.py` defines isolated user-owned wardrobe, outfit, wear and planner records. `routes.py` contains blueprint routes and upload validation. `intelligence.py` is deliberately independent of Flask: it generates only valid clean-item combinations, scores colour, occasion, weather, preference and diversity, then selects varied recommendations. The score weights are centralized in `WEIGHTS`.

The interface uses a warm ivory, linen, espresso and muted brass design system. Clothing images are stored under `static/uploads` with generated secure filenames and validated through Pillow. External weather services are not required; the studio accepts temperature and rain context directly.

## Current scope

The primary end-to-end flows are implemented: registration, login/logout, user-owned wardrobe CRUD, validated image uploads, searchable/filterable catalogue, outfit generation, saved outfit records, planner placement, profile preferences, utilization and cost-per-wear insights, and wardrobe gap suggestions. The application is intentionally local-first and uses no shopping API or external image dependency.
