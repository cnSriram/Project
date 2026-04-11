# Documentation

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Code Walkthrough](#2-code-walkthrough)
   - [igdb_service.py](#igdb_servicepy)
   - [search_service2.py](#search_service2py)
3. [API Endpoint Reference](#3-api-endpoint-reference)
4. [Troubleshooting](#4-troubleshooting)

---

## 1. Architecture Overview

```
Your Frontend
     │
     │  HTTP GET requests
     ▼
┌─────────────────────────┐
│   search_service2.py    │  FastAPI app — the core of the system
│   (runs on port 8000)   │
└────────────┬────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
┌─────────┐    ┌──────────────┐
│ MongoDB │    │ igdb_service │ ──► IGDB API (external)
│ (your   │    │     .py      │     cover art, ratings,
│  games) │    └──────────────┘     summaries
└─────────┘
```

**Data flow for a search request:**

1. Frontend sends `GET /nlp-search?q=some game`
2. `search_service2.py` scores all games in memory using NLP + fuzzy matching
3. Top results are fetched from MongoDB
4. Each result is enriched with live data from IGDB via `igdb_service.py`
5. Final enriched results are returned to the frontend as JSON

**Data flow for a detail request:**

1. Frontend sends `GET /game/{id}`
2. `search_service2.py` fetches the document from MongoDB by `_id`
3. `igdb_service.py` fetches deep metadata (summary, official name, rating)
4. Merged result is returned as JSON

---

## 2. Code Walkthrough

### `igdb_service.py`

This file is a self-contained API client for IGDB. It has one job: given a game name, return metadata from the IGDB database.

**Class: `IGDBService`**

```python
def __init__(self):
```
Reads `IGDB_CLIENT_ID` and `IGDB_ACCESS_TOKEN` from your `.env` file and stores them. These are used in every request header.

```python
def get_headers(self):
```
Returns the HTTP headers required by the IGDB API — your Client ID and Bearer token.

```python
def fetch_game_metadata(self, game_name: str):
```
The main method. Sends a POST request to `https://api.igdb.com/v4/games` with an IGDB query string asking for the name, summary, rating, cover image, release date, and genres of the closest matching game.

- Uses `search "{game_name}"` to find the best match
- Sets `limit 1` to return only the top result
- If a cover image exists, it upgrades the URL from thumbnail (`t_thumb`) to high resolution (`t_720p`)
- Returns the game dict on success, or `None` if the request fails or no results are found

---

### `search_service2.py`

This is the main FastAPI application. It handles startup, indexing, and all search logic.

**Startup (runs once when the server starts)**

```python
model = SentenceTransformer('all-MiniLM-L6-v2')
```
Loads a lightweight but powerful NLP model. On first run this downloads ~90MB from the internet and caches it locally.

```python
ALL_GAMES_DATA = list(collection.find({}, {"gameName": 1}))
GAME_NAMES = [g['gameName'] for g in ALL_GAMES_DATA if 'gameName' in g]
GAME_EMBEDDINGS = model.encode(GAME_NAMES, convert_to_tensor=True)
```
Pulls every game name from MongoDB and converts them all into vector embeddings upfront. This is what makes search fast — comparisons happen in memory, not with repeated database queries.

---

**Utility functions**

```python
def normalize_text(text: str):
```
Strips all non-alphanumeric characters and lowercases the string. Used to compare names without punctuation or casing getting in the way (e.g. `"The Witcher 3"` → `"thewitcher3"`).

```python
def serialize_doc(doc):
```
Converts MongoDB-specific types (`ObjectId`, `datetime`) into plain strings so they can be safely returned as JSON.

---

**Route: `GET /nlp-search`**

The search pipeline runs in three stages:

**Stage A — Discovery:** Finds candidate games using two methods in parallel:
- Text match: scans all game names for the normalized query string
- Semantic match: encodes the query and finds the top 50 closest games by cosine similarity

Both sets of indices are merged and deduplicated.

**Stage B — Scoring:** Every candidate gets a composite score:

| Signal | Weight |
|---|---|
| Cosine similarity (NLP) | 70% |
| Fuzzy token match (`rapidfuzz`) | 30% |
| Exact name match bonus | +2000 |
| Name starts with query bonus | +1200 |
| Name contains query bonus | +600 |

The large bonuses ensure that if someone types an exact game title, it always surfaces first regardless of NLP score.

**Stage C — Enrichment:** The top 8 results are fetched from MongoDB and passed to `igdb_service.py` to attach cover art and rating before being returned.

---

**Route: `GET /game/{game_id}`**

Looks up a single game by its MongoDB `_id`, then calls `igdb_service.py` for deeper metadata — summary, official name, and full rating. Used for a game detail/info page.

---

## 3. API Endpoint Reference

### `GET /nlp-search`

Search for games using natural language or a game title.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `q` | string | Yes | Search query (e.g. `open world rpg`, `witcher`) |

**Example request**
```
GET http://127.0.0.1:8000/nlp-search?q=dark+souls
```

**Example response**
```json
[
  {
    "_id": "64a2f1c3e4b09d1a2c3f4e5d",
    "gameName": "Dark Souls III",
    "cover_url": "https://images.igdb.com/igdb/image/upload/t_720p/co1wyy.jpg",
    "rating": 91.4
  }
]
```

**Notes**
- Returns a maximum of 8 results
- Results are sorted by relevance score, highest first
- `cover_url` and `rating` are `null` if IGDB has no match for that game

---

### `GET /game/{game_id}`

Fetch full details for a single game.

**Path parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `game_id` | string | Yes | The MongoDB `_id` of the game |

**Example request**
```
GET http://127.0.0.1:8000/game/64a2f1c3e4b09d1a2c3f4e5d
```

**Example response**
```json
{
  "_id": "64a2f1c3e4b09d1a2c3f4e5d",
  "gameName": "Dark Souls III",
  "summary": "Dark Souls III is an action RPG set in the kingdom of Lothric...",
  "full_rating": 91.4,
  "official_name": "Dark Souls III"
}
```

**Notes**
- Returns `{"error": "Game not found"}` with a 200 status if the ID doesn't exist
- `summary`, `full_rating`, and `official_name` are only present if IGDB returns a match

---

### Interactive API Explorer

When the server is running, visit:

```
http://127.0.0.1:8000/docs
```

This opens the auto-generated Swagger UI where you can test both endpoints directly in your browser without writing any code.

---

## 4. Troubleshooting

### Server won't start

**`ModuleNotFoundError: No module named 'sentence_transformers'`**
You haven't installed the dependencies, or your virtual environment isn't active.
```bash
source .venv/bin/activate   # Mac/Linux
.venv\Scripts\activate      # Windows
pip install -r requirements2.txt
```

**`pymongo.errors.ServerSelectionTimeoutError`**
Your `MONGO_URI` in `.env` is wrong or your MongoDB cluster is paused (free-tier Atlas clusters pause after inactivity). Log in to MongoDB Atlas and resume the cluster.

---

### Search returns no results

**The server started fine but `/nlp-search` always returns `[]`**
- Check that your MongoDB collection name in `search_service2.py` matches your actual collection (`fitgirl-games` by default)
- Confirm your documents have a `gameName` field — the indexer skips documents without it
- Check the terminal where the server is running for the line `✅ Ready: N games indexed.` — if N is 0, the collection is empty or the field name is wrong

---

### IGDB data is missing (`cover_url` and `rating` are null)

**All results have `null` for IGDB fields**
Your IGDB credentials are likely invalid or expired. Access tokens expire after a few hours. Generate a new one:
```bash
curl -X POST "https://id.twitch.tv/oauth2/token" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=client_credentials"
```
Copy the returned `access_token` into your `.env` file as `IGDB_ACCESS_TOKEN`.

**Only some games have missing IGDB data**
IGDB may not have an entry for that specific game title. This is expected for niche or non-commercial titles.

---

### CORS errors in the browser

**`Access to fetch at '...' has been blocked by CORS policy`**
The API is configured to allow all origins (`allow_origins=["*"]`), so this should not happen under normal circumstances. If you see it, confirm the server is actually running and that the URL in your frontend matches exactly (including the port `8000`).