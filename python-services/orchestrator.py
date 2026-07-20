"""
Orchestrator Service - Central coordination for autonomous funnel operations
Coordinates all services: content generation, email automation, lead optimization,
conversion optimization, Gumroad integration, and traffic acquisition
"""
import os
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from bson.errors import InvalidId
import redis
import aiohttp
import openai


# Initialize FastAPI app
app = FastAPI(title="Orchestrator Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Service URLs
CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://localhost:8001")
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "http://localhost:8003")
LEAD_SERVICE_URL = os.getenv("LEAD_SERVICE_URL", "http://localhost:8002")
CONVERSION_SERVICE_URL = os.getenv("CONVERSION_SERVICE_URL", "http://localhost:8004")
GUMROAD_SERVICE_URL = os.getenv("GUMROAD_SERVICE_URL", "http://localhost:8005")
TRAFFIC_SERVICE_URL = os.getenv("TRAFFIC_SERVICE_URL", "http://localhost:8006")
SOCIAL_SERVICE_URL = os.getenv("SOCIAL_SERVICE_URL", "http://localhost:8007")

# Initialize clients
openai.api_key = OPENAI_API_KEY
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
funnels_collection = db.funnels
orchestrator_logs_collection = db.orchestrator_logs
automation_workflows_collection = db.automation_workflows

