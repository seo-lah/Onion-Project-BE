import json
import certifi
import pymongo
import google.generativeai as genai
import re
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Response, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict
from collections import Counter
import os
from dotenv import load_dotenv
from bson import ObjectId
from bson.binary import Binary
from passlib.context import CryptContext # 비밀번호 해싱
from jose import JWTError, jwt # JWT 토큰
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import requests # [추가] HTTP 요청용
import threading # [추가] 백그라운드 실행용

load_dotenv() # .env 파일 로드

GENAI_API_KEY_1 = os.getenv("GENAI_API_KEY")
GENAI_API_KEY_2 = os.getenv("GENAI_API_KEY_2")
MONGO_URI = os.getenv("MONGO_URI")

API_KEYS = [key for key in [GENAI_API_KEY_1, GENAI_API_KEY_2] if key]

if not API_KEYS:
    raise ValueError("No GENAI_API_KEY found in environment variables.")


# JWT 보안 설정 (실제 배포 시엔 .env에 넣는 것이 좋습니다)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-should-be-very-secure") # .env에 SECRET_KEY 추가 권장
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 토큰 만료 시간 (24시간)

# 총괄 리포트 월간 제한 횟수
LIFE_MAP_MONTHLY_LIMIT = 2

# --- 1. 초기 설정 ---
MONGO_URI = MONGO_URI.strip()

# 모델 설정
#genai.configure(api_key=API_KEYS[0])
#model = genai.GenerativeModel(
#    'gemini-3-flash-preview',
#    generation_config={"response_mime_type": "application/json"}
#)

# MongoDB 연결
client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["Onion_Project"]
diary_collection = db["diaries"]
user_collection = db["users"]
report_collection = db["life_reports"]
music_collection = db["musics"]
image_collection = db["images"]

# 비밀번호 해싱 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 스키마 (토큰 URL 설정)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()

# --- [Security] HTTP/3(QUIC) 강제 연결 방지 미들웨어 ---
# 브라우저가 불안정한 UDP(QUIC) 통신을 시도하지 않도록 Alt-Svc 헤더를 삭제합니다.
class DisableHTTP3Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Alt-Svc 헤더가 있다면 삭제하여 브라우저의 QUIC 업그레이드 시도를 차단
        if "Alt-Svc" in response.headers:
            del response.headers["Alt-Svc"]
        return response

# 2. 미들웨어 적용
app.add_middleware(DisableHTTP3Middleware)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex="https://.*\.ngrok-free\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [Static] 기본 음악 파일 제공 설정 ---
if not os.path.exists("static/music"):
    os.makedirs("static/music", exist_ok=True)
if not os.path.exists("static/images"):
    os.makedirs("static/images", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- [Constants] 기본 음악 리스트 ---
DEFAULT_MUSIC_LIST = [
    {
        "_id": "default",
        "title": "Onion Standard",
        "artist": "Onion",
        "url": "/static/music/standard.mp3", # 프론트엔드는 이 URL로 재생
        "is_default": True
    }
]
DEFAULT_IMAGE_URL = "/static/images/default_bg.jpg"

# --- [Helper] 보안 함수 ---
def verify_password(plain_password, hashed_password):
    # 검증 시에도 72바이트 제한에 걸릴 수 있으므로 안전하게 처리
    # (passlib 버전에 따라 verify 내부에서 처리해주기도 하지만, 명시적으로 자르는 게 안전합니다)
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password):
    # [FIX] Bcrypt는 72바이트 제한이 있으므로, 초과 시 앞부분만 잘라서 해싱합니다.
    return pwd_context.hash(password[:72])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 현재 로그인한 유저 가져오기 (Dependency)
# 이 함수를 API의 파라미터로 넣으면, 토큰을 검사해서 유저 ID를 반환해줍니다.
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user_id

# --- [Helper] Gemini 호출 Fallback 함수 ---
async def call_gemini_with_fallback(prompt_parts, response_type="application/json", model_name="gemini-3-flash-preview"):
    """
    API 키를 순회하며 Gemini 호출.
    Args:
        model_name: 기본값은 'gemini-3-flash-preview'. 
                    챗봇 등에서 'gemini-2.0-flash-lite-preview' 등을 지정해서 사용 가능.
    """

    # 안전 필터 해제 (가장 낮은 수준으로 설정)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    for i, api_key in enumerate(API_KEYS):
        try:
            genai.configure(api_key=api_key)
            
            # [수정됨] 전달받은 model_name 사용
            current_model = genai.GenerativeModel(
                model_name,
                generation_config={"response_mime_type": response_type}
            )

            print(f"INFO: Trying {model_name} with Key {i+1}...") 
            response = current_model.generate_content(
                prompt_parts, 
                safety_settings=safety_settings
            )
            
            # 3. 응답 확인
            try:
                if response.text: 
                    return response
            except ValueError:
                print(f"⚠️ WARNING: Response blocked by Safety Filters (Key {i+1})")
                continue # 다음 키로 시도하거나 넘어감
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ WARNING: API Key {i+1} failed: {error_msg}")
            
            if "429" in error_msg or "ResourceExhausted" in error_msg or "403" in error_msg:
                print(f"🔄 Switching to next API Key...")
                continue
            
            continue
            
    print("❌ CRITICAL: All API keys exhausted or Content Blocked.")
    return None

# --- [Helper] 이미지 OCR Fallback 함수 ---
async def extract_text_from_image_with_fallback(image_path: str):
    """
    이미지를 업로드하고 텍스트를 추출합니다. 
    API 키 제한(429) 발생 시 다음 키로 전환하여 처음부터(업로드부터) 다시 시도합니다.
    """
    system_instruction = "You are a helpful assistant that transcribes handwritten notes into text. Output ONLY the transcribed text."
    prompt = system_instruction

    for i, api_key in enumerate(API_KEYS):
        uploaded_file = None
        try:
            # 1. 키 설정
            genai.configure(api_key=api_key)
            
            # 2. 모델 재설정 (키 변경 반영을 위해)
            local_model = genai.GenerativeModel(
                'gemini-3-flash-preview',
                generation_config={"response_mime_type": "text/plain"} # 텍스트만 받음
            )

            # 3. 파일 업로드 (해당 키의 공간에 업로드됨)
            print(f"INFO: Uploading image to Gemini with Key {i+1}...")
            uploaded_file = genai.upload_file(path=image_path)

            # 4. 분석 요청
            response = local_model.generate_content([prompt, uploaded_file])
            return response.text

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ WARNING: OCR failed with Key {i+1}: {error_msg}")
            
            # 리소스 부족 에러면 다음 키로 시도, 아니면 에러
            if "429" in error_msg or "ResourceExhausted" in error_msg or "403" in error_msg:
                continue
            else:
                # 파일 포맷 문제 등일 수 있으므로 로그 찍고 다음 키 시도 (혹은 중단)
                continue 
        
        finally:
            # 5. Gemini 서버 용량 관리를 위해 업로드한 파일 삭제
            if uploaded_file:
                try: 
                    uploaded_file.delete()
                    print(f"INFO: Deleted remote file for Key {i+1}")
                except: pass

    return None


