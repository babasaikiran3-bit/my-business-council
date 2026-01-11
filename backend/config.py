import os
from dotenv import load_dotenv

load_dotenv()

# Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Council members - list of Groq available models
COUNCIL_MODELS = [
    "llama-3.1-8b-instant",          
    "llama-3.3-70b-versatile", 
    "openai/gpt-oss-120b",     
    "openai/gpt-oss-20b", 
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "llama-3.3-70b-versatile"

# Groq API endpoint
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

os.makedirs(DATA_DIR, exist_ok=True)


# Rate limiting settings (Groq has rate limits)
RATE_LIMIT_REQUESTS_PER_MINUTE = 30