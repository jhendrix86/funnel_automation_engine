"""
Conversion Optimization Service - A/B testing and CRO automation
Integrates with Empire OS Monetization Engine
"""
import os
import json
import asyncio
import random
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
import redis
import openai
from scipy import stats
from dataclasses import dataclass

# Initialize FastAPI app
app = FastAPI(title="Conversion Optimization Service", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize clients
openai.api_key = OPENAI_API_KEY
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
ab_tests_collection = db.ab_tests
variants_collection = db.variants
funnels_collection = db.funnels

class ABTestRequest(BaseModel):
    funnel_id: str
    test_name: str
    element_type: str  # headline, cta, layout, color, pricing, lead_magnet
    variants: List[Dict]
    traffic_split: Dict[str, float]
    test_duration_days: int = 14
    minimum_sample_size: int = 1000
    confidence_level: float = 0.95

class ABTestResponse(BaseModel):
    test_id: str
    status: str
    variants: List[Dict]
    traffic_split: Dict[str, float]
    estimated_duration: str

class VariantPerformance(BaseModel):
    variant_id: str
    visitors: int
    conversions: int
    conversion_rate: float
    revenue: float
    statistical_significance: float
    is_winner: bool

class OptimizationSuggestion(BaseModel):
    element: str
    current_value: str
    suggested_value: str
    expected_improvement: float
    confidence: float
    priority: str

class LandingPageOptimization(BaseModel):
    funnel_id: str
    landing_page_id: str
    optimization_goals: List[str]

class CROAnalysis(BaseModel):
    funnel_id: str
    analysis_type: str
    recommendations: List[OptimizationSuggestion]
    expected_lift: float

@dataclass
class TestResult:
    variant_id: str
    conversion_rate: float
    confidence_interval: tuple
    is_statistically_significant: bool
    improvement_over_control: float

@app.post("/ab-test/create", response_model=ABTestResponse)
async def create_ab_test(request: ABTestRequest, background_tasks: BackgroundTasks):
    """Create new A/B test with automatic traffic allocation"""
    try:
        # Validate traffic split
        total_split = sum(request.traffic_split.values())
        if not np.isclose(total_split, 1.0, atol=0.01):
            raise HTTPException(status_code=400, detail="Traffic split must sum to 1.0")
        
        # Validate variants
        if len(request.variants) < 2:
            raise HTTPException(status_code=400, detail="At least 2 variants required")
        
        # Create test document
        test_doc = {
            "funnel_id": request.funnel_id,
            "test_name": request.test_name,
            "element_type": request.element_type,
            "variants": request.variants,
            "traffic_split": request.traffic_split,
            "test_duration_days": request.test_duration_days,
            "minimum_sample_size": request.minimum_sample_size,
            "confidence_level": request.confidence_level,
            "created_at": datetime.now(),
            "status": "running",
            "start_date": datetime.now(),
            "end_date": datetime.now() + timedelta(days=request.test_duration_days),
            "results": {
                variant['id']: {
                    "visitors": 0,
                    "conversions": 0,
                    "revenue": 0,
                    "conversion_rate": 0
                }
                for variant in request.variants
            },
            "winner": None,
            "statistical_significance": 0.0
        }
        
        result = ab_tests_collection.insert_one(test_doc)
        
        # Start background monitoring
        background_tasks.add_task(monitor_ab_test, str(result.inserted_id))
        
        # Calculate estimated duration
        estimated_duration = f"{request.test_duration_days} days"
        
        return ABTestResponse(
            test_id=str(result.inserted_id),
            status="running",
            variants=request.variants,
            traffic_split=request.traffic_split,
            estimated_duration=estimated_duration
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def monitor_ab_test(test_id: str):
    """Monitor A/B test progress and calculate results"""
    from bson import ObjectId
    while True:
        test = ab_tests_collection.find_one({"_id": ObjectId(test_id)})
        if not test:
            break
        
        # Check if test should end
        if datetime.now() >= test['end_date']:
            await complete_ab_test(test_id)
            break
        
        # Check if minimum sample size reached
        total_visitors = sum(
            result['visitors'] for result in test['results'].values()
        )
        
        if total_visitors >= test['minimum_sample_size']:
            # Check if we have statistical significance
            significance = calculate_statistical_significance(test['results'])
            if significance >= test['confidence_level']:
                await complete_ab_test(test_id)
                break
        
        # Wait before next check
        await asyncio.sleep(3600)  # Check every hour

async def complete_ab_test(test_id: str):
    """Complete A/B test and determine winner"""
    test = ab_tests_collection.find_one({"_id": test_id})
    if not test:
        return
    
    # Calculate final results
    results = test['results']
    winner = determine_test_winner(results)
    significance = calculate_statistical_significance(results)
    
    # Update test
    ab_tests_collection.update_one(
        {"_id": ObjectId(test_id)},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.now(),
                "winner": winner,
                "statistical_significance": significance
            }
        }
    )
    
    # Implement winner if statistical significance is high
    if significance >= test['confidence_level'] and winner:
        await implement_winning_variant(test['funnel_id'], test['element_type'], winner)

