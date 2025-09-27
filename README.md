# Qwipo B2B Marketplace Backend

An AI-powered backend system for Qwipo's B2B marketplace, featuring intelligent product recommendations, personalized homepage content, and an AI retail assistant.

## 🚀 Features

### Core Features
- **AI-Powered Recommendations**: Personalized product suggestions based on business type, location, and purchase history
- **Smart Homepage**: Dynamic content including daily deals, trending products, and low-stock alerts
- **AI Retail Assistant**: Conversational AI for business queries like "What should I stock for Diwali?"
- **Advanced Search**: Multi-filter product search with intelligent ranking
- **Deal Management**: Seasonal promotions, daily deals, and bulk offers

### Technical Features
- **FastAPI Framework**: High-performance async API with automatic documentation
- **SQLAlchemy ORM**: Robust database management with SQLite (dev) and PostgreSQL (prod) support
- **Intelligent Caching**: In-memory caching with Redis support for production
- **Comprehensive Logging**: Structured logging for monitoring and debugging
- **RESTful Design**: Clean API endpoints following REST principles

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (for version control)

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd qwipo.recommendation
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration (Optional)
Create a `.env` file for environment variables:
```env
# Database (optional - defaults to SQLite)
DATABASE_URL=sqlite:///./qwipo.db

# OpenAI API (optional - for enhanced AI features)
OPENAI_API_KEY=your_openai_api_key_here

# Redis (optional - for production caching)
REDIS_URL=redis://localhost:6379
```

### 5. Run the Application
```bash
python main.py
```

The API will be available at:
- **Main API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📚 API Endpoints

### Homepage & Recommendations
```http
GET /api/homepage?user_id=1
```
Returns personalized homepage with recommendations, deals, and trending products.

### AI Retail Assistant
```http
POST /api/ai-assistant
Content-Type: application/json

{
  "query": "What should I stock for Diwali?",
  "user_id": 1
}
```

### Product Details
```http
GET /api/products/1?user_id=1
```
Returns product details with AI-powered suggestions.

### Search Products
```http
GET /api/search?query=rice&user_id=1&category=grains&min_price=50&max_price=200
```

### Deals & Promotions
```http
GET /api/deals?user_id=1&deal_type=daily
```

### User Registration
```http
POST /api/register
Content-Type: application/json

{
  "user_type": "retailer",
  "business_name": "Sharma Kirana Store",
  "business_type": "kirana",
  "contact_person": "Raj Sharma",
  "email": "raj@sharma.com",
  "phone": "9876543210",
  "business_address": "123 Main Street",
  "city": "Mumbai",
  "state": "Maharashtra",
  "postal_code": "400001",
  "country": "India",
  "password": "securepassword"
}
```

## 🤖 AI Assistant Examples

The AI assistant can handle various business queries:

### Seasonal Stocking
```json
{
  "query": "What should I stock for Diwali season?",
  "user_id": 1
}
```

### Profit Optimization
```json
{
  "query": "Which products have the best profit margins?",
  "user_id": 1
}
```

### Inventory Planning
```json
{
  "query": "Generate a shopping list for my kirana store",
  "user_id": 1
}
```

### Market Trends
```json
{
  "query": "What are the trending products in Mumbai?",
  "user_id": 1
}
```

## 🗄️ Database Schema

### Key Tables
- **users**: Business profiles (retailers, distributors)
- **products**: Product catalog with pricing and inventory
- **purchase_history**: Transaction records for recommendations
- **deal_promotions**: Seasonal deals and promotions
- **ai_assistant_sessions**: AI conversation history
- **wishlists**: User product wishlists

### Sample Data
The application automatically creates sample data including:
- 2 sample users (retailer and distributor)
- 6 sample products across different categories
- Purchase history for recommendation testing
- Active promotional deals

## 🔧 Configuration

### Database Configuration
- **Development**: SQLite (automatic setup)
- **Production**: PostgreSQL (configure DATABASE_URL)

### Caching
- **Development**: In-memory caching
- **Production**: Redis (configure REDIS_URL)

### AI Features
- **Basic**: Rule-based responses (no API key required)
- **Enhanced**: OpenAI GPT integration (requires OPENAI_API_KEY)

## 🚀 Deployment

### Local Development
```bash
python main.py
```

### Production with Gunicorn
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Render (Docker) Deployment

1. Push this repo to GitHub (include `Dockerfile`, `.dockerignore`, `requirements.txt`).
2. Create a Web Service at [Render](https://render.com):
   - Runtime: Docker
   - Root directory: project root (where `Dockerfile` is)
   - Set environment variables:
     - `PORT=10000`
     - `DATABASE_URL`:
       - For quick smoke tests only: `sqlite:////opt/render/project/src/qwipo.db` (ephemeral)
       - Recommended (production): Render PostgreSQL Internal URL
3. Deploy, then test:
   - Health: `GET /health`
   - Docs: `/docs`

The provided `render.yaml` can also be used to create the service.

### Environment Configuration

Create a `.env` file from `.env.example` and set:

```
PORT=8000
DATABASE_URL=sqlite:///./qwipo.db
# DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

### Migrate from SQLite to Postgres

1. Create a PostgreSQL database (Render PostgreSQL or other managed service).
2. Set `DATABASE_URL` to your Postgres connection string.
3. Initial approach (no migrations yet):
   - Let the app create tables automatically at startup.
   - Optionally seed minimal data.
4. Later improvement: integrate Alembic migrations for schema changes.


## 📊 Performance Features

### Caching Strategy
- Homepage recommendations: 15 minutes
- Product page suggestions: 30 minutes
- Search results: 5 minutes
- AI responses: Session-based

### Database Optimization
- Indexed columns for fast queries
- Optimized recommendation algorithms
- Efficient JOIN operations for related data

## 🧪 Testing

### Run Tests
```bash
pytest
```

### Test Coverage
```bash
pytest --cov=. --cov-report=html
```

### API Testing
Use the interactive docs at `/docs` to test all endpoints with sample data.

## 📈 Monitoring & Logging

### Structured Logging
All operations are logged with:
- Request/response details
- Performance metrics
- Error tracking
- User activity patterns

### Health Monitoring
```http
GET /health
```
Returns system status and feature availability.

## 🔒 Security Features

- Password hashing with bcrypt
- Input validation with Pydantic
- SQL injection prevention with parameterized queries
- CORS configuration for frontend integration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the logs for error details
3. Ensure all dependencies are installed
4. Verify database connectivity

## 🔮 Future Enhancements

- Real-time notifications
- Advanced analytics dashboard
- Mobile app integration
- Multi-language support
- Enhanced AI capabilities
- Inventory management integration
