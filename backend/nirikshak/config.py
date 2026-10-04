import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NIRIKSHAK_DATA", ROOT / "data"))
WORK_DIR = DATA_DIR / "work"
REPORTS_DIR = DATA_DIR / "reports"
SEBI_DB = DATA_DIR / "sebi_registry.sqlite"
SEBI_CSV = DATA_DIR / "sebi_registry.csv"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("NIRIKSHAK_LLM", "qwen2.5:7b")
# Hindi output (translations, summary). Gemma 3 writes far more natural Hindi than Qwen.
HI_MODEL = os.environ.get("NIRIKSHAK_LLM_HI", "gemma3:4b")
WHISPER_MODEL = os.environ.get("NIRIKSHAK_WHISPER", "large-v3-turbo")
WHISPER_DEVICE = os.environ.get("NIRIKSHAK_WHISPER_DEVICE", "auto")

# Transcript window sent to the LLM in one request, in seconds.
WINDOW_SECONDS = int(os.environ.get("NIRIKSHAK_WINDOW", "90"))
# Longest video we agree to process, in seconds.
MAX_DURATION = int(os.environ.get("NIRIKSHAK_MAX_DURATION", str(45 * 60)))

for d in (DATA_DIR, WORK_DIR, REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
