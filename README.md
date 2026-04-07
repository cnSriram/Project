<<<<<<< HEAD
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
=======
# Project Setup & Deployment Guide

## Prerequisites

Ensure you have **Python** and **Git** installed on your system before proceeding.

---

## 1. `requirements.txt`

Make sure this file exists in your root folder before pushing to GitHub so others can install dependencies easily.

```
fastapi==0.110.0
uvicorn==0.27.1
pymongo==4.6.2
rapidfuzz==3.6.1
python-dotenv==1.0.1
requests==2.31.0
```

---

## 2. Step-by-Step Deployment Guide

### Phase 1: Setup & Environment

**1. Clone the repository**

```bash
git clone https://github.com/YourUsername/YourRepoName.git
cd YourRepoName
```

**2. Create a virtual environment**

This keeps your project dependencies separate from your system Python.

```bash
python -m venv .venv
```

**3. Activate the environment**

- Windows: `.venv\Scripts\activate`
- Mac/Linux: `source .venv/bin/activate`

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

---

### Phase 2: Configuration

Create a `.env` file in the root folder (same directory as your `.py` files). This file is ignored by GitHub but is essential for the code to run.

```
MONGO_URI=mongodb+srv://your_user:your_password@cluster0.mongodb.net/
RAWG_API_KEY=your_api_key_here
```

---

### Phase 3: Running the Programs

#### A. Initialize the Storefront — `store_categoriser.py`

Run this first to see how your games are categorized based on their RAWG metadata.

```bash
python store_categoriser.py
```

> Fetches ratings from the internet and prints the Top 10 lists for each category to your terminal.

---

#### B. Launch the Search API — `search_service.py`

This starts the local web server so your frontend can search for games.

```bash
uvicorn search_service:app --reload
```

> Open your browser to `http://127.0.0.1:8000/docs` to test the API interactively.

---

#### C. Update the Leaderboard — `store_updater1.py`

Run this whenever you add a new game to your main MongoDB collection.

```bash
python store_updater1.py
```

> When prompted, paste the `_id` of the new game. The script will automatically compare it against the current Top 10 and update the database if the new game ranks high enough.
>>>>>>> 6aefd25 (Fixed Readme)
