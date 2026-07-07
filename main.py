from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

import models, schemas, auth
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Antigravity API", version="2.0.0")

# --- Auth Routes ---
@app.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Device Routes ---
@app.post("/devices/", response_model=schemas.AntigravityDeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device: schemas.AntigravityDeviceCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    new_device = models.AntigravityDevice(**device.model_dump(), user_id=current_user.id)
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

@app.get("/users/me/devices", response_model=List[schemas.AntigravityDeviceResponse])
def read_user_devices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return current_user.devices

@app.get("/devices/", response_model=List[schemas.AntigravityDeviceResponse])
def read_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # This might be an admin route or open to all. The prompt doesn't strictly say to protect GET /devices/.
    # But usually GET all is allowed. I'll leave it open, but /users/me/devices gets only user's.
    devices = db.query(models.AntigravityDevice).offset(skip).limit(limit).all()
    return devices

@app.put("/devices/{id}", response_model=schemas.AntigravityDeviceResponse)
def update_device(
    id: int, 
    device_update: schemas.AntigravityDeviceCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    device = db.query(models.AntigravityDevice).filter(models.AntigravityDevice.id == id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        
    if device.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this device")
        
    for key, value in device_update.model_dump().items():
        setattr(device, key, value)
        
    db.commit()
    db.refresh(device)
    return device

@app.delete("/devices/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    device = db.query(models.AntigravityDevice).filter(models.AntigravityDevice.id == id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        
    if device.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this device")
        
    db.delete(device)
    db.commit()
    return None
