"""
Unified LLM Service - Supports OpenAI and Ollama (Llama/Mistral/CodeLlama)
Provides a unified interface for AI text generation across multiple providers
"""
import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import aiohttp

# Initialize FastAPI app
app = FastAPI(title="Unified LLM Service", version="1.0.0")

# Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "openai" or "ollama"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llama3.2")

# Available models per provider
AVAILABLE_MODELS = {
    "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
    "ollama": ["llama3.2", "mistral", "codellama"]
}

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False

class CompletionRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

class ModelInfo(BaseModel):
    provider: str
    model: str
    available: bool

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "llm-service",
        "provider": LLM_PROVIDER,
        "default_model": DEFAULT_MODEL,
        "timestamp": datetime.now()
    }

@app.get("/models")
async def list_models():
    """List available models"""
    models = []
    
    if LLM_PROVIDER == "openai":
        if OPENAI_API_KEY:
            try:
                client = openai.OpenAI(api_key=OPENAI_API_KEY)
                models_list = client.models.list()
                for model in models_list.data:
                    models.append(ModelInfo(
                        provider="openai",
                        model=model.id,
                        available=True
                    ))
            except Exception as e:
                print(f"Error fetching OpenAI models: {e}")
    elif LLM_PROVIDER == "ollama":
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_BASE_URL}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        for model in data.get('models', []):
                            models.append(ModelInfo(
                                provider="ollama",
                                model=model['name'],
                                available=True
                            ))
        except Exception as e:
            print(f"Error fetching Ollama models: {e}")
    
    return {"models": models}

@app.post("/chat/completions")
async def chat_completion(request: ChatRequest):
    """Generate chat completion using configured provider"""
    try:
        model = request.model or DEFAULT_MODEL
        
        if LLM_PROVIDER == "openai":
            return await openai_chat_completion(request, model)
        elif LLM_PROVIDER == "ollama":
            return await ollama_chat_completion(request, model)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {LLM_PROVIDER}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def openai_chat_completion(request: ChatRequest, model: str):
    """OpenAI chat completion"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=model,
        messages=request.messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens
    )
    
    return {
        "provider": "openai",
        "model": model,
        "content": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
    }

async def ollama_chat_completion(request: ChatRequest, model: str):
    """Ollama chat completion"""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    
    payload = {
        "model": model,
        "messages": request.messages,
        "stream": request.stream,
        "options": {
            "temperature": request.temperature,
            "num_predict": request.max_tokens
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(status_code=response.status, detail=error_text)
            
            data = await response.json()
            
            return {
                "provider": "ollama",
                "model": model,
                "content": data.get('message', {}).get('content', ''),
                "usage": {
                    "prompt_tokens": data.get('prompt_eval_count', 0),
                    "completion_tokens": data.get('eval_count', 0),
                    "total_tokens": data.get('prompt_eval_count', 0) + data.get('eval_count', 0)
                }
            }

@app.post("/completions")
async def text_completion(request: CompletionRequest):
    """Generate text completion using configured provider"""
    try:
        model = request.model or DEFAULT_MODEL
        
        # Convert to chat format
        messages = [{"role": "user", "content": request.prompt}]
        
        chat_request = ChatRequest(
            messages=messages,
            model=model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        result = await chat_completion(chat_request)
        
        return {
            "provider": result["provider"],
            "model": result["model"],
            "content": result["content"],
            "usage": result["usage"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/social-content")
async def generate_social_content(topic: str, platform: str, tone: str = "professional"):
    """Specialized endpoint for social media content generation"""
    try:
        model = DEFAULT_MODEL
        
        platform_guidelines = {
            "twitter": {
                "max_length": 280,
                "style": "concise, engaging, use emojis sparingly",
                "hashtags": "2-3 relevant hashtags"
            },
            "linkedin": {
                "max_length": 3000,
                "style": "professional, insightful, industry-focused",
                "hashtags": "3-5 relevant hashtags"
            }
        }
        
        guidelines = platform_guidelines.get(platform, platform_guidelines["twitter"])
        
        prompt = f"""
        Generate social media content for {platform}:
        Topic: {topic}
        Tone: {tone}
        Style: {guidelines['style']}
        Max length: {guidelines['max_length']} characters
        Include hashtags: true
        Hashtag count: {guidelines['hashtags']}
        
        Generate:
        1. Main post content
        2. Suggested hashtags
        3. Alternative variations (2-3 options)
        """
        
        messages = [
            {"role": "system", "content": "You are an expert social media content creator."},
            {"role": "user", "content": prompt}
        ]
        
        chat_request = ChatRequest(
            messages=messages,
            model=model,
            temperature=0.8,
            max_tokens=1500
        )
        
        result = await chat_completion(chat_request)
        
        return {
            "status": "success",
            "content": result["content"],
            "platform": platform,
            "provider": result["provider"],
            "model": result["model"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/product-research")
async def generate_product_research(niche: str, target_audience: str):
    """Specialized endpoint for product research"""
    try:
        model = DEFAULT_MODEL
        
        prompt = f"""
        Research and analyze product ideas for the following niche:
        Niche: {niche}
        Target Audience: {target_audience}
        
        Provide:
        1. Top 5 product ideas with descriptions
        2. Recommended pricing for each
        3. Key features to include
        4. Target pain points to address
        5. Marketing angles
        6. Potential challenges
        """
        
        messages = [
            {"role": "system", "content": "You are an expert product researcher and market analyst."},
            {"role": "user", "content": prompt}
        ]
        
        chat_request = ChatRequest(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2000
        )
        
        result = await chat_completion(chat_request)
        
        return {
            "status": "success",
            "research": result["content"],
            "provider": result["provider"],
            "model": result["model"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