# --- [DTO] 데이터 모델 ---

# [NEW] 회원가입 요청 모델
class UserCreate(BaseModel):
    user_id: str
    password: str

# 토큰 응답 모델
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

# 1. 일기 작성 요청 (필수 항목 대거 추가됨)
class DiaryRequest(BaseModel):
    #user_id: str
    content: str
    title: Optional[str] = None
    entry_date: Optional[str] = None 
    entry_time: Optional[str] = None
    mood: Optional[str] = None       
    weather: Optional[str] = None    
    tags: List[str] = []             
    is_temporary: bool = False       
    diary_id: Optional[str] = None

# 2. 일기 수정 요청
class DiaryUpdateRequest(BaseModel):
    #user_id: str
    title: Optional[str] = None      
    content: Optional[str] = None
    entry_date: Optional[str] = None
    entry_time: Optional[str] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    tags: Optional[List[str]] = None

# 3. 인생 지도 요청
class LifeMapRequest(BaseModel):
    #user_id: str
    period_months: int = 12

# 4. 음악 추가 요청
class UserProfileImageRequest(BaseModel):
    #user_id: str
    image_url: str

# 5. 태그 삭제 요청
class TagDeleteRequest(BaseModel):
    #user_id: str
    tag_name: str

# --- 미니 챗봇 요청 모델 (수정됨) ---
class DiaryChatRequest(BaseModel):
    #user_id: str
    diary_ids: List[str] # [변경] 일기 ID를 리스트로 받음 (최대 3개)
    user_message: str
    chat_history: List[Dict[str, str]] = [] # [{"role": "user", "text": "..."}, ...]

# --- [Helper] Big5 초기값 ---
def get_default_big5():
    default_score = 5
    return {
        "openness": { "imagination": default_score, "artistic": default_score, "emotionality": default_score, "adventurousness": default_score, "intellect": default_score, "liberalism": default_score },
        "conscientiousness": { "self_efficacy": default_score, "orderliness": default_score, "dutifulness": default_score, "achievement_striving": default_score, "self_discipline": default_score, "cautiousness": default_score },
        "extraversion": { "friendliness": default_score, "gregariousness": default_score, "assertiveness": default_score, "activity_level": default_score, "excitement_seeking": default_score, "cheerfulness": default_score },
        "agreeableness": { "trust": default_score, "morality": default_score, "altruism": default_score, "cooperation": default_score, "modesty": default_score, "sympathy": default_score },
        "neuroticism": { "anxiety": default_score, "anger": default_score, "depression": default_score, "self_consciousness": default_score, "immoderation": default_score, "vulnerability": default_score }
    }

# --- [Helper] Big5 업데이트 ---
def update_big5_scores(old_scores, new_scores, alpha=0.2):
    old_scores = old_scores or {}
    new_scores = new_scores or {}
    factors = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
    facets_list = {
        "openness": ["imagination", "artistic", "emotionality", "adventurousness", "intellect", "liberalism"],
        "conscientiousness": ["self_efficacy", "orderliness", "dutifulness", "achievement_striving", "self_discipline", "cautiousness"],
        "extraversion": ["friendliness", "gregariousness", "assertiveness", "activity_level", "excitement_seeking", "cheerfulness"],
        "agreeableness": ["trust", "morality", "altruism", "cooperation", "modesty", "sympathy"],
        "neuroticism": ["anxiety", "anger", "depression", "self_consciousness", "immoderation", "vulnerability"]
    }
    updated = {}
    for factor in factors:
        updated[factor] = {}
        factor_old = old_scores.get(factor) or {}
        factor_new = new_scores.get(factor) or {}
        for facet in facets_list[factor]:
            try: old_val = float(factor_old.get(facet, 5.0))
            except: old_val = 5.0
            try: new_val = float(factor_new.get(facet, old_val))
            except: new_val = old_val
            updated[factor][facet] = round((old_val * (1 - alpha)) + (new_val * alpha), 2)
    return updated

