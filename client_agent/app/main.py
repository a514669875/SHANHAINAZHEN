"""Client agent - lightweight file service for distributed storage."""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from app.config import FILE_SHARE_ROOT, API_KEY, SERVER_URL, COMPUTER_NAME, COMPUTER_IP, SERVICE_PORT

app = FastAPI(title="山海纳珍录 - 客户端文件服务")


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/files/{file_path:path}")
async def get_file(file_path: str, _: bool = Depends(verify_api_key)):
    """Serve file from local storage."""
    full_path = Path(FILE_SHARE_ROOT) / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    return FileResponse(str(full_path))


@app.get("/stream/{file_path:path}")
async def stream_file(file_path: str, _: bool = Depends(verify_api_key)):
    """Stream file for large files."""
    full_path = Path(FILE_SHARE_ROOT) / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    def iterfile():
        with open(full_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(iterfile(), media_type="application/octet-stream")


@app.get("/health")
def health():
    return {"status": "ok", "computer": COMPUTER_NAME}
