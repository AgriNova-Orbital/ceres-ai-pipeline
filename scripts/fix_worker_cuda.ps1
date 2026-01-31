# Fix PyTorch CUDA environment on Windows
Write-Host "Syncing base dependencies..."
uv sync --extra ml --extra distributed

Write-Host "Installing PyTorch with CUDA 12.4..."
uv pip install torch==2.5.1+cu124 torchvision==0.20.1+cu124 --index-url https://download.pytorch.org/whl/cu124

Write-Host "Verifying installation..."
uv run python -c "import torch; print(f'Torch: {torch.__version__}, CUDA: {torch.cuda.is_available()}')"

if ($?) {
    Write-Host "SUCCESS: CUDA-enabled Torch installed." -ForegroundColor Green
} else {
    Write-Host "ERROR: Verification failed." -ForegroundColor Red
}
