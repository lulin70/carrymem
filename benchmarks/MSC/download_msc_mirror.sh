#!/bin/bash
# Download MSC dataset from HuggingFace mirror sites

set -e

echo "========================================"
echo "Downloading MSC Dataset from Mirrors"
echo "========================================"

cd "$(dirname "$0")/data"

# Try multiple mirror sites
MIRRORS=(
    "https://hf-mirror.com"
    "https://huggingface.co"
)

DATASET="facebook/multi_session_chat"

for MIRROR in "${MIRRORS[@]}"; do
    echo ""
    echo "Trying mirror: $MIRROR"
    echo "----------------------------------------"
    
    # Try to download using wget
    if command -v wget &> /dev/null; then
        echo "Using wget..."
        
        # Download validation files
        wget -c "${MIRROR}/datasets/${DATASET}/resolve/main/msc_dialogue/session_4/valid.txt" -O msc_session4_valid.txt 2>&1 && echo "✅ Downloaded session 4 valid" && break
        
    elif command -v curl &> /dev/null; then
        echo "Using curl..."
        
        # Download validation files
        curl -L "${MIRROR}/datasets/${DATASET}/resolve/main/msc_dialogue/session_4/valid.txt" -o msc_session4_valid.txt 2>&1 && echo "✅ Downloaded session 4 valid" && break
    fi
done

echo ""
echo "========================================"
echo "Download completed!"
echo "========================================"
ls -lh
