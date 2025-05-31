import requests
import cv2
import numpy as np
from PIL import Image
import io
import base64
from openai import OpenAI
import time
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# 1. MJPEG 스트림에서 프레임 추출
url = "https://planty.gaeun.xyz/image_raw"
print("[1] MJPEG 스트림에서 프레임 추출 시도 (requests)")

r = requests.get(url, stream=True, timeout=20)
bytes_data = b""
frame_found = False

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
            print("[2] 프레임 추출 성공")
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            frame_found = True
            break

if not frame_found:
    raise Exception("프레임을 추출하지 못했습니다. 스트림이 정상인지 확인하세요.")

# 2. 이미지를 base64로 인코딩
print("[3] 프레임을 base64로 인코딩")
buffer = io.BytesIO()
img.save(buffer, format="JPEG")
base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
base64_image_url = f"data:image/jpeg;base64,{base64_image}"

# 4. FastAPI 서버에 POST로 저장하기 전에 plant_id로 식물 종류(type) 조회
plant_id = 4  # 실제 앱에서 사용하는 식물 id로 변경 가능
user_token = os.environ.get("USER_TOKEN")
if not user_token:
    raise Exception("USER_TOKEN 환경변수가 설정되어 있지 않습니다.")

plant_info_url = f"https://planty.gaeun.xyz/plants/{plant_id}"
headers = {"Authorization": f"Bearer {user_token}"}
plant_resp = requests.get(plant_info_url, headers=headers)
if plant_resp.status_code != 200 or not plant_resp.json().get("plant"):
    raise Exception(f"식물 정보를 불러오지 못했습니다: {plant_resp.text}")
plant_type = plant_resp.json()["plant"]["type"]

# 4. FastAPI 서버에 POST로 저장하기 전에 plant_id로 식물 종류(type) 조회
plant_id = 5  # 실제 앱에서 사용하는 식물 id로 변경 가능
user_token = os.environ.get("USER_TOKEN")
if not user_token:
    raise Exception("USER_TOKEN 환경변수가 설정되어 있지 않습니다.")

plant_info_url = f"https://planty.gaeun.xyz/plants/{plant_id}"
headers = {"Authorization": f"Bearer {user_token}"}
plant_resp = requests.get(plant_info_url, headers=headers)
if plant_resp.status_code != 200 or not plant_resp.json().get("plant"):
    raise Exception(f"식물 정보를 불러오지 못했습니다: {plant_resp.text}")
plant_type = plant_resp.json()["plant"]["type"]

# 3. OpenAI Vision API 호출 (openai 패키지 사용)
print("[4] OpenAI Vision API 호출")
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    raise Exception("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
client = OpenAI(api_key=openai_api_key)

prompt = f"이 식물({plant_type})의 건강 상태를 진단해줘. 병충해, 과습, 잎의 색 변화, 성장 상태 등을 고려해서 설명해줘."

response = client.chat.completions.create(
    model="gpt-4o",  # "gpt-4.1-mini"는 존재하지 않으므로 gpt-4o 또는 gpt-4 사용 권장
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
print("[5] GPT 분석 결과:", analysis_text)

# 4. FastAPI 서버에 POST로 저장
api_url = f"https://planty.gaeun.xyz/plants/{plant_id}/ai-analysis"
print("[6] FastAPI POST 요청 시작")
save_resp = requests.post(api_url, json={"analysis_text": analysis_text})
print("[7] POST status:", save_resp.status_code, save_resp.text)

# 5. FastAPI 서버에서 GET으로 조회 (앱에서 바로 확인 가능)
print("[8] FastAPI GET 요청 시작")
get_resp = requests.get(api_url)
print("[9] GET status:", get_resp.status_code, get_resp.text)
