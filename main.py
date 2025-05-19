from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import uvicorn
from sqlalchemy.orm import Session
from database import get_db, engine
import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Security configuration
SECRET_KEY = "your-secret-key-here"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Models
class User(BaseModel):
    userId: str
    nickname: str
    email: str

    class Config:
        from_attributes = True

class UserInDB(User):
    hashed_password: str

class LoginRequest(BaseModel):
    userId: str
    userPw: str

class SignupRequest(BaseModel):
    nickname: str
    userId: str
    userPw: str
    email: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    userData: Optional[User] = None
    requiresPlantRegistration: Optional[bool] = None

class SignupResponse(BaseModel):
    success: bool
    message: str
    errorCode: Optional[str] = None

class PlantBase(BaseModel):
    name: str
    type: str
    watering_cycle: int

class PlantCreate(PlantBase):
    pass

class Plant(PlantBase):
    id: int
    last_watered: datetime
    created_at: datetime
    owner_id: str

    class Config:
        from_attributes = True

class PlantResponse(BaseModel):
    success: bool
    message: str
    plant: Optional[Plant] = None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/auth/login", response_model=LoginResponse)
async def login(login_request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == login_request.userId).first()
    if not user:
        return LoginResponse(
            success=False,
            message="User not found",
            requiresPlantRegistration=False
        )
    
    if not verify_password(login_request.userPw, user.hashed_password):
        return LoginResponse(
            success=False,
            message="Incorrect password",
            requiresPlantRegistration=False
        )
    
    # Check if user has any plants
    has_plants = db.query(models.Plant).filter(models.Plant.owner_id == user.user_id).first() is not None
    
    access_token = create_access_token(data={"sub": user.user_id})
    return LoginResponse(
        success=True,
        message="Login successful",
        token=access_token,
        userData=User(
            userId=user.user_id,
            nickname=user.nickname,
            email=user.email
        ),
        requiresPlantRegistration=not has_plants
    )

@app.post("/auth/signup", response_model=SignupResponse)
async def signup(signup_request: SignupRequest, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(models.User).filter(models.User.user_id == signup_request.userId).first()
    if existing_user:
        return SignupResponse(
            success=False,
            message="User ID already exists",
            errorCode="USER_EXISTS"
        )
    
    # Check if email exists
    existing_email = db.query(models.User).filter(models.User.email == signup_request.email).first()
    if existing_email:
        return SignupResponse(
            success=False,
            message="Email already registered",
            errorCode="EMAIL_EXISTS"
        )
    
    hashed_password = get_password_hash(signup_request.userPw)
    new_user = models.User(
        user_id=signup_request.userId,
        nickname=signup_request.nickname,
        email=signup_request.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return SignupResponse(
        success=True,
        message="Signup successful"
    )

@app.post("/plants", response_model=PlantResponse)
async def register_plant(
    plant: PlantCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    new_plant = models.Plant(
        name=plant.name,
        type=plant.type,
        watering_cycle=plant.watering_cycle,
        owner_id=current_user.user_id
    )
    
    db.add(new_plant)
    db.commit()
    db.refresh(new_plant)
    
    return PlantResponse(
        success=True,
        message="Plant registered successfully",
        plant=new_plant
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 