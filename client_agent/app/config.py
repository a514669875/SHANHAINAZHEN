"""Client agent configuration."""
import os

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")
COMPUTER_NAME = os.getenv("COMPUTER_NAME", "LOCAL-PC")
COMPUTER_IP = os.getenv("COMPUTER_IP", "127.0.0.1")
FILE_SHARE_ROOT = os.getenv("FILE_SHARE_ROOT", "D:/shanhai_files")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8001"))
API_KEY = os.getenv("API_KEY", "your-secret-api-key")
