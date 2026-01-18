import os
from google.cloud import aiplatform
import vertexai

project_id = os.getenv("GCP_PROJECT_ID", "vaiv-observatory")
location = os.getenv("GCP_LOCATION", "us-central1")

print(f"Listing models for Project: {project_id}, Location: {location}...")

aiplatform.init(project=project_id, location=location)

try:
    models = aiplatform.Model.list()
    print("\n--- Registered Models (Custom) ---")
    for m in models:
        print(f"{m.display_name} ({m.resource_name})")
except Exception as e:
    print(f"Failed to list custom models: {e}")

print("\n--- Foundation Models (Generative AI) ---")
try:
    from vertexai.preview.generative_models import GenerativeModel
    # There isn't a direct list method in the high-level SDK easily, 
    # so we will rely on the Model Garden API or just try known candidates.
    
    candidates = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-pro-exp",
        "gemini-exp-1206",
        "gemini-1.5-pro-002",
        "gemini-1.5-flash-002"
    ]
    
    vertexai.init(project=project_id, location=location)
    
    for model_name in candidates:
        try:
            model = GenerativeModel(model_name)
            # Try a dummy generation to confirm access
            response = model.generate_content("Hello", stream=False)
            print(f"[AVAILABLE] {model_name}")
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                print(f"[MISSING]   {model_name}")
            else:
                print(f"[ERROR]     {model_name}: {e}")

except ImportError:
    print("vertexai SDK not installed or version too old?")
