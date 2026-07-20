"""
Social Media Service - Research, content creation, and posting
Autonomous social media management for funnel promotion
"""
import os
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime as dt
import redis
import aiohttp
import openai

# Initialize FastAPI app
app = FastAPI(title="Social Media Service", version="1.0.0")

# Configuration
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8008")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize clients
openai.api_key = OPENAI_API_KEY
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
social_posts_collection = db.social_posts
social_campaigns_collection = db.social_campaigns
social_analytics_collection = db.social_analytics

def _serialize_doc(doc):
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, dt):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                _serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, dt)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result

class SocialPostRequest(BaseModel):
    platform: str  # twitter, linkedin
    content: str
    funnel_id: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    hashtags: List[str] = []
    media_urls: List[str] = []

class ContentResearchRequest(BaseModel):
    niche: str
    target_audience: str
    funnel_id: Optional[str] = None
    platforms: List[str] = ["twitter", "linkedin"]
    num_ideas: int = 5

class ContentGenerationRequest(BaseModel):
    topic: str
    platform: str
    tone: str = "professional"
    include_hashtags: bool = True
    funnel_id: Optional[str] = None

class CampaignRequest(BaseModel):
    name: str
    funnel_id: str
    platforms: List[str]
    start_date: datetime
    end_date: datetime
    posts_per_day: int = 3

@app.post("/research/topics")
async def research_topics(request: ContentResearchRequest):
    """Research trending topics and content ideas"""
    try:
        prompt = f"""
        Research trending topics and content ideas for social media:
        Niche: {request.niche}
        Target Audience: {request.target_audience}
        Platforms: {', '.join(request.platforms)}
        
        Generate {request.num_ideas} content ideas with:
        1. Topic title
        2. Brief description
        3. Suggested hashtags
        4. Best platform for this content
        5. Optimal posting time
        """
        
        # Use LLM service
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LLM_SERVICE_URL}/generate/product-research", json={
                "niche": request.niche,
                "target_audience": request.target_audience
            }) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Failed to generate research")
                
                data = await response.json()
                research_data = data.get('research', '')
        
        # Store research
        research_doc = {
            "niche": request.niche,
            "target_audience": request.target_audience,
            "platforms": request.platforms,
            "funnel_id": request.funnel_id,
            "research_data": research_data,
            "created_at": datetime.now()
        }
        
        db.social_research.insert_one(research_doc)
        
        return {
            "status": "success",
            "research": research_data,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/content/generate")
async def generate_content(request: ContentGenerationRequest):
    """Generate social media content using AI"""
    try:
        # Use LLM service
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LLM_SERVICE_URL}/generate/social-content", json={
                "topic": request.topic,
                "platform": request.platform,
                "tone": request.tone
            }) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Failed to generate content")
                
                data = await response.json()
                content_data = data.get('content', '')
        
        # Store generated content
        content_doc = {
            "topic": request.topic,
            "platform": request.platform,
            "tone": request.tone,
            "content": content_data,
            "funnel_id": request.funnel_id,
            "created_at": datetime.now()
        }
        
        db.generated_content.insert_one(content_doc)
        
        return {
            "status": "success",
            "content": content_data,
            "platform": request.platform,
            "provider": data.get('provider', 'llm-service'),
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/post/create")
async def create_post(request: SocialPostRequest, background_tasks: BackgroundTasks):
    """Create and schedule a social media post"""
    try:
        post_doc = {
            "platform": request.platform,
            "content": request.content,
            "funnel_id": request.funnel_id,
            "hashtags": request.hashtags,
            "media_urls": request.media_urls,
            "scheduled_for": request.scheduled_for,
            "status": "scheduled" if request.scheduled_for else "pending",
            "created_at": datetime.now(),
            "posted_at": None,
            "analytics": {
                "impressions": 0,
                "engagements": 0,
                "clicks": 0,
                "shares": 0
            }
        }
        
        result = social_posts_collection.insert_one(post_doc)
        post_id = str(result.inserted_id)
        
        # If scheduled, add to background tasks
        if request.scheduled_for:
            background_tasks.add_task(schedule_post, post_id)
        else:
            # Post immediately
            background_tasks.add_task(post_to_platform, post_id)
        
        return {
            "status": "success",
            "post_id": post_id,
            "message": f"Post {'scheduled' if request.scheduled_for else 'created'} successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def post_to_platform(post_id: str):
    """Post content to the specified platform"""
    try:
        post = social_posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return
        
        platform = post['platform']
        content = post['content']
        hashtags = post.get('hashtags', [])
        
        full_content = f"{content}\n\n{' '.join(f'#{tag}' for tag in hashtags)}"
        
        if platform == "twitter":
            success = await post_to_twitter(full_content)
        elif platform == "linkedin":
            success = await post_to_linkedin(full_content)
        else:
            success = False
        
        if success:
            social_posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {
                    "$set": {
                        "status": "posted",
                        "posted_at": datetime.now()
                    }
                }
            )
        else:
            social_posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {"status": "failed"}}
            )
            
    except Exception as e:
        print(f"Error posting to platform: {str(e)}")

