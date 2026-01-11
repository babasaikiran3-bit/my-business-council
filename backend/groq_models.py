import requests
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.groq.com/openai/v1/models",
    headers=headers
)

if response.status_code == 200:
    models = response.json()['data']
    print("Available Groq models:")
    for model in models:
        print(f"  - {model['id']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)