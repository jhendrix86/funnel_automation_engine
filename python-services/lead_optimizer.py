"""
Lead Optimization Service - AI-powered lead scoring and nurturing
Integrates with Empire OS Growth Engine
"""
import os
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
import redis
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import openai

# Initialize FastAPI app
app = FastAPI(title="Lead Optimization Service", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize clients
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
leads_collection = db.leads
funnels_collection = db.funnels

class LeadScoreRequest(BaseModel):
    lead_id: str
    funnel_id: str
    behaviors: List[Dict]
    demographics: Dict
    custom_data: Dict

class LeadScoreResponse(BaseModel):
    lead_id: str
    score: int
    probability: float
    factors: Dict[str, float]
    recommendation: str
    next_best_action: str

class SegmentRequest(BaseModel):
    funnel_id: str
    criteria: Dict
    segment_count: int = 5

class SegmentResponse(BaseModel):
    segments: Dict[str, List[str]]
    segment_characteristics: Dict[str, Dict]
    recommendations: Dict[str, str]

class NurtureCampaignRequest(BaseModel):
    segment_id: str
    campaign_type: str
    duration_days: int = 30
    touchpoints: int = 5

class NurtureCampaignResponse(BaseModel):
    campaign_id: str
    sequence: List[Dict]
    schedule: List[Dict]
    expected_conversion_rate: float

# ML Model cache
lead_scoring_model = None
scaler = None

def load_ml_model():
    """Load or train the lead scoring model"""
    global lead_scoring_model, scaler
    
    try:
        # Try to load existing model
        lead_scoring_model = joblib.load('lead_scoring_model.pkl')
        scaler = joblib.load('scaler.pkl')
    except:
        # Train new model if none exists
        lead_scoring_model, scaler = train_lead_scoring_model()

def train_lead_scoring_model():
    """Train a lead scoring model using historical data"""
    # This would use your historical lead data
    # For now, create a simple model
    
    # In production, you would:
    # 1. Fetch historical leads with conversion data
    # 2. Extract features (behaviors, demographics, timing, etc.)
    # 3. Train RandomForest or similar model
    # 4. Save the model
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    scaler = StandardScaler()
    
    # Save models
    joblib.dump(model, 'lead_scoring_model.pkl')
    joblib.dump(scaler, 'scaler.pkl')
    
    return model, scaler

@app.on_event("startup")
async def startup_event():
    """Initialize ML model on startup"""
    load_ml_model()

@app.post("/score", response_model=LeadScoreResponse)
async def score_lead(request: LeadScoreRequest):
    """
    Score a lead based on behaviors, demographics, and custom data
    Uses ML model for accurate scoring
    """
    try:
        # Extract features from lead data
        features = extract_lead_features(request)
        
        # Scale features
        if scaler:
            features_scaled = scaler.transform([features])
        else:
            features_scaled = [features]
        
        # Predict conversion probability
        if lead_scoring_model:
            probability = lead_scoring_model.predict_proba(features_scaled)[0][1]
        else:
            # Fallback to rule-based scoring
            probability = calculate_rule_based_score(request)
        
        # Calculate score (0-100)
        score = int(probability * 100)
        
        # Identify key factors
        factors = identify_scoring_factors(request)
        
        # Generate recommendation
        recommendation = generate_score_recommendation(score, factors)
        
        # Suggest next best action
        next_action = suggest_next_best_action(score, request.behaviors)
        
        # Update lead in database
        from bson import ObjectId
        leads_collection.update_one(
            {"_id": ObjectId(request.lead_id)},
            {
                "$set": {
                    "score": score,
                    "conversion_probability": probability,
                    "last_scored_at": datetime.now()
                }
            }
        )
        
        # Cache the score
        cache_key = f"lead_score:{request.lead_id}"
        redis_client.setex(cache_key, 3600, json.dumps({
            "score": score,
            "probability": probability,
            "factors": factors
        }))
        
        return LeadScoreResponse(
            lead_id=request.lead_id,
            score=score,
            probability=probability,
            factors=factors,
            recommendation=recommendation,
            next_best_action=next_action
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_lead_features(request: LeadScoreRequest) -> List[float]:
    """Extract numerical features from lead data"""
    features = []
    
    # Behavior features
    behavior_types = [b['type'] for b in request.behaviors]
    features.append(len(behavior_types))  # Total behaviors
    features.append(behavior_types.count('page_view'))  # Page views
    features.append(behavior_types.count('email_open'))  # Email opens
    features.append(behavior_types.count('email_click'))  # Email clicks
    features.append(behavior_types.count('download'))  # Downloads
    features.append(behavior_types.count('purchase'))  # Purchases
    
    # Time-based features
    if request.behaviors:
        latest_behavior = max(b['timestamp'] for b in request.behaviors if isinstance(b['timestamp'], datetime))
        time_since_last_activity = (datetime.now() - latest_behavior).days
        features.append(time_since_last_activity)
    else:
        features.append(30)  # Default 30 days
    
    # Engagement rate
    if len(behavior_types) > 0:
        engagement_rate = sum(1 for b in request.behaviors if b['type'] in ['email_click', 'download', 'purchase']) / len(behavior_types)
        features.append(engagement_rate)
    else:
        features.append(0)
    
    # Demographic features (simplified)
    features.append(1 if request.demographics.get('company') else 0)  # Has company
    features.append(1 if request.demographics.get('phone') else 0)  # Has phone
    
    return features

def calculate_rule_based_score(request: LeadScoreRequest) -> float:
    """Fallback rule-based scoring if ML model is unavailable"""
    score = 0
    
    # Behavior scoring
    for behavior in request.behaviors:
        behavior_type = behavior['type']
        if behavior_type == 'page_view':
            score += 1
        elif behavior_type == 'email_open':
            score += 3
        elif behavior_type == 'email_click':
            score += 5
        elif behavior_type == 'download':
            score += 10
        elif behavior_type == 'purchase':
            score += 50
    
    # Normalize to 0-1
    return min(score / 100, 1.0)

def identify_scoring_factors(request: LeadScoreRequest) -> Dict[str, float]:
    """Identify key factors contributing to the score"""
    factors = {}
    
    # Behavior engagement
    high_value_behaviors = ['email_click', 'download', 'purchase']
    engagement_score = sum(1 for b in request.behaviors if b['type'] in high_value_behaviors)
    factors['engagement'] = min(engagement_score / 10, 1.0)
    
    # Data completeness
    completeness = sum([
        1 if request.demographics.get('firstName') else 0,
        1 if request.demographics.get('lastName') else 0,
        1 if request.demographics.get('company') else 0,
        1 if request.demographics.get('phone') else 0
    ]) / 4
    factors['data_completeness'] = completeness
    
    # Activity recency
    if request.behaviors:
        latest_behavior = max(b['timestamp'] for b in request.behaviors if isinstance(b['timestamp'], datetime))
        days_since_activity = (datetime.now() - latest_behavior).days
        factors['recency'] = max(0, 1 - (days_since_activity / 30))
    else:
        factors['recency'] = 0
    
    return factors

def generate_score_recommendation(score: int, factors: Dict[str, float]) -> str:
    """Generate recommendation based on score and factors"""
    if score >= 80:
        return "Hot lead - Immediate sales follow-up recommended"
    elif score >= 60:
        return "Qualified lead - Schedule demo or consultation"
    elif score >= 40:
        return "Nurturing required - Send targeted content sequence"
    elif score >= 20:
        return "Cold lead - Add to general nurture campaign"
    else:
        return "Low quality - Consider removing or re-engagement campaign"

def suggest_next_best_action(score: int, behaviors: List[Dict]) -> str:
    """Suggest the next best action for lead nurturing"""
    behavior_types = [b['type'] for b in behaviors]
    
    if score >= 80:
        return "Schedule sales call within 24 hours"
    elif score >= 60:
        return "Send personalized email with case study"
    elif 'download' not in behavior_types:
        return "Send lead magnet download link"
    elif 'email_open' in behavior_types and 'email_click' not in behavior_types:
        return "Send follow-up email with stronger CTA"
    elif len(behavior_types) < 3:
        return "Add to educational content sequence"
    else:
        return "Continue current nurture sequence"

@app.post("/segment", response_model=SegmentResponse)
async def segment_leads(request: SegmentRequest):
    """
    Segment leads based on criteria using ML clustering
    """
    try:
        # Fetch leads for the funnel
        leads = list(leads_collection.find({"funnel_id": request.funnel_id}))
        
        if not leads:
            raise HTTPException(status_code=404, detail="No leads found for this funnel")
        
        # Extract features for clustering
        lead_features = []
        lead_ids = []
        
        for lead in leads:
            features = extract_lead_features_from_db(lead)
            lead_features.append(features)
            lead_ids.append(str(lead['_id']))
        
        # Perform clustering
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(lead_features)
        
        kmeans = KMeans(n_clusters=request.segment_count, random_state=42)
        clusters = kmeans.fit_predict(features_scaled)
        
        # Organize leads by segment
        segments = {}
        for i, cluster_id in enumerate(clusters):
            if cluster_id not in segments:
                segments[f"segment_{cluster_id}"] = []
            segments[f"segment_{cluster_id}"].append(lead_ids[i])
        
        # Analyze segment characteristics
        segment_characteristics = analyze_segment_characteristics(leads, clusters, request.segment_count)
        
        # Generate recommendations for each segment
        recommendations = generate_segment_recommendations(segment_characteristics)
        
        return SegmentResponse(
            segments=segments,
            segment_characteristics=segment_characteristics,
            recommendations=recommendations
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_lead_features_from_db(lead: Dict) -> List[float]:
    """Extract features from database lead document"""
    features = []
    
    behaviors = lead.get('behaviors', [])
    behavior_types = [b['type'] for b in behaviors]
    
    features.append(len(behavior_types))
    features.append(behavior_types.count('page_view'))
    features.append(behavior_types.count('email_open'))
    features.append(behavior_types.count('email_click'))
    features.append(behavior_types.count('download'))
    features.append(behavior_types.count('purchase'))
    
    # Score
    features.append(lead.get('score', 0))
    
    return features

def analyze_segment_characteristics(leads: List[Dict], clusters: np.ndarray, num_clusters: int) -> Dict[str, Dict]:
    """Analyze characteristics of each segment"""
    characteristics = {}
    
    for cluster_id in range(num_clusters):
        cluster_leads = [leads[i] for i in range(len(leads)) if clusters[i] == cluster_id]
        
        if not cluster_leads:
            continue
        
        # Calculate average metrics
        avg_score = sum(lead.get('score', 0) for lead in cluster_leads) / len(cluster_leads)
        
        # Status distribution
        status_counts = {}
        for lead in cluster_leads:
            status = lead.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Common behaviors
        behavior_counts = {}
        for lead in cluster_leads:
            for behavior in lead.get('behaviors', []):
                behavior_type = behavior['type']
                behavior_counts[behavior_type] = behavior_counts.get(behavior_type, 0) + 1
        
        characteristics[f"segment_{cluster_id}"] = {
            "size": len(cluster_leads),
            "average_score": avg_score,
            "status_distribution": status_counts,
            "common_behaviors": behavior_counts,
            "quality": "high" if avg_score >= 60 else "medium" if avg_score >= 40 else "low"
        }
    
    return characteristics

def generate_segment_recommendations(characteristics: Dict[str, Dict]) -> Dict[str, str]:
    """Generate nurturing recommendations for each segment"""
    recommendations = {}
    
    for segment_id, chars in characteristics.items():
        quality = chars['quality']
        
        if quality == 'high':
            recommendations[segment_id] = "Immediate sales follow-up, personalized outreach"
        elif quality == 'medium':
            recommendations[segment_id] = "Targeted nurture campaign, product education"
        else:
            recommendations[segment_id] = "General nurture, re-engagement campaign"
    
    return recommendations

@app.post("/nurture-campaign", response_model=NurtureCampaignResponse)
async def create_nurture_campaign(request: NurtureCampaignRequest):
    """
    Generate AI-powered nurture campaign for a segment
    """
    try:
        # Generate campaign using AI
        campaign = await generate_ai_nurture_campaign(request)
        
        # Save campaign to database
        campaign_doc = {
            "segment_id": request.segment_id,
            "campaign_type": request.campaign_type,
            "duration_days": request.duration_days,
            "touchpoints": request.touchpoints,
            "sequence": campaign['sequence'],
            "schedule": campaign['schedule'],
            "created_at": datetime.now(),
            "status": "draft"
        }
        
        result = db.nurture_campaigns.insert_one(campaign_doc)
        
        return NurtureCampaignResponse(
            campaign_id=str(result.inserted_id),
            sequence=campaign['sequence'],
            schedule=campaign['schedule'],
            expected_conversion_rate=campaign['expected_conversion_rate']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_ai_nurture_campaign(request: NurtureCampaignRequest) -> Dict:
    """Generate nurture campaign using AI"""
    prompt = f"""
    Create a {request.campaign_type} nurture campaign with {request.touchpoints} touchpoints over {request.duration_days} days.
    
    Segment ID: {request.segment_id}
    
    Requirements:
    - Create engaging email sequences
    - Include varied content types (educational, promotional, social proof)
    - Optimize timing for maximum engagement
    - Include compelling subject lines
    - Add clear calls-to-action
    - Personalization elements
    
    Provide:
    1. Email sequence with subject lines and content summaries
    2. Send schedule (days between emails)
    3. Expected conversion rate estimate
    """
    
    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an email marketing automation expert with high conversion rates."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )
    
    # Parse response (in production, would be more structured)
    campaign_content = response.choices[0].message.content
    
    return {
        "sequence": [
            {
                "day": 1,
                "type": "welcome",
                "subject": "Welcome to our community",
                "content": campaign_content
            }
        ],
        "schedule": [
            {"touchpoint": 1, "day": 1},
            {"touchpoint": 2, "day": 3},
            {"touchpoint": 3, "day": 7},
            {"touchpoint": 4, "day": 14},
            {"touchpoint": 5, "day": 30}
        ],
        "expected_conversion_rate": 0.15
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "lead-optimization",
        "ml_model_loaded": lead_scoring_model is not None,
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)