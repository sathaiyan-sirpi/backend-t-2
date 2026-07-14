# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Depends, HTTPException, status, Query
# pyrefly: ignore [missing-import]
from fastapi.security import OAuth2PasswordRequestForm
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List, Optional
from sqlalchemy import or_, desc, asc

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

@app.get("/devices/", response_model=schemas.AntigravityDeviceListResponse)
def read_devices(
    category: Optional[str] = Query(None, description="Exact match category filter"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price (>=)"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price (<=)"),
    search: Optional[str] = Query(None, description="Search text (partial, case-insensitive)"),
    sort_by: Optional[str] = Query(None, description="Sort field: price or created_at"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order: asc or desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=0, le=100),
    db: Session = Depends(get_db)
):
    """
    Read devices with advanced querying: filtering, search, sorting, and pagination.

    Execution order: filtering -> search -> sorting -> pagination
    """

    query = db.query(models.AntigravityDevice)

    # --- Filtering ---
    # category: exact match if field exists
    if category and hasattr(models.AntigravityDevice, "category"):
        query = query.filter(models.AntigravityDevice.category == category)

    # Determine a numeric 'price' field fallback if real 'price' not present
    price_column = None
    if hasattr(models.AntigravityDevice, "price"):
        price_column = models.AntigravityDevice.price
    elif hasattr(models.AntigravityDevice, "max_altitude"):
        # fallback mapping: treat max_altitude as 'price' for this project
        price_column = models.AntigravityDevice.max_altitude
    elif hasattr(models.AntigravityDevice, "core_stability"):
        price_column = models.AntigravityDevice.core_stability

    if min_price is not None and price_column is not None:
        query = query.filter(price_column >= min_price)
    if max_price is not None and price_column is not None:
        query = query.filter(price_column <= max_price)

    # --- Search ---
    # Detect which text fields exist on the model
    text_fields = [f for f in ("name", "title", "description") if hasattr(models.AntigravityDevice, f)]
    if search and text_fields:
        search_term = f"%{search}%"
        search_clauses = [getattr(models.AntigravityDevice, f).ilike(search_term) for f in text_fields]
        query = query.filter(or_(*search_clauses))

    # --- Sorting ---
    # Allowed sort keys mapped to actual model columns to avoid SQL injection
    allowed_sort_map = {
        "price": price_column,
        "created_at": getattr(models.AntigravityDevice, "created_at", None),
    }

    if sort_by:
        if sort_by not in allowed_sort_map or allowed_sort_map.get(sort_by) is None:
            raise HTTPException(status_code=422, detail="Invalid sort_by field.")
        sort_col = allowed_sort_map[sort_by]
        if order == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))
    else:
        # default sort by created_at desc if available
        if hasattr(models.AntigravityDevice, "created_at"):
            query = query.order_by(desc(models.AntigravityDevice.created_at))

    # --- Total count BEFORE pagination ---
    total = query.count()

    # --- Pagination ---
    results = query.offset(skip).limit(limit).all()

    return {"total": total, "skip": skip, "limit": limit, "items": results}

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
