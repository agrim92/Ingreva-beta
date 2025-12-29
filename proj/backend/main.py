from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import json
from database import get_db, init_db
from models import User, Preference, Product, ConsumptionLog
from ai_service import analyze_ingredients
from scoring_engine import calculate_personalized_score
from weekly_insight import generate_weekly_insight

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

# Schemas
class UserCreate(BaseModel):
    name: str

class UserResponse(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True

class PreferenceCreate(BaseModel):
    user_id: int
    goal: str
    sugar_sensitivity: float
    additive_avoidance: float
    protein_priority: float

class PreferenceResponse(BaseModel):
    id: int
    user_id: int
    goal: str
    sugar_sensitivity: float
    additive_avoidance: float
    protein_priority: float
    
    class Config:
        from_attributes = True

# User endpoints
@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.name == user.name).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists")
    new_user = User(name=user.name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# Preference endpoints
@app.post("/preferences", response_model=PreferenceResponse)
def create_preference(pref: PreferenceCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == pref.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = db.query(Preference).filter(Preference.user_id == pref.user_id).first()
    if existing:
        existing.goal = pref.goal
        existing.sugar_sensitivity = pref.sugar_sensitivity
        existing.additive_avoidance = pref.additive_avoidance
        existing.protein_priority = pref.protein_priority
        db.commit()
        db.refresh(existing)
        return existing
    
    new_pref = Preference(**pref.dict())
    db.add(new_pref)
    db.commit()
    db.refresh(new_pref)
    return new_pref

@app.get("/preferences/{user_id}", response_model=PreferenceResponse)
def get_preference(user_id: int, db: Session = Depends(get_db)):
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return pref

@app.get("/")
def root():
    return {"status": "Nutrition Co-Pilot API Running"}

# Product endpoints
class ProductAnalyze(BaseModel):
    name: str
    ingredients_text: str
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    sugar: Optional[float] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    ingredients_text: str
    ai_analysis: Optional[dict] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    sugar: Optional[float] = None
    
    class Config:
        from_attributes = True

@app.post("/products/analyze", response_model=ProductResponse)
def analyze_product(product: ProductAnalyze, db: Session = Depends(get_db)):
    analysis = analyze_ingredients(product.ingredients_text)
    
    new_product = Product(
        name=product.name,
        ingredients_text=product.ingredients_text,
        calories=product.calories,
        protein=product.protein,
        carbs=product.carbs,
        fat=product.fat,
        sugar=product.sugar,
        ai_analysis=json.dumps(analysis)
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    response_data = {
        "id": new_product.id,
        "name": new_product.name,
        "ingredients_text": new_product.ingredients_text,
        "ai_analysis": analysis,
        "calories": new_product.calories,
        "protein": new_product.protein,
        "carbs": new_product.carbs,
        "fat": new_product.fat,
        "sugar": new_product.sugar
    }
    
    return response_data

@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    response_data = {
        "id": product.id,
        "name": product.name,
        "ingredients_text": product.ingredients_text,
        "ai_analysis": json.loads(product.ai_analysis) if product.ai_analysis else None,
        "calories": product.calories,
        "protein": product.protein,
        "carbs": product.carbs,
        "fat": product.fat,
        "sugar": product.sugar
    }
    
    return response_data

# Scoring endpoint
class ScoreRequest(BaseModel):
    user_id: int
    product_id: int

class ScoreResponse(BaseModel):
    product_id: int
    product_name: str
    user_id: int
    final_score: int
    explanation: list[str]
    ingredient_scores: list[dict]

@app.post("/score", response_model=ScoreResponse)
def score_product(request: ScoreRequest, db: Session = Depends(get_db)):
    pref = db.query(Preference).filter(Preference.user_id == request.user_id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="User preferences not found")
    
    product = db.query(Product).filter(Product.id == request.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if not product.ai_analysis:
        raise HTTPException(status_code=400, detail="Product not analyzed yet")
    
    ingredient_analysis = json.loads(product.ai_analysis)
    
    product_data = {
        "name": product.name,
        "ingredients_text": product.ingredients_text,
        "calories": product.calories,
        "protein": product.protein,
        "carbs": product.carbs,
        "fat": product.fat,
        "sugar": product.sugar
    }
    
    preferences_data = {
        "goal": pref.goal,
        "sugar_sensitivity": pref.sugar_sensitivity,
        "additive_avoidance": pref.additive_avoidance,
        "protein_priority": pref.protein_priority
    }
    
    score_result = calculate_personalized_score(product_data, preferences_data, ingredient_analysis)
    
    return {
        "product_id": product.id,
        "product_name": product.name,
        "user_id": request.user_id,
        "final_score": score_result["final_score"],
        "explanation": score_result["explanation"],
        "ingredient_scores": score_result.get("ingredient_scores", [])
    }

# Consumption logging endpoints
class LogConsumption(BaseModel):
    user_id: int
    product_id: int
    servings: Optional[float] = 1.0

class ConsumptionResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    product_name: str
    servings: float
    calories: float
    protein: float
    carbs: float
    fat: float
    sugar: float
    consumed_at: datetime
    
    class Config:
        from_attributes = True

@app.post("/consume", response_model=ConsumptionResponse)
def log_consumption(log: LogConsumption, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == log.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    product = db.query(Product).filter(Product.id == log.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product.calories is None:
        raise HTTPException(status_code=400, detail="Product missing nutrition data")
    
    servings = log.servings if log.servings else 1.0
    
    consumption = ConsumptionLog(
        user_id=log.user_id,
        product_id=log.product_id,
        servings=servings,
        calories=product.calories * servings,
        protein=product.protein * servings if product.protein else 0,
        carbs=product.carbs * servings if product.carbs else 0,
        fat=product.fat * servings if product.fat else 0,
        sugar=product.sugar * servings if product.sugar else 0
    )
    
    db.add(consumption)
    db.commit()
    db.refresh(consumption)
    
    return {
        "id": consumption.id,
        "user_id": consumption.user_id,
        "product_id": consumption.product_id,
        "product_name": product.name,
        "servings": consumption.servings,
        "calories": consumption.calories,
        "protein": consumption.protein,
        "carbs": consumption.carbs,
        "fat": consumption.fat,
        "sugar": consumption.sugar,
        "consumed_at": consumption.consumed_at
    }

class WeeklySummary(BaseModel):
    user_id: int
    week_start: datetime
    week_end: datetime
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    total_sugar: float
    entries_count: int
    daily_avg_calories: float
    daily_avg_protein: float
    ai_insight: Optional[str] = None

@app.get("/weekly-summary/{user_id}", response_model=WeeklySummary)
def get_weekly_summary(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()
    
    week_end = datetime.utcnow()
    week_start = week_end - timedelta(days=7)
    
    logs = db.query(ConsumptionLog).filter(
        ConsumptionLog.user_id == user_id,
        ConsumptionLog.consumed_at >= week_start,
        ConsumptionLog.consumed_at <= week_end
    ).all()
    
    if not logs:
        return {
            "user_id": user_id,
            "week_start": week_start,
            "week_end": week_end,
            "total_calories": 0,
            "total_protein": 0,
            "total_carbs": 0,
            "total_fat": 0,
            "total_sugar": 0,
            "entries_count": 0,
            "daily_avg_calories": 0,
            "daily_avg_protein": 0,
            "ai_insight": "No consumption data available for the past week."
        }
    
    total_calories = sum(log.calories for log in logs)
    total_protein = sum(log.protein for log in logs)
    total_carbs = sum(log.carbs for log in logs)
    total_fat = sum(log.fat for log in logs)
    total_sugar = sum(log.sugar for log in logs)
    entries_count = len(logs)
    
    weekly_data = {
        "user_id": user_id,
        "week_start": week_start,
        "week_end": week_end,
        "total_calories": round(total_calories, 1),
        "total_protein": round(total_protein, 1),
        "total_carbs": round(total_carbs, 1),
        "total_fat": round(total_fat, 1),
        "total_sugar": round(total_sugar, 1),
        "entries_count": entries_count,
        "daily_avg_calories": round(total_calories / 7, 1),
        "daily_avg_protein": round(total_protein / 7, 1)
    }
    
    ai_insight = None
    if pref:
        preferences_data = {
            "goal": pref.goal,
            "sugar_sensitivity": pref.sugar_sensitivity,
            "additive_avoidance": pref.additive_avoidance,
            "protein_priority": pref.protein_priority
        }
        ai_insight = generate_weekly_insight(weekly_data, preferences_data)
    
    weekly_data["ai_insight"] = ai_insight
    return weekly_data
