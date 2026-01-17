import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("API Key missing")
        return

    genai.configure(api_key=api_key)
    
    print("--- Listing Available Models ---")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Name: {m.name}")
    except Exception as e:
        print(f"List models failed: {e}")

if __name__ == "__main__":
    list_models()
