import os
from pathlib import Path

from dotenv import load_dotenv


DATA_DIR = Path(__file__).resolve().parent
os.environ.setdefault("KAGGLEHUB_CACHE", str(DATA_DIR))

load_dotenv()
token = os.getenv("KAGGLE_API_KEY")
if not token:
    raise ValueError("KAGGLE_API_KEY environment variable is not set")

import kagglehub  # noqa: E402  (must follow the KAGGLEHUB_CACHE assignment)

path = kagglehub.dataset_download("wordsforthewise/lending-club")
print("Path to dataset files:", path)
