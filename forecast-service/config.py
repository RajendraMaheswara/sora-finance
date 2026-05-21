import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8080/api')
    MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')