"""
Upload trained models to Hugging Face Hub
Run this ONCE to upload your models, then they'll be available for deployment
"""
import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo, login

# Configuration
REPO_ID = "Feras07/hackinsight-pm25-models"  # Using your HF username
TOKEN = os.getenv("HF_TOKEN")

if not TOKEN:
    print("❌ HF_TOKEN not found in environment!")
    print("Set it in .env file or run: $env:HF_TOKEN='your_token_here'")
    exit(1)

def upload_models():
    """Upload all trained models to HuggingFace Hub"""
    
    print("\n" + "=" * 70)
    print("Uploading Models to Hugging Face Hub")
    print("=" * 70)
    
    # Login
    print(f"\nLogging in...")
    login(token=TOKEN)
    
    api = HfApi()
    
    # Create repo (or use existing)
    print(f"Creating/accessing repo: {REPO_ID}")
    try:
        create_repo(repo_id=REPO_ID, token=TOKEN, private=False, exist_ok=True)
        print("✓ Repository ready")
    except Exception as e:
        print(f"Note: {e}")
    
    # Models to upload
    models_dir = Path("models")
    model_files = [
        "lgb_median.pkl",
        "lgb_lower.pkl",
        "lgb_upper.pkl",
        "cb_median.cbm",
        "cb_lower.cbm",
        "cb_upper.cbm",
        "hybrid_meta.pkl"
    ]
    
    print(f"\nUploading {len(model_files)} model files...\n")
    
    for model_file in model_files:
        model_path = models_dir / model_file
        
        if not model_path.exists():
            print(f"  ⚠️  {model_file} not found, skipping")
            continue
        
        try:
            print(f"  Uploading {model_file}...", end=" ", flush=True)
            
            api.upload_file(
                path_or_fileobj=str(model_path),
                path_in_repo=model_file,
                repo_id=REPO_ID,
                token=TOKEN
            )
            
            size_mb = model_path.stat().st_size / (1024 * 1024)
            print(f"✓ ({size_mb:.2f} MB)")
            
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    print("\n" + "=" * 70)
    print("UPLOAD COMPLETE!")
    print("=" * 70)
    print(f"\nModels available at: https://huggingface.co/{REPO_ID}")
    print(f"\nNext steps:")
    print(f"  1. Verify models at the URL above")
    print(f"  2. Update scripts/download_models.py with REPO_ID = '{REPO_ID}'")
    print(f"  3. Set HF_TOKEN in Render dashboard environment variables")
    print(f"  4. Push to GitHub - Render will auto-download models on build")
    print()

if __name__ == "__main__":
    upload_models()
