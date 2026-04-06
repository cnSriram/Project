import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from rapidfuzz import process, fuzz
from datetime import datetime
from dotenv import load_dotenv
from bson import ObjectId

# 1. Initialize and Security
load_dotenv()
app = FastAPI()

# Enable CORS so the Frontend/Express can talk to Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"], # We only need GET for searching
    allow_headers=["*"],
)

# 2. MongoDB Connection
# Ensure your .env has: MONGO_URI=mongodb://...
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client['gamesDB']
collection = db['fitgirl-games']

try:
    # This "pings" the database to see if it's alive
    client.admin.command('ping')
    print("✅ MongoDB Connection Successful!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")

# 3. Global Memory Cache (For instant results)
print("⚡ Initializing Search Cache...")
ALL_GAMES = list(collection.find({}, {"gameName": 1, "_id": 0}))
CACHED_NAMES = [g['gameName'] for g in ALL_GAMES if 'gameName' in g]
print(f"✅ Cache Ready: {len(CACHED_NAMES)} games loaded.")

# 1. Load and Map the Cache (Run this at startup)
# This creates a dictionary mapping 'lowercase_name': 'Original Name'
ALL_GAMES_RAW = list(collection.find({}, {"gameName": 1, "_id": 0}))
NAME_MAP = {g['gameName'].lower(): g['gameName'] for g in ALL_GAMES_RAW if 'gameName' in g}
CACHED_NAMES_LOWER = list(NAME_MAP.keys())

ACRONYMS = {
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
    "got": "Ghost of Tsushima", # Note: Also maps to 'Game of Thrones' but Ghost is more likely here
    "hks": "Hollow Knight: Silksong",
    "cyberpunk": "Cyberpunk 2077",
    "ts4": "The Sims 4",
    "nfs": "Need for Speed",
    "ets2": "Euro Truck Simulator 2",
    "mk1": "Mortal Kombat 1",
    "mk11": "Mortal Kombat 11",
    "stalker2": "S.T.A.L.K.E.R. 2",
    "bmw": "Black Myth: Wukong" # Common shorthand for Black Myth
}

# --- THE GET ROUTE ---
@app.get("/nlp-search")
async def nlp_search(q: str = ""):
    """
    Case-insensitive, acronym-aware fuzzy search for MongoDB games.
    """
    if not q or len(q) < 1:
        return []

    # --- STEP 1: NORMALIZE INPUT ---
    # Force the user's messy input to lowercase
    query_clean = q.lower().strip()
    
    # Check acronyms using the lowercase query
    target = ACRONYMS.get(query_clean, query_clean).lower()

    # --- STEP 2: FUZZY SEARCH (LOWERCASE VS LOWERCASE) ---
    # We search against CACHED_NAMES_LOWER so casing never breaks the match
    matches = process.extract(
        target, 
        CACHED_NAMES_LOWER, 
        scorer=fuzz.token_set_ratio, # Best for titles with colons/subtitles
        limit=15, 
        score_cutoff=25
    )
    
    results = []
    for name_l, score, _ in matches:
        # Retrieve the original correctly-cased name from our map
        original_db_name = NAME_MAP[name_l]
        doc = collection.find_one({"gameName": original_db_name})
        
        if doc:
            # --- STEP 3: SERIALIZATION (JSON FIXES) ---
            doc["_id"] = str(doc["_id"])
            
            # Convert any other ObjectIds (like downloadLinksId)
            for key, value in doc.items():
                if isinstance(value, ObjectId):
                    doc[key] = str(value)
            
            # Format dates to ISO strings
            for date_field in ["createdAt", "updatedAt"]:
                if date_field in doc and isinstance(doc[date_field], datetime):
                    doc[date_field] = doc[date_field].isoformat()

            # --- STEP 4: DYNAMIC RANKING BOOST ---
            final_score = score
            
            # Since both name_l and query_clean are lowercase, this is 100% reliable
            if name_l.startswith(query_clean):
                final_score += 100 # Priority for games starting with the search
            elif query_clean in name_l:
                final_score += 40 # Boost for partial matches
            
            doc["search_score"] = final_score
            results.append(doc)

    results.sort(key=lambda x: x["search_score"], reverse=True)
    return results[:6]


if __name__ == "__main__":
    import uvicorn
    # This runs the server on http://localhost:8000
    uvicorn.run("search_service:app", host="127.0.0.1", port=8000, reload=True)