def determine_test_winner(results: Dict) -> Optional[str]:
    """Determine winning variant based on conversion rate"""
    best_variant = None
    best_rate = 0
    
    for variant_id, data in results.items():
        rate = data['conversions'] / data['visitors'] if data['visitors'] > 0 else 0
        if rate > best_rate:
            best_rate = rate
            best_variant = variant_id
    
    return best_variant

def calculate_statistical_significance(results: Dict) -> float:
    """Calculate statistical significance using chi-square test"""
    variant_ids = list(results.keys())
    
    if len(variant_ids) < 2:
        return 0.0
    
    # Get conversion data
    conversions = [results[vid]['conversions'] for vid in variant_ids]
    visitors = [results[vid]['visitors'] for vid in variant_ids]
    
    # Ensure we have data
    if sum(visitors) == 0:
        return 0.0
    
    # Perform chi-square test
    try:
        # Create contingency table
        observed = np.array([
            conversions,
            [v - c for v, c in zip(visitors, conversions)]
        ])
        
        # Calculate expected values
        row_totals = observed.sum(axis=1)
        col_totals = observed.sum(axis=0)
        total = observed.sum()
        
        expected = np.outer(row_totals, col_totals) / total
        
        # Chi-square statistic
        chi_square = ((observed - expected) ** 2 / expected).sum()
        
        # Degrees of freedom
        dof = (len(variant_ids) - 1) * (2 - 1)
        
        # P-value
        p_value = 1 - stats.chi2.cdf(chi_square, dof)
        
        # Statistical significance (1 - p_value)
        significance = 1 - p_value
        
        return min(max(significance, 0), 1)
        
    except:
        return 0.0

async def implement_winning_variant(funnel_id: str, element_type: str, variant_id: str):
    """Implement winning variant in funnel"""
    try:
        from bson import ObjectId
        # Get variant details
        variant = variants_collection.find_one({"_id": ObjectId(variant_id)})
        if not variant:
            return
        
        # Update funnel with winning variant
        update_field = {
            'headline': 'landingPages.0.variants',
            'cta': 'landingPages.0.cta',
            'layout': 'landingPages.0.layout',
            'color': 'landingPages.0.colorScheme',
            'pricing': 'pricing',
            'lead_magnet': 'leadMagnets.0'
        }.get(element_type, 'landingPages.0.variants')
        
        funnels_collection.update_one(
            {"_id": ObjectId(funnel_id)},
            {"$set": {update_field: variant['content']}}
        )
        
        print(f"Implemented winning variant {variant_id} for funnel {funnel_id}")
        
    except Exception as e:
        print(f"Error implementing winning variant: {str(e)}")

