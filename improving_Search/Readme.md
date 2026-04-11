# Game Search API

A semantic game search API built with FastAPI, MongoDB, and IGDB. Uses NLP and fuzzy matching to find games, enriched with cover art and ratings from the IGDB database.

---

## Files

| File | Purpose |
|---|---|
| `search_service2.py` | FastAPI app — search and game detail endpoints |
| `igdb_service.py` | IGDB API client — fetches cover art, ratings, summaries |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/cnSriram/Project
cd Project
python -m venv .venv
```

Activate the environment:
- Windows: `.venv\Scripts\activate`
- Mac/Linux: `source .venv/bin/activate`

```bash
pip install -r requirements2.txt
```

> `sentence-transformers` and `torch` are large — first install may take a few minutes.

---

### 2. Environment variables

Create a `.env` file in the root folder:

```
MONGO_URI=mongodb+srv://your_user:your_password@cluster0.mongodb.net/
IGDB_CLIENT_ID=your_client_id_here
IGDB_ACCESS_TOKEN=your_access_token_here
```

**Getting IGDB credentials:** Register at [https://api.igdb.com](https://api.igdb.com) and follow the Twitch OAuth flow to generate your `CLIENT_ID` and `ACCESS_TOKEN`.

---

### 3. Run the API

```bash
uvicorn search_service2:app --reload
```

On first run, the app will download the NLP model (`all-MiniLM-L6-v2`) and index all games in your MongoDB collection. This may take a moment.

Once ready, visit `http://127.0.0.1:8000/docs` to explore the API interactively.

---

## Endpoints

### `GET /nlp-search?q={query}`

Searches your game library using a combination of semantic NLP and fuzzy text matching.

**Example:**
```
GET /nlp-search?q=open world rpg
```

**Returns:** Up to 8 results, each enriched with IGDB cover art and rating.

---

### `GET /game/{game_id}`

Returns full details for a single game by its MongoDB `_id`.

**Example:**
```
GET /game/64a2f1c3e4b09d1a2c3f4e5d
```

**Returns:** Full game document enriched with IGDB summary, official name, and rating.

---

## How Search Works

1. **Text match** — finds games whose names contain the query string directly
2. **Semantic search** — encodes the query with `all-MiniLM-L6-v2` and compares against pre-indexed game embeddings using cosine similarity
3. **Fuzzy scoring** — re-scores candidates with `rapidfuzz` token set ratio
4. **Boost rules** — exact matches, prefix matches, and substring matches receive score bonuses to surface the most relevant result first
5. **Enrichment** — top results are fetched from MongoDB and augmented with live IGDB data
