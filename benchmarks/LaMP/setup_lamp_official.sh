#!/bin/bash
# Setup LaMP Official Benchmark Framework
# Official repo: https://github.com/LaMP-Benchmark/LaMP

set -e

echo "============================================"
echo "LaMP Official Benchmark Setup"
echo "============================================"
echo

# Create LaMP directory structure
LAMP_DIR="/Users/lin/trae_projects/carrymem/benchmarks/LaMP"
cd "$LAMP_DIR"

# Clone official LaMP repository
if [ ! -d "LaMP-official" ]; then
    echo "Cloning official LaMP repository..."
    git clone https://github.com/LaMP-Benchmark/LaMP.git LaMP-official
    echo "✅ Repository cloned"
else
    echo "✅ Repository already exists"
fi

cd LaMP-official

# Install dependencies
echo
echo "Installing LaMP dependencies..."
pip3 install -r requirements.txt 2>/dev/null || echo "⚠️  requirements.txt not found, installing common dependencies..."

# Install common dependencies for LaMP
pip3 install torch transformers datasets huggingface_hub sacrebleu bert-score rouge-score

echo
echo "============================================"
echo "Downloading LaMP Datasets"
echo "============================================"
echo

# Download LaMP datasets from Hugging Face
# LaMP has 7 tasks, we'll focus on LaMP-2, LaMP-3, LaMP-4 as per research

echo "Downloading LaMP-2 (Movie Tagging)..."
python3 -c "
from datasets import load_dataset
try:
    dataset = load_dataset('LaMP/LaMP_2')
    print('✅ LaMP-2 downloaded')
except Exception as e:
    print(f'❌ LaMP-2 download failed: {e}')
"

echo
echo "Downloading LaMP-3 (Product Rating)..."
python3 -c "
from datasets import load_dataset
try:
    dataset = load_dataset('LaMP/LaMP_3')
    print('✅ LaMP-3 downloaded')
except Exception as e:
    print(f'❌ LaMP-3 download failed: {e}')
"

echo
echo "Downloading LaMP-4 (News Categorization)..."
python3 -c "
from datasets import load_dataset
try:
    dataset = load_dataset('LaMP/LaMP_4')
    print('✅ LaMP-4 downloaded')
except Exception as e:
    print(f'❌ LaMP-4 download failed: {e}')
"

echo
echo "============================================"
echo "✅ LaMP Setup Complete!"
echo "============================================"
echo
echo "Next steps:"
echo "1. Review LaMP code in LaMP-official/"
echo "2. Adapt CarryMem to LaMP tasks using lamp_adapter.py"
echo "3. Run benchmarks with Claude model"
echo
