import os
from dotenv import load_dotenv

load_dotenv()

WITHINGS_CLIENT_ID = os.getenv("WITHINGS_CLIENT_ID")
WITHINGS_CLIENT_SECRET = os.getenv("WITHINGS_CLIENT_SECRET")
WITHINGS_REDIRECT_URI = os.getenv("WITHINGS_REDIRECT_URI")