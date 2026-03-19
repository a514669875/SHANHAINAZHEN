"""Client registration API for distributed file storage."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.models.client_registration import ClientRegistration
from app.config import CLIENT_API_KEY

router = APIRouter(prefix="/api/clients", tags=["clients"])


class RegisterRequest(BaseModel):
    computer_name: str
    computer_ip: str
    file_service_port: int = 8001
    file_share_path: str
    api_key: str


class HeartbeatRequest(BaseModel):
    computer_name: str
    computer_ip: str


@router.post("/register")
def register_client(data: RegisterRequest, db: Session = Depends(get_db)):
    if data.api_key != CLIENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Find user by computer_name (simplified - in production would need user_id in request)
    user = db.query(User).filter(User.computer_name == data.computer_name).first()
    if not user:
        user = db.query(User).first()  # Fallback: assign to first user
    if user:
        user.computer_ip = data.computer_ip
        user.file_service_port = data.file_service_port
        user.file_share_path = data.file_share_path
        user.is_online = True
        user.last_heartbeat = datetime.now()
    reg = db.query(ClientRegistration).filter(
        ClientRegistration.computer_name == data.computer_name
    ).first()
    if reg:
        reg.computer_ip = data.computer_ip
        reg.file_service_port = data.file_service_port
        reg.file_share_path = data.file_share_path
        reg.status = "active"
        reg.last_heartbeat = datetime.now()
    else:
        db.add(ClientRegistration(
            user_id=user.id if user else 1,
            computer_name=data.computer_name,
            computer_ip=data.computer_ip,
            file_service_port=data.file_service_port,
            file_share_path=data.file_share_path,
            status="active",
            last_heartbeat=datetime.now(),
        ))
    db.commit()
    return {"status": "success"}


@router.post("/heartbeat")
def heartbeat(data: HeartbeatRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.computer_name == data.computer_name,
        User.computer_ip == data.computer_ip,
    ).first()
    if user:
        user.is_online = True
        user.last_heartbeat = datetime.now()
        db.commit()
    return {"status": "success"}