@app.get("/ab-test/{test_id}")
async def get_ab_test_results(test_id: str):
    """Get A/B test results"""
    from bson import ObjectId
    test = ab_tests_collection.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")
    
    # Calculate performance metrics for each variant
    variant_performances = []
    for variant_id, result in test['results'].items():
        performance = {
            "variant_id": variant_id,
            "visitors": result['visitors'],
            "conversions": result['conversions'],
            "conversion_rate": result['conversion_rate'],
            "revenue": result['revenue'],
            "is_winner": variant_id == test['winner']
        }
        variant_performances.append(performance)
    
    return {
        "test_id": test_id,
        "test_name": test['test_name'],
        "status": test['status'],
        "element_type": test['element_type'],
        "variants": variant_performances,
        "winner": test['winner'],
        "statistical_significance": test['statistical_significance'],
        "created_at": test['created_at'],
        "completed_at": test.get('completed_at')
    }

@app.post("/optimize/landing-page")
async def optimize_landing_page(request: LandingPageOptimization):
    """Generate AI-powered landing page optimization suggestions"""
    try:
        from bson import ObjectId
        # Get funnel data
        funnel = funnels_collection.find_one({"_id": ObjectId(request.funnel_id)})
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        # Get landing page
        landing_page = next(
            (lp for lp in funnel.get('landingPages', []) if lp['_id'] == request.landing_page_id),
            None
        )
        
        if not landing_page:
            raise HTTPException(status_code=404, detail="Landing page not found")
        
        # Generate optimization suggestions using AI
        suggestions = await generate_optimization_suggestions(
            landing_page,
            request.optimization_goals,
            funnel
        )
        
        return {
            "funnel_id": request.funnel_id,
            "landing_page_id": request.landing_page_id,
            "suggestions": suggestions,
            "expected_improvement": calculate_expected_improvement(suggestions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_optimization_suggestions(landing_page: Dict, goals: List[str], funnel: Dict) -> List[Dict]:
    """Generate AI-powered optimization suggestions"""
    prompt = f"""
    Analyze this landing page and provide optimization suggestions:
    
    Landing Page Data:
    {json.dumps(landing_page, indent=2)}
    
    Optimization Goals:
    {', '.join(goals)}
    
    Funnel Context:
    - Conversion rate: {funnel.get('analytics', {}).get('conversionRate', 0)}%
    - Primary audience: {funnel.get('targetAudience', 'general')}
    
    Provide specific, actionable suggestions for:
    1. Headline optimization
    2. Call-to-action improvements
    3. Layout and design
    4. Copy and messaging
    5. Trust elements
    6. Form optimization
    
    For each suggestion, include:
    - Current state
    - Suggested change
    - Expected improvement percentage
    - Implementation difficulty
    - Priority level
    
    Format as JSON array of suggestions.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a conversion rate optimization expert with proven track record of improving landing page performance."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    try:
        suggestions = json.loads(response.choices[0].message.content)
        return suggestions
    except:
        # Fallback suggestions if AI parsing fails
        return [
            {
                "element": "headline",
                "current_value": landing_page.get('headline', 'Current headline'),
                "suggested_value": "Improved headline with stronger value proposition",
                "expected_improvement": 15,
                "confidence": 0.7,
                "priority": "high"
            }
        ]

def calculate_expected_improvement(suggestions: List[Dict]) -> float:
    """Calculate expected overall improvement from suggestions"""
    if not suggestions:
        return 0.0
    
    # Weight improvements by confidence and priority
    priority_weights = {"high": 1.0, "medium": 0.7, "low": 0.4}
    
    weighted_improvements = []
    for suggestion in suggestions:
        weight = priority_weights.get(suggestion.get('priority', 'medium'), 0.7)
        confidence = suggestion.get('confidence', 0.5)
        improvement = suggestion.get('expected_improvement', 0)
        
        weighted_improvement = improvement * weight * confidence
        weighted_improvements.append(weighted_improvement)
    
    # Calculate combined improvement (diminishing returns)
    total_improvement = sum(weighted_improvements)
    combined_improvement = total_improvement * (1 - min(len(suggestions) * 0.1, 0.5))
    
    return min(combined_improvement, 50)  # Cap at 50% improvement

@app.post("/analyze/cro", response_model=CROAnalysis)
async def analyze_cro(funnel_id: str, analysis_type: str = "comprehensive"):
    """Perform comprehensive CRO analysis"""
    try:
        from bson import ObjectId
        funnel = funnels_collection.find_one({"_id": ObjectId(funnel_id)})
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        # Perform analysis based on type
        if analysis_type == "comprehensive":
            recommendations = await comprehensive_cro_analysis(funnel)
        elif analysis_type == "quick":
            recommendations = await quick_cro_analysis(funnel)
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        # Calculate expected lift
        expected_lift = calculate_expected_improvement(recommendations)
        
        return CROAnalysis(
            funnel_id=funnel_id,
            analysis_type=analysis_type,
            recommendations=recommendations,
            expected_lift=expected_lift
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def comprehensive_cro_analysis(funnel: Dict) -> List[Dict]:
    """Perform comprehensive CRO analysis using AI"""
    analytics = funnel.get('analytics', {})
    landing_pages = funnel.get('landingPages', [])
    
    prompt = f"""
    Perform a comprehensive conversion rate optimization analysis for this funnel:
    
    Funnel Analytics:
    - Visitors: {analytics.get('visitors', 0)}
    - Leads: {analytics.get('leads', 0)}
    - Conversions: {analytics.get('conversions', 0)}
    - Conversion rate: {analytics.get('conversionRate', 0)}%
    - Lead rate: {(analytics.get('leads', 0) / analytics.get('visitors', 1) * 100) if analytics.get('visitors', 0) > 0 else 0}%
    
    Landing Pages: {len(landing_pages)}
    
    Provide detailed recommendations for:
    1. Traffic quality optimization
    2. Lead capture optimization
    3. Conversion optimization
    4. User experience improvements
    5. Technical performance
    6. Mobile optimization
    
    Each recommendation should include:
    - Specific action
    - Expected impact
    - Implementation complexity
    - Priority level
    - Estimated timeline
    
    Format as JSON array.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a CRO expert with deep expertise in funnel optimization and user psychology."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2500
    )
    
    try:
        recommendations = json.loads(response.choices[0].message.content)
        return recommendations
    except:
        return generate_fallback_recommendations(funnel)

async def quick_cro_analysis(funnel: Dict) -> List[Dict]:
    """Perform quick CRO analysis focusing on high-impact changes"""
    analytics = funnel.get('analytics', {})
    
    recommendations = []
    
    # Quick wins based on data
    if analytics.get('conversionRate', 0) < 2:
        recommendations.append({
            "element": "overall_conversion",
            "current_value": f"{analytics.get('conversionRate', 0)}%",
            "suggested_value": "Focus on headline and CTA optimization",
            "expected_improvement": 25,
            "confidence": 0.8,
            "priority": "high"
        })
    
    if analytics.get('leads', 0) / analytics.get('visitors', 1) < 0.05:
        recommendations.append({
            "element": "lead_capture",
            "current_value": "Low lead capture rate",
            "suggested_value": "Add exit-intent popup and improve lead magnet visibility",
            "expected_improvement": 30,
            "confidence": 0.7,
            "priority": "high"
        })
    
    return recommendations

def generate_fallback_recommendations(funnel: Dict) -> List[Dict]:
    """Generate fallback recommendations if AI analysis fails"""
    return [
        {
            "element": "headline",
            "current_value": "Current headline",
            "suggested_value": "Test benefit-driven headlines",
            "expected_improvement": 10,
            "confidence": 0.6,
            "priority": "medium"
        },
        {
            "element": "cta",
            "current_value": "Current CTA",
            "suggested_value": "Test action-oriented CTAs with urgency",
            "expected_improvement": 15,
            "confidence": 0.7,
            "priority": "high"
        }
    ]

@app.get("/ab-test/active")
async def get_active_tests(funnel_id: Optional[str] = None):
    """Get all active A/B tests"""
    query = {"status": "running"}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    tests = list(ab_tests_collection.find(query))
    return {"tests": tests}

@app.post("/ab-test/{test_id}/stop")
async def stop_ab_test(test_id: str):
    """Stop running A/B test"""
    from bson import ObjectId
    test = ab_tests_collection.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")
    
    if test['status'] != 'running':
        raise HTTPException(status_code=400, detail="Test is not running")
    
    await complete_ab_test(test_id)
    
    return {"message": "A/B test stopped and completed"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "conversion-optimizer",
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)