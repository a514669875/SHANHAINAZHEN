"""File proxy service - fetch files from distributed client storage."""
import requests
from pathlib import Path
from fastapi import HTTPException
from app.config import CLIENT_API_KEY


def proxy_file_from_client(client_ip: str, port: int, file_path: str, file_name: str = None):
    """Proxy file download from client."""
    p = port if port else 8001
    url = f"http://{client_ip}:{p}/stream/{file_path}"
    try:
        resp = requests.get(url, headers={"X-API-Key": CLIENT_API_KEY}, timeout=30, stream=True)
        resp.raise_for_status()
        return resp
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail=f"存储电脑不可达: {client_ip}")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="请求超时")
