"""
Traffic Acquisition Service - Autonomous traffic generation
Handles social media automation, SEO automation, and paid traffic
"""
import os
import json
import asyncio
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
import redis
import aiohttp
import openai

# Initialize FastAPI app
app = FastAPI(title="Traffic Acquisition Service", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Social Media API Keys (optional)
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")

# Initialize clients
openai.api_key = OPENAI_API_KEY
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
traffic_campaigns_collection = db.traffic_campaigns
social_posts_collection = db.social_posts
seo_tasks_collection = db.seo_tasks

class TrafficCampaign(BaseModel):
    funnel_id: str
    campaign_name: str
    channels: List[str]  # twitter, linkedin, facebook, instagram, seo, ads
    budget: Optional[float] = None
    target_audience: Dict
    duration_days: int = 30
    auto_optimize: bool = True

class SocialPostRequest(BaseModel):
    funnel_id: str
    platform: str
    content_type: str  # promotional, educational, engagement, announcement
    topic: Optional[str] = None
    schedule: Optional[Dict] = None

class SEOTaskRequest(BaseModel):
    funnel_id: str
    target_keywords: List[str]
    content_types: List[str]  # blog, article, infographic, video
    priority: str = "medium"

class TrafficResponse(BaseModel):
    campaign_id: str
    status: str
    message: str
    scheduled_tasks: List[str]

@app.post("/campaign/create")
async def create_traffic_campaign(campaign: TrafficCampaign, background_tasks: BackgroundTasks):
    """Create and launch autonomous traffic campaign"""
    try:
        # Validate channels
        valid_channels = ['twitter', 'linkedin', 'facebook', 'instagram', 'seo', 'ads']
        for channel in campaign.channels:
            if channel not in valid_channels:
                raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        
        # Create campaign document
        campaign_doc = {
            "funnel_id": campaign.funnel_id,
            "campaign_name": campaign.campaign_name,
            "channels": campaign.channels,
            "budget": campaign.budget,
            "target_audience": campaign.target_audience,
            "duration_days": campaign.duration_days,
            "auto_optimize": campaign.auto_optimize,
            "created_at": datetime.now(),
            "status": "active",
            "end_date": datetime.now() + timedelta(days=campaign.duration_days),
            "stats": {
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "cost": 0.0,
                "ctr": 0.0,
                "cpa": 0.0
            }
        }
        
        result = traffic_campaigns_collection.insert_one(campaign_doc)
        campaign_id = str(result.inserted_id)
        
        # Launch campaign tasks
        scheduled_tasks = []
        for channel in campaign.channels:
            if channel == 'seo':
                background_tasks.add_task(launch_seo_campaign, campaign_id, campaign)
                scheduled_tasks.append(f"SEO campaign for {campaign_id}")
            elif channel in ['twitter', 'linkedin', 'facebook', 'instagram']:
                background_tasks.add_task(launch_social_campaign, campaign_id, campaign, channel)
                scheduled_tasks.append(f"Social campaign on {channel} for {campaign_id}")
            elif channel == 'ads':
                background_tasks.add_task(launch_ad_campaign, campaign_id, campaign)
                scheduled_tasks.append(f"Ad campaign for {campaign_id}")
        
        return TrafficResponse(
            campaign_id=campaign_id,
            status="active",
            message=f"Traffic campaign created and launched across {len(campaign.channels)} channels",
            scheduled_tasks=scheduled_tasks
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def launch_social_campaign(campaign_id: str, campaign: TrafficCampaign, platform: str):
    """Launch social media automation campaign"""
    funnel = db.funnels.find_one({"_id": campaign.funnel_id})
    if not funnel:
        return
    
    # Generate content schedule
    content_schedule = await generate_social_content_schedule(campaign, platform, funnel)
    
    # Schedule posts
    for content_item in content_schedule:
        post_doc = {
            "campaign_id": campaign_id,
            "platform": platform,
            "content": content_item['content'],
            "scheduled_at": content_item['scheduled_at'],
            "status": "scheduled",
            "created_at": datetime.now(),
            "stats": {
                "impressions": 0,
                "engagements": 0,
                "clicks": 0,
                "shares": 0
            }
        }
        
        result = social_posts_collection.insert_one(post_doc)
        
        # Schedule actual posting
        delay = (content_item['scheduled_at'] - datetime.now()).total_seconds()
        if delay > 0:
            asyncio.create_task(schedule_social_post(str(result.inserted_id), delay))

async def generate_social_content_schedule(campaign: TrafficCampaign, platform: str, funnel: Dict) -> List[Dict]:
    """Generate AI-powered social content schedule"""
    schedule = []
    posts_per_day = {'twitter': 3, 'linkedin': 1, 'facebook': 2, 'instagram': 1}.get(platform, 1)
    
    for day in range(campaign.duration_days):
        for post_num in range(posts_per_day):
            # Generate content using AI
            content = await generate_social_post_content(
                platform=platform,
                funnel=funnel,
                target_audience=campaign.target_audience,
                content_type=random.choice(['promotional', 'educational', 'engagement'])
            )
            
            # Schedule time (spread throughout the day)
            hour = 9 + (post_num * 6)  # 9 AM, 3 PM, 9 PM
            scheduled_time = datetime.now() + timedelta(days=day, hours=hour)
            
            schedule.append({
                "content": content,
                "scheduled_at": scheduled_time
            })
    
    return schedule

async def generate_social_post_content(platform: str, funnel: Dict, target_audience: Dict, content_type: str) -> str:
    """Generate social media post content using AI"""
    product_name = funnel.get('productName', 'our product')
    value_proposition = funnel.get('valueProposition', 'amazing value')
    
    prompt = f"""
    Create a {content_type} social media post for {platform}.
    
    Product: {product_name}
    Value Proposition: {value_proposition}
    Target Audience: {target_audience.get('description', 'general audience')}
    
    Requirements:
    - Platform-specific format and tone
    - Include relevant hashtags
    - Compelling hook
    - Clear call-to-action
    - Optimal length for {platform}
    
    Content Type: {content_type}
    - Promotional: Focus on product benefits and urgency
    - Educational: Share valuable insights related to the product
    - Engagement: Ask questions, encourage interaction
    
    Generate the post content.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You are a social media expert specializing in {platform} marketing with high engagement rates."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=500
    )
    
    return response.choices[0].message.content

async def schedule_social_post(post_id: str, delay_seconds: float):
    """Schedule and execute social media post"""
    await asyncio.sleep(delay_seconds)
    
    post = social_posts_collection.find_one({"_id": post_id})
    if not post or post['status'] != 'scheduled':
        return
    
    try:
        # Post to platform
        success = await post_to_social_media(post['platform'], post['content'])
        
        if success:
            social_posts_collection.update_one(
                {"_id": post_id},
                {
                    "$set": {
                        "status": "posted",
                        "posted_at": datetime.now()
                    }
                }
            )
        else:
            social_posts_collection.update_one(
                {"_id": post_id},
                {"$set": {"status": "failed"}}
            )
    except Exception as e:
        print(f"Error posting to social media: {str(e)}")
        social_posts_collection.update_one(
            {"_id": post_id},
            {"$set": {"status": "failed"}}
        )

async def post_to_social_media(platform: str, content: str) -> bool:
    """Post content to social media platform"""
    try:
        if platform == 'twitter' and TWITTER_ACCESS_TOKEN:
            return await post_to_twitter(content)
        elif platform == 'linkedin' and LINKEDIN_ACCESS_TOKEN:
            return await post_to_linkedin(content)
        elif platform == 'facebook' and FACEBOOK_ACCESS_TOKEN:
            return await post_to_facebook(content)
        else:
            # Log for manual posting if API not configured
            print(f"Manual posting required for {platform}: {content}")
            return True
    except Exception as e:
        print(f"Error posting to {platform}: {str(e)}")
        return False

async def post_to_twitter(content: str) -> bool:
    """Post to Twitter API"""
    # Implementation would use tweepy or similar
    # For now, placeholder
    print(f"Twitter post: {content[:100]}...")
    return True

async def post_to_linkedin(content: str) -> bool:
    """Post to LinkedIn API"""
    # Implementation would use LinkedIn API
    print(f"LinkedIn post: {content[:100]}...")
    return True

async def post_to_facebook(content: str) -> bool:
    """Post to Facebook API"""
    # Implementation would use Facebook Graph API
    print(f"Facebook post: {content[:100]}...")
    return True

async def launch_seo_campaign(campaign_id: str, campaign: TrafficCampaign):
    """Launch SEO automation campaign"""
    funnel = db.funnels.find_one({"_id": campaign.funnel_id})
    if not funnel:
        return
    
    # Generate SEO tasks
    seo_tasks = await generate_seo_tasks(campaign, funnel)
    
    for task in seo_tasks:
        task_doc = {
            "campaign_id": campaign_id,
            "funnel_id": campaign.funnel_id,
            "task_type": task['type'],
            "keywords": task['keywords'],
            "content": task.get('content', ''),
            "status": "pending",
            "priority": task.get('priority', 'medium'),
            "created_at": datetime.now(),
            "scheduled_at": task.get('scheduled_at', datetime.now())
        }
        
        seo_tasks_collection.insert_one(task_doc)

async def generate_seo_tasks(campaign: TrafficCampaign, funnel: Dict) -> List[Dict]:
    """Generate SEO tasks using AI"""
    tasks = []
    
    # Generate keyword research
    keywords = await generate_keywords(funnel)
    
    # Generate content ideas
    content_ideas = await generate_seo_content_ideas(funnel, keywords)
    
    for idea in content_ideas:
        tasks.append({
            "type": idea['type'],
            "keywords": idea['keywords'],
            "title": idea['title'],
            "priority": "high",
            "scheduled_at": datetime.now() + timedelta(days=random.randint(1, 7))
        })
    
    return tasks

async def generate_keywords(funnel: Dict) -> List[str]:
    """Generate SEO keywords using AI"""
    product_name = funnel.get('productName', '')
    value_proposition = funnel.get('valueProposition', '')
    
    prompt = f"""
    Generate 20 high-value SEO keywords for:
    Product: {product_name}
    Value: {value_proposition}
    
    Focus on:
    - Long-tail keywords with commercial intent
    - Problem-solving keywords
    - Industry-specific terms
    - Location-based keywords (if applicable)
    
    Return as a comma-separated list.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SEO expert with deep knowledge of keyword research and search intent."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=300
    )
    
    keywords_text = response.choices[0].message.content
    return [k.strip() for k in keywords_text.split(',')]

async def generate_seo_content_ideas(funnel: Dict, keywords: List[str]) -> List[Dict]:
    """Generate SEO content ideas"""
    prompt = f"""
    Generate 10 SEO content ideas using these keywords: {', '.join(keywords[:10])}
    
    For each idea, provide:
    - Content type (blog post, article, infographic, video)
    - Target keywords
    - Title/headline
    - Brief description
    
    Format as JSON array.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SEO content strategist with expertise in content marketing and search optimization."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=1000
    )
    
    try:
        ideas = json.loads(response.choices[0].message.content)
        return ideas
    except:
        # Fallback ideas
        return [
            {
                "type": "blog",
                "keywords": keywords[:3],
                "title": f"Ultimate Guide to {funnel.get('productName', 'Our Product')}"
            }
        ]

async def launch_ad_campaign(campaign_id: str, campaign: TrafficCampaign):
    """Launch paid advertising campaign"""
    funnel = db.funnels.find_one({"_id": campaign.funnel_id})
    if not funnel:
        return
    
    # Generate ad creatives
    ad_creatives = await generate_ad_creatives(campaign, funnel)
    
    # In production, this would integrate with Facebook Ads, Google Ads, etc.
    print(f"Ad campaign {campaign_id} creatives generated for {len(ad_creatives)} platforms")

async def generate_ad_creatives(campaign: TrafficCampaign, funnel: Dict) -> List[Dict]:
    """Generate ad creatives using AI"""
    prompt = f"""
    Generate ad creatives for:
    Product: {funnel.get('productName', '')}
    Value: {funnel.get('valueProposition', '')}
    Target Audience: {campaign.target_audience.get('description', '')}
    Budget: ${campaign.budget if campaign.budget else 'Not specified'}
    
    Create variations for:
    1. Facebook/Instagram (image + copy)
    2. Google Search (headlines + descriptions)
    3. LinkedIn (professional copy)
    
    For each, provide:
    - Platform
    - Headline
    - Primary text
    - Call-to-action
    - Target keywords
    
    Format as JSON array.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a paid advertising specialist with high ROI campaigns across multiple platforms."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=1500
    )
    
    try:
        creatives = json.loads(response.choices[0].message.content)
        return creatives
    except:
        return []

