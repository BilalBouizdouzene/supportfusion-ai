$ErrorActionPreference = "Stop"
$scriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptsDirectory
Set-Location $root

$pythonPath = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = Join-Path $root ".venv-supportfusion\Scripts\python.exe"
}
if (-not (Test-Path $pythonPath)) {
    throw "Python environment not found. Run .\setup_local.ps1 first."
}

$downloadModels = @'
import gc
from sentence_transformers import CrossEncoder, SentenceTransformer
from backend.app.dense import EMBEDDING_MODEL, RERANKER_MODEL

print(f"Caching embedding model: {EMBEDDING_MODEL}")
embedding = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
del embedding
gc.collect()

print(f"Caching reranker model: {RERANKER_MODEL}")
reranker = CrossEncoder(RERANKER_MODEL, device="cpu")
del reranker
print("Model cache is ready.")
'@

& $pythonPath -c $downloadModels
if ($LASTEXITCODE -ne 0) {
    throw "Model download failed with exit code $LASTEXITCODE."
}