async def post_to_twitter(content: str) -> bool:
    """Post to Twitter/X API"""
    try:
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
            print("Twitter API credentials not configured")
            return False
        
        # Twitter API v2 implementation
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {TWITTER_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {"text": content}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return response.status == 201
                
    except Exception as e:
        print(f"Twitter API error: {str(e)}")
        return False

async def post_to_linkedin(content: str) -> bool:
    """Post to LinkedIn API"""
    try:
        if not LINKEDIN_ACCESS_TOKEN:
            print("LinkedIn API credentials not configured")
            return False
        
        # LinkedIn UGC API implementation
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        # Get user profile ID (simplified)
        person_urn = "person"  # Would need to fetch actual URN
        
        payload = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return response.status == 201
                
    except Exception as e:
        print(f"LinkedIn API error: {str(e)}")
        return False

async def schedule_post(post_id: str):
    """Schedule a post for future posting"""
    try:
        post = social_posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post or not post.get('scheduled_for'):
            return
        
        scheduled_time = post['scheduled_for']
        now = datetime.now()
        
        if scheduled_time <= now:
            await post_to_platform(post_id)
        else:
            delay = (scheduled_time - now).total_seconds()
            await asyncio.sleep(delay)
            await post_to_platform(post_id)
            
    except Exception as e:
        print(f"Error scheduling post: {str(e)}")

@app.post("/campaign/create")
async def create_campaign(request: CampaignRequest, background_tasks: BackgroundTasks):
    """Create an automated social media campaign"""
    try:
        campaign_doc = {
            "name": request.name,
            "funnel_id": request.funnel_id,
            "platforms": request.platforms,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "posts_per_day": request.posts_per_day,
            "status": "active",
            "created_at": datetime.now()
        }
        
        result = social_campaigns_collection.insert_one(campaign_doc)
        campaign_id = str(result.inserted_id)
        
        # Start campaign automation
        background_tasks.add_task(run_campaign, campaign_id)
        
        return {
            "status": "success",
            "campaign_id": campaign_id,
            "message": "Social media campaign created and started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_campaign(campaign_id: str):
    """Execute automated social media campaign"""
    try:
        campaign = social_campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            return
        
        funnel_id = campaign['funnel_id']
        platforms = campaign['platforms']
        posts_per_day = campaign['posts_per_day']
        
        # Get funnel details for content generation
        funnel = db.funnels.find_one({"_id": ObjectId(funnel_id)})
        if not funnel:
            return
        
        product_name = funnel.get('productName', '')
        value_proposition = funnel.get('valueProposition', '')
        target_audience = funnel.get('targetAudience', {})
        
        while campaign['status'] == 'active':
            now = datetime.now()
            
            if now < campaign['start_date']:
                await asyncio.sleep(60)
                continue
            
            if now > campaign['end_date']:
                social_campaigns_collection.update_one(
                    {"_id": ObjectId(campaign_id)},
                    {"$set": {"status": "completed"}}
                )
                break
            
            # Generate and post content
            for platform in platforms:
                for _ in range(posts_per_day):
                    topic = f"{product_name} - {value_proposition}"
                    
                    # Generate content
                    content_response = await generate_content(ContentGenerationRequest(
                        topic=topic,
                        platform=platform,
                        funnel_id=funnel_id
                    ))
                    
                    if content_response['status'] == 'success':
                        # Create post
                        await create_post(SocialPostRequest(
                            platform=platform,
                            content=content_response['content'],
                            funnel_id=funnel_id,
                            hashtags=["#marketing", "#growth", "#automation"]
                        ))
                    
                    await asyncio.sleep(3600)  # Wait 1 hour between posts
            
            await asyncio.sleep(86400)  # Wait 1 day before next batch
            
    except Exception as e:
        print(f"Error running campaign: {str(e)}")

@app.get("/posts")
async def get_posts(funnel_id: Optional[str] = None, platform: Optional[str] = None):
    """Get social media posts"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    if platform:
        query['platform'] = platform
    
    posts = list(social_posts_collection.find(query).sort("created_at", -1))
    return {"posts": [_serialize_doc(post) for post in posts]}

@app.get("/campaigns")
async def get_campaigns(funnel_id: Optional[str] = None):
    """Get social media campaigns"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    campaigns = list(social_campaigns_collection.find(query))
    return {"campaigns": [_serialize_doc(campaign) for campaign in campaigns]}

@app.delete("/campaign/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """Delete a social media campaign"""
    try:
        social_campaigns_collection.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {"status": "cancelled"}}
        )
        
        return {"status": "cancelled", "message": "Campaign cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{campaign_id}")
async def get_campaign_analytics(campaign_id: str):
    """Get analytics for a campaign"""
    try:
        campaign = social_campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        posts = list(social_posts_collection.find({"funnel_id": campaign['funnel_id']}))
        
        total_impressions = sum(p.get('analytics', {}).get('impressions', 0) for p in posts)
        total_engagements = sum(p.get('analytics', {}).get('engagements', 0) for p in posts)
        total_clicks = sum(p.get('analytics', {}).get('clicks', 0) for p in posts)
        
        return {
            "campaign": _serialize_doc(campaign),
            "analytics": {
                "total_posts": len(posts),
                "total_impressions": total_impressions,
                "total_engagements": total_engagements,
                "total_clicks": total_clicks,
                "engagement_rate": (total_engagements / total_impressions * 100) if total_impressions > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "social-media",
        "twitter_configured": bool(TWITTER_API_KEY),
        "linkedin_configured": bool(LINKEDIN_ACCESS_TOKEN),
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
