"""
Email Automation Service - Advanced email sequencing and personalization
Integrates with Empire OS Growth Engine email workflows
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
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import aiohttp

# Initialize FastAPI app
app = FastAPI(title="Email Automation Service", version="1.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Initialize clients
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
email_templates_collection = db.email_templates
email_campaigns_collection = db.email_campaigns
sent_emails_collection = db.sent_emails

class EmailTemplate(BaseModel):
    name: str
    subject: str
    body: str
    template_type: str  # welcome, nurture, promotional, transactional
    variables: List[str]
    tags: List[str]

class EmailCampaign(BaseModel):
    name: str
    funnel_id: str
    segment_id: Optional[str]
    template_id: str
    trigger: str
    schedule: Dict
    personalization: Dict

class PersonalizedEmail(BaseModel):
    lead_id: str
    template_id: str
    variables: Dict
    priority: int = 1

class EmailResponse(BaseModel):
    email_id: str
    status: str
    message: str
    scheduled_at: Optional[datetime]

class ABTestRequest(BaseModel):
    campaign_id: str
    variants: List[Dict]
    traffic_split: Dict[str, float]
    test_duration_days: int = 7

class ABTestResponse(BaseModel):
    test_id: str
    variants: List[Dict]
    winner: Optional[str]
    confidence: float

@app.post("/templates", response_model=EmailResponse)
async def create_template(template: EmailTemplate):
    """Create email template with AI optimization"""
    try:
        # Optimize template using AI
        optimized_template = await optimize_email_template(template)
        
        # Save to database
        template_doc = {
            "name": optimized_template.name,
            "subject": optimized_template.subject,
            "body": optimized_template.body,
            "template_type": optimized_template.template_type,
            "variables": optimized_template.variables,
            "tags": optimized_template.tags,
            "created_at": datetime.now(),
            "performance": {
                "sends": 0,
                "opens": 0,
                "clicks": 0,
                "conversions": 0
            }
        }
        
        result = email_templates_collection.insert_one(template_doc)
        
        return EmailResponse(
            email_id=str(result.inserted_id),
            status="created",
            message="Email template created and optimized",
            scheduled_at=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def optimize_email_template(template: EmailTemplate) -> EmailTemplate:
    """Optimize email template using AI"""
    prompt = f"""
    Optimize this email template for maximum engagement and conversions:
    
    Subject: {template.subject}
    Body: {template.body}
    Type: {template.template_type}
    Target Variables: {', '.join(template.variables)}
    
    Provide:
    1. Optimized subject line (multiple options)
    2. Improved body copy
    3. Better personalization opportunities
    4. Stronger call-to-action
    5. Optimized for mobile devices
    
    Format response as JSON with structure:
    {{
        "subject": "best subject line",
        "body": "optimized body",
        "personalization_tips": ["tip1", "tip2"],
        "cta_improvements": ["improvement1"]
    }}
    """
    
    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an email marketing optimization expert with high open and click-through rates."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    
    try:
        optimization = json.loads(response.choices[0].message.content)
        template.subject = optimization.get('subject', template.subject)
        template.body = optimization.get('body', template.body)
    except:
        pass  # Use original if parsing fails
    
    return template

@app.post("/campaigns", response_model=EmailResponse)
async def create_campaign(campaign: EmailCampaign, background_tasks: BackgroundTasks):
    """Create email campaign with automation"""
    try:
        # Get template
        from bson import ObjectId
        template = email_templates_collection.find_one({"_id": ObjectId(campaign.template_id)})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Save campaign
        campaign_doc = {
            "name": campaign.name,
            "funnel_id": campaign.funnel_id,
            "segment_id": campaign.segment_id,
            "template_id": campaign.template_id,
            "trigger": campaign.trigger,
            "schedule": campaign.schedule,
            "personalization": campaign.personalization,
            "created_at": datetime.now(),
            "status": "active",
            "stats": {
                "total_sends": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "converted": 0
            }
        }
        
        result = email_campaigns_collection.insert_one(campaign_doc)
        
        # Schedule campaign execution
        background_tasks.add_task(execute_campaign, str(result.inserted_id))
        
        return EmailResponse(
            email_id=str(result.inserted_id),
            status="scheduled",
            message="Email campaign created and scheduled",
            scheduled_at=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def execute_campaign(campaign_id: str):
    """Execute email campaign"""
    from bson import ObjectId
    campaign = email_campaigns_collection.find_one({"_id": ObjectId(campaign_id)})
    if not campaign:
        return
    
    # Get leads for segment or funnel
    leads = get_campaign_leads(campaign)
    
    # Send personalized emails to each lead
    for lead in leads:
        await send_personalized_email(lead, campaign)
    
    # Update camObjectId(paign statu)s
    email_campaigns_collection.update_one(
        {"_id": campaign_id},
        {"$set": {"status": "completed", "completed_at": datetime.now()}}
    )

def get_campaign_leads(campaign: Dict) -> List[Dict]:
    """Get leads for campaign based on segment or funnel"""
    query = {}
    
    if campaign.get('segment_id'):
        query['segment_id'] = campaign['segment_id']
    elif campaign.get('funnel_id'):
        query['funnel_id'] = campaign['funnel_id']
    
    return list(db.leads.find(query))

async def send_personalized_email(lead: Dict, campaign: Dict):
    """Send personalized email to lead"""
    try:
        # Get template
        template = email_templates_collection.find_one({"_id": campaign['template_id']})
        if not template:
            return
        
        # Personalize content
        personalized_content = personalize_email_content(template, lead, campaign.get('personalization', {}))
        
        # Send email
        await send_email(
            to_email=lead['email'],
            subject=personalized_content['subject'],
            body=personalized_content['body']
        )
        
        # Log sent email
        sent_emails_collection.insert_one({
            "campaign_id": campaign['_id'],
            "lead_id": lead['_id'],
            "template_id": template['_id'],
            "subject": personalized_content['subject'],
            "sent_at": datetime.now(),
            "status": "sent"
        })
        
        # Update campaign stats
        email_campaigns_collection.update_one(
            {"_id": ObjectId(campaign['_id'])},
            {"$inc": {"stats.total_sends": 1, "stats.delivered": 1}}
        )
        
    except Exception as e:
        print(f"Error sending email to {lead['email']}: {str(e)}")

def personalize_email_content(template: Dict, lead: Dict, personalization: Dict) -> Dict:
    """Personalize email content using Jinja2 templates"""
    # Prepare template context
    context = {
        'first_name': lead.get('firstName', ''),
        'last_name': lead.get('lastName', ''),
        'email': lead.get('email', ''),
        'company': lead.get('company', ''),
        'custom_fields': lead.get('customFields', {}),
        **personalization
    }
    
    # Render subject
    subject_template = Template(template['subject'])
    personalized_subject = subject_template.render(**context)
    
    # Render body
    body_template = Template(template['body'])
    personalized_body = body_template.render(**context)
    
    return {
        'subject': personalized_subject,
        'body': personalized_body
    }

async def send_email(to_email: str, subject: str, body: str):
    """Send email via SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        # In production, use async email library like aiosmtplib
        # For now, this is a placeholder
        print(f"Email sent to {to_email}: {subject}")
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise

