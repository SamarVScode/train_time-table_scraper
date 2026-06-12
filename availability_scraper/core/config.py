import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SCRAPERAPI_KEY = os.environ.get('SCRAPERAPI_KEY', '2489929e94aa0f1851699927d4155daf')
    SCRAPERAPI_ENDPOINT = 'https://api.scraperapi.com/'
    DEFAULT_TIMEOUT = 30
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
