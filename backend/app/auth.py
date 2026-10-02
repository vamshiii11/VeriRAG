from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer=HTTPBearer()

def hash_password(password:str)->str: return pwd_context.hash(password)
def verify_password(password:str, hashed:str)->bool: return pwd_context.verify(password, hashed)

def create_user(db:Session,email:str,password:str):
    user=User(id=str(uuid4()),email=email.lower().strip(),password_hash=hash_password(password))
    db.add(user); db.commit(); db.refresh(user); return user

def create_token(user:User):
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub":user.id,"email":user.email,"exp":exp},settings.jwt_secret,algorithm="HS256")

def current_user(creds:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db)):
    try: payload=jwt.decode(creds.credentials,settings.jwt_secret,algorithms=["HS256"])
    except JWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired token")
    user=db.get(User,payload.get("sub"))
    if not user: raise HTTPException(status_code=401,detail="User not found")
    return user
