import requests
import os
from .config import Config

class NetworkClient:
    @staticmethod
    def get(url, params=None):
        headers = {'User-Agent': Config.USER_AGENT}
        payload = {
            'api_key': Config.SCRAPERAPI_KEY,
            'url': url
        }
        if params:
            # Append params to the target URL for ScraperAPI
            import urllib.parse
            query_string = urllib.parse.urlencode(params)
            payload['url'] = f"{url}?{query_string}" if '?' not in url else f"{url}&{query_string}"
        
        response = requests.get(
            Config.SCRAPERAPI_ENDPOINT, 
            params=payload, 
            headers=headers, 
            timeout=Config.DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        
        # Handle UTF-8 BOM if present
        content = response.content
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
            
        decoded_content = content.decode('utf-8')
        if os.getenv("DEBUG", "False") == "True":
            print(f"DEBUG: Response Preview: {decoded_content[:100]}...")
        return decoded_content

    @staticmethod
    def post(url, params=None, json_data=None):
        headers = {'User-Agent': Config.USER_AGENT}
        payload = {
            'api_key': Config.SCRAPERAPI_KEY,
            'url': url
        }
        if params:
            # Append params to the target URL for ScraperAPI
            import urllib.parse
            query_string = urllib.parse.urlencode(params)
            payload['url'] = f"{url}?{query_string}" if '?' not in url else f"{url}&{query_string}"
        
        response = requests.post(
            Config.SCRAPERAPI_ENDPOINT, 
            params=payload, 
            json=json_data,
            headers=headers, 
            timeout=Config.DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        
        # Handle UTF-8 BOM if present
        content = response.content
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
            
        decoded_content = content.decode('utf-8')
        if os.getenv("DEBUG", "False") == "True":
            print(f"DEBUG: Response Preview: {decoded_content[:100]}...")
        return decoded_content

