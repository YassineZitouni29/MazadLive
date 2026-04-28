# MazaLive

MazaLive is a focused Django auction platform with timed listings, bidding, auto-bid ceilings, watchlists, seller dashboards, notifications, and lightweight JSON endpoints.

## Stack

- Django 6
- SQLite
- Custom templates, CSS, and a small amount of vanilla JavaScript

## Core Features

- Create scheduled or live auctions with category, reserve price, and shipping notes
- Place manual bids with validation against the current leading price
- Optional auto-bid ceiling per user and auction
- Automatic settlement when an auction reaches its end time
- Watchlist and winner views for bidders
- Seller dashboard with active listings, recent activity, notifications, and revenue
- JSON API for auctions, bids, categories, watchlist, and won auctions

## Run Locally

1. Create a virtual environment if needed:

```bash
python3 -m venv .venv
```

2. Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

3. Apply migrations:

```bash
.venv/bin/python manage.py migrate
```

4. Start the server:

```bash
.venv/bin/python manage.py runserver
```

## Main Routes

- `/` home page
- `/auctions/` browse listings
- `/auctions/create/` create a listing
- `/dashboard/` seller dashboard
- `/watchlist/` saved auctions
- `/wins/` won auctions
- `/api/auctions/` list or create auctions
- `/api/auctions/<id>/` detail view
- `/api/auctions/<id>/bid/` place a bid
- `/api/users/me/watchlist/` watchlist API
- `/api/users/me/won/` won auctions API
- `/api/categories/` category tree API
