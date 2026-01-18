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

load_dotenv() # .env 파일 로드

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# [NEW] JWT 보안 설정 (실제 배포 시엔 .env에 넣는 것이 좋습니다)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-should-be-very-secure") # .env에 SECRET_KEY 추가 권장
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 토큰 만료 시간 (24시간)

# --- 1. 초기 설정 ---
MONGO_URI = MONGO_URI.strip()

# 모델 설정
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(
    'gemini-3-flash-preview',
    generation_config={"response_mime_type": "application/json"}
)

# MongoDB 연결
client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["Onion_Project"]
diary_collection = db["diaries"]
user_collection = db["users"]
report_collection = db["life_reports"]
music_collection = db["musics"]
image_collection = db["images"]

# [NEW] 비밀번호 해싱 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# [NEW] OAuth2 스키마 (토큰 URL 설정)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# [NEW] 현재 로그인한 유저 가져오기 (Dependency)
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

# --- [DTO] 데이터 모델 ---

# [NEW] 회원가입 요청 모델
class UserCreate(BaseModel):
    user_id: str
    password: str

# [NEW] 토큰 응답 모델
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str # 클라이언트 편의를 위해 user_id도 같이 반환

# --- [DTO] 요청 데이터 모델 (422 에러 해결의 핵심!) ---

# 1. 일기 작성 요청 (필수 항목 대거 추가됨)
class DiaryRequest(BaseModel):
    user_id: str
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
    user_id: str
    title: Optional[str] = None      
    content: Optional[str] = None
    entry_date: Optional[str] = None
    entry_time: Optional[str] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    tags: Optional[List[str]] = None

# 3. 인생 지도 요청
class LifeMapRequest(BaseModel):
    user_id: str
    period_months: int = 12

# 4. 음악 추가 요청
class UserProfileImageRequest(BaseModel):
    user_id: str
    image_url: str

# 5. 태그 삭제 요청
class TagDeleteRequest(BaseModel):
    user_id: str
    tag_name: str

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
    cleaned_text = re.sub(r'<img[^>]*>', '', diary_text)
    
    # !!! 중요: 여기에 system_instruction 내용이 반드시 있어야 합니다 !!!
    system_instruction = """
        Role Definition: You are "Onion," an empathetic and insightful AI psychological analyst. 
        Your goal is to peel back the layers of the user's conscious thoughts. 
        **Crucially, you must balance identifying subconscious triggers with celebrating the user's resilience and strengths.**
        You provide analysis based on Cognitive Behavioral Therapy (CBT) AND Positive Psychology principles. 
        You use a warm, polite, and professional tone (Korean honorifics, 존댓말).

        Input Data:
        Diary Entry: The user's daily journal text.
        User Traits (Context): Existing personality keywords.

        Task Instructions: 
        1. **Determine the Sentiment:** First, assess if the entry is predominantly positive, neutral, or negative.
        2. **Adaptive Analysis:** - **If Positive/Resolved:** Focus on *why* the user felt good. Identify their strengths, successful coping mechanisms, and core values. Do NOT invent problems.
           - **If Negative/Unresolved:** Use CBT to identify cognitive distortions and schemas.
        3. Generate a JSON response following the strict structure below.
        4. Score the Big Five (OCEAN) personality traits (0-10) for this specific entry.

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

        JSON Structure:
        {
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
        Reasoning: User feels humiliated (Surface). Fear of unemployment links to 'Catastrophizing' and 'Low Self-Esteem' (Deep). The pattern is 'Validation Seeking' vs. 'Fear of Failure'.
        Output Generation: (Return the JSON structure in Korean based on this reasoning).
"""


    traits_context = ', '.join(user_traits) if user_traits else "None"
    user_input = f"Diary Entry: {cleaned_text}\nUser Traits (Context): {traits_context}"
    
    for attempt in range(retries + 1):
        try:
            response = model.generate_content([system_instruction, user_input])
            clean_json = re.sub(r"```json|```", "", response.text).strip()
            data = json.loads(clean_json)
            if all(k in data for k in ["analysis", "recommend", "keywords", "big5"]):
                return data
        except Exception as e:
            if attempt < retries: time.sleep(1)
    return None

