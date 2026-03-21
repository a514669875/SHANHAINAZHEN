"""File proxy service - fetch files from distributed client storage."""
import requests
from urllib.parse import quote
from fastapi import HTTPException
from app.config import CLIENT_API_KEY


def proxy_file_from_client(client_ip: str, port: int, file_path: str, file_name: str = None):
    """Proxy file download from client. file_path 为相对归档根的路径，含中文时需 URL 编码。"""
    p = port if port else 8001
    norm = (file_path or "").replace("\\", "/").lstrip("/")
    encoded = quote(norm, safe="/")
    url = f"http://{client_ip}:{p}/stream/{encoded}"
    try:
        resp = requests.get(url, headers={"X-API-Key": CLIENT_API_KEY}, timeout=30, stream=True)
        resp.raise_for_status()
        return resp
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail=f"存储电脑不可达: {client_ip}")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="请求超时")
    except requests.HTTPError as e:
        st = e.response.status_code if e.response is not None else 0
        if st == 404:
            raise HTTPException(
                status_code=404,
                detail="存储电脑未找到该文件。单机开发请把 client_agent 的 FILE_SHARE_ROOT 设为与后端 ARCHIVED_FILE_ROOT 相同，"
                "或确保文件已存在于存储端对应目录。",
            )
        raise HTTPException(status_code=502, detail=f"存储端返回错误: HTTP {st}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"拉取文件失败: {e!s}")
