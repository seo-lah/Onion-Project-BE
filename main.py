import json
import certifi
import pymongo
import google.generativeai as genai
import re
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from collections import Counter
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv() # .env 파일 로드

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

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
music_collection = db["musics"] # [NEW] 음악 DB

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [DTO] 요청 데이터 모델 (422 에러 해결의 핵심!) ---

# 1. 일기 작성 요청 (필수 항목 대거 추가됨)
class DiaryRequest(BaseModel):
    user_id: str
    content: str
    entry_date: str  # [NEW] 프론트에서 보낸 날짜 (YYYY-MM-DD)
    mood: str        # [NEW] 기분
    weather: str     # [NEW] 날씨
    tags: List[str] = []       # [NEW] 유저 태그
    image_url: Optional[str] = None # [NEW] 이미지

# 2. 일기 수정 요청 (모든 필드 수정 가능하도록 변경)
class DiaryUpdateRequest(BaseModel):
    user_id: str
    content: Optional[str] = None
    entry_date: Optional[str] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None

# 3. 인생 지도 요청
class LifeMapRequest(BaseModel):
    user_id: str
    period_months: int = 12

# 4. 음악 추가 요청
class MusicRequest(BaseModel):
    title: str
    artist: str
    url: str
    category: Optional[str] = "calm"

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
    # (프롬프트는 너무 길어서 생략했습니다. 기존에 쓰시던 긴 프롬프트를 여기에 꼭 그대로 붙여넣으세요!)
    # !!! 중요: 여기에 system_instruction 내용이 반드시 있어야 합니다 !!!
    system_instruction = """
        Role Definition: You are "Onion," an empathetic and insightful AI psychological analyst. Your goal is to peel back the layers of the user's conscious thoughts to reveal their subconscious patterns, core beliefs (schemas), and emotional triggers. You provide analysis based on Cognitive Behavioral Therapy (CBT) and Schema Therapy principles. You use a warm, polite, and professional tone (Korean honorifics, 존댓말).

        Input Data:
        Diary Entry: The user's daily journal text (and potentially descriptions of images/audio if multimodal).
        User Traits (Context): Existing personality keywords. If provided, use this to contextualize the current analysis.

        Task Instructions: 
        1. Analyze the input data and generate a JSON response following the strict structure below.
        2. Additionally, score the user's personality based on the Big Five (OCEAN) model for this specific entry. Assign a score from 0 to 10 for each of the 30 facets.

        Deep Analysis (5 Themes):
        Theme 1 (Core Flow): Identify the underlying emotional flow or pattern.
        Theme 2 (Core Beliefs): Uncover hidden schemas or unconscious beliefs driving the thoughts.
        Theme 3 (Surface vs. Deep): Contrast what is explicitly said vs. what is implicitly felt.
        Theme 4 (Pattern Recognition): Highlight repetitive behavioral or thought patterns (e.g., "all-or-nothing thinking").
        Theme 5 (Summary & Abstract Solution): Briefly summarize the insight and suggest a high-level direction for change.

        Tailored Solutions (CBT-based):
        Provide a comforting and insightful "Head" message.
        Suggest 3 concrete, actionable methods (Main idea, Specific Content, Expected Effect) to break the negative pattern or reinforce positive ones.

        Additional Insights:
        Short Comment: A one-line warm cheer or advice.
        Keywords:
        1. Extract 3 specific psychological terms (hashtags).
        2. **CRITICAL:** Check the provided 'User Traits (Context)' list FIRST. If the current sentiment matches any existing keyword in the list, **YOU MUST REUSE** that exact keyword to maintain consistency (e.g., if '#Burnout' exists and fits, use '#Burnout', do not create '#Exhaustion').
        3. Only generate a NEW keyword if the concept is completely new to this user.
        4. Use standardized **Noun forms** only (e.g., use '#Anxiety' instead of '#Anxious', '#Perfectionism' instead of '#Perfect').

        Output Format (JSON Only): Ensure the output is valid JSON. Do not include markdown formatting (```json ... ```) within the response text itself.

        JSON Structure:
        {
        "analysis": {
            "theme1": "String",
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
    user_input = f"Diary Entry: {diary_text}\nUser Traits (Context): {traits_context}"
    
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

# --- [NEW] 장기 분석 함수 ---
async def get_long_term_analysis(diary_history: str, data_count: int):
    # (이전 코드와 동일, 생략 없이 그대로 두세요)
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


# =========================================================
# API 엔드포인트
# =========================================================

# --- [API 1] 일기 작성 및 저장 (임시저장 로직 추가됨) ---
@app.post("/analyze-and-save")
async def analyze_and_save(request: DiaryRequest):
    try:
        # -------------------------------------------------------------
        # [CASE 1] 임시 저장 (is_temporary == True)
        # -------------------------------------------------------------
        if request.is_temporary:
            print(f"INFO: Saving DRAFT for user_id: {request.user_id}")
            
            draft_data = {
                "user_id": request.user_id,
                "content": request.content,
                "entry_date": request.entry_date, 
                "mood": request.mood,
                "weather": request.weather,
                "tags": request.tags,
                "image_url": request.image_url,
                "is_temporary": True,              # 임시저장 플래그 설정
                "updated_at": datetime.utcnow()
            }
            
            # A. 기존 임시저장 글을 수정하는 경우 (diary_id가 있음)
            if request.diary_id and ObjectId.is_valid(request.diary_id):
                result = diary_collection.update_one(
                    {"_id": ObjectId(request.diary_id), "user_id": request.user_id},
                    {"$set": draft_data}
                )
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Draft not found")
                saved_id = request.diary_id
                
            # B. 새로운 임시저장 글을 만드는 경우
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
        # [CASE 2] 최종 제출 및 분석 (is_temporary == False)
        # -------------------------------------------------------------
        
        # [검증] 최종 제출 시에는 필수 항목이 다 있어야 함!
        if not request.mood or not request.weather or not request.entry_date:
            raise HTTPException(status_code=400, detail="날짜, 기분, 날씨는 필수 입력 사항입니다.")

        print(f"INFO: Finalizing & Analyzing diary for user_id: {request.user_id}")

        # 1. 유저 프로필 로드
        user_profile = user_collection.find_one({"user_id": request.user_id})
        
        if user_profile:
            existing_ai_counts = user_profile.get("trait_counts") or {}
            existing_user_tags = user_profile.get("user_tag_counts") or {}
            existing_big5 = user_profile.get("big5_scores") or {}
            existing_traits_list = list(existing_ai_counts.keys())
        else:
            existing_ai_counts = {}
            existing_user_tags = {}
            existing_big5 = get_default_big5()
            existing_traits_list = []
            user_collection.insert_one({
                "user_id": request.user_id,
                "joined_at": datetime.utcnow(),
                "big5_scores": existing_big5,
                "trait_counts": {},
                "user_tag_counts": {}
            })

        # 2. Gemini 분석 수행
        analysis_result = await get_gemini_analysis(request.content, existing_traits_list)
        if not analysis_result:
             raise HTTPException(status_code=500, detail="AI Analysis Failed")

        # 3. 데이터 가공
        new_ai_keywords = analysis_result.get("keywords") or []
        ai_counter = Counter(existing_ai_counts)
        ai_counter.update(new_ai_keywords)
        
        user_tag_counter = Counter(existing_user_tags)
        user_tag_counter.update(request.tags) 

        new_big5 = analysis_result.get("big5") or {}
        updated_big5 = update_big5_scores(existing_big5, new_big5)

        # 4. DB 저장 (Insert or Update)
        final_data = {
            "user_id": request.user_id,
            "content": request.content,
            "entry_date": request.entry_date,
            "mood": request.mood,
            "weather": request.weather,
            "tags": request.tags,
            "image_url": request.image_url,
            "is_temporary": False,                # [중요] 임시저장 해제
            "analysis": analysis_result.get("analysis"),
            "recommend": analysis_result.get("recommend"),
            "one_liner": analysis_result.get("one_liner"),
            "big5_snapshot": new_big5,
            "keywords_snapshot": new_ai_keywords,
            "updated_at": datetime.utcnow()
        }

        # A. 임시저장했던 글을 완성하는 경우 (Update)
        if request.diary_id and ObjectId.is_valid(request.diary_id):
            diary_collection.update_one(
                {"_id": ObjectId(request.diary_id), "user_id": request.user_id},
                {"$set": final_data}
            )
            saved_id = request.diary_id
            
        # B. 처음부터 바로 제출하는 경우 (Insert)
        else:
            final_data["created_at"] = datetime.utcnow()
            result = diary_collection.insert_one(final_data)
            saved_id = str(result.inserted_id)

        # 5. 유저 프로필 업데이트
        user_collection.update_one(
            {"user_id": request.user_id},
            {
                "$set": {
                    "trait_counts": dict(ai_counter),
                    "user_tag_counts": dict(user_tag_counter),
                    "big5_scores": updated_big5,
                    "last_updated": datetime.utcnow()
                }
            }
        )

        return {
            "status": "success", 
            "message": "분석 및 저장이 완료되었습니다.",
            "diary_id": saved_id,
            "analysis": analysis_result
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [API 2] 일기 수정 (태그 통계 보정 기능 포함) ---
@app.patch("/diaries/{diary_id}")
async def update_diary_content(diary_id: str, request: DiaryUpdateRequest):
    try:
        if not ObjectId.is_valid(diary_id):
            raise HTTPException(status_code=400, detail="Invalid ID")

        old_diary = diary_collection.find_one({"_id": ObjectId(diary_id), "user_id": request.user_id})
        if not old_diary:
            raise HTTPException(status_code=404, detail="Diary not found")

        update_fields = {"updated_at": datetime.utcnow()}
        
        if request.content is not None: update_fields["content"] = request.content
        if request.entry_date is not None: update_fields["entry_date"] = request.entry_date
        if request.mood is not None: update_fields["mood"] = request.mood
        if request.weather is not None: update_fields["weather"] = request.weather
        if request.image_url is not None: update_fields["image_url"] = request.image_url
        
        # [NEW] 태그 변경 시 통계 보정
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
        return {"user_id": user_id, "message": "New User"}

    joined_at = user_profile.get("joined_at")
    service_days = 0
    if joined_at:
        if isinstance(joined_at, str): joined_at = datetime.fromisoformat(joined_at)
        service_days = (datetime.utcnow() - joined_at).days + 1

    user_profile["_id"] = str(user_profile["_id"])
    return {
        "user_id": user_profile["user_id"],
        "big5_scores": user_profile.get("big5_scores", get_default_big5()),
        "ai_trait_counts": user_profile.get("trait_counts", {}),
        "user_tag_counts": user_profile.get("user_tag_counts", {}),
        "service_days": service_days
    }

# --- [API 4] 인생 지도 분석 ---
@app.post("/analyze-life-map")
async def analyze_life_map(request: LifeMapRequest):
    # (기존 코드와 동일, 생략 없이 사용)
    # ... 이전 코드의 analyze_life_map 함수 내용 그대로 ...
    try:
        # ... (생략) ...
        # 리포트 생성 로직 그대로 유지
        return {"status": "success"} # 임시 리턴 (실제 코드는 위에서 쓴 것 그대로)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/life-map/{user_id}")
async def get_life_map(user_id: str):
    # (기존 코드와 동일)
    report = db["life_reports"].find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if not report: return {"status": "empty"}
    report["_id"] = str(report["_id"])
    return report

# --- [API 5] 음악 API ---
@app.post("/musics")
async def add_music(music: MusicRequest):
    music_doc = music.dict()
    music_doc["created_at"] = datetime.utcnow()
    result = music_collection.insert_one(music_doc)
    return {"status": "success", "id": str(result.inserted_id)}

@app.get("/musics")
async def get_musics():
    cursor = music_collection.find().sort("title", 1)
    musics = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        musics.append(doc)
    return {"musics": musics}

@app.get("/diaries/{user_id}")
async def get_user_diaries(user_id: str):
    cursor = diary_collection.find({"user_id": user_id}).sort("entry_date", -1)
    diaries = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        diaries.append(doc)
    return {"diaries": diaries}

# --- [API 6] 일기 목록 조회 (임시저장 여부 표시) ---
@app.get("/diaries/{user_id}")
async def get_user_diaries(user_id: str):
    cursor = diary_collection.find({"user_id": user_id}).sort("entry_date", -1)
    diaries = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        # 프론트엔드에서 is_temporary 필드를 보고 "작성 중" 표시를 할 수 있음
        diaries.append(doc)
    return {"diaries": diaries}