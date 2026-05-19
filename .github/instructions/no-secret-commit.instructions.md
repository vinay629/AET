---
description: "Use when staging files for commit. Enforces strict rules against committing secrets, credentials, datasets, trained models, cache artifacts, and other files that must never enter version control. Critical for ML/research projects."
---

# Never Commit Secrets or Artifacts

Before every commit, audit the staged files. **Never** commit the following categories.

## Absolute Never-Commit List

### Secrets & Credentials
- `.env` files (any variant: `.env.local`, `.env.production`, etc.)
- API keys, tokens, passwords, or connection strings
- Private keys, certificates, or credential files (`*.pem`, `*.key`, `*.p12`)
- Files containing `SECRET`, `PASSWORD`, `TOKEN`, or `API_KEY` in their names

### ML / Research Artifacts
- Trained model files: `*.pt`, `*.pth`, `*.onnx`, `*.h5`, `*.pb`, `*.ckpt`, `*.safetensors`
- Serialized models: `*.pkl`, `*.pickle`, `*.joblib`
- Model registries: `mlruns/`, `wandb/`, `checkpoints/`

### Datasets & Large Data Files
- `*.parquet`, `*.csv`, `*.jsonl`, `*.feather`, `*.hdf5`, `*.sqlite`
- `data/raw/`, `data/processed/`, `data/results/` directories
- Compressed archives: `*.zip`, `*.tar`, `*.tar.gz`, `*.7z`

### Cache & Generated Artifacts
- `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `.ipynb_checkpoints/`
- `*.egg-info/`, `dist/`, `build/`
- Coverage reports: `.coverage`, `coverage.xml`, `htmlcov/`

### Logs & Temporary Files
- `*.log` files
- `logs/` directory contents
- Temporary files: `*.tmp`, `*.bak`, `*.swp`, `*~`

### OS & IDE Junk
- `.DS_Store`, `Thumbs.db`, `desktop.ini`
- IDE configs not shared by team: `.vscode/`, `.idea/`

## Enforcement

1. **Before every commit**, run `git diff --cached --name-only` and verify no file in the list above is staged.
2. If a file that should be committed is missing from `.gitignore`, add it to `.gitignore` first (in a separate commit).
3. If you accidentally staged a secret, **unstage it immediately** with `git restore --staged <file>` and add it to `.gitignore`.
4. If a secret was already committed, **do not just remove it in a new commit** — the secret remains in history. Ask the user how to proceed (e.g., `git filter-branch` or `git filter-repo`).
