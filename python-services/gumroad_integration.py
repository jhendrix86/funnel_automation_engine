"""
Gumroad Integration Service - Product sync and sales tracking
Integrates with Gumroad API for autonomous funnel management
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
import aiohttp
import openai

# Initialize FastAPI app
app = FastAPI(title="Gumroad Integration Service", version="1.0.0")

# Configuration
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize clients
openai.api_key = OPENAI_API_KEY
mongo_client = MongoClient(MONGODB_URI)
redis_client = redis.from_url(REDIS_URL)

# Database
db = mongo_client.traffic_funnel
gumroad_products_collection = db.gumroad_products
gumroad_sales_collection = db.gumroad_sales
gumroad_customers_collection = db.gumroad_customers

class GumroadProduct(BaseModel):
    product_id: str
    name: str
    description: str
    price: float
    url: str
    published: bool
    tags: List[str]
    funnel_id: Optional[str] = None

class GumroadSale(BaseModel):
    sale_id: str
    product_id: str
    customer_email: str
    customer_name: str
    amount: float
    purchase_date: datetime
    funnel_id: Optional[str] = None

class GumroadCustomer(BaseModel):
    customer_id: str
    email: str
    name: str
    total_purchases: int
    total_spent: float
    first_purchase: datetime
    last_purchase: datetime
    funnel_id: Optional[str] = None

class FunnelMapping(BaseModel):
    product_id: str
    funnel_id: str
    auto_sync: bool = True
    lead_source: str = "gumroad"

@app.post("/sync/products")
async def sync_products(background_tasks: BackgroundTasks):
    """Sync all products from Gumroad"""
    try:
        if not GUMROAD_ACCESS_TOKEN:
            raise HTTPException(status_code=400, detail="Gumroad access token not configured")
        
        products = await fetch_gumroad_products()
        
        synced_count = 0
        for product in products:
            # Check if product exists
            existing = gumroad_products_collection.find_one({"product_id": product['id']})
            
            product_doc = {
                "product_id": product['id'],
                "name": product['name'],
                "description": product.get('description', ''),
                "price": float(product.get('price', 0)),
                "url": product.get('url', ''),
                "published": product.get('published', False),
                "tags": product.get('tags', []),
                "created_at": product.get('created_at'),
                "updated_at": datetime.now(),
                "stats": {
                    "total_sales": 0,
                    "total_revenue": 0.0,
                    "conversion_rate": 0.0
                }
            }
            
            if existing:
                gumroad_products_collection.update_one(
                    {"product_id": product['id']},
                    {"$set": product_doc}
                )
            else:
                gumroad_products_collection.insert_one(product_doc)
            
            synced_count += 1
        
        # Schedule background analytics update
        background_tasks.add_task(update_product_analytics)
        
        return {
            "status": "success",
            "synced_products": synced_count,
            "message": f"Successfully synced {synced_count} products from Gumroad"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_gumroad_products() -> List[Dict]:
    """Fetch products from Gumroad API"""
    url = "https://api.gumroad.com/v2/products"
    headers = {"Authorization": f"Bearer {GUMROAD_ACCESS_TOKEN}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch Gumroad products")
            
            data = await response.json()
            return data.get('products', [])

@app.post("/sync/sales")
async def sync_sales(product_id: Optional[str] = None, background_tasks: BackgroundTasks = None):
    """Sync sales from Gumroad"""
    try:
        if not GUMROAD_ACCESS_TOKEN:
            raise HTTPException(status_code=400, detail="Gumroad access token not configured")
        
        sales = await fetch_gumroad_sales(product_id)
        
        synced_count = 0
        for sale in sales:
            # Check if sale exists
            existing = gumroad_sales_collection.find_one({"sale_id": sale['id']})
            
            if existing:
                continue
            
            sale_doc = {
                "sale_id": sale['id'],
                "product_id": sale['product_id'],
                "customer_email": sale.get('email', ''),
                "customer_name": sale.get('full_name', ''),
                "amount": float(sale.get('amount', 0)),
                "purchase_date": sale.get('created_at'),
                "created_at": datetime.now(),
                "funnel_id": get_funnel_for_product(sale['product_id'])
            }
            
            gumroad_sales_collection.insert_one(sale_doc)
            
            # Create or update customer
            await update_customer_data(sale)
            
            synced_count += 1
        
        # Update product analytics
        if background_tasks:
            background_tasks.add_task(update_product_analytics)
        
        return {
            "status": "success",
            "synced_sales": synced_count,
            "message": f"Successfully synced {synced_count} sales from Gumroad"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_gumroad_sales(product_id: Optional[str] = None) -> List[Dict]:
    """Fetch sales from Gumroad API"""
    url = "https://api.gumroad.com/v2/sales"
    headers = {"Authorization": f"Bearer {GUMROAD_ACCESS_TOKEN}"}
    
    params = {}
    if product_id:
        params['product_id'] = product_id
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch Gumroad sales")
            
            data = await response.json()
            return data.get('sales', [])

def get_funnel_for_product(product_id: str) -> Optional[str]:
    """Get funnel ID mapped to a product"""
    mapping = db.funnel_mappings.find_one({"product_id": product_id})
    return mapping.get('funnel_id') if mapping else None

async def update_customer_data(sale: Dict):
    """Create or update customer record"""
    customer = gumroad_customers_collection.find_one({"email": sale.get('email')})
    
    if customer:
        # Update existing customer
        gumroad_customers_collection.update_one(
            {"email": sale.get('email')},
            {
                "$inc": {
                    "total_purchases": 1,
                    "total_spent": float(sale.get('amount', 0))
                },
                "$set": {
                    "last_purchase": sale.get('created_at'),
                    "updated_at": datetime.now()
                }
            }
        )
    else:
        # Create new customer
        customer_doc = {
            "customer_id": sale.get('customer_id', sale.get('email')),
            "email": sale.get('email', ''),
            "name": sale.get('full_name', ''),
            "total_purchases": 1,
            "total_spent": float(sale.get('amount', 0)),
            "first_purchase": sale.get('created_at'),
            "last_purchase": sale.get('created_at'),
            "created_at": datetime.now(),
            "funnel_id": get_funnel_for_product(sale['product_id'])
        }
        
        gumroad_customers_collection.insert_one(customer_doc)
        
        # Add to leads collection for funnel nurturing
        add_customer_to_leads(customer_doc, sale['product_id'])

def add_customer_to_leads(customer: Dict, product_id: str):
    """Add Gumroad customer to leads collection"""
    funnel_id = get_funnel_for_product(product_id)
    
    lead_doc = {
        "email": customer['email'],
        "firstName": customer['name'].split()[0] if customer['name'] else '',
        "lastName": ' '.join(customer['name'].split()[1:]) if customer['name'] and len(customer['name'].split()) > 1 else '',
        "source": "gumroad_purchase",
        "funnel_id": funnel_id,
        "status": "customer",
        "score": 90,  # High score for actual customers
        "behaviors": [
            {
                "type": "purchase",
                "timestamp": customer['last_purchase'],
                "value": customer['total_spent']
            }
        ],
        "customFields": {
            "gumroad_customer_id": customer['customer_id'],
            "total_purchases": customer['total_purchases'],
            "total_spent": customer['total_spent']
        },
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    # Check if lead exists
    existing = db.leads.find_one({"email": customer['email']})
    if existing:
        db.leads.update_one({"email": customer['email']}, {"$set": lead_doc})
    else:
        db.leads.insert_one(lead_doc)

async def update_product_analytics():
    """Update analytics for all products"""
    products = list(gumroad_products_collection.find())
    
    for product in products:
        # Calculate sales stats
        sales = list(gumroad_sales_collection.find({"product_id": product['product_id']}))
        
        total_sales = len(sales)
        total_revenue = sum(sale['amount'] for sale in sales)
        
        # Get funnel visitors for conversion rate
        funnel_id = get_funnel_for_product(product['product_id'])
        conversion_rate = 0.0
        
        if funnel_id:
            funnel = db.funnels.find_one({"_id": funnel_id})
            if funnel:
                visitors = funnel.get('analytics', {}).get('visitors', 0)
                conversion_rate = (total_sales / visitors * 100) if visitors > 0 else 0.0
        
        gumroad_products_collection.update_one(
            {"product_id": product['product_id']},
            {
                "$set": {
                    "stats.total_sales": total_sales,
                    "stats.total_revenue": total_revenue,
                    "stats.conversion_rate": conversion_rate,
                    "updated_at": datetime.now()
                }
            }
        )

@app.post("/map-funnel")
async def map_product_to_funnel(mapping: FunnelMapping):
    """Map a Gumroad product to a funnel"""
    try:
        # Check if product exists
        product = gumroad_products_collection.find_one({"product_id": mapping.product_id})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Check if funnel exists
        funnel = db.funnels.find_one({"_id": mapping.funnel_id})
        if not funnel:
            raise HTTPException(status_code=404, detail="Funnel not found")
        
        # Create or update mapping
        mapping_doc = {
            "product_id": mapping.product_id,
            "funnel_id": mapping.funnel_id,
            "auto_sync": mapping.auto_sync,
            "lead_source": mapping.lead_source,
            "created_at": datetime.now()
        }
        
        existing = db.funnel_mappings.find_one({"product_id": mapping.product_id})
        if existing:
            db.funnel_mappings.update_one(
                {"product_id": mapping.product_id},
                {"$set": mapping_doc}
            )
        else:
            db.funnel_mappings.insert_one(mapping_doc)
        
        # Update product with funnel_id
        gumroad_products_collection.update_one(
            {"product_id": mapping.product_id},
            {"$set": {"funnel_id": mapping.funnel_id}}
        )
        
        return {
            "status": "success",
            "message": f"Product {mapping.product_id} mapped to funnel {mapping.funnel_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products")
async def get_products(funnel_id: Optional[str] = None):
    """Get all Gumroad products"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    products = list(gumroad_products_collection.find(query))
    return {"products": products}