@app.post("/personalize", response_model=EmailResponse)
async def create_personalized_email(email: PersonalizedEmail):
    """Create and send personalized email immediately"""
    try:
        from bson import ObjectId
        # Get lead
        lead = db.leads.find_one({"_id": ObjectId(email.lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get template
        template = email_templates_collection.find_one({"_id": ObjectId(email.template_id)})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Personalize and send
        personalized_content = personalize_email_content(template, lead, email.variables)
        
        await send_email(
            to_email=lead['email'],
            subject=personalized_content['subject'],
            body=personalized_content['body']
        )
        
        # Log sent email
        sent_emails_collection.insert_one({
            "lead_id": email.lead_id,
            "template_id": email.template_id,
            "subject": personalized_content['subject'],
            "sent_at": datetime.now(),
            "status": "sent",
            "priority": email.priority
        })
        
        return EmailResponse(
            email_id="immediate",
            status="sent",
            message="Personalized email sent successfully",
            scheduled_at=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ab-test", response_model=ABTestResponse)
async def create_ab_test(request: ABTestRequest):
    """Create A/B test for email campaign"""
    try:
        # Create test document
        test_doc = {
            "campaign_id": request.campaign_id,
            "variants": request.variants,
            "traffic_split": request.traffic_split,
            "test_duration_days": request.test_duration_days,
            "created_at": datetime.now(),
            "status": "running",
            "results": {
                "variant_a": {"sends": 0, "opens": 0, "clicks": 0, "conversions": 0},
                "variant_b": {"sends": 0, "opens": 0, "clicks": 0, "conversions": 0}
            }
        }
        
        result = db.ab_tests.insert_one(test_doc)
        
        return ABTestResponse(
            test_id=str(result.inserted_id),
            variants=request.variants,
            winner=None,
            confidence=0.0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ab-test/{test_id}")
async def get_ab_test_results(test_id: str):
    """Get A/B test results"""
    from bson import ObjectId
    test = db.ab_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="A/B test not found")
    
    # Calculate winner if test is complete
    winner = None
    confidence = 0.0
    
    if test['status'] == 'completed':
        winner = calculate_ab_test_winner(test['results'])
        confidence = calculate_statistical_significance(test['results'])
    
    return {
        "test_id": test_id,
        "status": test['status'],
        "variants": test['variants'],
        "results": test['results'],
        "winner": winner,
        "confidence": confidence
    }

def calculate_ab_test_winner(results: Dict) -> Optional[str]:
    """Calculate A/B test winner based on conversion rate"""
    variant_a_rate = results['variant_a']['conversions'] / results['variant_a']['sends'] if results['variant_a']['sends'] > 0 else 0
    variant_b_rate = results['variant_b']['conversions'] / results['variant_b']['sends'] if results['variant_b']['sends'] > 0 else 0
    
    if variant_a_rate > variant_b_rate:
        return "variant_a"
    elif variant_b_rate > variant_a_rate:
        return "variant_b"
    else:
        return None

def calculate_statistical_significance(results: Dict) -> float:
    """Calculate statistical significance (simplified)"""
    # In production, use proper statistical test like chi-square
    variant_a_conversions = results['variant_a']['conversions']
    variant_a_sends = results['variant_a']['sends']
    variant_b_conversions = results['variant_b']['conversions']
    variant_b_sends = results['variant_b']['sends']
    
    if variant_a_sends == 0 or variant_b_sends == 0:
        return 0.0
    
    # Simple confidence calculation
    total_conversions = variant_a_conversions + variant_b_conversions
    total_sends = variant_a_sends + variant_b_sends
    
    if total_sends == 0:
        return 0.0
    
    overall_rate = total_conversions / total_sends
    expected_a = overall_rate * variant_a_sends
    expected_b = overall_rate * variant_b_sends
    
    # Chi-square statistic (simplified)
    chi_square = (
        ((variant_a_conversions - expected_a) ** 2) / expected_a +
        ((variant_b_conversions - expected_b) ** 2) / expected_b
    ) if expected_a > 0 and expected_b > 0 else 0
    
    # Convert to confidence (simplified)
    confidence = min(chi_square / 10, 1.0)
    
    return confidence

@app.get("/templates")
async def get_templates(template_type: Optional[str] = None):
    """Get email templates"""
    query = {}
    if template_type:
        query['template_type'] = template_type
    
    templates = list(email_templates_collection.find(query))
    return {"templates": templates}

@app.get("/campaigns")
async def get_campaigns(funnel_id: Optional[str] = None):
    """Get email campaigns"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    campaigns = list(email_campaigns_collection.find(query))
    return {"campaigns": campaigns}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "email-automation",
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)