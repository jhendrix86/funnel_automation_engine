# Traffic Funnel Engine

A fully autonomous traffic funnel system for Gumroad products. This AI-powered platform automatically generates traffic, nurtures leads, optimizes conversions, and syncs with your Gumroad products to maximize sales.

## 🚀 Features

### Core Services
- **Orchestrator Service** - Central coordination for all funnel operations
- **Gumroad Integration** - Automatic product sync and sales tracking
- **Traffic Acquisition** - Social media automation, SEO automation, and paid traffic management
- **Content Generation** - AI-powered content creation for blogs, social media, emails, and landing pages
- **Email Automation** - Advanced email sequencing with personalization and A/B testing
- **Lead Optimization** - ML-based lead scoring, segmentation, and nurturing campaigns
- **Conversion Optimization** - A/B testing, landing page optimization, and CRO analysis

### Key Capabilities
- 🤖 **Fully Autonomous** - Set up once and let the system run automatically
- 🎯 **AI-Powered** - Uses GPT-4 for content generation and optimization
- 📊 **Real-Time Analytics** - Comprehensive dashboard with funnel performance metrics
- 🔁 **Continuous Optimization** - Auto-optimizes campaigns based on performance data
- 🌐 **Multi-Channel Traffic** - Social media, SEO, and paid advertising integration
- 💰 **Gumroad Integration** - Seamless sync with your Gumroad products and sales

## 🏗️ Architecture

```
traffic-funnel-engine/
├── python-services/          # Backend microservices
│   ├── orchestrator.py       # Central coordination service
│   ├── gumroad_integration.py # Gumroad API integration
│   ├── traffic_acquisition.py # Traffic generation
│   ├── content_generator.py  # AI content creation
│   ├── email_automation.py   # Email campaigns
│   ├── lead_optimizer.py     # Lead scoring & nurturing
│   ├── conversion_optimizer.py # A/B testing & CRO
│   └── requirements.txt      # Python dependencies
├── frontend/                # Next.js dashboard
│   ├── app/                 # Next.js 14 app directory
│   ├── components/          # React components
│   └── package.json         # Frontend dependencies
├── docker/                  # Docker configurations
├── docker-compose.yml       # Multi-container orchestration
└── .env.example            # Environment variables template
```

## 📋 Prerequisites

- Docker and Docker Compose
- OpenAI API Key
- Gumroad Access Token
- (Optional) Social media API keys for automated posting
- (Optional) SMTP credentials for email sending

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd traffic-funnel-engine
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
OPENAI_API_KEY=your_openai_api_key_here
GUMROAD_ACCESS_TOKEN=your_gumroad_access_token_here
MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379
```

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

This will start all services:
- MongoDB (port 27017)
- Redis (port 6379)
- Orchestrator (port 8000)
- Content Generator (port 8001)
- Lead Optimizer (port 8002)
- Email Automation (port 8003)
- Conversion Optimizer (port 8004)
- Gumroad Integration (port 8005)
- Traffic Acquisition (port 8006)
- Frontend Dashboard (port 3000)

### 4. Access the Dashboard

Open your browser and navigate to:
```
http://localhost:3000
```

## 🎮 Usage

### Creating Your First Funnel

1. **Get Your Gumroad Product ID**
   - Go to your Gumroad dashboard
   - Select your product
   - Copy the product ID from the URL

2. **Create a Funnel**
   - Click "Create Funnel" in the dashboard
   - Enter:
     - Funnel name
     - Gumroad product ID
     - Target audience description
     - Primary goal (sales, audience, awareness, leads)
   - Click "Create Funnel"

3. **Launch the Funnel**
   - The system will automatically:
     - Sync your Gumroad product data
     - Generate initial content
     - Set up email automation
     - Configure lead scoring
     - Launch traffic campaigns
     - Start continuous optimization

### Monitoring Performance

The dashboard provides:
- **Overview Tab** - Quick stats on leads and revenue
- **Analytics Tab** - Detailed metrics (visitors, conversions, rates)
- **Actions Tab** - Launch, pause, or resume funnels

### Managing Funnels

- **Launch** - Start autonomous operations
- **Pause** - Temporarily stop all automation
- **Resume** - Continue paused operations
- **View Analytics** - Deep dive into performance data

## 🔌 API Endpoints

### Orchestrator Service (Port 8000)

```bash
# Create autonomous funnel
POST /funnel/create
{
  "name": "My Funnel",
  "gumroad_product_id": "product-id",
  "target_audience": {"description": "Developers"},
  "goals": ["increase_sales"],
  "auto_launch": true
}

# Get all funnels
GET /funnels

# Get specific funnel
GET /funnel/{funnel_id}

# Launch funnel
POST /funnel/{funnel_id}/launch

# Pause funnel
POST /funnel/{funnel_id}/pause

# Resume funnel
POST /funnel/{funnel_id}/resume

# Get funnel analytics
GET /analytics/{funnel_id}
```

### Gumroad Integration (Port 8005)

```bash
# Sync products
POST /sync/products

# Sync sales
POST /sync/sales?product_id={id}

# Get products
GET /products

# Get sales
GET /sales?product_id={id}

# Map product to funnel
POST /map-funnel
{
  "product_id": "product-id",
  "funnel_id": "funnel-id",
  "auto_sync": true
}
```

### Traffic Acquisition (Port 8006)

```bash
# Create traffic campaign
POST /campaign/create
{
  "funnel_id": "funnel-id",
  "campaign_name": "My Campaign",
  "channels": ["twitter", "linkedin", "seo"],
  "target_audience": {"description": "Developers"},
  "duration_days": 30,
  "auto_optimize": true
}