@app.post("/social/post")
async def create_social_post(request: SocialPostRequest, background_tasks: BackgroundTasks):
    """Create and schedule individual social post"""
    try:
        funnel = db.funnels.find_one({"_id": request.funnel_id})
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        # Generate content
        content = await generate_social_post_content(
            platform=request.platform,
            funnel=funnel,
            target_audience=funnel.get('targetAudience', {}),
            content_type=request.content_type
        )
        
        # Schedule post
        scheduled_at = request.schedule.get('datetime', datetime.now()) if request.schedule else datetime.now()
        
        post_doc = {
            "funnel_id": request.funnel_id,
            "platform": request.platform,
            "content": content,
            "content_type": request.content_type,
            "scheduled_at": scheduled_at,
            "status": "scheduled",
            "created_at": datetime.now(),
            "stats": {
                "impressions": 0,
                "engagements": 0,
                "clicks": 0,
                "shares": 0
            }
        }
        
        result = social_posts_collection.insert_one(post_doc)
        
        # Schedule posting
        if scheduled_at > datetime.now():
            delay = (scheduled_at - datetime.now()).total_seconds()
            background_tasks.add_task(schedule_social_post, str(result.inserted_id), delay)
        
        return {
            "post_id": str(result.inserted_id),
            "status": "scheduled",
            "scheduled_at": scheduled_at,
            "content": content
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/seo/tasks")
async def create_seo_tasks(request: SEOTaskRequest):
    """Create SEO optimization tasks"""
    try:
        funnel = db.funnels.find_one({"_id": request.funnel_id})
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        tasks = []
        for content_type in request.content_types:
            for keyword in request.target_keywords[:5]:  # Limit to 5 keywords per type
                task_doc = {
                    "funnel_id": request.funnel_id,
                    "task_type": content_type,
                    "keywords": [keyword],
                    "status": "pending",
                    "priority": request.priority,
                    "created_at": datetime.now()
                }
                
                result = seo_tasks_collection.insert_one(task_doc)
                tasks.append(str(result.inserted_id))
        
        return {
            "status": "success",
            "tasks_created": len(tasks),
            "task_ids": tasks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/campaigns")
async def get_campaigns(funnel_id: Optional[str] = None):
    """Get traffic campaigns"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    campaigns = list(traffic_campaigns_collection.find(query))
    return {"campaigns": campaigns}

@app.get("/social/posts")
async def get_social_posts(funnel_id: Optional[str] = None, status: Optional[str] = None):
    """Get social media posts"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    if status:
        query['status'] = status
    
    posts = list(social_posts_collection.find(query))
    return {"posts": posts}

@app.get("/seo/tasks")
async def get_seo_tasks(funnel_id: Optional[str] = None):
    """Get SEO tasks"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    tasks = list(seo_tasks_collection.find(query))
    return {"tasks": tasks}

@app.get("/analytics/{campaign_id}")
async def get_campaign_analytics(campaign_id: str):
    """Get analytics for a traffic campaign"""
    campaign = traffic_campaigns_collection.find_one({"_id": campaign_id})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Aggregate stats from social posts
    social_posts = list(social_posts_collection.find({"campaign_id": campaign_id}))
    
    total_impressions = sum(p.get('stats', {}).get('impressions', 0) for p in social_posts)
    total_engagements = sum(p.get('stats', {}).get('engagements', 0) for p in social_posts)
    total_clicks = sum(p.get('stats', {}).get('clicks', 0) for p in social_posts)
    
    return {
        "campaign": campaign,
        "social_stats": {
            "total_posts": len(social_posts),
            "total_impressions": total_impressions,
            "total_engagements": total_engagements,
            "total_clicks": total_clicks,
            "engagement_rate": (total_engagements / total_impressions * 100) if total_impressions > 0 else 0
        },
        "campaign_stats": campaign.get('stats', {})
    }

@app.post("/optimize/{campaign_id}")
async def optimize_campaign(campaign_id: str):
    """Auto-optimize campaign based on performance"""
    try:
        campaign = traffic_campaigns_collection.find_one({"_id": campaign_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        if not campaign['auto_optimize']:
            raise HTTPException(status_code=400, detail="Auto-optimization not enabled")
        
        # Get performance data
        analytics = await get_campaign_analytics(campaign_id)
        
        # Generate optimization suggestions using AI
        suggestions = await generate_optimization_suggestions(campaign, analytics)
        
        return {
            "status": "success",
            "suggestions": suggestions,
            "message": "Campaign optimization analysis completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def generate_optimization_suggestions(campaign: Dict, analytics: Dict) -> List[Dict]:
    """Generate AI-powered optimization suggestions"""
    prompt = f"""
    Analyze this traffic campaign performance and provide optimization suggestions:
    
    Campaign: {campaign['campaign_name']}
    Channels: {', '.join(campaign['channels'])}
    Duration: {campaign['duration_days']} days
    
    Performance:
    - Impressions: {analytics['campaign_stats'].get('impressions', 0)}
    - Clicks: {analytics['campaign_stats'].get('clicks', 0)}
    - Conversions: {analytics['campaign_stats'].get('conversions', 0)}
    - CTR: {analytics['campaign_stats'].get('ctr', 0)}%
    - CPA: ${analytics['campaign_stats'].get('cpa', 0)}
    
    Provide specific recommendations for:
    1. Budget reallocation
    2. Content improvements
    3. Targeting adjustments
    4. Timing optimization
    5. Channel performance
    
    Format as JSON array of actionable suggestions.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a digital marketing optimization expert with proven track record of improving campaign performance."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    
    try:
        suggestions = json.loads(response.choices[0].message.content)
        return suggestions
    except:
        return []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "traffic-acquisition",
        "social_apis_configured": {
            "twitter": bool(TWITTER_ACCESS_TOKEN),
            "linkedin": bool(LINKEDIN_ACCESS_TOKEN),
            "facebook": bool(FACEBOOK_ACCESS_TOKEN)
        },
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
