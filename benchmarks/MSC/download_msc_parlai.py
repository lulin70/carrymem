#!/usr/bin/env python3
"""
Download MSC dataset using ParlAI
Alternative method when Hugging Face fails
"""

import os
import subprocess
import sys

def download_msc_with_parlai():
    """Download MSC dataset using ParlAI"""
    
    print("=" * 60)
    print("Downloading MSC Dataset using ParlAI")
    print("=" * 60)
    print()
    
    try:
        # Check if parlai is installed
        import parlai
        print(f"✅ ParlAI version: {parlai.__version__}")
    except ImportError:
        print("❌ ParlAI not installed")
        print("Installing ParlAI...")
        subprocess.run([sys.executable, "-m", "pip", "install", "parlai"], check=True)
        import parlai
        print(f"✅ ParlAI installed: {parlai.__version__}")
    
    print()
    print("Downloading MSC validation data...")
    print("This will download data to ~/.parlai/data/msc/")
    print()
    
    # Use ParlAI to download and display data
    cmd = [
        "parlai", "display_data",
        "-t", "msc",
        "-dt", "valid",
        "--num-examples", "5"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ MSC data downloaded successfully!")
            print()
            print("Sample output:")
            print(result.stdout[:1000])
            print()
            print("Data location: ~/.parlai/data/msc/")
            print()
            
            # Check data directory
            parlai_data_dir = os.path.expanduser("~/.parlai/data/msc/")
            if os.path.exists(parlai_data_dir):
                print(f"✅ Data directory exists: {parlai_data_dir}")
                files = os.listdir(parlai_data_dir)
                print(f"Files: {files}")
            
            return True
        else:
            print(f"❌ Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Download timeout (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = download_msc_with_parlai()
    sys.exit(0 if success else 1)
