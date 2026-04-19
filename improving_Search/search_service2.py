import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Import your IGDB Service
from igdb_service import IGDBService

# --- 1. INITIALIZATION & SETUP ---
load_dotenv(find_dotenv())
app = FastAPI(title="Game Search API - Multi-User Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows your friend's website to call this API
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Connections
client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client['gamesDB']
collection = db['fitgirl-games']
igdb = IGDBService() # Initialize IGDB

async def verify_mongo():
    try:
        await client.admin.command('ping')
        print("[INFO] MongoDB Connection Successful!")
    except Exception as e:
        print(f"[ERROR] MongoDB Connection Failed: {e}")

# We create the ping task to run in the background
asyncio.create_task(verify_mongo())

# --- 2. CACHE & INDEXING ---
# We no longer need to load all games into memory or use local NLP models.
# MongoDB Atlas Search handles this far more efficiently.
print("[INFO] Server initialized with Atlas Search support.")

# --- 3. UTILITY FUNCTIONS ---
# Extensive acronyms mapped to full names (Syncing with search_service.py)
COMMON_ACRONYMS = {
    # Grand Theft Auto Series
    "gta": "Grand Theft Auto",
    "gta5": "Grand Theft Auto V",
    "gta4": "Grand Theft Auto IV",
    "gtav": "Grand Theft Auto V",
    "gtaiv": "Grand Theft Auto IV",
    
    # Call of Duty Series
    "cod": "Call of Duty",
    "mw": "Modern Warfare",
    "mw2": "Modern Warfare II",
    "mw3": "Modern Warfare III",
    "bo": "Black Ops",
    "bo6": "Black Ops 6",
    "bo3": "Black Ops 3",
    "bo2": "Black Ops 2",
    
    # Resident Evil Series
    "re": "Resident Evil",
    "re4": "Resident Evil 4",
    "re2": "Resident Evil 2",
    "re7": "Resident Evil 7",
    "revillage": "Resident Evil: Village",
    
    # Marvel / Spider-Man
    "spiderman": "Marvel’s Spider-Man",
    "miles": "Spider-Man: Miles Morales",
    "sm2": "Marvel’s Spider-Man 2",
    
    # Red Dead Redemption
    "rdr": "Red Dead Redemption",
    "rdr2": "Red Dead Redemption 2",
    
    # Assassin's Creed
    "ac": "Assassin’s Creed",
    "aciv": "Assassin’s Creed IV",
    "acm": "Assassin’s Creed Mirage",
    
    # Sports Games
    "fifa": "EA SPORTS",
    "fc26": "EA SPORTS FC 26",
    "wwe": "WWE 2K",
    
    # Others
    "gow": "God of War",
    "er": "ELDEN RING",
    "sote": "Shadow of the Erdtree",
    "tlou": "The Last of Us",
    "tlou2": "The Last of Us: Part II",
    "got": "Ghost of Tsushima",
    "hks": "Hollow Knight: Silksong",
    "cyberpunk": "Cyberpunk 2077",
    "ts4": "The Sims 4",
    "nfs": "Need for Speed",
    "ets2": "Euro Truck Simulator 2",
    "mk": "Mortal Kombat",
    "mk1": "Mortal Kombat 1",
    "mk11": "Mortal Kombat 11",
    "stalker2": "S.T.A.L.K.E.R. 2",
    "bmw": "Black Myth: Wukong"
}

def expand_query(q: str) -> str:
    # Cleanup query
    query_clean = q.lower().strip()
    
    # Check for direct matches in the acronym map
    if query_clean in COMMON_ACRONYMS:
        return COMMON_ACRONYMS[query_clean]
    
    # Otherwise check word by word
    words = query_clean.split()
    expanded = [COMMON_ACRONYMS.get(w, w) for w in words]
    return " ".join(expanded)

def serialize_doc(doc):
    """Recursively serializes MongoDB documents for JSON output."""
    if isinstance(doc, list):
        return [serialize_doc(i) for i in doc]
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
            elif isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                doc[key] = serialize_doc(value)
    return doc

# --- 4. ROUTES ---

@app.get("/nlp-search")
async def nlp_search(q: str = ""):
    if not q or len(q.strip()) < 1:
        return []

    search_query = expand_query(q)
    start_time = time.time()

    # Using MongoDB Atlas Search ($search) with Compound Boosting
    pipeline = [
        {
            "$search": {
                "index": "default",
                "compound": {
                    "should": [
                        {
                            # 1. Exact Phrase Match (Highest priority)
                            "phrase": {
                                "query": search_query,
                                "path": "gameName",
                                "score": { "boost": { "value": 15 } }
                            }
                        },
                        {
                            # 2. Prefix Match (High priority for "start with")
                            "wildcard": {
                                "query": f"{search_query}*",
                                "path": "gameName",
                                "allowAnalyzedField": True,
                                "score": { "boost": { "value": 10 } }
                            }
                        },
                        {
                            # 3. Text Match (Standard search)
                            "text": {
                                "query": search_query,
                                "path": "gameName",
                                "score": { "boost": { "value": 5 } }
                            }
                        },
                        {
                            # 4. Fuzzy Match (Typo tolerance)
                            "text": {
                                "query": search_query,
                                "path": "gameName",
                                "fuzzy": { "maxEdits": 1, "prefixLength": 2 },
                                "score": { "boost": { "value": 2 } }
                            }
                        }
                    ],
                    "minimumShouldMatch": 1
                }
            }
        },
        { "$limit": 8 },
        {
            "$project": {
                "score": { "$meta": "searchScore" },
                "gameName": 1,
                "repackSize": 1,
                "downloadLinks": 1,
                "genres": 1,
            }
        }
    ]

    try:
        db_start = time.time()
        # motor handles aggregate with an async for loop or to_list()
        search_results = await collection.aggregate(pipeline).to_list(length=8)
        db_time = time.time() - db_start
        
        enrich_start = time.time()
        async def enrich_result(doc):
            doc = serialize_doc(doc)
            # Alias score to search_score for legacy compatibility
            doc["search_score"] = doc.get("score", 0)
            
            # Enrich with IGDB data
            external_data = await igdb.fetch_game_metadata(doc["gameName"])
            if external_data:
                doc["cover_url"] = external_data.get("cover_url")
                doc["rating"] = external_data.get("total_rating")
            return doc

        # Parallelize the enrichment calls
        results = await asyncio.gather(*[enrich_result(doc) for doc in search_results])
        enrich_time = time.time() - enrich_start
        
        # Limit to 6 results as per original search_service.py
        results = results[:6]
        
        # Total performance logging
        total_time = time.time() - start_time
        print(f"[PERF] Search '{q}': DB {round(db_time*1000)}ms, Enrich {round(enrich_time*1000)}ms, Total {round(total_time*1000)}ms")
        
        return results

    except Exception as e:
        print(f"Search Error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# NEW ROUTE: For a "Game Details" page
@app.get("/game/{game_id}")
async def get_game_details(game_id: str):
    try:
        doc = await collection.find_one({"_id": ObjectId(game_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if not doc:
        raise HTTPException(status_code=404, detail="Game not found")
    
    doc = serialize_doc(doc)
    
    # Deep enrichment for the detail page
    external_data = await igdb.fetch_game_metadata(doc["gameName"])
    if external_data:
        doc["summary"] = external_data.get("summary")
        doc["full_rating"] = external_data.get("total_rating")
        doc["official_name"] = external_data.get("name")
    
    return doc

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) # host 0.0.0.0 allows external access