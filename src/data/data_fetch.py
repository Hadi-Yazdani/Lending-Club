import os
from dotenv import load_dotenv
import kagglehub


load_dotenv()
token = os.getenv("KAGGLE_API_KEY")
if not token:
    raise ValueError("KAGGLE_API_KEY environment variable is not set")


kagglehub.login
path = kagglehub.dataset_download("wordsforthewise/lending-club")
print("Path to dataset files:", path)