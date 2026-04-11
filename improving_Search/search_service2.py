import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId

# NLP & Search Libraries
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import process, fuzz
import torch

# Import your IGDB Service
from igdb_service import IGDBService

# --- 1. INITIALIZATION & SETUP ---
load_dotenv()
app = FastAPI(title="Game Search API - Multi-User Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows your friend's website to call this API
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Connections
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client['gamesDB']
collection = db['fitgirl-games']
igdb = IGDBService() # Initialize IGDB

# --- 2. MODEL & CACHE LOADING ---
print("🤖 Loading NLP Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

print("⚡ Indexing games...")
ALL_GAMES_DATA = list(collection.find({}, {"gameName": 1}))
GAME_NAMES = [g['gameName'] for g in ALL_GAMES_DATA if 'gameName' in g]
GAME_EMBEDDINGS = model.encode(GAME_NAMES, convert_to_tensor=True)
print(f"✅ Ready: {len(GAME_NAMES)} games indexed.")

# --- 3. UTILITY FUNCTIONS ---
def normalize_text(text: str):
    return re.sub(r'[^a-zA-Z0-9]', '', text.lower().strip())

def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    for key, value in doc.items():
        if isinstance(value, ObjectId): doc[key] = str(value)
        if isinstance(value, datetime): doc[key] = value.isoformat()
    return doc

# --- 4. ROUTES ---

@app.get("/nlp-search")
async def nlp_search(q: str = ""):
    if not q or len(q.strip()) < 1:
        return []

    query_norm = normalize_text(q)

    # A. DISCOVERY
    text_indices = [i for i, n in enumerate(GAME_NAMES) if query_norm in normalize_text(n)]
    query_emb = model.encode(q, convert_to_tensor=True)
    cos_scores = util.cos_sim(query_emb, GAME_EMBEDDINGS)[0]
    nlp_indices = torch.topk(cos_scores, k=min(50, len(GAME_NAMES))).indices.tolist()
    all_indices = list(set(text_indices + nlp_indices))

    # B. SCORING
    scored = []
    candidate_names = [GAME_NAMES[i] for i in all_indices]
    fuzzy_dict = {n: s for n, s, _ in process.extract(q, candidate_names, scorer=fuzz.token_set_ratio)}

    for idx in all_indices:
        name = GAME_NAMES[idx]
        name_norm = normalize_text(name)
        score = (float(cos_scores[idx]) * 70) + (fuzzy_dict.get(name, 0) * 0.3)

        if name_norm == query_norm: score += 2000
        elif name_norm.startswith(query_norm): score += 1200
        elif query_norm in name_norm: score += 600

        scored.append({"name": name, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    # C. ENRICHMENT & OUTPUT
    results = []
    for candidate in scored[:8]:
        doc = collection.find_one({"gameName": candidate["name"]})
        if doc:
            doc = serialize_doc(doc)
            
            # Enrich with IGDB data so your friend's site looks professional
            external_data = igdb.fetch_game_metadata(candidate["name"])
            if external_data:
                doc["cover_url"] = external_data.get("cover_url")
                doc["rating"] = external_data.get("total_rating")
            
            results.append(doc)
    return results

# NEW ROUTE: For a "Game Details" page
@app.get("/game/{game_id}")
async def get_game_details(game_id: str):
    doc = collection.find_one({"_id": ObjectId(game_id)})
    if not doc:
        return {"error": "Game not found"}
    
    doc = serialize_doc(doc)
    
    # Deep enrichment for the detail page
    external_data = igdb.fetch_game_metadata(doc["gameName"])
    if external_data:
        doc["summary"] = external_data.get("summary")
        doc["full_rating"] = external_data.get("total_rating")
        doc["official_name"] = external_data.get("name")
    
    return doc

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) # host 0.0.0.0 allows external access