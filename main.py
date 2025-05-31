from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import uvicorn
from sqlalchemy.orm import Session
from database import get_db, engine
import models
from models import PlantAIAnalysis
from sqlalchemy import desc
from ros_publisher import rgb_publisher
import cv2
import numpy as np
from PIL import Image
import io
import base64
from openai import OpenAI
import os
from dotenv import load_dotenv
import requests

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Security configuration
SECRET_KEY = "your-secret-key-here"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours instead of 30 minutes

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
    last_watered: Optional[str] = None  # ISO string from client

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

class PlantLedBase(BaseModel):
    plant_id: int
    mode: str
    r: int
    g: int
    b: int
    strength: int = 128

class PlantLedCreate(PlantLedBase):
    pass

class PlantLedResponse(BaseModel):
    success: bool
    message: str
    led: Optional[PlantLedBase] = None

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
    print(f"Received Authorization header: {authorization}")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    token = authorization.split(" ")[1]
    print(f"Extracted token: {token}")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        print(f"Decoded user_id: {user_id}")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
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
    from datetime import datetime
    last_watered_dt = None
    if plant.last_watered:
        try:
            last_watered_dt = datetime.fromisoformat(plant.last_watered)
        except Exception:
            last_watered_dt = datetime.utcnow()
    else:
        last_watered_dt = datetime.utcnow()

    new_plant = models.Plant(
        name=plant.name,
        type=plant.type,
        watering_cycle=plant.watering_cycle,
        last_watered=last_watered_dt,
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

@app.post("/auth/refresh", response_model=LoginResponse)
async def refresh_token(current_user: models.User = Depends(get_current_user)):
    access_token = create_access_token(data={"sub": current_user.user_id})
    return LoginResponse(
        success=True,
        message="Token refreshed successfully",
        token=access_token,
        userData=User(
            userId=current_user.user_id,
            nickname=current_user.nickname,
            email=current_user.email
        ),
        requiresPlantRegistration=False
    )

@app.get("/plants", response_model=List[Plant])
async def get_plants(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plants = db.query(models.Plant).filter(models.Plant.owner_id == current_user.user_id).all()
    return plants

@app.post("/plants/{plant_id}/led", response_model=PlantLedResponse)
async def set_plant_led(
    plant_id: int,
    led: PlantLedCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plant = db.query(models.Plant).filter(models.Plant.id == plant_id, models.Plant.owner_id == current_user.user_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    plant_led = db.query(models.PlantLed).filter(models.PlantLed.plant_id == plant_id).first()
    if plant_led:
        plant_led.mode = led.mode
        plant_led.r = led.r
        plant_led.g = led.g
        plant_led.b = led.b
        plant_led.strength = led.strength
    else:
        plant_led = models.PlantLed(
            plant_id=plant_id,
            mode=led.mode,
            r=led.r,
            g=led.g,
            b=led.b,
            strength=led.strength
        )
        db.add(plant_led)
    
    # Publish RGB values to ROS
    try:
        strength_ratio = led.strength / 255.0
        strength_ratio /= 2.0
        rgb_publisher.publish_rgb(
            led.r * strength_ratio,
            led.g * strength_ratio,
            led.b * strength_ratio
        )
    except Exception as e:
        print(f"Error publishing RGB values: {str(e)}")
        # Continue with database update even if ROS publishing fails
    
    db.commit()
    db.refresh(plant_led)
    return PlantLedResponse(success=True, message="LED mode updated", led=led)


@app.get("/plants/{plant_id}/led", response_model=PlantLedResponse)
async def get_plant_led(
    plant_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plant_led = db.query(models.PlantLed).join(models.Plant).filter(
        models.PlantLed.plant_id == plant_id,
        models.Plant.owner_id == current_user.user_id
    ).first()
    if not plant_led:
        return PlantLedResponse(success=False, message="No LED setting found")
    return PlantLedResponse(
        success=True,
        message="LED setting found",
        led=PlantLedBase(
            plant_id=plant_led.plant_id,
            mode=plant_led.mode,
            r=plant_led.r,
            g=plant_led.g,
            b=plant_led.b,
            strength=plant_led.strength
        )
    )

@app.get("/plants/{plant_id}/ai-analysis")
async def get_latest_plant_ai_analysis(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. MJPEG 스트림에서 프레임 추출
    url = "https://planty.gaeun.xyz/image_raw"
    try:
        r = requests.get(url, stream=True, timeout=20)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to image stream: {str(e)}")
    bytes_data = b""
    frame_found = False
    img = None
    for chunk in r.iter_content(chunk_size=1024):
        bytes_data += chunk
        a = bytes_data.find(b'\xff\xd8')  # JPEG 시작
        b = bytes_data.find(b'\xff\xd9')  # JPEG 끝
        if a != -1 and b != -1 and b > a:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]
            img_array = np.frombuffer(jpg, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is not None:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                frame_found = True
                break
    if not frame_found or img is None:
        raise HTTPException(status_code=500, detail="프레임을 추출하지 못했습니다. 스트림이 정상인지 확인하세요.")

    # 2. 이미지를 base64로 인코딩
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
    base64_image_url = f"data:image/jpeg;base64,{base64_image}"

    # 3. DB에서 plant_id로 식물 종류(type) 조회
    plant = db.query(models.Plant).filter(models.Plant.id == plant_id, models.Plant.owner_id == current_user.user_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    plant_type = plant.type

    # 4. OpenAI Vision API 호출
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
    client = OpenAI(api_key=openai_api_key)
    prompt = f"이 식물({plant_type})의 건강 상태를 진단해줘. 병충해, 과습, 잎의 색 변화, 성장 상태 등을 고려해서 설명해줘."
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        { "type": "text", "text": prompt },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": base64_image_url
                            },
                        },
                    ],
                }
            ],
            max_tokens=1024,
        )
        analysis_text = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI Vision API 호출 실패: {str(e)}")

    # 5. DB에 저장
    analysis = PlantAIAnalysis(plant_id=plant_id, analysis_text=analysis_text)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return {"success": True, "id": analysis.id, "created_at": analysis.created_at, "analysis_text": analysis.analysis_text}

@app.get("/plants/{plant_id}", response_model=PlantResponse)
async def get_plant(
    plant_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    plant = db.query(models.Plant).filter(models.Plant.id == plant_id, models.Plant.owner_id == current_user.user_id).first()
    print('plant', plant)
    if not plant:
        return PlantResponse(success=False, message="Plant not found", plant=None)
    return PlantResponse(success=True, message="Plant found", plant=plant)

# .env 파일에서 환경변수 로드
load_dotenv()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 