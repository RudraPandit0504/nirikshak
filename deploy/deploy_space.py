"""Create/update the Hugging Face Space for the hosted demo.

Reads HF_TOKEN plus GROQ_API_KEY and/or GEMINI_API_KEY from ~/.config/nirikshak/env. The API keys
are stored as encrypted Space *secrets* (never committed, never sent to browsers).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
env = dict(l.strip().split("=", 1) for l in (Path.home() / ".config/nirikshak/env").read_text().splitlines() if "=" in l)
api = HfApi(token=env["HF_TOKEN"])
user = api.whoami()["name"]
repo = f"{user}/{sys.argv[1] if len(sys.argv) > 1 else 'nirikshak'}"

api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
for k in ("AWS_BEARER_TOKEN_BEDROCK", "GROQ_API_KEY", "GEMINI_API_KEY"):
    if env.get(k):
        api.add_space_secret(repo, k, env[k])
# Optional model choices (comma-separated, tried in order), e.g. NIRIKSHAK_GROQ_MODELS=llama-3.3-70b-versatile
for k in ("AWS_REGION", "NIRIKSHAK_BEDROCK_MODELS", "NIRIKSHAK_GROQ_MODELS", "NIRIKSHAK_GROQ_VISION", "NIRIKSHAK_GEMINI_MODELS", "NIRIKSHAK_GEMINI_VISION"):
    if env.get(k):
        api.add_space_variable(repo, k, env[k])

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    # Tracked source files only (git archive), then the demo data.
    subprocess.run(f"git -C {ROOT} archive HEAD | tar -x -C {tmp}", shell=True, check=True)
    shutil.copy(ROOT / "deploy/Dockerfile.space", tmp / "Dockerfile")
    # The repo's .dockerignore keeps local reports out of dev builds; the demo image needs them.
    (tmp / ".dockerignore").write_text("\n".join(l for l in (ROOT / ".dockerignore").read_text().splitlines()
                                                if l not in ("backend/data/reports", "backend/data/speech")) + "\n")
    shutil.copy(ROOT / "deploy/space_README.md", tmp / "README.md")
    data = ROOT / "backend/data"
    (tmp / "backend/data/reports").mkdir(parents=True, exist_ok=True)
    (tmp / "backend/data/speech").mkdir(parents=True, exist_ok=True)
    (tmp / "backend/data/profiles").mkdir(parents=True, exist_ok=True)
    kept = []
    for p in (data / "reports").glob("*.json"):
        if not json.loads(p.read_text()).get("private"):
            shutil.copy(p, tmp / "backend/data/reports" / p.name)
            kept.append(p.stem)
    for p in (data / "speech").glob("*.m4a"):
        if p.name.split("-")[0] in kept:
            shutil.copy(p, tmp / "backend/data/speech" / p.name)
    for p in (data / "profiles").glob("*.json"):
        shutil.copy(p, tmp / "backend/data/profiles" / p.name)
    for junk in ["presentation", "docs", "SUBMISSION.md"]:
        shutil.rmtree(tmp / junk, ignore_errors=True) if (tmp / junk).is_dir() else (tmp / junk).unlink(missing_ok=True)
    api.upload_folder(folder_path=str(tmp), repo_id=repo, repo_type="space",
                      commit_message="Deploy Nirikshak demo", delete_patterns=["*"])
print(f"https://huggingface.co/spaces/{repo}")
print(f"App URL: https://{repo.replace('/', '-').lower()}.hf.space")
