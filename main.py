import json
import certifi
import pymongo
import google.generativeai as genai
import re
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from collections import Counter
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv() # .env 파일 로드

GENAI_API_KEY = os.getenv("GENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# --- 1. 초기 설정 (Gemini & MongoDB) ---
MONGO_URI = MONGO_URI.strip() 

# 모델 설정: gemini-1.5-flash (안정적인 버전)
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

app = FastAPI()

class DiaryRequest(BaseModel):
    user_id: str
    content: str

class LifeMapRequest(BaseModel):
    user_id: str
    period_months: int = 12  # 기본값: 최근 12개월

class DiaryUpdateRequest(BaseModel):
    user_id: str
    content: str

# --- [NEW] Big5 초기값 생성 함수 (모든 값 5.0) ---
def get_default_big5():
    """신규 유저를 위한 Big5 초기값(중간값 5.0) 생성"""
    default_score = 5
    return {
        "openness": { "imagination": default_score, "artistic": default_score, "emotionality": default_score, "adventurousness": default_score, "intellect": default_score, "liberalism": default_score },
        "conscientiousness": { "self_efficacy": default_score, "orderliness": default_score, "dutifulness": default_score, "achievement_striving": default_score, "self_discipline": default_score, "cautiousness": default_score },
        "extraversion": { "friendliness": default_score, "gregariousness": default_score, "assertiveness": default_score, "activity_level": default_score, "excitement_seeking": default_score, "cheerfulness": default_score },
        "agreeableness": { "trust": default_score, "morality": default_score, "altruism": default_score, "cooperation": default_score, "modesty": default_score, "sympathy": default_score },
        "neuroticism": { "anxiety": default_score, "anger": default_score, "depression": default_score, "self_consciousness": default_score, "immoderation": default_score, "vulnerability": default_score }
    }

# --- 2. Big5 이동 평균 업데이트 함수 (안전장치 강화 버전) ---
def update_big5_scores(old_scores, new_scores, alpha=0.2):
    """
    사용자의 성격 지표를 점진적으로 업데이트 (alpha=0.2는 20% 반영)
    None 데이터가 들어와도 에러가 나지 않도록 방어 코드가 적용됨.
    """
    # 입력값이 None일 경우 빈 딕셔너리로 초기화
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
        
        # 각 팩터(예: openness)가 없거나 None일 경우 대비
        factor_old = old_scores.get(factor) or {}
        factor_new = new_scores.get(factor) or {}
        
        for facet in facets_list[factor]:
            # 1. 기존 값 가져오기 (에러 방지: 숫자가 아니면 5.0 기본값)
            try:
                old_val = float(factor_old.get(facet, 5.0))
            except (TypeError, ValueError):
                old_val = 5.0
            
            # 2. 새 값 가져오기 (없으면 기존 값 유지)
            try:
                new_val = float(factor_new.get(facet, old_val))
            except (TypeError, ValueError):
                new_val = old_val
            
            # 3. 이동 평균 계산
            updated[factor][facet] = round((old_val * (1 - alpha)) + (new_val * alpha), 2)
                
    return updated

# --- 3. Gemini 분석 함수 (프롬프트 전체 포함) ---
async def get_gemini_analysis(diary_text: str, user_traits: List[str], retries=2):
    # 사용자가 제공한 원본 페르소나 및 지침을 생략 없이 반영
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
    # 키워드 정보가 있을 경우 프롬프트에 추가, 없으면 빈 문자열
    traits_context = ', '.join(user_traits) if user_traits else "None"
    user_input = f"Diary Entry: {diary_text}\nUser Traits (Context): {traits_context}"
    
    # API 실패에 대비한 재시도 로직
    for attempt in range(retries + 1):
        try:
            response = model.generate_content([system_instruction, user_input])
            # 마크다운 응답이 올 경우 정제
            clean_json = re.sub(r"```json|```", "", response.text).strip()
            data = json.loads(clean_json)
            
            # 필수 필드 검증 (하나라도 없으면 재시도 유도)
            if all(k in data for k in ["analysis", "recommend", "keywords", "big5"]):
                return data
            else:
                print(f"Warning: Attempt {attempt + 1} - Missing fields in Gemini response.")
        except Exception as e:
            print(f"Error: Attempt {attempt + 1} - {e}")
            if attempt < retries:
                print("⏳ API 쿨타임 대기 중 (30초)...")
                time.sleep(1) # 1초 대기 후 재시도
                
    return None

# --- 4. API 엔드포인트 ---
@app.post("/analyze-and-save")
async def analyze_and_save(request: DiaryRequest):
    try:
        print(f"INFO: Processing request for user_id: {request.user_id}")
        
        # A. 기존 데이터 로드
        user_profile = user_collection.find_one({"user_id": request.user_id})
        
        if user_profile:
            # 카운팅 딕셔너리 및 Big5 점수 가져오기 (None일 경우 빈 객체로 방어)
            existing_counts = user_profile.get("trait_counts") or {}
            existing_big5 = user_profile.get("big5_scores") or {}
            # 기존 키워드 리스트는 문맥 제공용
            existing_traits = list(existing_counts.keys())
        else:
            print(f"INFO: New user detected ({request.user_id}). Initializing DEFAULT profile.")
            existing_counts = {}
            # [변경점] 신규 유저는 빈 객체가 아니라 5.0 기본값으로 초기화
            existing_big5 = get_default_big5() 
            existing_traits = []

        # B. Gemini 분석 수행
        analysis_result = await get_gemini_analysis(request.content, existing_traits)
        
        if analysis_result is None:
            # Gemini가 끝까지 응답하지 못한 경우
            print("CRITICAL ERROR: Gemini analysis returned None.")
            raise HTTPException(status_code=500, detail="AI analysis failed. Please try again.")

        # C. 데이터 가공 (Big5 & Keywords)
        # .get() 결과가 None일 수 있으므로 'or' 연산자로 안전하게 처리
        new_keywords = analysis_result.get("keywords") or []
        new_big5 = analysis_result.get("big5") or {}
        
        # 1. Big5 업데이트 (기본값 5.0에서 출발하여 업데이트됨)
        updated_big5 = update_big5_scores(existing_big5, new_big5)

        # 2. 키워드 빈도수 업데이트 (Counter 사용)
        counter = Counter(existing_counts)
        counter.update(new_keywords) # 새로운 키워드 카운트 추가
        updated_counts = dict(counter)
        
        # 단순 리스트 (참고용/디버깅용)
        updated_traits_list = list(updated_counts.keys())

        # D. MongoDB 저장 로직
        # 1. 일기 내역 저장
        diary_collection.insert_one({
            "user_id": request.user_id,
            "content": request.content,
            "created_at": datetime.utcnow(),
            "analysis": analysis_result.get("analysis"),
            "recommend": analysis_result.get("recommend"),
            "one_liner": analysis_result.get("one_liner", ""),
            "big5_snapshot": new_big5,       # 이번 일기의 Big5
            "keywords_snapshot": new_keywords # 이번 일기의 키워드
        })

        # 2. 유저 전체 성향 프로필 업데이트
        user_collection.update_one(
            {"user_id": request.user_id},
            {
                "$set": {
                    "traits": updated_traits_list,   # 키워드 목록
                    "trait_counts": updated_counts,  # [핵심] 키워드별 빈도수
                    "big5_scores": updated_big5,     # 누적 Big5 점수
                    "last_updated": datetime.utcnow()
                }
            },
            upsert=True
        )

        print(f"INFO: Successfully processed user_id: {request.user_id}")
        return {
            "status": "success",
            "analysis": analysis_result,
            "updated_counts": updated_counts, # 응답에 카운트 정보 포함
            "total_big5_scores": updated_big5
        }
        
    except Exception as e:
        print(f"CRITICAL SERVER ERROR: {e}")
        # 구체적인 에러 메시지를 반환하여 디버깅 용이하게 함
        raise HTTPException(status_code=500, detail=str(e))
    

# --- [NEW] 장기 분석 함수 (데이터 양에 따른 유연한 분석) ---
async def get_long_term_analysis(diary_history: str, data_count: int):
    # 데이터가 적을 때와 많을 때를 구분하여 지시
    analysis_focus = "Focus on Deep Patterns and Seasonality."
    if data_count < 10:
        analysis_focus = "The dataset is small. Focus on short-term emotional changes and immediate triggers instead of long-term patterns."

    system_instruction = f"""
Role: You are "Onion Master," an AI life coach.
Goal: Analyze the user's diary history. {analysis_focus}

Input: A chronological list of diary entries.

Task:
1. **Identify Patterns:** Find connections between events.
2. **Growth Trajectory:** Evaluate coping mechanisms.
3. **Life Keywords:** Define the period with 3 keywords.

**CRITICAL INSTRUCTION:**
- If the data covers a short period (less than a few months), DO NOT invent seasonality or long-term cycles. Just analyze the available timeframe accurately.
- If the data is sufficient, find deep, recurring patterns over time.

Output Format (JSON Only):
{{
  "deep_patterns": [
    {{ "pattern_name": "String", "description": "String", "evidence_dates": ["YYYY-MM-DD"] }}
  ],
  "seasonality": "String (If data is insufficient, say 'Not enough data yet')",
  "growth_evaluation": "String",
  "life_keywords": ["String", "String", "String"],
  "advice_for_future": "String"
}}
"""
    try:
        response = model.generate_content([system_instruction, diary_history])
        clean_json = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Long-term analysis error: {e}")
        return None

# --- [NEW] API 엔드포인트: 인생 지도 분석 ---
@app.post("/analyze-life-map")
async def analyze_life_map(request: LifeMapRequest):
    try:
        print(f"INFO: Starting Life Map analysis for {request.user_id}")

        # 1. MongoDB에서 일기 가져오기
        cursor = diary_collection.find({"user_id": request.user_id}).sort("created_at", 1)
        diaries = list(cursor)

        # [안전장치 1] 데이터 개수 확인
        if not diaries:
            return {"status": "error", "message": "분석할 일기가 없습니다."}
        
        # 최소 3개는 있어야 분석 시도 (3개 미만이면 거절)
        if len(diaries) < 3:
            return {
                "status": "fail", 
                "message": "데이터가 너무 적습니다. 일기를 3개 이상 작성한 후 다시 시도해주세요."
            }

        # 2. 텍스트 변환
        full_context = ""
        for d in diaries:
            # 날짜가 없을 경우 대비 안전 처리
            date_val = d.get("created_at", datetime.utcnow())
            date_str = date_val.strftime("%Y-%m-%d")
            content = d.get("content", "")
            full_context += f"[{date_str}] {content}\n"

        print(f"INFO: Context created. Diaries: {len(diaries)}, Length: {len(full_context)}")

        # 3. Gemini 분석 요청 (개수 정보 함께 전달)
        report_result = await get_long_term_analysis(full_context, len(diaries))

        if not report_result:
             raise HTTPException(status_code=500, detail="Gemini generated an empty report.")

        # 4. 저장
        report_data = {
            "user_id": request.user_id,
            "created_at": datetime.utcnow(),
            "period_months": request.period_months,
            "diary_count": len(diaries), # 분석에 사용된 일기 개수 저장
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

@app.get("/diaries/{user_id}")
async def get_user_diaries(user_id: str):
    # 최신순 정렬
    cursor = diary_collection.find({"user_id": user_id}).sort("created_at", -1)
    diaries = []
    for doc in cursor:
        # ObjectId는 JSON 직렬화가 안 되므로 문자열로 변환
        doc["_id"] = str(doc["_id"])
        diaries.append(doc)
    return {"diaries": diaries}

@app.get("/user/stats/{user_id}")
async def get_user_stats(user_id: str):
    user_profile = user_collection.find_one({"user_id": user_id})
    if not user_profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    # ObjectId 변환 및 필요한 데이터만 리턴
    user_profile["_id"] = str(user_profile["_id"])
    return {
        "user_id": user_profile["user_id"],
        "big5_scores": user_profile.get("big5_scores", {}),
        "trait_counts": user_profile.get("trait_counts", {}),
        "last_updated": user_profile.get("last_updated")
    }

@app.get("/life-map/{user_id}")
async def get_life_map(user_id: str):
    # 가장 최근 리포트 1개만 가져오기
    report = db["life_reports"].find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )
    
    if not report:
        return {"status": "empty", "message": "아직 생성된 리포트가 없습니다."}
    
    report["_id"] = str(report["_id"])
    return report

# --- [API] 4. 일기 내용 수정 (분석 없이 텍스트만) ---
@app.patch("/diaries/{diary_id}")
async def update_diary_content(diary_id: str, request: DiaryUpdateRequest):
    try:
        # 1. ID 유효성 검사 (MongoDB ObjectId 형식이 맞는지)
        if not ObjectId.is_valid(diary_id):
            raise HTTPException(status_code=400, detail="유효하지 않은 일기 ID입니다.")

        # 2. 업데이트 실행
        # 보안을 위해 _id(일기번호)와 user_id(작성자)가 모두 일치할 때만 수정
        result = diary_collection.update_one(
            {"_id": ObjectId(diary_id), "user_id": request.user_id},
            {
                "$set": {
                    "content": request.content,          # 내용 수정
                    "updated_at": datetime.utcnow()      # 수정 시간 기록 (선택 사항)
                }
            }
        )

        # 3. 결과 확인
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="일기를 찾을 수 없거나 수정 권한이 없습니다.")

        return {"status": "success", "message": "일기 내용이 수정되었습니다."}

    except Exception as e:
        print(f"Update Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# python -m uvicorn main6:app --reload
# http://127.0.0.1:8000/docs