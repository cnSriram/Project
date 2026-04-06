import os
import re
import time
import requests
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import json
import random

# 1. SETUP & CONFIGURATION
load_dotenv()

# Replace with your actual credentials or use .env keys
# This tells Python: "Look for 'RAWG_KEY' in .env. If it's not there, use this backup string."
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "a112284d327c4fa0bc027f7f38188e4b")

# This tells Python: "Look for 'MONGO_URI' in .env."
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://sriram:sriram@cluster0.ddm9vqv.mongodb.net/")

# Initialize Mongo
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['gamesDB']
    collection = db['fitgirl-games']
    # Trigger a quick check to see if DB is reachable
    client.admin.command('ping')
    print("✅ Connected to MongoDB at 172.25.5.110")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    exit()

def get_clean_name(name):
    pattern = r'(?i)[:/,+;]|v\d+\.|Build|repack'
    return re.split(pattern, name)[0].strip()

def generate_curated_lists():
    # 1. Connect with a timeout to prevent infinite hanging
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client['gamesDB']
        collection = db['fitgirl-games']
        cursor = list(collection.find({}, {"gameName": 1, "_id": 1}))
    except Exception as e:
        print(f"❌ MongoDB Error: {e}")
        return

    if not cursor:
        print("❌ No games found in MongoDB.")
        return

    scored_data = []
    total = len(cursor)
    print(f"📡 Starting data sync for {total} games...")

    # 2. Use a Session for faster networking
    session = requests.Session()

    for i, doc in enumerate(cursor):
        clean_name = get_clean_name(doc['gameName'])
        
        # --- PROGRESS TRACKER ---
        print(f"🔎 [{i+1}/{total}] Fetching: {clean_name[:30]}...", end="\r")
        
        url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&search={clean_name}&page_size=1"
        
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('results'):
                    res = data['results'][0]
                    scored_data.append({
                        "mongo_id": str(doc['_id']),
                        "raw_name": doc['gameName'],
                        "rating": res.get("rating", 0),
                        "metacritic": res.get("metacritic") or 0,
                        "released": res.get("released", "1900-01-01"),
                        "added": res.get("added", 0),
                        "genres": [g['name'] for g in res.get("genres", [])]
                    })
            # Anti-throttle delay
            time.sleep(0.1) 
        except Exception:
            # Skip games that timeout and keep moving
            continue

    print(f"\n✅ Sync Complete! Categorizing {len(scored_data)} matched games...")

    # --- CATEGORIZATION LOGIC ---
    def get_year(d): return int(d[:4]) if d and len(d) >= 4 else 1900

    # We filter and sort the results
    cats = {
        "Latest Releases": [g for g in scored_data if get_year(g['released']) >= 2024],
        "Must Play Classics": [g for g in scored_data if g['metacritic'] >= 85 and get_year(g['released']) <= 2021],
        "Trending Now": sorted(scored_data, key=lambda x: x['added'], reverse=True),
        "Top Action Repacks": [g for g in scored_data if "Action" in g['genres'] and "repack" in g['raw_name'].lower()],
        "Hidden Gems": [g for g in scored_data if g['rating'] >= 4.0 and g['added'] < 2000],
        "Award Winning Games": [g for g in scored_data if g['metacritic'] >= 90],
        "Masterpiece RPGs": [g for g in scored_data if "RPG" in g['genres'] and g['rating'] >= 4.0],
        "Atmospheric Horror": [g for g in scored_data if "Horror" in g['genres']],
        "High-Octane Racing": [g for g in scored_data if "Racing" in g['genres']]
    }

    # --- FINAL PRINT ---
    for name, games in cats.items():
        # Sort by rating/metacritic and take top 10
        top_games = sorted(games, key=lambda x: x.get('metacritic', 0) or x.get('rating', 0), reverse=True)[:10]
        ids = [{"$oid": g['mongo_id']} for g in top_games]
        
        print(f"\n📂 {name.upper()}")
        print(json.dumps(ids, indent=2) if ids else "[]")

if __name__ == "__main__":
    generate_curated_lists()