def _to_object_id(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return value

def _serialize_doc(doc: Optional[Dict]) -> Optional[Dict]:
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                _serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result

def _normalize_gumroad_product(raw: Dict) -> Dict:
    product_id = raw.get("product_id") or raw.get("id")
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {
        "product_id": product_id,
        "name": raw.get("name", ""),
        "description": raw.get("description", ""),
        "price": float(raw.get("price", 0) or 0),
        "url": raw.get("url", ""),
        "published": raw.get("published", False),
        "tags": tags,
    }

class FunnelCreationRequest(BaseModel):
    name: str
    gumroad_product_id: Optional[str] = None
    target_audience: Dict
    goals: List[str]
    budget: Optional[float] = None
    auto_launch: bool = True
    # Product creation fields
    create_product: bool = False
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    product_price: Optional[float] = None
    product_tags: Optional[List[str]] = None

class AutomationWorkflow(BaseModel):
    funnel_id: str
    workflow_name: str
    triggers: List[Dict]
    actions: List[Dict]
    enabled: bool = True

class FunnelLaunchRequest(BaseModel):
    funnel_id: Optional[str] = None
    launch_traffic: bool = True
    launch_email_campaign: bool = True
    launch_seo: bool = True

class OrchestratorResponse(BaseModel):
    workflow_id: str
    status: str
    message: str
    tasks_completed: List[str]

@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator on startup"""
    # Resume any paused workflows
    await resume_paused_workflows()

async def resume_paused_workflows():
    """Resume workflows that were paused"""
    paused_workflows = automation_workflows_collection.find({"status": "paused"})
    for workflow in paused_workflows:
        if workflow.get('enabled'):
            asyncio.create_task(execute_workflow(str(workflow['_id'])))

@app.post("/funnel/create")
async def create_autonomous_funnel(request: FunnelCreationRequest, background_tasks: BackgroundTasks):
    """Create a fully autonomous funnel from Gumroad product or create new product"""
    try:
        product_id = request.gumroad_product_id
        product = None
        
        # Step 1: Create product if requested
        if request.create_product:
            if not all([request.product_name, request.product_description, request.product_price]):
                raise HTTPException(status_code=400, detail="Product name, description, and price are required when create_product is true")
            
            # Create product via Gumroad service
            product = await create_gumroad_product(
                request.product_name,
                request.product_description,
                request.product_price,
                request.product_tags or [],
                funnel_id=None  # Will set after funnel creation
            )
            product_id = product['product_id']
        else:
            # Step 1: Fetch Gumroad product details
            if not product_id:
                raise HTTPException(status_code=400, detail="gumroad_product_id is required when create_product is false")
            product = await fetch_gumroad_product(product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Gumroad product not found")
        
        # Step 2: Create funnel structure
        funnel_id = await create_funnel_structure(request, product)
        
        # Step 3: Map product to funnel
        await map_product_to_funnel(product_id, funnel_id)
        
        # Step 4: Generate initial content
        content_tasks = await generate_initial_content(funnel_id, product, request.target_audience)
        
        # Step 5: Set up email automation
        email_setup = await setup_email_automation(funnel_id, request.target_audience)
        
        # Step 6: Configure lead scoring
        lead_setup = await configure_lead_scoring(funnel_id)
        
        # Step 7: Set up social media automation
        social_setup = await setup_social_media_automation(funnel_id, product, request.target_audience)
        
        # Step 8: Create automation workflow
        workflow_id = await create_automation_workflow(funnel_id, request)
        
        # Step 8: Launch if auto_launch is enabled
        if request.auto_launch:
            background_tasks.add_task(
                _execute_funnel_launch,
                funnel_id,
                FunnelLaunchRequest(
                    funnel_id=funnel_id,
                    launch_traffic=True,
                    launch_email_campaign=True,
                    launch_seo=True
                ),
            )
        
        return {
            "funnel_id": funnel_id,
            "workflow_id": workflow_id,
            "product_id": product_id,
            "status": "created",
            "message": "Autonomous funnel created successfully",
            "components": {
                "content_generated": len(content_tasks),
                "email_automation": email_setup,
                "lead_scoring": lead_setup,
                "auto_launched": request.auto_launch,
                "product_created": request.create_product
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error creating funnel: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_gumroad_product(product_id: str) -> Optional[Dict]:
    """Fetch product from synced MongoDB data or Gumroad product list API."""
    try:
        cached = db.gumroad_products.find_one({"product_id": product_id})
        if cached:
            return _normalize_gumroad_product(cached)

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{GUMROAD_SERVICE_URL}/sync/products") as sync_response:
                pass

        cached = db.gumroad_products.find_one({"product_id": product_id})
        if cached:
            return _normalize_gumroad_product(cached)

        gumroad_token = os.getenv("GUMROAD_ACCESS_TOKEN")
        if not gumroad_token:
            return None

        async with aiohttp.ClientSession() as session:
            url = "https://api.gumroad.com/v2/products"
            headers = {"Authorization": f"Bearer {gumroad_token}"}
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    for product in data.get("products", []):
                        if product.get("id") == product_id:
                            return _normalize_gumroad_product(product)
        return None
    except Exception as e:
        print(f"Error fetching Gumroad product: {str(e)}")
        return None

async def create_gumroad_product(name: str, description: str, price: float, tags: List[str], funnel_id: Optional[str] = None) -> Dict:
    """Create a new product via Gumroad service"""
    try:
        payload = {
            "name": name,
            "description": description,
            "price": price,
            "tags": tags,
            "published": False,
            "funnel_id": funnel_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{GUMROAD_SERVICE_URL}/product/create", json=payload) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise HTTPException(status_code=response.status, detail=error_data.get('message', 'Failed to create product'))
                
                data = await response.json()
                return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def create_funnel_structure(request: FunnelCreationRequest, product: Dict) -> str:
    """Create funnel structure in database"""
    funnel_doc = {
        "name": request.name,
        "gumroad_product_id": request.gumroad_product_id,
        "productName": product['name'],
        "valueProposition": product.get('description', ''),
        "targetAudience": request.target_audience,
        "goals": request.goals,
        "budget": request.budget,
        "created_at": datetime.now(),
        "status": "draft",
        "landingPages": [],
        "leadMagnets": [],
        "emailSequences": [],
        "analytics": {
            "visitors": 0,
            "leads": 0,
            "conversions": 0,
            "revenue": 0,
            "conversionRate": 0
        },
        "automation": {
            "enabled": True,
            "last_run": None
        }
    }
    
    result = funnels_collection.insert_one(funnel_doc)
    return str(result.inserted_id)

async def map_product_to_funnel(product_id: str, funnel_id: str):
    """Map Gumroad product to funnel"""
    mapping_doc = {
        "product_id": product_id,
        "funnel_id": funnel_id,
        "auto_sync": True,
        "lead_source": "gumroad",
        "created_at": datetime.now()
    }
    
    existing = db.funnel_mappings.find_one({"product_id": product_id})
    if existing:
        db.funnel_mappings.update_one({"product_id": product_id}, {"$set": mapping_doc})
    else:
        db.funnel_mappings.insert_one(mapping_doc)

async def generate_initial_content(funnel_id: str, product: Dict, target_audience: Dict) -> List[str]:
    """Generate initial content for funnel"""
    content_types = ['blog', 'social', 'landing_page', 'email']
    generated_content = []
    
    for content_type in content_types:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "funnel_id": funnel_id,
                    "content_type": content_type,
                    "topic": product['name'],
                    "target_audience": target_audience.get('description', 'general audience'),
                    "keywords": [product['name'], product.get('tags', [''])[0] if product.get('tags') else ''],
                    "tone": "professional"
                }
                
                async with session.post(f"{CONTENT_SERVICE_URL}/generate", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        generated_content.append(data['content_id'])
        except Exception as e:
            print(f"Error generating {content_type} content: {str(e)}")
    
    return generated_content

async def setup_email_automation(funnel_id: str, target_audience: Dict) -> Dict:
    """Set up email automation for funnel"""
    try:
        async with aiohttp.ClientSession() as session:
            # Create welcome email template
            template_payload = {
                "name": "Welcome Sequence",
                "subject": "Welcome to {{ first_name }}!",
                "body": """
                <h1>Welcome to our community!</h1>
                <p>Hi {{ first_name }},</p>
                <p>Thanks for joining us. We're excited to have you on board.</p>
                <p>Here's what you can expect from us:</p>
                <ul>
                    <li>Valuable tips and insights</li>
                    <li>Exclusive offers</li>
                    <li>Early access to new features</li>
                </ul>
                <p>Best regards,<br>The Team</p>
                """,
                "template_type": "welcome",
                "variables": ["first_name", "email"],
                "tags": ["welcome", "onboarding"]
            }
            
            async with session.post(f"{EMAIL_SERVICE_URL}/templates", json=template_payload) as response:
                if response.status == 200:
                    data = await response.json()
                    template_id = data['email_id']
                    
                    # Create campaign
                    campaign_payload = {
                        "name": "Welcome Campaign",
                        "funnel_id": funnel_id,
                        "template_id": template_id,
                        "trigger": "new_lead",
                        "schedule": {"delay_hours": 0},
                        "personalization": {}
                    }
                    
                    async with session.post(f"{EMAIL_SERVICE_URL}/campaigns", json=campaign_payload) as campaign_response:
                        if campaign_response.status == 200:
                            return {"status": "success", "template_id": template_id}
        
        return {"status": "failed"}
    except Exception as e:
        print(f"Error setting up email automation: {str(e)}")
        return {"status": "failed"}

async def configure_lead_scoring(funnel_id: str) -> Dict:
    """Configure lead scoring for funnel"""
    try:
        async with aiohttp.ClientSession() as session:
            # Segment leads
            segment_payload = {
                "funnel_id": funnel_id,
                "criteria": {},
                "segment_count": 3
            }
            
            async with session.post(f"{LEAD_SERVICE_URL}/segment", json=segment_payload) as response:
                if response.status == 200:
                    return {"status": "success", "segments_configured": 3}
        
        return {"status": "failed"}
    except Exception as e:
        print(f"Error configuring lead scoring: {str(e)}")
        return {"status": "failed"}

async def setup_social_media_automation(funnel_id: str, product: Dict, target_audience: Dict) -> Dict:
    """Set up social media automation for funnel"""
    try:
        async with aiohttp.ClientSession() as session:
            # Create social media campaign
            from datetime import datetime, timedelta
            start_date = datetime.now()
            end_date = start_date + timedelta(days=30)
            
            campaign_payload = {
                "name": f"Auto Campaign for {product['name']}",
                "funnel_id": funnel_id,
                "platforms": ["twitter", "linkedin"],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "posts_per_day": 2
            }
            
            async with session.post(f"{SOCIAL_SERVICE_URL}/campaign/create", json=campaign_payload) as response:
                if response.status == 200:
                    return {"status": "configured", "funnel_id": funnel_id}
                return {"status": "failed"}
    except Exception as e:
        print(f"Error setting up social media automation: {str(e)}")
        return {"status": "failed"}

async def create_automation_workflow(funnel_id: str, request: FunnelCreationRequest) -> str:
    """Create automation workflow for funnel"""
    workflow_doc = {
        "funnel_id": funnel_id,
        "workflow_name": f"Autonomous Workflow - {request.name}",
        "triggers": [
            {"type": "new_lead", "action": "send_welcome_email"},
            {"type": "purchase", "action": "send_thank_you"},
            {"type": "abandoned_cart", "action": "send_recovery_email"},
            {"type": "low_engagement", "action": "send_re_engagement"}
        ],
        "actions": [
            {"type": "email", "service": "email_automation"},
            {"type": "lead_scoring", "service": "lead_optimization"},
            {"type": "content_generation", "service": "content_generator"},
            {"type": "traffic_generation", "service": "traffic_acquisition"}
        ],
        "enabled": True,
        "status": "active",
        "created_at": datetime.now(),
        "last_run": None
    }
    
    result = automation_workflows_collection.insert_one(workflow_doc)
    return str(result.inserted_id)

@app.post("/funnel/{funnel_id}/launch")
async def launch_funnel_endpoint(funnel_id: str, request: FunnelLaunchRequest, background_tasks: BackgroundTasks):
    """Launch autonomous funnel operations"""
    try:
        return await _execute_funnel_launch(funnel_id, request, background_tasks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _execute_funnel_launch(funnel_id: str, request: FunnelLaunchRequest, background_tasks: Optional[BackgroundTasks] = None):
    """Internal launch logic shared by API endpoint and background tasks."""
    funnel_oid = _to_object_id(funnel_id)
    funnel = funnels_collection.find_one({"_id": funnel_oid})
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")

    tasks_completed = []

    if request.launch_traffic:
        traffic_campaign = await launch_traffic_campaign(funnel_id, funnel)
        tasks_completed.append(f"Traffic campaign: {traffic_campaign}")

    if request.launch_email_campaign:
        email_campaign = await launch_email_campaign(funnel_id)
        tasks_completed.append(f"Email campaign: {email_campaign}")

    if request.launch_seo:
        seo_campaign = await launch_seo_campaign(funnel_id)
        tasks_completed.append(f"SEO campaign: {seo_campaign}")

    funnels_collection.update_one(
        {"_id": funnel_oid},
        {
            "$set": {
                "status": "active",
                "launched_at": datetime.now(),
                "automation.last_run": datetime.now()
            }
        }
    )

    if background_tasks:
        background_tasks.add_task(run_continuous_optimization, funnel_id)
    else:
        asyncio.create_task(run_continuous_optimization(funnel_id))

    return {
        "funnel_id": funnel_id,
        "status": "launched",
        "message": "Funnel launched successfully",
        "tasks_completed": tasks_completed
    }

async def launch_traffic_campaign(funnel_id: str, funnel: Dict) -> str:
    """Launch traffic campaign"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "funnel_id": funnel_id,
                "campaign_name": f"Traffic - {funnel['name']}",
                "channels": ["twitter", "linkedin", "seo"],
                "target_audience": funnel.get('targetAudience', {}),
                "duration_days": 30,
                "auto_optimize": True
            }
            
            async with session.post(f"{TRAFFIC_SERVICE_URL}/campaign/create", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['campaign_id']
        
        return "failed"
    except Exception as e:
        print(f"Error launching traffic campaign: {str(e)}")
        return "failed"

async def launch_email_campaign(funnel_id: str) -> str:
    """Launch email campaign"""
    try:
        async with aiohttp.ClientSession() as session:
            # Get existing templates
            async with session.get(f"{EMAIL_SERVICE_URL}/templates") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('templates'):
                        template_id = data['templates'][0]['_id']
                        
                        payload = {
                            "name": "Nurture Campaign",
                            "funnel_id": funnel_id,
                            "template_id": template_id,
                            "trigger": "time_based",
                            "schedule": {"frequency": "weekly"},
                            "personalization": {}
                        }
                        
                        async with session.post(f"{EMAIL_SERVICE_URL}/campaigns", json=payload) as campaign_response:
                            if campaign_response.status == 200:
                                campaign_data = await campaign_response.json()
                                return campaign_data['email_id']
        
        return "failed"
    except Exception as e:
        print(f"Error launching email campaign: {str(e)}")
        return "failed"

async def launch_seo_campaign(funnel_id: str) -> str:
    """Launch SEO campaign"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "funnel_id": funnel_id,
                "target_keywords": ["digital product", "online course", funnel.get('productName', '')],
                "content_types": ["blog", "article"],
                "priority": "high"
            }
            
            async with session.post(f"{TRAFFIC_SERVICE_URL}/seo/tasks", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return f"{data['tasks_created']} tasks created"
        
        return "failed"
    except Exception as e:
        print(f"Error launching SEO campaign: {str(e)}")
        return "failed"

async def run_continuous_optimization(funnel_id: str):
    """Run continuous optimization loop"""
    while True:
        try:
            funnel = funnels_collection.find_one({"_id": _to_object_id(funnel_id)})
            if not funnel or funnel.get('status') != 'active':
                break
            
            # Sync Gumroad data
            await sync_gumroad_data(funnel_id)
            
            # Run A/B tests
            await run_ab_tests(funnel_id)
            
            # Optimize content
            await optimize_content(funnel_id)
            
            # Update analytics
            await update_funnel_analytics(funnel_id)
            
            # Log optimization run
            orchestrator_logs_collection.insert_one({
                "funnel_id": funnel_id,
                "action": "continuous_optimization",
                "timestamp": datetime.now(),
                "status": "success"
            })
            
            # Wait before next run (every 6 hours)
            await asyncio.sleep(21600)
            
        except Exception as e:
            print(f"Error in continuous optimization: {str(e)}")
            await asyncio.sleep(3600)  # Wait 1 hour on error

async def sync_gumroad_data(funnel_id: str):
    """Sync Gumroad sales and product data"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{GUMROAD_SERVICE_URL}/sync/sales") as response:
                if response.status == 200:
                    print(f"Gumroad data synced for funnel {funnel_id}")
    except:
        pass

