import requests
import os
from dotenv import load_dotenv

load_dotenv()

class IGDBService:
    def __init__(self):
        self.client_id = os.getenv("IGDB_CLIENT_ID")
        self.access_token = os.getenv("IGDB_ACCESS_TOKEN")
        self.base_url = "https://api.igdb.com/v4/games"

    def get_headers(self):
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "text/plain"
        }

    def fetch_game_metadata(self, game_name: str):
        """Calls IGDB and returns cleaned data."""
        # We use 'search' for the name and 'where version_parent = n' to avoid duplicates
        query = f"""
        fields name, summary, total_rating, cover.url, first_release_date, genres.name;
        search "{game_name}";
        limit 1;
        """
        
        try:
            response = requests.post(self.base_url, headers=self.get_headers(), data=query)
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            game = data[0]
            
            # Formatting the image and date for your frontend
            if "cover" in game:
                game["cover_url"] = "https:" + game["cover"]["url"].replace("t_thumb", "t_720p")
            
            return game

        except requests.exceptions.HTTPError as e:
            print(f"❌ IGDB API Error: {e}")
            return None