import os
from dotenv import load_dotenv

load_dotenv()

WITHINGS_CLIENT_ID = os.getenv("WITHINGS_CLIENT_ID")
WITHINGS_CLIENT_SECRET = os.getenv("WITHINGS_CLIENT_SECRET")
WITHINGS_REDIRECT_URI = os.getenv("WITHINGS_REDIRECT_URI")

XERT_USERNAME = os.getenv("XERT_USERNAME")
XERT_PASSWORD = os.getenv("XERT_PASSWORD")

HEVY_API_KEY = os.getenv("HEVY_API_KEY")

APPLE_EXPORT_FOLDER = "/Users/nikhall/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents"