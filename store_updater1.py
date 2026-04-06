import os
import re
import time
import json
import requests
import random
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()



# --- CONFIGURATION ---
# This tells Python: "Look for 'RAWG_KEY' in .env. If it's not there, use this backup string."
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "a112284d327c4fa0bc027f7f38188e4b")

# This tells Python: "Look for 'MONGO_URI' in .env."
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://sriram:sriram@cluster0.ddm9vqv.mongodb.net/")

# Initialize Mongo
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client['gamesDB']
main_col = db['fitgirl-games']
page_col = db['New Page test'] # Updated Collection Name

def get_clean_name(name):
    pattern = r'(?i)[:/,+;]|v\d+\.|Build|repack'
    return re.split(pattern, name)[0].strip()

def fetch_metadata(game_name):
    """Fetches game DNA with error handling and retries."""
    url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&search={game_name}&page_size=1"
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('results'):
                res = data['results'][0]
                return {
                    "rating": res.get("rating", 0),
                    "metacritic": res.get("metacritic") or 0,
                    "released": res.get("released", "1900-01-01"),
                    "added": res.get("added", 0),
                    "genres": [g['name'] for g in res.get("genres", [])]
                }
    except Exception:
        return None
    return None

def update_top_10_with_new_game(new_game_mongo_id):
    # 1. Fetch New Game Details
    new_game_doc = main_col.find_one({"_id": ObjectId(new_game_mongo_id)})
    if not new_game_doc:
        print(f"❌ Error: ID {new_game_mongo_id} not found in fitgirl-games.")
        return
    
    print(f"🚀 Processing New Game: {new_game_doc['gameName']}")
    new_meta = fetch_metadata(get_clean_name(new_game_doc['gameName']))
    if not new_meta:
        print("❌ Could not find metadata for the new game. Aborting.")
        return
    
    new_meta['mongo_id'] = str(new_game_mongo_id)
    new_meta['raw_name'] = new_game_doc['gameName']

    # 2. Fetch the "New Page test" Leaderboard
    page_doc = page_col.find_one({"name": "New Page test"})
    if not page_doc:
        print("❌ Error: Document 'New Page test' not found in collection.")
        return

    # 3. Create a Local Backup for Safety
    with open("new_page_backup.json", "w") as f:
        json.dump(json.loads(json.dumps(page_doc, default=str)), f, indent=2)
    print("📂 Created 'new_page_backup.json' before processing.")

    updated_sections = []

    # 4. Process Every Section
    for section in page_doc.get('sections', []):
        title = section.get('title', '')
        # Only process sections that have a 'games' array
        if 'games' not in section or not isinstance(section['games'], list):
            updated_sections.append(section)
            continue
            
        current_game_oids = [g['$oid'] for g in section['games'] if '$oid' in g]
        
        # Build a comparison pool (Existing 10 + New 1)
        pool = []
        print(f"🔎 Analyzing Section: {title}...")
        
        for oid in current_game_oids:
            g_doc = main_col.find_one({"_id": ObjectId(oid)})
            if g_doc:
                m = fetch_metadata(get_clean_name(g_doc['gameName']))
                if m:
                    m['mongo_id'] = oid
                    m['raw_name'] = g_doc['gameName']
                    pool.append(m)
                time.sleep(0.1) # Small delay to respect API

        # Add the newcomer to the race
        pool.append(new_meta)

        # 5. Sorting Logic by Category Title
        def get_year(d): return int(d[:4]) if d and len(d) >= 4 else 1900
        
        if title == "Latest Releases":
            # Sort by release date (newest first)
            sorted_pool = sorted(pool, key=lambda x: (x['released'], x['added']), reverse=True)
        elif title in ["Must Play Classics", "Award Winning Games"]:
            # Sort by Metacritic score
            sorted_pool = sorted(pool, key=lambda x: (x['metacritic'], x['rating']), reverse=True)
        elif title == "Trending Now":
            # Sort by RAWG popularity (Added count)
            sorted_pool = sorted(pool, key=lambda x: x['added'], reverse=True)
        else:
            # Sort by User Rating (Hidden Gems, RPGs, Racing, Horror)
            sorted_pool = sorted(pool, key=lambda x: x['rating'], reverse=True)

        # 6. Slice to Top 10
        new_top_10 = [{"$oid": g['mongo_id']} for g in sorted_pool[:10]]
        section['games'] = new_top_10
        updated_sections.append(section)

    # 7. FINAL UPDATE (The Write Action)
    # UNCOMMENT THE LINE BELOW TO PERMANENTLY CHANGE THE DATABASE
    page_col.update_one({"name": "New Page test"}, {"$set": {"sections": updated_sections}})
    
    print("\n" + "="*30)
    print("✨ UPDATED LEADERBOARD PREVIEW")
    print("="*30)
    for s in updated_sections:
        print(f"\n📂 {s['title']}: {[g['$oid'] for g in s['games']]}")

if __name__ == "__main__":
    # Input the _id of the game you just added to test the competition
    target_id = input("Enter the MongoDB _id of the new game: ").strip()
    if target_id:
        update_top_10_with_new_game(target_id)