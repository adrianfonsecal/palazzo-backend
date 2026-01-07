# Palazzo Invites - Backend

Django REST Framework API for managing wedding invitations, guest lists, and WhatsApp integrations.

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or higher
- Redis server installed and running
- Meta WhatsApp Business API credentials (optional for WhatsApp features)

### 2. Installation

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers celery redis pandas openpyxl pillow requests
```

### 3. Environment Configuration

Create a `.env.local` file in the backend directory (or configure in `settings.py`):

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (default SQLite, configure PostgreSQL for production)
# DATABASE_URL=postgresql://user:password@localhost:5432/palazzo_invites

# Redis
CELERY_BROKER_URL=redis://127.0.0.1:6379/0

# Meta WhatsApp Business API
META_ACCESS_TOKEN=your-meta-access-token
META_PHONE_ID=your-phone-number-id
META_API_VERSION=v22.0

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://palazzoinvites.com
```

### 4. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser (optional, for Django admin)
python manage.py createsuperuser
```

### 5. Start Development Server

You need to run three separate processes:

**Terminal 1 - Django Server:**
```bash
python manage.py runserver
```

**Terminal 2 - Redis (if not running as service):**
```bash
redis-server
```

**Terminal 3 - Celery Worker:**
```bash
celery -A restapi worker --loglevel=info
```

The API will be available at `http://localhost:8000`