@app.get("/sales")
async def get_sales(product_id: Optional[str] = None, funnel_id: Optional[str] = None):
    """Get Gumroad sales"""
    query = {}
    if product_id:
        query['product_id'] = product_id
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    sales = list(gumroad_sales_collection.find(query))
    return {"sales": sales}

@app.get("/customers")
async def get_customers(funnel_id: Optional[str] = None):
    """Get Gumroad customers"""
    query = {}
    if funnel_id:
        query['funnel_id'] = funnel_id
    
    customers = list(gumroad_customers_collection.find(query))
    return {"customers": customers}

@app.get("/analytics/{product_id}")
async def get_product_analytics(product_id: str):
    """Get analytics for a specific product"""
    product = gumroad_products_collection.find_one({"product_id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    sales = list(gumroad_sales_collection.find({"product_id": product_id}))
    
    # Calculate additional metrics
    daily_sales = {}
    for sale in sales:
        date = sale['purchase_date'].strftime('%Y-%m-%d')
        daily_sales[date] = daily_sales.get(date, 0) + 1
    
    # Customer retention
    repeat_customers = len(set(
        s['customer_email'] for s in sales 
        if gumroad_sales_collection.count_documents({"customer_email": s['customer_email']}) > 1
    ))
    
    return {
        "product": product,
        "stats": product.get('stats', {}),
        "daily_sales": daily_sales,
        "total_customers": len(set(s['customer_email'] for s in sales)),
        "repeat_customers": repeat_customers,
        "avg_order_value": sum(s['amount'] for s in sales) / len(sales) if sales else 0
    }

@app.post("/auto-sync/enable")
async def enable_auto_sync():
    """Enable automatic sync for all mapped products"""
    try:
        mappings = list(db.funnel_mappings.find({"auto_sync": True}))
        
        for mapping in mappings:
            # Sync products and sales for this mapping
            await sync_sales(mapping['product_id'])
        
        return {
            "status": "success",
            "synced_mappings": len(mappings),
            "message": "Auto-sync completed for all mapped products"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gumroad-integration",
        "gumroad_configured": bool(GUMROAD_ACCESS_TOKEN),
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