# Create social post
POST /social/post
{
  "funnel_id": "funnel-id",
  "platform": "twitter",
  "content_type": "promotional",
  "topic": "My Product"
}

# Create SEO tasks
POST /seo/tasks
{
  "funnel_id": "funnel-id",
  "target_keywords": ["keyword1", "keyword2"],
  "content_types": ["blog", "article"]
}
```

### Content Generation (Port 8001)

```bash
# Generate content
POST /generate
{
  "funnel_id": "funnel-id",
  "content_type": "blog",
  "topic": "My Topic",
  "target_audience": "Developers",
  "keywords": ["keyword1", "keyword2"],
  "tone": "professional"
}

# Optimize content
POST /optimize
{
  "content": "Existing content",
  "target_keywords": ["keyword1"],
  "target_audience": "Developers",
  "optimization_goals": ["seo", "conversion"]
}
```

### Email Automation (Port 8003)

```bash
# Create template
POST /templates
{
  "name": "Welcome Email",
  "subject": "Welcome {{ first_name }}",
  "body": "Email content with Jinja2 templates",
  "template_type": "welcome",
  "variables": ["first_name", "email"]
}

# Create campaign
POST /campaigns
{
  "name": "Welcome Campaign",
  "funnel_id": "funnel-id",
  "template_id": "template-id",
  "trigger": "new_lead",
  "schedule": {"delay_hours": 0}
}
```

### Lead Optimization (Port 8002)

```bash
# Score lead
POST /score
{
  "lead_id": "lead-id",
  "funnel_id": "funnel-id",
  "behaviors": [{"type": "page_view", "timestamp": "2024-01-01"}],
  "demographics": {"firstName": "John"},
  "custom_data": {}
}

# Segment leads
POST /segment
{
  "funnel_id": "funnel-id",
  "criteria": {},
  "segment_count": 5
}
```

### Conversion Optimization (Port 8004)

```bash
# Create A/B test
POST /ab-test/create
{
  "funnel_id": "funnel-id",
  "test_name": "Headline Test",
  "element_type": "headline",
  "variants": [
    {"id": "variant_a", "content": "Original"},
    {"id": "variant_b", "content": "New"}
  ],
  "traffic_split": {"variant_a": 0.5, "variant_b": 0.5}
}

# Get test results
GET /ab-test/{test_id}
```

## 🛠️ Development

### Running Services Locally

#### Python Services

```bash
cd python-services
pip install -r requirements.txt

# Run individual services
uvicorn orchestrator:app --host 0.0.0.0 --port 8000
uvicorn content_generator:app --host 0.0.0.0 --port 8001
uvicorn lead_optimizer:app --host 0.0.0.0 --port 8002
uvicorn email_automation:app --host 0.0.0.0 --port 8003
uvicorn conversion_optimizer:app --host 0.0.0.0 --port 8004
uvicorn gumroad_integration:app --host 0.0.0.0 --port 8005
uvicorn traffic_acquisition:app --host 0.0.0.0 --port 8006
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Adding New Services

1. Create new service file in `python-services/`
2. Create corresponding Dockerfile
3. Add service to `docker-compose.yml`
4. Update orchestrator to communicate with new service

## 🔐 Security

- API keys are stored in environment variables
- Never commit `.env` file to version control
- Use secrets management in production
- Implement rate limiting for API endpoints
- Use HTTPS in production

## 📊 Monitoring

### Health Checks

Each service has a health check endpoint:

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "service-name",
  "timestamp": "2024-01-01T00:00:00"
}
```

### Logs

View logs for all services:

```bash
docker-compose logs -f
```

View specific service logs:

```bash
docker-compose logs -f orchestrator
docker-compose logs -f frontend
```

## 🚀 Deployment

### Production Setup

1. **Use Production Database**
   - Use managed MongoDB (e.g., MongoDB Atlas)
   - Use managed Redis (e.g., Redis Labs)

2. **Configure SSL**
   - Add SSL certificates to nginx
   - Update nginx configuration

3. **Set Up Domain**
   - Configure DNS records
   - Update environment variables

4. **Enable Monitoring**
   - Set up application monitoring (e.g., Sentry)
   - Configure log aggregation (e.g., ELK stack)

### Scaling

- Scale individual services based on load
- Use load balancer for frontend
- Implement caching for frequently accessed data
- Use message queues for async tasks

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up -d --build
```

### Database Connection Issues

- Ensure MongoDB is running: `docker-compose ps mongodb`
- Check connection string in `.env`
- Verify network connectivity

### API Key Errors

- Verify API keys in `.env`
- Check API key has required permissions
- Ensure API key hasn't expired

### Frontend Not Connecting

- Check API URL in `.env`
- Verify orchestrator is running
- Check browser console for errors

## 📚 Additional Resources

- [Gumroad API Documentation](https://gumroad.com/api)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Next.js Documentation](https://nextjs.org/docs)

## 🎯 Roadmap

- [ ] Add more social media platforms
- [ ] Implement advanced analytics dashboard
- [ ] Add mobile app support
- [ ] Integrate with more payment processors
- [ ] Add webhook support
- [ ] Implement multi-language support
- [ ] Add team collaboration features
- [ ] Create template library

## 💬 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section

---

Built with ❤️ for autonomous Gumroad sales funnels
