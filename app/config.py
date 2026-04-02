
# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

REBRICKABLE_API_KEY = os.getenv("REBRICKABLE_API_KEY")
