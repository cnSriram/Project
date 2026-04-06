1. search_service.py (The Search Engine)
Purpose: Provides a high-performance, NLP-lite search API for the game database.

Core Logic: Uses Fuzzy String Matching (via RapidFuzz) to handle typos and mixed-case inputs.

Key Feature: Implements an Acronym Mapper (e.g., "GTA" → "Grand Theft Auto") and a startup Memory Cache to ensure search results are returned in milliseconds without hitting the database repeatedly.

Tech Stack: FastAPI, MongoDB, RapidFuzz.



2. store_categoriser.py (The Data Enricher)
Purpose: Scans the entire database to fetch professional metadata and group games into curated collections.

Core Logic: Uses Regex to clean raw filenames and queries the RAWG API for Metacritic scores, ratings, and genres.

Output: Generates top-10 lists of ObjectIDs for categories like Latest Releases, Must Play Classics, and Hidden Gems.

Note: This is an initialization tool. It provides the data structure for the storefront but does not modify the live database automatically (prevents accidental data overwrites).



3. store_updater1.py (The Leaderboard Manager)
Purpose: Automatically maintains the "Top 10" integrity of the storefront as new games are added.

Input: Requires the MongoDB _id of a newly added game.

Core Logic: Performs a "King of the Hill" comparison. It fetches the new game's stats and compares them against the current leaders in the New Page test collection.

Output: If the new game qualifies, it re-ranks the category and performs a Live Write to the database. Includes an automatic JSON Backup feature for safety before every update.
