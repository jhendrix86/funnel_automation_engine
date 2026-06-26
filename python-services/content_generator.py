"""
Content Generation Service - AI-powered content creation for traffic funnels
Integrates with Empire OS Content Machine
"""
import os
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import openai
from pymongo import MongoClient
import redis
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

# Initialize FastAPI app
app = FastAPI(title="Content Generation Service", version="1.0.0")

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
content_collection = db.content_assets

class ContentRequest(BaseModel):
    funnel_id: str
    content_type: str  # blog, social, email, landing_page, ad_copy
    topic: str
    target_audience: str
    keywords: List[str]
    tone: str = "professional"
    length: str = "medium"  # short, medium, long
    language: str = "en"

class ContentResponse(BaseModel):
    content_id: str
    content: str
    metadata: Dict
    generated_at: datetime

class ContentOptimizer(BaseModel):
    content: str
    target_keywords: List[str]
    target_audience: str
    optimization_goals: List[str]

class ContentClusterRequest(BaseModel):
    topics: List[str]
    cluster_count: int = 5

@app.post("/generate", response_model=ContentResponse)
async def generate_content(request: ContentRequest, background_tasks: BackgroundTasks):
    """
    Generate content based on funnel and content type
    Integrates with Empire OS Content Machine outputs
    """
    try:
        # Check cache first
        cache_key = f"content:{request.funnel_id}:{request.content_type}:{hash(request.topic)}"
        cached_content = redis_client.get(cache_key)
        
        if cached_content:
            return ContentResponse(
                content_id="cached",
                content=json.loads(cached_content),
                metadata={"source": "cache"},
                generated_at=datetime.now()
            )
        
        # Generate content based on type
        if request.content_type == "blog":
            content = await generate_blog_post(request)
        elif request.content_type == "social":
            content = await generate_social_post(request)
        elif request.content_type == "email":
            content = await generate_email_copy(request)
        elif request.content_type == "landing_page":
            content = await generate_landing_page(request)
        elif request.content_type == "ad_copy":
            content = await generate_ad_copy(request)
        else:
            raise HTTPException(status_code=400, detail="Invalid content type")
        
        # Store in database
        content_doc = {
            "funnel_id": request.funnel_id,
            "content_type": request.content_type,
            "topic": request.topic,
            "content": content,
            "metadata": {
                "target_audience": request.target_audience,
                "keywords": request.keywords,
                "tone": request.tone,
                "length": request.length,
                "language": request.language
            },
            "created_at": datetime.now(),
            "performance": {
                "views": 0,
                "engagement": 0,
                "conversions": 0
            }
        }
        
        result = content_collection.insert_one(content_doc)
        
        # Cache the result
        redis_client.setex(cache_key, 3600, json.dumps(content))
        
        # Schedule background optimization
        background_tasks.add_task(schedule_content_optimization, str(result.inserted_id))
        
        return ContentResponse(
            content_id=str(result.inserted_id),
            content=content,
            metadata=content_doc["metadata"],
            generated_at=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_blog_post(request: ContentRequest) -> str:
    """Generate SEO-optimized blog post"""
    prompt = f"""
    Write a {request.length} blog post about "{request.topic}" for {request.target_audience}.
    
    Requirements:
    - Tone: {request.tone}
    - Include these keywords naturally: {', '.join(request.keywords)}
    - Structure: Attention-grabbing headline, introduction, 3-5 main sections with H2 headings, conclusion
    - SEO-optimized with meta description
    - Include internal linking suggestions
    - Add a compelling call-to-action at the end
    - Length: {'300-500 words' if request.length == 'short' else '800-1200 words' if request.length == 'medium' else '1500-2000 words'}
    
    Format the response as:
    HEADLINE: [Your headline]
    META_DESCRIPTION: [Meta description]
    
    [Blog post content]
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert content writer specializing in SEO and conversion optimization."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content

async def generate_social_post(request: ContentRequest) -> str:
    """Generate engaging social media posts"""
    platforms = {
        "twitter": {"length": 280, "style": "concise, hashtag-heavy"},
        "linkedin": {"length": 3000, "style": "professional, business-focused"},
        "instagram": {"length": 2200, "style": "visual, emoji-rich, hashtag-heavy"},
        "facebook": {"length": 63206, "style": "engaging, conversation-starting"}
    }
    
    platform = request.metadata.get("platform", "linkedin") if hasattr(request, 'metadata') else "linkedin"
    platform_config = platforms.get(platform, platforms["linkedin"])
    
    prompt = f"""
    Write a {platform} post about "{request.topic}" for {request.target_audience}.
    
    Requirements:
    - Tone: {request.tone}
    - Style: {platform_config['style']}
    - Include relevant hashtags
    - Maximum length: {platform_config['length']} characters
    - Include a call-to-action
    - Keywords to include: {', '.join(request.keywords)}
    
    Make it engaging and shareable.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a social media expert with high engagement rates."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=500
    )
    
    return response.choices[0].message.content

