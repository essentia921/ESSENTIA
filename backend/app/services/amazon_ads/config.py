# backend/services/amazon_ads/config.py
# Costanti e credenziali Amazon Ads (ex settings.py top-level).

import os
from dotenv import load_dotenv

# Carica il file .env nella root del progetto
load_dotenv()

# ==========================================================
# VARIABILI DAL FILE .ENV
# ==========================================================

CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMAZON_ADS_CLIENT_SECRET")
REDIRECT_URI = os.getenv("AMAZON_ADS_REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError(
        "Variabili .env mancanti. "
        "Devi avere AMAZON_ADS_CLIENT_ID, AMAZON_ADS_CLIENT_SECRET, AMAZON_ADS_REDIRECT_URI."
    )

# ==========================================================
# COSTANTI AMAZON ADS (FISSE)
# ==========================================================

API_BASE_URL = "https://advertising-api.amazon.com"
LWA_AUTHORIZE_URL = "https://www.amazon.com/ap/oa"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SCOPE = "advertising::campaign_management"

API_REGIONS = {
    "NA": {
        "url": "https://advertising-api.amazon.com",
        "name": "North America",
        "countries": ["US", "CA", "MX", "BR"],
    },
    "EU": {
        "url": "https://advertising-api-eu.amazon.com",
        "name": "Europe",
        "countries": ["UK", "GB", "DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE", "AE", "SA", "EG", "TR", "IN"],
    },
    "FE": {
        "url": "https://advertising-api-fe.amazon.com",
        "name": "Far East",
        "countries": ["JP", "AU", "SG"],
    },
}
