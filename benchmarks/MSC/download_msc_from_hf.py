#!/usr/bin/env python3
"""
Download MSC (Multi-Session Chat) dataset from Hugging Face
Official dataset: facebook/multi_session_chat
"""

import os
from datasets import load_dataset

def download_msc_dataset():
    """Download MSC dataset from Hugging Face"""
    
    print("=" * 60)
    print("Downloading MSC Dataset from Hugging Face")
    print("=" * 60)
    print()
    print("Dataset: facebook/multi_session_chat")
    print("Splits: train, validation, test")
    print()
    
    # Create data directory
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        # Download validation split
        print("Downloading validation split...")
        dataset = load_dataset("facebook/multi_session_chat", split="validation")
        
        print(f"✅ Downloaded {len(dataset)} validation samples")
        print()
        print("Sample structure:")
        print(dataset[0])
        print()
        
        # Save to JSON
        output_file = os.path.join(data_dir, "msc_validation_hf.json")
        dataset.to_json(output_file)
        print(f"✅ Saved to: {output_file}")
        
        # Download test split
        print()
        print("Downloading test split...")
        test_dataset = load_dataset("facebook/multi_session_chat", split="test")
        
        print(f"✅ Downloaded {len(test_dataset)} test samples")
        
        # Save to JSON
        test_output_file = os.path.join(data_dir, "msc_test_hf.json")
        test_dataset.to_json(test_output_file)
        print(f"✅ Saved to: {test_output_file}")
        
        print()
        print("=" * 60)
        print("✅ MSC Dataset Download Complete!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error downloading dataset: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check internet connectio install datasets")
        print("3. Try with authentication if needed:")
        print("   huggingface-cli login")
        return False

if __name__ == "__main__":
    download_msc_dataset()