async def generate_email_copy(request: ContentRequest) -> str:
    """Generate high-converting email copy"""
    prompt = f"""
    Write an email about "{request.topic}" for {request.target_audience}.
    
    Requirements:
    - Tone: {request.tone}
    - Compelling subject line (multiple options)
    - Preview text
    - Personal greeting
    - Value-driven body content
    - Strong call-to-action
    - P.S. line
    - Keywords: {', '.join(request.keywords)}
    - Length: {'200-300 words' if request.length == 'short' else '400-600 words' if request.length == 'medium' else '800-1000 words'}
    
    Format:
    SUBJECT LINES:
    1. [Option 1]
    2. [Option 2]
    3. [Option 3]
    
    PREVIEW TEXT: [Preview text]
    
    [Email body]
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an email marketing specialist with high open and click-through rates."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    
    return response.choices[0].message.content

async def generate_landing_page(request: ContentRequest) -> str:
    """Generate high-converting landing page copy"""
    prompt = f"""
    Write landing page copy for "{request.topic}" targeting {request.target_audience}.
    
    Requirements:
    - Tone: {request.tone}
    - Compelling headline
    - Subheadline
    - Benefit-focused bullet points
    - Social proof section
    - Call-to-action buttons
    - Trust indicators
    - FAQ section
    - Keywords: {', '.join(request.keywords)}
    
    Format as complete landing page structure with clear section labels.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a conversion copywriter specializing in high-converting landing pages."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content

async def generate_ad_copy(request: ContentRequest) -> str:
    """Generate ad copy for various platforms"""
    prompt = f"""
    Write ad copy for "{request.topic}" targeting {request.target_audience}.
    
    Requirements:
    - Tone: {request.tone}
    - Multiple headline options
    - Primary text
    - Description
    - Call-to-action button text
    - Keywords: {', '.join(request.keywords)}
    
    Provide variations for:
    1. Facebook/Instagram ads
    2. Google Search ads
    3. LinkedIn ads
    
    Focus on high click-through rates and conversions.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a paid advertising specialist with high ROI campaigns."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=1500
    )
    
    return response.choices[0].message.content

@app.post("/optimize")
async def optimize_content(optimizer: ContentOptimizer):
    """
    Optimize existing content for better performance
    Uses NLP and SEO analysis
    """
    try:
        # Analyze current content
        analysis = analyze_content_performance(
            optimizer.content,
            optimizer.target_keywords,
            optimizer.target_audience
        )
        
        # Generate optimization suggestions
        suggestions = await generate_optimization_suggestions(
            optimizer.content,
            analysis,
            optimizer.optimization_goals
        )
        
        return {
            "current_analysis": analysis,
            "optimization_suggestions": suggestions,
            "optimized_version": suggestions.get("rewritten_content", optimizer.content)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def analyze_content_performance(content: str, keywords: List[str], audience: str) -> Dict:
    """Analyze content performance metrics"""
    # Basic text analysis
    word_count = len(content.split())
    sentences = content.split('.')
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    # Keyword analysis
    keyword_density = {}
    for keyword in keywords:
        count = content.lower().count(keyword.lower())
        keyword_density[keyword] = (count / word_count) * 100 if word_count > 0 else 0
    
    # Readability score (simplified Flesch-Kincaid)
    readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * (sum(1 for word in content.split() if len(word) > 6) / word_count)) if word_count > 0 else 0
    
    return {
        "word_count": word_count,
        "sentence_count": len(sentences),
        "avg_sentence_length": avg_sentence_length,
        "keyword_density": keyword_density,
        "readability_score": readability,
        "estimated_reading_time": word_count / 200  # Average reading speed
    }

async def generate_optimization_suggestions(content: str, analysis: Dict, goals: List[str]) -> Dict:
    """Generate AI-powered optimization suggestions"""
    prompt = f"""
    Analyze this content and provide optimization suggestions:
    
    CONTENT:
    {content}
    
    CURRENT ANALYSIS:
    {json.dumps(analysis, indent=2)}
    
    OPTIMIZATION GOALS:
    {', '.join(goals)}
    
    Provide:
    1. Specific improvement suggestions
    2. Rewritten content incorporating improvements
    3. Expected impact on performance
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a content optimization expert with SEO and conversion focus."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )
    
    return {
        "suggestions": response.choices[0].message.content,
        "rewritten_content": content  # Would be parsed from response in production
    }

@app.post("/content-clusters")
async def create_content_clusters(request: ContentClusterRequest):
    """
    Create content clusters for SEO strategy
    Uses machine learning for topic clustering
    """
    try:
        # Generate content ideas for each topic
        content_ideas = []
        for topic in request.topics:
            ideas = await generate_content_ideas(topic, 10)
            content_ideas.extend(ideas)
        
        # Use TF-IDF and K-means for clustering
        vectorizer = TfidfVectorizer(max_features=1000)
        tfidf_matrix = vectorizer.fit_transform([idea['content'] for idea in content_ideas])
        
        kmeans = KMeans(n_clusters=request.cluster_count, random_state=42)
        clusters = kmeans.fit_predict(tfidf_matrix)
        
        # Organize content by clusters
        clustered_content = {}
        for i, label in enumerate(clusters):
            if label not in clustered_content:
                clustered_content[label] = []
            clustered_content[label].append(content_ideas[i])
        
        return {
            "clusters": clustered_content,
            "cluster_centers": kmeans.cluster_centers_.tolist(),
            "total_ideas": len(content_ideas)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_content_ideas(topic: str, count: int) -> List[Dict]:
    """Generate content ideas for a topic"""
    prompt = f"""
    Generate {count} content ideas for "{topic}".
    
    For each idea, provide:
    1. Catchy headline
    2. Brief description
    3. Target keyword
    4. Content format (blog, video, infographic, etc.)
    
    Format as JSON array.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a content strategist with expertise in SEO and audience engagement."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=1000
    )
    
    try:
        ideas = json.loads(response.choices[0].message.content)
        return [{"topic": topic, "content": json.dumps(idea)} for idea in ideas]
    except:
        return [{"topic": topic, "content": response.choices[0].message.content}]

def schedule_content_optimization(content_id: str):
    """Schedule background content optimization"""
    # This would use Celery or similar for async tasks
    pass

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "content-generation",
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)