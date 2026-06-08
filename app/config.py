import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.getenv('SECRET_KEY', 'secret-key')

SQLALCHEMY_DATABASE_URI = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{os.path.join(BASE_DIR, 'project.db')}",
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = False

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'media', 'images')