# --- 장기 분석 함수 ---
async def get_long_term_analysis(diary_history: str, data_count: int):
    analysis_focus = "Focus on Deep Patterns."
    if data_count < 10: analysis_focus = "Focus on short-term changes."
    
    system_instruction = f"""
    Role: Onion Master. Analyze diary history. {analysis_focus}
    Output JSON: {{ "deep_patterns": [...], "seasonality": "...", "growth_evaluation": "...", "life_keywords": [...], "advice_for_future": "..." }}
    """
    try:
        response = model.generate_content([system_instruction, diary_history])
        clean_json = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean_json)
    except: return None

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

# --- [API 0] 회원가입 & 로그인 (NEW!) ---

@app.post("/signup", response_model=Token)
async def signup(user: UserCreate):
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
        "profile_image": ""
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
async def analyze_and_save(request: DiaryRequest, background_tasks: BackgroundTasks):
    try:
        # -------------------------------------------------------------
        # [CASE 1] 임시 저장 (is_temporary == True)
        # -------------------------------------------------------------
        if request.is_temporary:
            print(f"INFO: Saving DRAFT for user_id: {request.user_id}")
            
            draft_data = {
                "user_id": request.user_id,
                "title": request.title,        # [NEW] 제목 저장
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
                    {"_id": ObjectId(request.diary_id), "user_id": request.user_id},
                    {"$set": draft_data}
                )
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Draft not found")
                saved_id = request.diary_id
            else:
                draft_data["created_at"] = datetime.utcnow()
                result = diary_collection.insert_one(draft_data)
                saved_id = str(result.inserted_id)

            return {
                "status": "draft_saved",
                "message": "임시 저장되었습니다.",
                "diary_id": saved_id,
                "is_temporary": True
            }

        # -------------------------------------------------------------
        # [CASE 2] 최종 제출 (여기가 핵심!)
        # -------------------------------------------------------------
        
        # 1. 유저 컨텍스트 로드 (최소한의 정보만 가져오기)
        # 통계 업데이트용 데이터는 여기서 계산 안 함! AI한테 줄 정보만 가져옴
        user_profile = user_collection.find_one({"user_id": request.user_id}, {"trait_counts": 1})
        
        existing_traits_list = []
        if user_profile:
            existing_traits_list = list(user_profile.get("trait_counts", {}).keys())
        
        # 2. Gemini 분석 (가장 오래 걸림 - 어쩔 수 없음)
        analysis_result = await get_gemini_analysis(request.content, existing_traits_list)
        if not analysis_result:
             raise HTTPException(status_code=500, detail="AI Analysis Failed")

        # 3. 결과 파싱
        new_big5 = analysis_result.get("big5") or {}
        new_ai_keywords = analysis_result.get("keywords") or []

        # 4. 일기 데이터 저장 (Insert는 빠름)
        final_data = {
            "user_id": request.user_id,
            "title": request.title,
            "content": request.content,
            "entry_date": request.entry_date,
            "entry_time": request.entry_time,
            "mood": request.mood,
            "weather": request.weather,
            "tags": request.tags,
            "is_temporary": False,
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
                {"_id": ObjectId(request.diary_id), "user_id": request.user_id},
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
        background_tasks.add_task(
            update_user_stats_bg, 
            request.user_id, 
            new_ai_keywords, 
            request.tags, 
            new_big5
        )

        # 5. 사용자에게 바로 응답 (통계 업데이트 기다리지 않음!)
        return {
            "status": "success", 
            "message": "저장 완료 (분석 결과 도착)",
            "diary_id": saved_id,
            "analysis": analysis_result
            # 주의: 응답에 total_big5_scores가 빠짐 (바로 계산 안 하니까). 
            # 프론트에서 그래프는 이번 분석값(snapshot)으로 보여주거나, 
            # 통계 페이지 들어갈 때 다시 로딩하게 하면 됨.
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [API 2] 일기 수정 ---
@app.patch("/diaries/{diary_id}")
async def update_diary_content(diary_id: str, request: DiaryUpdateRequest):
    try:
        if not ObjectId.is_valid(diary_id):
            raise HTTPException(status_code=400, detail="Invalid ID")

        old_diary = diary_collection.find_one({"_id": ObjectId(diary_id), "user_id": request.user_id})
        if not old_diary:
            raise HTTPException(status_code=404, detail="Diary not found")

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
                user_profile = user_collection.find_one({"user_id": request.user_id})
                if user_profile:
                    tag_counts = Counter(user_profile.get("user_tag_counts", {}))
                    tag_counts.subtract(old_tags)
                    tag_counts.update(new_tags)
                    tag_counts = {k: v for k, v in tag_counts.items() if v > 0}
                    
                    user_collection.update_one(
                        {"user_id": request.user_id},
                        {"$set": {"user_tag_counts": tag_counts}}
                    )
            update_fields["tags"] = new_tags

        diary_collection.update_one(
            {"_id": ObjectId(diary_id)},
            {"$set": update_fields}
        )

        return {"status": "success", "message": "Updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- [API 3] 유저 정보 조회 ---
@app.get("/user/stats/{user_id}")
async def get_user_stats(user_id: str):
    user_profile = user_collection.find_one({"user_id": user_id})
    if not user_profile:
        return {
            "user_id": user_id, 
            "message": "New User",
            "mood_stats": {"week": {}, "month": {}, "all": {}} # 빈 통계 리턴
        }

    joined_at = user_profile.get("joined_at")
    service_days = 0
    if joined_at:
        if isinstance(joined_at, str): joined_at = datetime.fromisoformat(joined_at)
        service_days = (datetime.utcnow() - joined_at).days + 1

    # 기분 통계 계산 함수 호출
    mood_stats = calculate_mood_statistics(user_id)

    user_profile["_id"] = str(user_profile["_id"])

    return {
        "user_id": user_profile["user_id"],
        "big5_scores": user_profile.get("big5_scores", get_default_big5()),
        "ai_trait_counts": user_profile.get("trait_counts", {}),
        "user_tag_counts": user_profile.get("user_tag_counts", {}),
        "service_days": service_days,
        "mood_stats": mood_stats
    }

# --- [API 4] 인생 지도 분석 ---
@app.post("/analyze-life-map")
async def analyze_life_map(request: LifeMapRequest):
    try:
        print(f"INFO: Starting Life Map analysis for {request.user_id}")

        # 1. MongoDB에서 일기 가져오기
        cursor = diary_collection.find({"user_id": request.user_id}).sort("created_at", 1)
        diaries = list(cursor)

        if not diaries:
            return {"status": "error", "message": "분석할 일기가 없습니다."}
        
        if len(diaries) < 3:
            return {
                "status": "fail", 
                "message": "데이터가 너무 적습니다. 일기를 3개 이상 작성한 후 다시 시도해주세요."
            }

        # 2. 텍스트 변환
        full_context = ""
        for d in diaries:
            date_val = d.get("created_at", datetime.utcnow())
            date_str = date_val.strftime("%Y-%m-%d")
            content = d.get("content", "")
            full_context += f"[{date_str}] {content}\n"

        # 3. Gemini 분석 요청
        report_result = await get_long_term_analysis(full_context, len(diaries))

        if not report_result:
             raise HTTPException(status_code=500, detail="Gemini generated an empty report.")

        # 4. 저장
        report_data = {
            "user_id": request.user_id,
            "created_at": datetime.utcnow(),
            "period_months": request.period_months,
            "diary_count": len(diaries),
            "result": report_result
        }
        db["life_reports"].insert_one(report_data)

        return {
            "status": "success",
            "message": "인생 지도 분석 완료",
            "data": report_result
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/life-map/{user_id}")
async def get_life_map(user_id: str):
    # (기존 코드와 동일)
    report = db["life_reports"].find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if not report: return {"status": "empty"}
    report["_id"] = str(report["_id"])
    return report

# --- [API 5] 음악 파일 업로드 (덮어쓰기 모드) ---
@app.post("/user/music/upload")
async def upload_music(
    user_id: str = Form(...),
    title: str = Form(...),
    artist: str = Form(...),
    category: str = Form("calm"),
    file: UploadFile = File(...)
):
    try:
        file_content = await file.read()
        # 15MB 제한
        if len(file_content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Limit is 15MB.")

        # [NEW] 1. 기존 음악 삭제 (덮어쓰기 효과)
        # 이 유저가 올린 음악이 있다면 싹 지웁니다.
        music_collection.delete_many({"user_id": user_id})

        # 2. 새 음악 저장
        music_doc = {
            "user_id": user_id,
            "title": title,
            "artist": artist,
            "category": category,
            "file_data": Binary(file_content), 
            "content_type": file.content_type,
            "uploaded_at": datetime.utcnow()
        }
        
        result = music_collection.insert_one(music_doc)
        new_music_id = str(result.inserted_id)
        
        # [NEW] 프론트엔드가 바로 쓸 수 있는 URL 생성
        new_music_url = f"/user/music/stream/{new_music_id}"
        
        return {
            "status": "success", 
            "message": "Music uploaded successfully (Overwritten)", 
            "music_id": new_music_id,
            "music_url": new_music_url # 👈 프론트엔드 편의를 위해 추가
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
@app.get("/user/music/list/{user_id}")
async def get_user_music_list(user_id: str):
    try:
        # file_data 제외하고 가져오기 (속도 향상)
        cursor = music_collection.find({"user_id": user_id}, {"file_data": 0})
        user_musics = []
        for doc in cursor:
            # 재생 URL 생성
            music_url = f"/user/music/stream/{str(doc['_id'])}"
            user_musics.append({
                "_id": str(doc["_id"]),
                "title": doc["title"],
                "artist": doc["artist"],
                "category": doc.get("category", "calm"),
                "url": music_url,
                "is_default": False
            })
            
        # 유저 음악이 없으면 기본 음악 리스트 반환
        if not user_musics:
            return {"user_id": user_id, "musics": DEFAULT_MUSIC_LIST, "is_default": True}
            
        return {"user_id": user_id, "musics": user_musics, "is_default": False}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- [API 8] 일기 목록 ---
@app.get("/diaries/{user_id}")
async def get_user_diaries(user_id: str):
    cursor = diary_collection.find({"user_id": user_id}).sort("entry_date", -1)
    diaries = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        diaries.append(doc)
    return {"diaries": diaries}

# --- [API 5.5] 이미지 파일 업로드 (덮어쓰기 모드) ---
@app.post("/user/image/upload")
async def upload_image(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_content = await file.read()
        # 5MB 제한
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Limit is 5MB.")

        # [핵심] 기존 이미지 삭제 (덮어쓰기 효과)
        # 이 유저가 올린 이미지가 있다면 싹 지웁니다.
        image_collection.delete_many({"user_id": user_id})

        # 새 이미지 저장
        image_doc = {
            "user_id": user_id,
            "filename": file.filename,
            "file_data": Binary(file_content),
            "content_type": file.content_type,
            "uploaded_at": datetime.utcnow()
        }
        
        # 'images'라는 별도 컬렉션에 저장
        result = image_collection.insert_one(image_doc)
        
        # 프론트에서 바로 쓸 수 있는 이미지 주소 생성
        image_url = f"/user/image/stream/{str(result.inserted_id)}"
        
        return {
            "status": "success", 
            "message": "Image uploaded successfully (Overwritten)",
            "image_url": image_url 
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
async def update_profile_image(request: UserProfileImageRequest):
    try:
        # 디버깅용 로그
        print(f"INFO: Request to update profile image for user: {request.user_id}")
        print(f"INFO: New Image URL: {request.image_url}")
        
        # 유저가 존재하는지 확인
        user = user_collection.find_one({"user_id": request.user_id})
        
        # 유저 정보 업데이트 (이미지 주소 저장)
        result = user_collection.update_one(
            {"user_id": request.user_id}, 
            {"$set": {"profile_image": request.image_url}}, 
            upsert=True
        )
        
        print(f"INFO: Update success. Matched: {result.matched_count}, Modified: {result.modified_count}")
        return {"status": "success", "message": "Profile image updated successfully"}
        
    except Exception as e:
        print(f"CRITICAL ERROR in update_profile_image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

# --- [API 9.1] 프로필 이미지 주소 조회 ---
@app.get("/user/profile-image/{user_id}")
async def get_profile_image(user_id: str):
    try:
        user = user_collection.find_one({"user_id": user_id}, {"profile_image": 1})
        
        # 1. 유저 정보가 있고, 프로필 이미지가 설정되어 있다면 -> 그 이미지 반환
        if user and user.get("profile_image"): 
            return {"image_url": user["profile_image"]}
            
        # 2. 유저가 없거나, 이미지가 비어있다면("") -> 디폴트 이미지 반환
        else: 
            return {"image_url": DEFAULT_IMAGE_URL} 
            
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 9.2] 프로필 이미지 초기화 (디폴트로 복귀) ---
@app.delete("/user/profile-image")
async def reset_profile_image(user_id: str = Form(...)): # 또는 JSON 바디 사용
    try:
        # DB에서 이미지 필드를 빈 값("")으로 변경 -> 조회 시 자동으로 디폴트가 됨
        result = user_collection.update_one(
            {"user_id": user_id},
            {"$set": {"profile_image": ""}}
        )
        
        # 기존에 업로드했던 이미지 파일도 삭제 (용량 절약)
        image_collection.delete_many({"user_id": user_id})
        
        return {
            "status": "success", 
            "message": "Reset to default image",
            "image_url": DEFAULT_IMAGE_URL
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [API 10] 태그 삭제 및 'unsorted'로 대체 ---
@app.delete("/user/tags")
async def delete_and_replace_tag(request: TagDeleteRequest):
    try:
        # "unsorted" 태그 자체를 삭제하려는 경우 차단
        if request.tag_name == "unsorted":
            raise HTTPException(status_code=400, detail="Cannot delete the default 'unsorted' tag.")

        print(f"INFO: Deleting tag '{request.tag_name}' for user {request.user_id}")

        # 1. 유저 프로필(통계) 업데이트
        # 삭제할 태그의 카운트를 가져와서 'unsorted'에 더해줍니다.
        user = user_collection.find_one({"user_id": request.user_id})
        if user:
            tag_counts = user.get("user_tag_counts", {})
            count_to_move = tag_counts.get(request.tag_name, 0)

            if count_to_move > 0:
                # (1) 기존 태그 삭제 ($unset) 및 (2) unsorted 카운트 증가 ($inc)
                user_collection.update_one(
                    {"user_id": request.user_id},
                    {
                        "$unset": {f"user_tag_counts.{request.tag_name}": ""},
                        "$inc": {"user_tag_counts.unsorted": count_to_move}
                    }
                )

        # 2. 일기 데이터 업데이트 (Bulk Update)
        # 해당 태그를 가진 모든 일기를 찾아서 처리합니다.
        
        # 단계 2-1: 해당 태그가 있는 일기에 'unsorted' 태그 추가 ($addToSet은 중복 방지됨)
        diary_collection.update_many(
            {"user_id": request.user_id, "tags": request.tag_name},
            {"$addToSet": {"tags": "unsorted"}}
        )

        # 단계 2-2: 해당 태그 삭제 ($pull)
        result = diary_collection.update_many(
            {"user_id": request.user_id, "tags": request.tag_name},
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