"""
Download trained models from Hugging Face Hub during deployment
"""
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

# Configuration - UPDATE THIS AFTER UPLOADING
REPO_ID = "Feras07/hackinsight-pm25-models"  # Your HF repo ID
TOKEN = os.getenv("HF_TOKEN")  # Set in Render dashboard

MODELS = [
    "lgb_median.pkl",
    "lgb_lower.pkl", 
    "lgb_upper.pkl",
    "cb_median.cbm",
    "cb_lower.cbm",
    "cb_upper.cbm",
    "hybrid_meta.pkl"
]

def download_all_models():
    """Download all models from HF Hub"""
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("Downloading models from Hugging Face Hub...")
    print(f"Repo: {REPO_ID}")
    print("=" * 70)
    
    for model_file in MODELS:
        try:
            print(f"  Downloading {model_file}...", end=" ", flush=True)
            
            downloaded_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=model_file,
                local_dir=models_dir,
                token=TOKEN,
                local_dir_use_symlinks=False
            )
            
            print(f"OK")
            
        except Exception as e:
            print(f"FAILED: {e}")
            # Don't raise - allow deployment to continue, backend will show error
    
    print("=" * 70)
    print("Model download complete!")
    print("=" * 70)

if __name__ == "__main__":
    download_all_models()