async def run_ab_tests(funnel_id: str):
    """Run A/B tests for funnel optimization"""
    try:
        async with aiohttp.ClientSession() as session:
            # Check for active tests
            async with session.get(f"{CONVERSION_SERVICE_URL}/ab-test/active?funnel_id={funnel_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    if not data.get('tests'):
                        # Create new A/B test
                        test_payload = {
                            "funnel_id": funnel_id,
                            "test_name": "Headline Optimization",
                            "element_type": "headline",
                            "variants": [
                                {"id": "variant_a", "content": "Original Headline"},
                                {"id": "variant_b", "content": "AI-Optimized Headline"}
                            ],
                            "traffic_split": {"variant_a": 0.5, "variant_b": 0.5},
                            "test_duration_days": 7
                        }
                        
                        async with session.post(f"{CONVERSION_SERVICE_URL}/ab-test/create", json=test_payload) as test_response:
                            if test_response.status == 200:
                                print(f"A/B test created for funnel {funnel_id}")
    except:
        pass

async def optimize_content(funnel_id: str):
    """Optimize content based on performance"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{CONTENT_SERVICE_URL}/health") as response:
                if response.status == 200:
                    # Content optimization logic would go here
                    pass
    except:
        pass

async def update_funnel_analytics(funnel_id: str):
    """Update funnel analytics"""
    try:
        funnel = funnels_collection.find_one({"_id": _to_object_id(funnel_id)})
        
        # Get Gumroad sales
        gumroad_sales = list(db.gumroad_sales.find({"funnel_id": funnel_id}))
        
        # Get leads
        leads = list(db.leads.find({"funnel_id": funnel_id}))
        
        # Calculate metrics
        total_revenue = sum(sale['amount'] for sale in gumroad_sales)
        total_conversions = len(gumroad_sales)
        total_leads = len(leads)
        
        # Get traffic stats
        traffic_campaigns = list(db.traffic_campaigns.find({"funnel_id": funnel_id}))
        total_visitors = sum(c.get('stats', {}).get('impressions', 0) for c in traffic_campaigns)
        
        conversion_rate = (total_conversions / total_visitors * 100) if total_visitors > 0 else 0
        
        funnels_collection.update_one(
            {"_id": _to_object_id(funnel_id)},
            {
                "$set": {
                    "analytics.visitors": total_visitors,
                    "analytics.leads": total_leads,
                    "analytics.conversions": total_conversions,
                    "analytics.revenue": total_revenue,
                    "analytics.conversionRate": conversion_rate,
                    "updated_at": datetime.now()
                }
            }
        )
    except:
        pass

@app.post("/workflow/create")
async def create_workflow(workflow: AutomationWorkflow):
    """Create custom automation workflow"""
    try:
        workflow_doc = {
            "funnel_id": workflow.funnel_id,
            "workflow_name": workflow.workflow_name,
            "triggers": workflow.triggers,
            "actions": workflow.actions,
            "enabled": workflow.enabled,
            "status": "active" if workflow.enabled else "paused",
            "created_at": datetime.now(),
            "last_run": None
        }
        
        result = automation_workflows_collection.insert_one(workflow_doc)
        
        return {
            "workflow_id": str(result.inserted_id),
            "status": "created",
            "message": "Automation workflow created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/{workflow_id}/execute")
async def execute_workflow_endpoint(workflow_id: str, background_tasks: BackgroundTasks):
    """Manually execute a workflow"""
    background_tasks.add_task(execute_workflow, workflow_id)
    
    return {
        "workflow_id": workflow_id,
        "status": "executing",
        "message": "Workflow execution started"
    }

async def execute_workflow(workflow_id: str):
    """Execute automation workflow"""
    try:
        workflow = automation_workflows_collection.find_one({"_id": _to_object_id(workflow_id)})
        if not workflow:
            return
        
        if not workflow.get('enabled'):
            return
        
        # Execute actions based on triggers
        for action in workflow['actions']:
            await execute_workflow_action(action)
        
        # Update workflow
        automation_workflows_collection.update_one(
            {"_id": _to_object_id(workflow_id)},
            {
                "$set": {
                    "last_run": datetime.now(),
                    "status": "completed"
                }
            }
        )
        
    except Exception as e:
        print(f"Error executing workflow: {str(e)}")

async def execute_workflow_action(action: Dict):
    """Execute a single workflow action"""
    action_type = action['type']
    service = action.get('service', '')
    
    if action_type == 'email':
        # Trigger email service
        pass
    elif action_type == 'lead_scoring':
        # Trigger lead scoring
        pass
    elif action_type == 'content_generation':
        # Trigger content generation
        pass
    elif action_type == 'traffic_generation':
        # Trigger traffic generation
        pass

@app.get("/funnels")
async def get_funnels(status: Optional[str] = None):
    """Get all funnels"""
    query = {}
    if status:
        query['status'] = status
    
    funnels = [_serialize_doc(funnel) for funnel in funnels_collection.find(query)]
    return {"funnels": funnels}

@app.get("/funnel/{funnel_id}")
async def get_funnel(funnel_id: str):
    """Get specific funnel details"""
    funnel = funnels_collection.find_one({"_id": _to_object_id(funnel_id)})
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")
    
    # Get related data
    workflows = list(automation_workflows_collection.find({"funnel_id": funnel_id}))
    traffic_campaigns = list(db.traffic_campaigns.find({"funnel_id": funnel_id}))
    
    return {
        "funnel": _serialize_doc(funnel),
        "workflows": [_serialize_doc(w) for w in workflows],
        "traffic_campaigns": [_serialize_doc(c) for c in traffic_campaigns]
    }

@app.get("/analytics/{funnel_id}")
async def get_funnel_analytics(funnel_id: str):
    """Get comprehensive funnel analytics"""
    funnel = funnels_collection.find_one({"_id": _to_object_id(funnel_id)})
    if not funnel:
        raise HTTPException(status_code=404, detail="Funnel not found")
    
    # Gumroad analytics
    gumroad_product = db.gumroad_products.find_one({"funnel_id": funnel_id})
    gumroad_sales = list(db.gumroad_sales.find({"funnel_id": funnel_id}))
    
    # Traffic analytics
    traffic_campaigns = list(db.traffic_campaigns.find({"funnel_id": funnel_id}))
    
    # Lead analytics
    leads = list(db.leads.find({"funnel_id": funnel_id}))
    
    # Email analytics
    email_campaigns = list(db.email_campaigns.find({"funnel_id": funnel_id}))
    
    return {
        "funnel": _serialize_doc(funnel),
        "analytics": funnel.get('analytics', {}),
        "gumroad": {
            "product": gumroad_product,
            "total_sales": len(gumroad_sales),
            "total_revenue": sum(s['amount'] for s in gumroad_sales)
        },
        "traffic": {
            "campaigns": len(traffic_campaigns),
            "total_impressions": sum(c.get('stats', {}).get('impressions', 0) for c in traffic_campaigns)
        },
        "leads": {
            "total": len(leads),
            "avg_score": sum(l.get('score', 0) for l in leads) / len(leads) if leads else 0
        },
        "email": {
            "campaigns": len(email_campaigns),
            "total_sent": sum(c.get('stats', {}).get('total_sends', 0) for c in email_campaigns)
        }
    }

@app.delete("/funnel/{funnel_id}")
async def delete_funnel(funnel_id: str):
    """Delete a funnel and all associated data"""
    try:
        # Delete funnel
        funnels_collection.delete_one({"_id": _to_object_id(funnel_id)})
        
        # Delete associated workflows
        automation_workflows_collection.delete_many({"funnel_id": funnel_id})
        
        # Delete associated traffic campaigns
        db.traffic_campaigns.delete_many({"funnel_id": funnel_id})
        
        # Delete associated email campaigns
        db.email_campaigns.delete_many({"funnel_id": funnel_id})
        
        # Delete associated leads
        db.leads.delete_many({"funnel_id": funnel_id})
        
        return {"status": "deleted", "message": "Funnel and all associated data deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/funnel/{funnel_id}/pause")
async def pause_funnel(funnel_id: str):
    """Pause funnel operations"""
    funnels_collection.update_one(
        {"_id": _to_object_id(funnel_id)},
        {"$set": {"status": "paused"}}
    )
    
    # Pause workflows
    automation_workflows_collection.update_many(
        {"funnel_id": funnel_id},
        {"$set": {"status": "paused"}}
    )
    
    return {"status": "paused", "message": "Funnel operations paused"}

@app.post("/funnel/{funnel_id}/resume")
async def resume_funnel(funnel_id: str, background_tasks: BackgroundTasks):
    """Resume funnel operations"""
    funnels_collection.update_one(
        {"_id": _to_object_id(funnel_id)},
        {"$set": {"status": "active"}}
    )
    
    # Resume workflows
    automation_workflows_collection.update_many(
        {"funnel_id": funnel_id},
        {"$set": {"status": "active"}}
    )
    
    # Restart continuous optimization
    background_tasks.add_task(run_continuous_optimization, funnel_id)
    
    return {"status": "active", "message": "Funnel operations resumed"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "services_configured": {
            "content": CONTENT_SERVICE_URL,
            "email": EMAIL_SERVICE_URL,
            "lead": LEAD_SERVICE_URL,
            "conversion": CONVERSION_SERVICE_URL,
            "gumroad": GUMROAD_SERVICE_URL,
            "traffic": TRAFFIC_SERVICE_URL
        },
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