# --- [Gemini] 분석 함수 ---
async def get_gemini_analysis(diary_text: str, user_traits: List[str], retries=2):
    # 1. [NEW] 이미지 데이터(Base64) 추출 로직
    # 일기 본문에서 <img src="data:image/..."> 패턴을 찾아냅니다.
    image_parts = []
    
    # 정규표현식: data:image/jpeg;base64,뒷부분코드... 를 잡습니다.
    # HTML src 속성 안의 따옴표(") 전까지를 캡처합니다.
    img_matches = re.findall(r'data:(image\/[^;]+);base64,([^"]+)', diary_text)
    
    for mime_type, base64_data in img_matches:
        # Gemini API는 딕셔너리 형태로 이미지 데이터를 받습니다.
        image_parts.append({
            "mime_type": mime_type,
            "data": base64_data
        })
    
    if image_parts:
        print(f"INFO: {len(image_parts)} image(s) detected in diary for Multimodal Analysis.")
    
    cleaned_text = re.sub(r'<[^>]+>', '', diary_text).strip()
    
    # !!! 중요: 여기에 system_instruction 내용이 반드시 있어야 합니다 !!!
    system_instruction = """
        Role Definition: You are "Onion," an empathetic and insightful AI psychological analyst. 
        Your goal is to peel back the layers of the user's conscious thoughts. 
        **Crucially, you must balance identifying subconscious triggers with celebrating the user's resilience and strengths.**
        You provide analysis based on Cognitive Behavioral Therapy (CBT) AND Positive Psychology principles. 
        You use a warm, polite, and professional tone (**Your Output MUST be in English.**).

        Input Data:
        Diary Entry: The user's daily journal text (and optional images).
        User Traits (Context): Existing personality keywords.

        Task Instructions: 
        1. **Event Extraction (CRITICAL STEP):** Before analyzing emotions, extract the **main objective event** (What happened?) in 1 concise sentence. 
           - Rule: Remove subjective emotions and focus strictly on the facts. 
           - Example: (Input: "I felt terrible because I failed the exam.") -> (Output: "Took an exam and received a failing grade.")
        2. **Determine the Sentiment:** Assess if the entry is predominantly positive, neutral, or negative.
        3. **Adaptive Analysis:** - **If Positive/Resolved:** Focus on *why* the user felt good. Identify their strengths, successful coping mechanisms, and core values. Do NOT invent problems.
           - **If Negative/Unresolved:** Use CBT to identify cognitive distortions and schemas.
        4. **Image Analysis (If provided):** If an image is present, analyze its mood, content, and connection to the text. Use visual cues to deepen the psychological insight (e.g., a messy room might indicate stress, a clear sky might indicate hope).
        5. Generate a JSON response following the strict structure below.
        6. Score the Big Five (OCEAN) personality traits (0-10) for this specific entry.

        Deep Analysis (5 Themes):
        Theme 1 (Core Flow): Identify the underlying emotional flow (e.g., Satisfaction, Anxiety, Relief).
        Theme 2 (Core Beliefs & Values): Uncover hidden schemas OR affirm positive core values demonstrated (e.g., "I am capable").
        Theme 3 (Surface vs. Deep): Contrast explicit words with implicit feelings. **If they match well, acknowledge the user's emotional honesty.**
        Theme 4 (Pattern Recognition): Highlight repetitive patterns. If the user broke a bad habit or handled a situation well, explicitly praise this change.
        Theme 5 (Summary & Direction): Summarize the insight. If the user already solved the problem in the diary, **validate their solution** instead of offering a new one.

        Tailored Solutions (Action & Growth):
        Provide a comforting and insightful "Head" message.
        Suggest 3 concrete methods. **The nature of these methods depends on the diary's content:**
        - **If the diary is Positive/Success:** Suggest ways to **sustain** this mood, **reward** themselves, or **apply this success** to other areas (Reinforcement).
        - **If the diary is Negative/Struggle:** Suggest ways to **break** the pattern or **soothe** the emotion (Correction).
        
        **Structure for Methods:** { "main": "Main Idea", "content": "Specific Action", "effect": "Expected Positive Outcome" }

        Additional Insights:
        Short Comment: A one-line warm cheer or advice.
        Keywords:
        1. Extract 3 specific psychological terms (hashtags).
        2. **CRITICAL:** Check the 'User Traits (Context)' list. Reuse existing keywords if applicable.
        3. **Balance:** Include positive psychological terms if appropriate (e.g., #SelfEfficacy, #Resilience, #Gratitude) alongside clinical terms.
        4. Use standardized **Noun forms** only.

        Output Format (JSON Only): Ensure the output is valid JSON. Do not include markdown formatting.
        **All text values in JSON must be in English.**

        JSON Structure:
        {
        "event_summary": "String (KEY: A factual, one-sentence summary of the event itself, devoid of emotion)",
        "analysis": {
            "theme1": "String",
            "theme2_title": "String", 
            "theme2": "String",        
            "theme3": "String",
            "theme4": "String",
            "theme5": "String"
        },
        "recommend": {
            "head": "String",
            "method1": { "main": "String", "content": "String", "effect": "String" },
            "method2": { "main": "String", "content": "String", "effect": "String" },
            "method3": { "main": "String", "content": "String", "effect": "String" }
        },
        "one_liner": "String",
        "keywords": ["String", "String", "String"],
        "big5": {
            "openness": { "imagination": int, "artistic": int, "emotionality": int, "adventurousness": int, "intellect": int, "liberalism": int },
            "conscientiousness": { "self_efficacy": int, "orderliness": int, "dutifulness": int, "achievement_striving": int, "self_discipline": int, "cautiousness": int },
            "extraversion": { "friendliness": int, "gregariousness": int, "assertiveness": int, "activity_level": int, "excitement_seeking": int, "cheerfulness": int },
            "agreeableness": { "trust": int, "morality": int, "altruism": int, "cooperation": int, "modesty": int, "sympathy": int },
            "neuroticism": { "anxiety": int, "anger": int, "depression": int, "self_consciousness": int, "immoderation": int, "vulnerability": int }
        }
        }

        Few-Shot Example (Mental Chain of Thought):
        Input: "I hate my boss. He always criticizes me in front of everyone. I just want to quit, but I'm scared I won't find another job." + (User Trait: Low Self-Esteem)
        Reasoning: 
        - Event: Received public criticism from the boss at work. (Fact only)
        - Emotion: Humiliation, Fear, Resentment.
        - Analysis: User feels humiliated (Surface). Fear of unemployment links to 'Catastrophizing' and 'Low Self-Esteem' (Deep). The pattern is 'Validation Seeking' vs. 'Fear of Failure'.
        Output Generation: (Return the JSON structure in English based on this reasoning).
"""


    traits_context = ', '.join(user_traits) if user_traits else "None"
    user_input = f"Diary Entry: {cleaned_text}\nUser Traits (Context): {traits_context}"
    
    # 4. [NEW] 프롬프트 구성 (텍스트 + 이미지 리스트)
    # 기본적으로 시스템 지시문과 유저 텍스트를 넣습니다.
    prompt_parts = [system_instruction, user_input]
    
    # 이미지가 있다면 리스트 뒤에 추가합니다. (Gemini는 이렇게 주면 알아서 멀티모달로 인식합니다)
    if image_parts:
        prompt_parts.extend(image_parts)

    # [FIX] 단순 model.generate_content 대신 Fallback 함수 사용
    for attempt in range(retries + 1):
        try:
            # Fallback 함수 호출 (알아서 키 바꿔가며 시도함)
            response = await call_gemini_with_fallback(prompt_parts, response_type="application/json")
            
            if response:
                clean_json = re.sub(r"```json|```", "", response.text).strip()
                data = json.loads(clean_json)
                if all(k in data for k in ["analysis", "recommend", "keywords", "big5"]):
                    return data
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < retries: time.sleep(1)
            
    return None

# --- [Helper] 장기 분석 함수 (Event & Growth Focused) ---
async def get_long_term_analysis_rag(context_data: str, data_count: int):
    
    system_instruction = """
    Role: You are an "Insightful AI Psychological Profiler."
    
    Goal: Analyze the user's diary timeline provided in the format: Date | Mood | [EVENT] | [PSYCHOLOGY].
    Your ultimate goal is to answer the user's subconscious question: "Who am I really, and how have I changed?"
    
    **Analysis Guidelines (Deep Dive):**
    1. **Identify the 'Trigger-Reaction' Loop:** Don't just list events. Find what specifically triggers the user's emotions (e.g., Criticism, Loneliness, Failure) and identify their habitual reaction pattern.
    2. **Uncover the Narrative Arc:** How has the user's *perspective* on the world changed? 
       - (e.g., From "The world is scary" to "I can handle this", OR from "I am ambitious" to "I am burnt out".)
    3. **No Toxic Positivity:** If the user is stagnating or regressing, state it objectively. Validating their struggle is more helpful than false hope.
    4. **Connect the Dots:** Explicitly link a past event to a current behavior using the [EVENT] and [PSYCHOLOGY] tags in the input.

    **Output JSON Structure & Content Guide:**
    **All values must be in English.**
    {
        "major_events_timeline": [
            "String (Format: 'YYYY-MM: [Event Summary] - [Brief Impact]'. Select the top 3-5 most significant events/turning points that shaped the user's narrative.)",
            "String",
            "String"
        ],
        "deep_patterns": [
            "String. (Identify a hidden psychological habit. e.g., 'You tend to seek validation from others when stressed.')",
            "String. (Identify a recurring emotional cycle.)",
            "String. (Identify a coping mechanism they use often.)"
        ], 
        "past_vs_present": "String. (The Narrative Arc. Contrast the 'Past You' vs 'Current You'. Focus on changes in *Values*, *Attitude*, and *Emotional Stability*. Be specific about what has changed and what has remained the same.)",
        "change_analysis": "String. (Diagnosis of their current state. Are they in a period of 'Growth', 'Rest', 'Burnout', or 'Turmoil'? Explain why based on the data.)",
        "life_keywords": ["Keyword1", "Keyword2", "Keyword3", "Keyword4", "Keyword5"],
        "advice_for_future": "String. (One actionable piece of advice based on their patterns. If they are doing well, tell them how to sustain it. If they are struggling, suggest a small perspective shift. Do NOT give generic advice like 'Cheer up'.)"
    }
    
    Tone: Professional, Analytical, Deep, and Warm English.
    """
    
    try:
        # Fallback 함수 사용하여 안정성 확보
        response = await call_gemini_with_fallback([system_instruction, context_data])
        
        if response:
            clean_json = re.sub(r"```json|```", "", response.text).strip()
            return json.loads(clean_json)
    except Exception as e:
        print(f"Analysis Error: {e}")
        return None

