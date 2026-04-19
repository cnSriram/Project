import httpx
import asyncio
import os
import time
from dotenv import load_dotenv, find_dotenv
from cachetools import TTLCache

load_dotenv(find_dotenv())

class IGDBService:
    def __init__(self):
        self.client_id = os.getenv("IGDB_CLIENT_ID")
        self.client_secret = os.getenv("IGDB_CLIENT_SECRET")
        self.access_token = os.getenv("IGDB_ACCESS_TOKEN")
        self.token_expiry = 0
        self.base_url = "https://api.igdb.com/v4/games"
        self.token_url = "https://id.twitch.tv/oauth2/token"
        
        # Robust in-memory cache: Max 1024 items, expires after 24 hours (86400 seconds)
        self._cache = TTLCache(maxsize=1024, ttl=86400)
        
        # Persistent HTTP client for connection pooling
        self._client = httpx.AsyncClient(timeout=10.0)
        
        # Lock to prevent multiple simultaneous token refreshes
        self._token_lock = asyncio.Lock()

    async def _get_access_token(self):
        """Fetches a new access token if the current one is missing or expired (with locking)."""
        async with self._token_lock:
            now = time.time()
            
            # Re-check inside the lock in case another request already refreshed it
            if self.access_token and now < self.token_expiry - 60:
                return self.access_token

            if not self.client_id or not self.client_secret:
                print("[WARNING] IGDB Credentials missing. Enrichment will be limited.")
                return self.access_token

            try:
                params = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
                }
                response = await self._client.post(self.token_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                self.access_token = data["access_token"]
                self.token_expiry = now + data["expires_in"]
                
                print("[INFO] IGDB Access Token refreshed.")
                return self.access_token
            except Exception as e:
                print(f"[ERROR] Failed to refresh IGDB token: {e}")
                return self.access_token

    async def get_headers(self):
        # We check the condition outside the lock first for performance
        now = time.time()
        if not self.access_token or now >= self.token_expiry - 60:
            token = await self._get_access_token()
        else:
            token = self.access_token
            
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain"
        }

    async def fetch_game_metadata(self, game_name: str):
        """Calls IGDB and returns cleaned data. Uses cache for repeated lookups."""
        if not game_name:
            return None

        # Check cache first
        if game_name in self._cache:
            return self._cache[game_name]

        query = f"""
        fields name, summary, total_rating, cover.url, first_release_date, genres.name;
        search "{game_name}";
        limit 1;
        """
        
        req_start = time.time()
        try:
            headers = await self.get_headers()
            response = await self._client.post(self.base_url, headers=headers, content=query)
            response.raise_for_status()
            data = response.json()

            if not data:
                self._cache[game_name] = None
                return None

            game = data[0]
            
            # Formatting the image URL
            if "cover" in game:
                game["cover_url"] = "https:" + game["cover"]["url"].replace("t_thumb", "t_720p")
            
            # Save to cache
            self._cache[game_name] = game
            
            # Optional debug log
            # print(f"  - IGDB '{game_name}' took {round((time.time()-req_start)*1000)}ms")
            
            return game

        except Exception as e:
            print(f"[ERROR] IGDB API Error for '{game_name}': {e}")
            return None

    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()