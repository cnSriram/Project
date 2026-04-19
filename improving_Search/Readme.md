# Game Search API (High-Concurrency Edition)

A professional-grade game search API built with FastAPI, MongoDB Atlas Search, and IGDB. Refactored for high-performance async I/O and parallel data enrichment.

---

## 🚀 Recent Upgrades
- **Atlas Search Integration**: Transitioned from in-memory processing to Lucene-based Atlas Search for sub-second responses on millions of documents.
- **Asynchronous Architecture**: Fully rewritten using `motor` (MongoDB) and `httpx` (HTTP) to ensure the server never blocks.
- **Parallel Enrichment**: Metadata for all search results is fetched concurrently, cutting latency by 60-80%.
- **Smart Acronyms**: Supports over 50 common game acronyms (GTA, COD, RE, etc.) for intuitive searching.

---

## 🛠️ Setup

### 1. Installation
```bash
git clone https://github.com/cnSriram/Project
cd Project/improving_Search
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements2.txt
```

### 2. Configuration
Create a `.env` file in the root directory (one level up from `improving_Search`):
```ini
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
IGDB_CLIENT_ID=your_id
IGDB_CLIENT_SECRET=your_secret
```

### 3. Run the Service
```bash
python search_service2.py
```

---

## 🔗 API Endpoints

### `GET /nlp-search?q={query}`
The primary search route. Supports partial titles, acronyms, and fuzzy matching.
- **Example**: `GET /nlp-search?q=gta`
- **Logic**: Expands acronyms -> Atlas Search query -> Parallel IGDB enrichment -> Cache result.

### `GET /game/{game_id}`
Fetches full details for a specific game by its MongoDB ID.
- **Example**: `GET /game/64a2f1c3...`

---

## 🧠 How it Works
1. **Request**: User types a partial name.
2. **Expansion**: `expand_query` checks for acronyms like "mw2" -> "Modern Warfare II".
3. **Atlas Search**: Compound scoring with prefix prioritizing (e.g., "spi" matches "Spider-Man" first).
4. **Parallel Fetch**: `asyncio.gather` triggers 8 simultaneous requests to IGDB for cover art and ratings.
5. **Efficiency**: `TTLCache` keeps results in memory for 24 hours to prevent redundant API calls.