# --- 백그라운드 작업 함수 (뒤에서 몰래 계산할 녀석) ---
def update_user_stats_bg(user_id: str, new_keywords: List[str], new_tags: List[str], new_big5: dict):
    try:
        # 1. 유저 프로필 다시 로드 (최신 상태)
        user_profile = user_collection.find_one({"user_id": user_id})
        if not user_profile: return

        # 2. 통계 계산 (무거운 작업)
        # (1) AI 키워드 누적
        existing_ai_counts = user_profile.get("trait_counts") or {}
        ai_counter = Counter(existing_ai_counts)
        ai_counter.update(new_keywords)

        # (2) 유저 태그 누적
        existing_user_tags = user_profile.get("user_tag_counts") or {}
        user_tag_counter = Counter(existing_user_tags)
        user_tag_counter.update(new_tags)

        # (3) Big5 점수 재계산
        existing_big5 = user_profile.get("big5_scores") or get_default_big5()
        updated_big5 = update_big5_scores(existing_big5, new_big5)

        # 3. DB 업데이트 (느린 작업)
        user_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "trait_counts": dict(ai_counter),
                    "user_tag_counts": dict(user_tag_counter),
                    "big5_scores": updated_big5,
                    "last_updated": datetime.utcnow()
                }
            }
        )
        print(f"INFO: [Background] User stats updated for {user_id}")
        
    except Exception as e:
        print(f"ERROR: [Background] Failed to update stats: {e}")

# --- 기분 통계 계산 헬퍼 함수 ---
def calculate_mood_statistics(user_id: str):
    # 1. 임시저장이 아닌(is_temporary=False) 일기의 날짜와 기분만 가져옴
    cursor = diary_collection.find(
        {"user_id": user_id, "is_temporary": False},
        {"entry_date": 1, "mood": 1, "_id": 0}
    )

    stats = {
        "week": Counter(),  # 최근 7일
        "month": Counter(), # 최근 30일
        "all": Counter()    # 전체 기간
    }

    # 현재 날짜 (시간은 버리고 날짜만 비교)
    today = datetime.utcnow().date()

    for doc in cursor:
        mood = doc.get("mood")
        date_str = doc.get("entry_date") # YYYY-MM-DD 형식

        if not mood or not date_str:
            continue

        try:
            # 문자열("2024-01-16") -> 날짜 객체로 변환
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # 며칠 전인지 계산 (오늘 - 일기날짜)
            days_diff = (today - entry_date).days

            # 1. 전체 기간 카운트
            stats["all"][mood] += 1

            # 2. 최근 30일 (0일~30일 전)
            if 0 <= days_diff <= 30:
                stats["month"][mood] += 1

            # 3. 최근 7일 (0일~7일 전)
            if 0 <= days_diff <= 7:
                stats["week"][mood] += 1
                
        except ValueError:
            continue # 날짜 형식이 이상하면 무시

    # Counter 객체를 dict로 변환해서 리턴
    return {k: dict(v) for k, v in stats.items()}

# =========================================================
# API 엔드포인트
# =========================================================

# --- [API: Server Keep-alive] 서버 생존 확인용 ---
@app.get("/health")
def health_check():
    return {"status": "alive", "timestamp": datetime.utcnow()}

# --- [API 0] 회원가입 & 로그인 (NEW!) ---

@app.post("/signup", response_model=Token)
async def signup(user: UserCreate):
    # [디버깅] 서버가 받은 비밀번호를 콘솔에 찍어봅니다.
    #print(f"DEBUG: Received Password: {user.password}") 
    #print(f"DEBUG: Password Length: {len(user.password)}")

    # 1. 이미 존재하는 ID인지 확인
    if user_collection.find_one({"user_id": user.user_id}):
        raise HTTPException(status_code=400, detail="User ID already exists")
    
    # 2. 비밀번호 해싱 (암호화)
    hashed_password = get_password_hash(user.password)
    
    # 3. 유저 정보 저장 (초기값 포함)
    new_user = {
        "user_id": user.user_id,
        "hashed_password": hashed_password,
        "joined_at": datetime.utcnow(),
        "big5_scores": get_default_big5(),
        "trait_counts": {},
        "user_tag_counts": {},
        "saved_musics": [],
        "profile_image": "",
        "life_map_usage": {"month": datetime.utcnow().strftime("%Y-%m"), "count": 0}
    }
    user_collection.insert_one(new_user)
    
    # 4. 바로 로그인 처리 (토큰 발급)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_id}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.user_id}

