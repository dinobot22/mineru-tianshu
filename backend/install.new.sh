#!/bin/bash

echo "📦 Installing MinerU Tianshu Backend Dependencies..."
echo ""
echo "📋 Installation Options:"
echo "  - Core Dependencies (Required)"
echo "  - PaddleOCR-VL"
echo "  - Audio Processing (SenseVoice)"
echo "  - Video Processing"
echo "  - Watermark Removal"
echo "  - Format Engines (FASTA/GenBank)"
echo ""
echo "Installation Strategy:"
echo "  1. Install PaddlePaddle first (CUDA 12.6)"
echo "  2. Install PyTorch with compatible version"
echo "  3. Install packages separately to avoid conflicts"
echo "  4. Use legacy resolver for final dependency resolution"
echo ""
echo "============================================================"

# Step 1: Check system
echo ""
echo "[Step 1/8] Checking system requirements..."
if [ "$(uname)" != "Linux" ]; then
    echo "Warning: This script is designed for Linux/WSL"
    echo "Windows users should use WSL2 or Docker"
fi

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "✓ GPU detected:"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
else
    echo "⚠ Warning: nvidia-smi not found. GPU may not be available."
fi

# Step 2: Install system library
echo ""
echo "[Step 2/8] Installing system libraries..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y libgomp1 ffmpeg
    echo "✓ System libraries installed (libgomp1, ffmpeg)"
else
    echo "⚠ Warning: apt-get not found. You may need to install libgomp1 and ffmpeg manually."
fi

# Step 3: Install required packages
echo ""
echo "[Step 3/8] Installing required packages..."
pip install -r requirements.new.txt  --use-deprecated=legacy-resolver
echo "✓ All required packages installed"


# Verification
echo ""
echo "============================================================"
echo "Verifying installation..."
echo "============================================================"

python3 << 'EOF'
import sys

print("\nChecking frameworks...")
success = True

# Check PaddlePaddle
try:
    import paddle
    print(f"✓ PaddlePaddle: {paddle.__version__}")
    if paddle.device.is_compiled_with_cuda():
        print(f"  CUDA: Available ({paddle.device.cuda.device_count()} GPU)")
    else:
        print("  ⚠ CUDA: Not available")
        success = False
except Exception as e:
    print(f"✗ PaddlePaddle: {str(e)[:80]}")
    success = False

# Check PyTorch
try:
    import torch
    print(f"✓ PyTorch: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"  CUDA: Available ({torch.cuda.device_count()} GPU)")
    else:
        print("  ⚠ CUDA: Not available")
        success = False
except Exception as e:
    print(f"✗ PyTorch: {str(e)[:80]}")
    success = False

# Check Transformers
try:
    from transformers import AutoModel
    print("✓ Transformers: Ready")
except Exception as e:
    print(f"✗ Transformers: {str(e)[:80]}")
    success = False

# Check PaddleOCR-VL
try:
    from paddleocr import PaddleOCRVL
    print("✓ PaddleOCR-VL: Ready")
except Exception as e:
    print(f"⚠ PaddleOCR-VL: {str(e)[:80]}")
    # Not critical if this fails

# Check FunASR (Audio Processing with Speaker Diarization)
try:
    import funasr
    print("✓ FunASR: Ready (Audio Processing + Speaker Diarization)")
except Exception as e:
    print(f"⚠ FunASR: {str(e)[:80]}")
    # Not critical if this fails

print("")
if success:
    print("="*60)
    print("✓ Installation successful!")
    print("="*60)
    sys.exit(0)
else:
    print("="*60)
    print("✗ Installation completed with warnings")
    print("  Please check the errors above")
    print("="*60)
    sys.exit(1)
EOF

VERIFY_EXIT=$?

echo ""
if [ $VERIFY_EXIT -eq 0 ]; then
    echo "============================================================"
    echo "Installation complete! You can now start the server."
    echo "============================================================"
else
    echo "============================================================"
    echo "Installation completed with warnings."
    echo "See INSTALL.md for troubleshooting."
    echo "============================================================"
fi