@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm은 username, password 필드를 가집니다.
    # 여기서는 username을 user_id로 사용합니다.
    user = user_collection.find_one({"user_id": form_data.username})
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect user ID or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 토큰 발급
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["user_id"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer", "user_id": user["user_id"]}

# --- [API 1] 일기 작성 및 저장 ---
@app.post("/analyze-and-save")
async def analyze_and_save(request: DiaryRequest, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    try:
        # -------------------------------------------------------------
        # [CASE 1] 임시 저장 (is_temporary == True)
        # -------------------------------------------------------------
        if request.is_temporary:
            print(f"INFO: Saving DRAFT for user_id: {current_user}")
            
            draft_data = {
                "user_id": current_user,
                "title": request.title,
                "content": request.content,
                "entry_date": request.entry_date, 
                "entry_time": request.entry_time, 
                "mood": request.mood,
                "weather": request.weather,
                "tags": request.tags,
                "is_temporary": True,
                "updated_at": datetime.utcnow()
            }
            
            if request.diary_id and ObjectId.is_valid(request.diary_id):
                result = diary_collection.update_one(
                    {"_id": ObjectId(request.diary_id), "user_id": current_user},
                    {"$set": draft_data}
                )
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Draft not found")
                saved_id = request.diary_id
            else:
                draft_data["created_at"] = datetime.utcnow()
                result = diary_collection.insert_one(draft_data)
                saved_id = str(result.inserted_id)

            background_tasks.add_task(update_user_stats_bg, current_user, [], request.tags, {})
            return {"status": "draft_saved", "message": "임시 저장되었습니다.", "diary_id": saved_id, "is_temporary": True}

        # -------------------------------------------------------------
        # [CASE 2] 최종 제출 (여기가 핵심!)
        # -------------------------------------------------------------
        
        # 1. 유저 컨텍스트 로드 (최소한의 정보만 가져오기)
        # 통계 업데이트용 데이터는 여기서 계산 안 함! AI한테 줄 정보만 가져옴
        user_profile = user_collection.find_one({"user_id": current_user}, {"trait_counts": 1})
        
        existing_traits_list = list(user_profile.get("trait_counts", {}).keys()) if user_profile else []
        
        # 2. Gemini 분석 (가장 오래 걸림 - 어쩔 수 없음)
        analysis_result = await get_gemini_analysis(request.content, existing_traits_list)
        if not analysis_result:
             raise HTTPException(status_code=500, detail="AI Analysis Failed")

        # 3. 결과 파싱
        new_big5 = analysis_result.get("big5") or {}
        new_ai_keywords = analysis_result.get("keywords") or []

        # 사건 요약 추출 (없으면 one_liner라도 가져와서 채움)
        extracted_event = analysis_result.get("event_summary", "")
        if not extracted_event:
            extracted_event = analysis_result.get("one_liner", "")

        # 4. 일기 데이터 저장 (Insert는 빠름)
        final_data = {
            "user_id": current_user,
            "title": request.title,
            "content": request.content,
            "entry_date": request.entry_date,
            "entry_time": request.entry_time,
            "mood": request.mood,
            "weather": request.weather,
            "tags": request.tags,
            "is_temporary": False,
            "event_summary": extracted_event,
            "analysis": analysis_result.get("analysis"),
            "recommend": analysis_result.get("recommend"),
            "one_liner": analysis_result.get("one_liner"),
            "big5_snapshot": new_big5,
            "keywords_snapshot": new_ai_keywords,
            "updated_at": datetime.utcnow()
        }

        saved_id = None
        
        if request.diary_id and ObjectId.is_valid(request.diary_id):
            diary_collection.update_one(
                {"_id": ObjectId(request.diary_id), "user_id": current_user},
                {"$set": final_data}
            )
            saved_id = request.diary_id
        else:
            final_data["created_at"] = datetime.utcnow()
            result = diary_collection.insert_one(final_data)
            saved_id = str(result.inserted_id)

        # ---------------------------------------------------------
        # [핵심] 무거운 통계 업데이트는 "나중에 해!" 하고 넘겨버림
        # ---------------------------------------------------------
        background_tasks.add_task(update_user_stats_bg, current_user, new_ai_keywords, request.tags, new_big5)

        # 5. 사용자에게 바로 응답 (통계 업데이트 기다리지 않음!)
        return {"status": "success", "message": "저장 완료", "diary_id": saved_id, "analysis": analysis_result}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [API 2] 일기 수정 ---
@app.patch("/diaries/{diary_id}")
async def update_diary_content(diary_id: str, request: DiaryUpdateRequest, current_user: str = Depends(get_current_user)):
    try:
        if not ObjectId.is_valid(diary_id):
            raise HTTPException(status_code=400, detail="Invalid ID")

        old_diary = diary_collection.find_one({"_id": ObjectId(diary_id), "user_id": current_user})
        if not old_diary:   raise HTTPException(status_code=404, detail="Diary not found")

        update_fields = {"updated_at": datetime.utcnow()}
        if request.title is not None: update_fields["title"] = request.title # [NEW] 제목 수정
        if request.content is not None: update_fields["content"] = request.content
        if request.entry_date is not None: update_fields["entry_date"] = request.entry_date
        if request.entry_time is not None: update_fields["entry_time"] = request.entry_time
        if request.mood is not None: update_fields["mood"] = request.mood
        if request.weather is not None: update_fields["weather"] = request.weather
        
        if request.tags is not None:
            old_tags = old_diary.get("tags", [])
            new_tags = request.tags
            
            if set(old_tags) != set(new_tags):
                user_profile = user_collection.find_one({"user_id": current_user})
                if user_profile:
                    tag_counts = Counter(user_profile.get("user_tag_counts", {}))
                    tag_counts.subtract(old_tags)
                    tag_counts.update(new_tags)
                    tag_counts = {k: v for k, v in tag_counts.items() if v > 0}
                    
                    user_collection.update_one(
                        {"user_id": current_user},
                        {"$set": {"user_tag_counts": tag_counts}}
                    )
            update_fields["tags"] = new_tags

        diary_collection.update_one({"_id": ObjectId(diary_id)}, {"$set": update_fields})
        return {"status": "success", "message": "Updated successfully"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- [API 3] 유저 정보 조회 ---
@app.get("/user/stats")
async def get_user_stats(current_user: str = Depends(get_current_user)):
    user_profile = user_collection.find_one({"user_id": current_user})
    if not user_profile:
        return {"user_id": current_user, "message": "New User", "mood_stats": {"week": {}, "month": {}, "all": {}}}

    joined_at = user_profile.get("joined_at")
    service_days = 0
    if joined_at:
        if isinstance(joined_at, str): joined_at = datetime.fromisoformat(joined_at)
        service_days = (datetime.utcnow() - joined_at).days + 1

    # 기분 통계 계산 함수 호출
    mood_stats = calculate_mood_statistics(current_user)
    user_profile["_id"] = str(user_profile["_id"])

    # 총괄 리포트 사용량 로직
    current_month = datetime.utcnow().strftime("%Y-%m")
    usage_data = user_profile.get("life_map_usage", {"month": current_month, "count": 0})
    if usage_data["month"] != current_month:
        usage_data = {"month": current_month, "count": 0}

    print(f"DEBUG: user_profile found for {current_user}") 
    print(f"DEBUG: service_days = {service_days}")

    return {
        "user_id": user_profile["user_id"],
        "big5_scores": user_profile.get("big5_scores", get_default_big5()),
        "ai_trait_counts": user_profile.get("trait_counts", {}),
        "user_tag_counts": user_profile.get("user_tag_counts", {}),
        "service_days": service_days,
        "mood_stats": mood_stats,
        "life_map_usage": usage_data,           # 현재 사용량 전달
        "life_map_limit": LIFE_MAP_MONTHLY_LIMIT # 전체 한도 전달
    }

# --- [API 4] 인생 지도 분석 (Timeline-Flow: 과거 vs 현재 균형 분석) ---
@app.post("/analyze-life-map")
async def analyze_life_map(request: LifeMapRequest, current_user: str = Depends(get_current_user)):
    try:
        print(f"INFO: Starting Life Map analysis for {current_user}")

        # ▼▼▼ [NEW] 0. 유저 및 사용량 확인 & 제한 체크 ▼▼▼
        user = user_collection.find_one({"user_id": current_user})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        current_month = datetime.utcnow().strftime("%Y-%m")
        usage_data = user.get("life_map_usage", {"month": current_month, "count": 0})

        # 월이 바뀌었으면 초기화
        if usage_data["month"] != current_month:
            usage_data = {"month": current_month, "count": 0}

        # 횟수 제한 체크 (이미 다 썼으면 429 에러)
        if usage_data["count"] >= LIFE_MAP_MONTHLY_LIMIT:
             raise HTTPException(
                status_code=429, # Too Many Requests
                detail=f"이번 달 총괄 리포트 생성 한도({LIFE_MAP_MONTHLY_LIMIT}회)를 초과했습니다."
            )

        # 1. 모든 일기 가져오기 (오래된 순)
        # 필요한 필드(특히 analysis)만 가져와서 최적화
        cursor = diary_collection.find(
            {"user_id": current_user},
            {
                "entry_date": 1, 
                "content": 1, 
                "mood": 1, 
                "event_summary": 1,
                "keywords_snapshot": 1, 
                "one_liner": 1,
                "analysis": 1, # [핵심] 심리 분석 데이터 포함
                "_id": 0
            }
        ).sort("entry_date", 1)
        diaries = list(cursor)

        if not diaries: return {"status": "error", "message": "분석할 일기가 없습니다."}
        if len(diaries) < 3: return {"status": "fail", "message": "데이터가 너무 적습니다. 최소 3개 이상의 일기가 필요합니다."}

        # 2. [Context Building] 사건(Fact)과 심리(Feeling)의 분리 구성
        full_context = "--- User's Life Timeline ---\n"
        for d in diaries:
            date_str = d.get("entry_date", "Unknown")
            mood = d.get("mood", "Neutral")
            
            # (1) 사건 정보 추출
            event_text = d.get("event_summary")
            if not event_text:
                event_text = d.get("one_liner")
            if not event_text:
                event_text = d.get("content", "")[:50] + "..." 

            # (2) 심리 정보 추출 [수정됨: Theme 4 포함!]
            analysis_data = d.get("analysis", {})
            if analysis_data:
                # 감정 흐름 / 핵심 신념 / 행동 패턴까지 모두 포함
                psych_text = (
                    f"Emotion: {analysis_data.get('theme1', '')} / "
                    f"Belief: {analysis_data.get('theme2', '')} / "
                    f"Pattern: {analysis_data.get('theme4', '')}"
                )
            else:
                psych_text = f"Summary: {d.get('one_liner', 'No deep analysis')}"

            # (3) AI에게 줄 최종 라인 조립
            line = f"Date: {date_str} | Mood: {mood} | [EVENT]: {event_text} | [PSYCHOLOGY]: {psych_text}"
            
            full_context += line + "\n"

        # 3. Gemini 분석 요청
        report_result = await get_long_term_analysis_rag(full_context, len(diaries))

        if not report_result:
             raise HTTPException(status_code=500, detail="Gemini generated an empty report.")

        # 4. 저장
        report_data = {
            "user_id": current_user,
            "created_at": datetime.utcnow(),
            "period_type": "ALL_TIME_EVENT_CENTERED", 
            "diary_count": len(diaries),
            "result": report_result
        }
        db["life_reports"].insert_one(report_data)

        # ▼▼▼ 사용 횟수 1 증가 (성공 시에만 DB 업데이트) ▼▼▼
        new_count = usage_data["count"] + 1
        user_collection.update_one(
            {"user_id": current_user},
            {"$set": {"life_map_usage": {"month": current_month, "count": new_count}}}
        )

        return {
            "status": "success",
            "message": "인생 지도 분석 완료",
            "data": report_result,
            "usage": {"current": new_count, "limit": LIFE_MAP_MONTHLY_LIMIT}
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        if "429" in str(e) or "한도" in str(e):
             raise HTTPException(status_code=429, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/life-map")
async def get_life_map(current_user: str = Depends(get_current_user)):
    report = db["life_reports"].find_one({"user_id": current_user}, sort=[("created_at", -1)])
    if not report: return {"status": "empty"}
    report["_id"] = str(report["_id"])
    return report

# --- [API 5] 음악 파일 업로드 (덮어쓰기 모드) ---
@app.post("/user/music/upload")
async def upload_music(
    title: str = Form(...),
    artist: str = Form(...),
    category: str = Form("calm"),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    try:
        file_content = await file.read()
        # 15MB 제한
        if len(file_content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Limit is 15MB.")

        # [NEW] 1. 기존 음악 삭제 (덮어쓰기 효과)
        # 이 유저가 올린 음악이 있다면 싹 지웁니다.
        music_collection.delete_many({"user_id": current_user})

        # 2. 새 음악 저장
        music_doc = {
            "user_id": current_user,
            "title": title,
            "artist": artist,
            "category": category,
            "file_data": Binary(file_content), 
            "content_type": file.content_type,
            "uploaded_at": datetime.utcnow()
        }
        
        result = music_collection.insert_one(music_doc)
        new_music_id = str(result.inserted_id)
        
        return {
            "status": "success", 
            "message": "Music uploaded successfully (Overwritten)", 
            "music_id": new_music_id,
            "music_url": f"/user/music/stream/{new_music_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- [API 6] 음악 스트리밍 (DB 재생) ---
@app.get("/user/music/stream/{music_id}")
async def stream_music(music_id: str):
    try:
        if not ObjectId.is_valid(music_id): raise HTTPException(status_code=400, detail="Invalid Music ID")
        music = music_collection.find_one({"_id": ObjectId(music_id)})
        if not music: raise HTTPException(status_code=404, detail="Music not found")
        return Response(content=music["file_data"], media_type=music.get("content_type", "audio/mpeg"))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- [API 7] 유저 음악 목록 조회 ---
@app.get("/user/music/list")
async def get_user_music_list(current_user: str = Depends(get_current_user)):
    try:
        # file_data 제외하고 가져오기 (속도 향상)
        cursor = music_collection.find({"user_id": current_user}, {"file_data": 0})
        user_musics = []
        for doc in cursor:
            # 재생 URL 생성
            user_musics.append({
                "_id": str(doc["_id"]),
                "title": doc["title"],
                "artist": doc["artist"],
                "category": doc.get("category", "calm"),
                "url": f"/user/music/stream/{str(doc['_id'])}",
                "is_default": False
            })
            
        # 유저 음악이 없으면 기본 음악 리스트 반환
        if not user_musics:
            return {"user_id": current_user, "musics": DEFAULT_MUSIC_LIST, "is_default": True}
            
        return {"user_id": current_user, "musics": user_musics, "is_default": False}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- [API 8] 일기 목록 ---
@app.get("/diaries")
async def get_user_diaries(current_user: str = Depends(get_current_user)):
    cursor = diary_collection.find({"user_id": current_user}).sort("entry_date", -1)
    diaries = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        diaries.append(doc)
    return {"diaries": diaries}

# --- [API 5.5] 이미지 파일 업로드 ---
@app.post("/user/image/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    try:
        file_content = await file.read()
        # 5MB 제한
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Limit is 5MB.")

        image_collection.delete_many({"user_id": current_user})

        # 새 이미지 저장
        image_doc = {
            "user_id": current_user,
            "filename": file.filename,
            "file_data": Binary(file_content),
            "content_type": file.content_type,
            "uploaded_at": datetime.utcnow()
        }
        
        # 'images'라는 별도 컬렉션에 저장
        result = image_collection.insert_one(image_doc)
        
        return {
            "status": "success", 
            "message": "Image uploaded successfully (Overwritten)",
            "image_url": f"/user/image/stream/{str(result.inserted_id)}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- [API 5.6] 이미지 스트리밍 (보여주기) ---
@app.get("/user/image/stream/{image_id}")
async def stream_image(image_id: str):
    try:
        if not ObjectId.is_valid(image_id): 
            raise HTTPException(status_code=400, detail="Invalid ID")
            
        image = image_collection.find_one({"_id": ObjectId(image_id)})
        if not image: 
            raise HTTPException(status_code=404, detail="Image not found")
            
        return Response(content=image["file_data"], media_type=image.get("content_type", "image/jpeg"))
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 9] 프로필 이미지 주소 저장 (2단계: 변경 확정) ---
@app.put("/user/profile-image")
async def update_profile_image(request: UserProfileImageRequest, current_user: str = Depends(get_current_user)):
    try:
        # 디버깅용 로그
        print(f"INFO: Request to update profile image for user: {current_user}")
        print(f"INFO: New Image URL: {request.image_url}")
        
        # 유저가 존재하는지 확인
        user = user_collection.find_one({"user_id": current_user})
        
        # 유저 정보 업데이트 (이미지 주소 저장)
        result = user_collection.update_one(
            {"user_id": current_user}, 
            {"$set": {"profile_image": request.image_url}}, 
            upsert=True
        )
        
        print(f"INFO: Update success. Matched: {result.matched_count}, Modified: {result.modified_count}")
        return {"status": "success", "message": "Profile image updated successfully"}
        
    except Exception as e:
        print(f"CRITICAL ERROR in update_profile_image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

# --- [API 9.1] 프로필 이미지 주소 조회 ---
@app.get("/user/profile-image")
async def get_profile_image(current_user: str = Depends(get_current_user)):
    try:
        user = user_collection.find_one({"user_id": current_user}, {"profile_image": 1})
        
        if user and user.get("profile_image"): 
            return {"image_url": user["profile_image"]}
        else: 
            return {"image_url": DEFAULT_IMAGE_URL} 
            
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 9.2] 프로필 이미지 초기화 (디폴트로 복귀) ---
@app.delete("/user/profile-image")
async def reset_profile_image(current_user: str = Depends(get_current_user)): # 또는 JSON 바디 사용
    try:
        # DB에서 이미지 필드를 빈 값("")으로 변경 -> 조회 시 자동으로 디폴트가 됨
        result = user_collection.update_one(
            {"user_id": current_user},
            {"$set": {"profile_image": ""}}
        )
        
        # 기존에 업로드했던 이미지 파일도 삭제 (용량 절약)
        image_collection.delete_many({"user_id": current_user})
        
        return {
            "status": "success", 
            "message": "Reset to default image",
            "image_url": DEFAULT_IMAGE_URL
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 10] 태그 삭제 및 'unsorted'로 대체 ---
@app.delete("/user/tags")
async def delete_and_replace_tag(request: TagDeleteRequest, current_user: str = Depends(get_current_user)):
    try:
        # "unsorted" 태그 자체를 삭제하려는 경우 차단
        if request.tag_name == "unsorted":
            raise HTTPException(status_code=400, detail="Cannot delete the default 'unsorted' tag.")

        print(f"INFO: Deleting tag '{request.tag_name}' for user {current_user}")

        # 1. 유저 프로필(통계) 업데이트
        # 삭제할 태그의 카운트를 가져와서 'unsorted'에 더해줍니다.
        user = user_collection.find_one({"user_id": current_user})
        if user:
            tag_counts = user.get("user_tag_counts", {})
            count_to_move = tag_counts.get(request.tag_name, 0)

            if count_to_move > 0:
                # (1) 기존 태그 삭제 ($unset) 및 (2) unsorted 카운트 증가 ($inc)
                user_collection.update_one(
                    {"user_id": current_user},
                    {
                        "$unset": {f"user_tag_counts.{request.tag_name}": ""},
                        "$inc": {"user_tag_counts.unsorted": count_to_move}
                    }
                )

        # 2. 일기 데이터 업데이트 (Bulk Update)
        # 해당 태그를 가진 모든 일기를 찾아서 처리합니다.
        
        # 단계 2-1: 해당 태그가 있는 일기에 'unsorted' 태그 추가 ($addToSet은 중복 방지됨)
        diary_collection.update_many(
            {"user_id": current_user, "tags": request.tag_name},
            {"$addToSet": {"tags": "unsorted"}}
        )

        # 단계 2-2: 해당 태그 삭제 ($pull)
        result = diary_collection.update_many(
            {"user_id": current_user, "tags": request.tag_name},
            {"$pull": {"tags": request.tag_name}}
        )

        return {
            "status": "success", 
            "message": f"Tag '{request.tag_name}' replaced with 'unsorted'.",
            "modified_diaries": result.modified_count
        }

    except Exception as e:
        print(f"Error in delete_tag: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 11] 일기 삭제 (Big5 유지, 태그 카운트 감소) ---
@app.delete("/diaries/{diary_id}")
async def delete_diary(diary_id: str, current_user: str = Depends(get_current_user)):
    try:
        # 1. ID 유효성 검사
        if not ObjectId.is_valid(diary_id):
            raise HTTPException(status_code=400, detail="Invalid Diary ID")

        # 2. 삭제할 일기 먼저 찾기 (태그 정보를 얻기 위해)
        target_diary = diary_collection.find_one(
            {"_id": ObjectId(diary_id), "user_id": current_user}
        )

        if not target_diary:
            raise HTTPException(status_code=404, detail="Diary not found or permission denied")

        # 3. 유저 태그 통계 업데이트
        tags_to_remove = target_diary.get("tags", [])
        if tags_to_remove:
            inc_update = {f"user_tag_counts.{tag}": -1 for tag in tags_to_remove}
            user_collection.update_one(
                {"user_id": current_user},
                {"$inc": inc_update}
            )
            
            # (선택 사항) 카운트가 0 이하가 된 태그 찌꺼기 청소
            # 굳이 안 해도 되지만, DB를 깔끔하게 유지하고 싶다면 아래 주석 해제
            # user_collection.update_one(
            #     {"user_id": user_id},
            #     {"$pull": {"user_tag_counts": {"$lte": 0}}} # 주의: 구조에 따라 쿼리 복잡해질 수 있음, 일단 생략 권장
            # )

        # 4. 일기 데이터 삭제
        delete_result = diary_collection.delete_one({"_id": ObjectId(diary_id)})

        return {
            "status": "success", 
            "message": "Diary deleted successfully",
            "deleted_count": delete_result.deleted_count,
            "removed_tags": tags_to_remove
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print(f"Error in delete_diary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 12] 손글씨 이미지 텍스트 추출 (OCR) ---
@app.post("/scan-diary")
async def scan_diary_text(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    timestamp = str(time.time()).replace(".", "") # 소수점(.)만 제거
    temp_filename = f"temp_ocr_{current_user}_{timestamp}.jpg"
    
    try:
        print(f"INFO: Receiving image for OCR from user {current_user}")
        
        # 1. 서버에 잠시 저장 (Gemini 업로드를 위해)
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        # 2. Fallback 함수 호출하여 텍스트 추출
        extracted_text = await extract_text_from_image_with_fallback(temp_filename)

        if not extracted_text:
            raise HTTPException(status_code=500, detail="Failed to extract text from image.")

        print(f"INFO: Text extracted successfully: {extracted_text[:30]}...")

        return {
            "status": "success",
            "message": "Text extracted successfully",
            "extracted_text": extracted_text.strip()
        }

    except Exception as e:
        print(f"Error in scan_diary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 3. 로컬 임시 파일 삭제 (청소)
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


# --- [API 13] 미니 챗봇 (일기 3개 선택 + 짧은 답변 + 멀티모달 지원) ---
@app.post("/chat/diary")
async def chat_about_diary(request: DiaryChatRequest, current_user: str = Depends(get_current_user)):
    try:
        # 1. 일기 개수 제한 체크 (최대 3개)
        if len(request.diary_ids) > 3:
            raise HTTPException(status_code=400, detail="You can select up to 3 diaries.")

        # 2. 일기 데이터 일괄 조회 (MongoDB $in 연산자 사용)
        obj_ids = [ObjectId(id) for id in request.diary_ids if ObjectId.is_valid(id)]
        cursor = diary_collection.find(
            {"_id": {"$in": obj_ids}, "user_id": current_user}
        )
        diaries = list(cursor)

        if not diaries:
            raise HTTPException(status_code=404, detail="No diaries found.")

        # 3. 문맥 조립 및 [이미지 추출]
        combined_context = ""
        chat_image_parts = []  # 챗봇에게 보여줄 이미지 리스트

        for i, d in enumerate(diaries):
            date = d.get("entry_date", "Unknown")
            content = d.get("content", "")
            
            # [NEW] 일기 본문에서 이미지 추출 (Base64)
            img_matches = re.findall(r'data:(image\/[^;]+);base64,([^"]+)', content)
            for mime_type, base64_data in img_matches:
                chat_image_parts.append({
                    "mime_type": mime_type,
                    "data": base64_data
                })

            # 분석 데이터 요약
            analysis = d.get("analysis", {})
            emotion = analysis.get("theme1", "Unknown")
            
            # 텍스트 문맥 구성 (이미지 태그 제거 후 텍스트만)
            clean_content = re.sub(r'<[^>]+>', '', content).strip()
            combined_context += f"[Diary {i+1} ({date})]\nContent: {clean_content}\nMain Emotion: {emotion}\n---\n"

        if chat_image_parts:
            print(f"INFO: Chatbot detected {len(chat_image_parts)} images in context.")

        # 4. 대화 기록 관리 (최근 5개 턴만 기억)
        recent_history = request.chat_history[-5:]        
        history_text = ""
        for chat in recent_history:
            role = chat.get("role", "user")
            text = chat.get("text", "")
            history_text += f"{role}: {text}\n"

        # 5. 시스템 프롬프트 (제약 조건 강화)
        system_instruction = f"""
        Role: You are "Mini Onion," a concise and warm psychological counselor.
        
        Context: The user has selected {len(diaries)} diary entries. Answer their question based on these entries.
        **The user might ask about the photos attached to these diaries. If images are provided, use them to enrich your answer.**

        **CRITICAL RESPONSE RULES:**
        1. **Separator:** You MUST use the symbol **'||'** to separate distinct sentences (This creates the chat bubbles).
        2. **Length Limit:** Answer within **50 ~ 80 characters** (including spaces). This is a hard limit.
        3. **Sentence Limit:** Use only **1 or 2 sentences**.
        4. **Tone:** Warm, supportive, conversational **English**. 
        5. **No Fluff:** Do not use greetings like "Hello". Get straight to the answer.
        
        Example Input: "I feel so tired lately."
        Example Output: "You've been working so hard. || Please take some time to rest and recharge today!"

        [Selected Diaries Context]:
        {combined_context}
        """

        final_prompt = f"{system_instruction}\n\n[Chat History (Last 5)]\n{history_text}\nUser: {request.user_message}\nMini Onion:"

        # 6. Gemini 호출 (텍스트 + 이미지 리스트 결합)
        prompt_parts = [final_prompt]
        if chat_image_parts:
            prompt_parts.extend(chat_image_parts)
            
        response = await call_gemini_with_fallback(
            prompt_parts, 
            response_type="text/plain", 
            model_name="gemini-2.5-flash-lite"
        )
        
        if not response:
             # 실패 시 폴백 메시지
             print("ERROR: Gemini returned None. Sending fallback message.")
             return {
                "status": "success",
                "messages": [
                    "Sorry, I'm a bit overwhelmed right now.",
                    "Please ask me again in a moment!"
                ]
            }

        raw_text = response.text.strip()
        
        # 7. 응답 후처리: '||' 기준으로 잘라서 리스트로 변환
        # 예: "고생했어 || 쉬자" -> ["고생했어", "쉬자"]
        messages = [msg.strip() for msg in raw_text.split("||") if msg.strip()]

        # (혹시 AI가 ||를 안 썼을 경우를 대비해, 리스트가 비어있으면 원본 통째로 넣음)
        if not messages:
            messages = [raw_text]

        return {
            "status": "success",
            "messages": messages
        }

    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# =========================================================
# [Self-Ping] Render 슬립 모드 방지 로직
# =========================================================
def run_self_ping():
    # TODO: 아래 주소를 본인의 실제 Render 배포 URL로 변경하세요!
    # 예: https://onion-project.onrender.com/health
    target_url = "https://onion-project-fqyt.onrender.com/health" 
    
    print(f"INFO: Self-ping task started for {target_url}")
    while True:
        try:
            # 10분(600초)마다 요청을 보냄 (Render 슬립 기준이 15분)
            time.sleep(600) 
            response = requests.get(target_url)
            print(f"INFO: Self-ping signal sent. Status: {response.status_code}")
        except Exception as e:
            print(f"WARNING: Self-ping failed: {e}")

# 서버 시작 시 별도 스레드(Daemon Thread)로 실행
# 메인 프로세스가 죽으면 이 스레드도 같이 죽으므로 안전합니다.
threading.Thread(target=run_self_ping, daemon=True).start()