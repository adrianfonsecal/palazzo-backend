# Palazzo Invites - Backend

Django REST Framework API for managing wedding invitations, guest lists, and WhatsApp integrations.

## 🏗️ Architecture

This backend follows a **multi-tenant architecture** where each wedding operates as an isolated tenant. All data is filtered by the `Wedding` model through foreign key relationships.

### Tech Stack

- **Django 6.0** - Web framework and ORM
- **Django REST Framework** - RESTful API framework
- **djangorestframework-simplejwt** - JWT authentication
- **Celery** - Asynchronous task processing
- **Redis** - Message broker for Celery
- **Pandas** - CSV/Excel data processing
- **Pillow** - Image processing for photo uploads
- **SQLite** (development) / **PostgreSQL** (recommended for production)

## 📦 Dependencies

### Core Dependencies
```
django>=6.0
djangorestframework
djangorestframework-simplejwt
django-cors-headers
celery
redis
pandas
openpyxl
pillow
requests
```

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

## 📁 Project Structure

```
backend/
├── manage.py                 # Django management script
├── db.sqlite3               # SQLite database (dev)
├── dump.rdb                 # Redis dump file
│
├── core/                    # Main application
│   ├── models.py           # Data models (Wedding, Invitation, Guest, Photo)
│   ├── serializers.py      # DRF serializers
│   ├── views.py            # API viewsets
│   ├── tasks.py            # Celery async tasks
│   ├── urls.py             # App-level URL routing
│   ├── webhooks.py         # WhatsApp webhook handlers
│   ├── admin.py            # Django admin configuration
│   └── migrations/         # Database migrations
│
└── restapi/                # Project configuration
    ├── settings.py         # Django settings
    ├── urls.py             # Root URL configuration
    ├── celery.py           # Celery configuration
    ├── asgi.py             # ASGI application
    └── wsgi.py             # WSGI application
```

## 🗄️ Database Models

### Wedding (Tenant)
Main tenant model representing a wedding event.

```python
class Wedding(models.Model):
    slug                    # URL identifier (unique)
    couple_names            # "Juan y María"
    event_date              # Date and time of wedding
    location_name           # Venue name
    location_latitude       # GPS coordinates
    location_longitude      # GPS coordinates
    theme_config            # JSON field for UI customization
    owner                   # OneToOne with User
    claim_code              # For claiming unclaimed weddings
```

### Invitation
Represents a family/group invitation with unique UUID.

```python
class Invitation(models.Model):
    wedding                 # ForeignKey to Wedding
    uuid                    # Unique secure access token
    family_name             # "Familia López"
    phone_number            # E.164 format (+5215551234567)
    email                   # Optional email
    status                  # PENDING, SENT, DELIVERED, OPENED, COMPLETED
    whatsapp_message_id     # Meta API message ID
    last_sent_at            # Timestamp of last send
```

### Guest
Individual attendees within an invitation.

```python
class Guest(models.Model):
    invitation              # ForeignKey to Invitation
    full_name               # "Juan López"
    is_child                # Boolean for children's menu
    attendance              # PENDING, ACCEPTED, DECLINED
    dietary_restrictions    # Text field for allergies, preferences
```

### Photo
Collaborative wedding album photos.

```python
class Photo(models.Model):
    wedding                 # ForeignKey to Wedding
    uploaded_by             # ForeignKey to Invitation (tracking)
    image                   # ImageField
    caption                 # Optional description
    is_approved             # Moderation flag
    created_at              # Upload timestamp
```

## 🔌 API Endpoints

### Authentication

**Obtain JWT Token:**
```http
POST /api/token/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Refresh Token:**
```http
POST /api/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Register Wedding Owner:**
```http
POST /api/register/
Content-Type: application/json

{
  "username": "novios@email.com",
  "password": "securepass123",
  "email": "novios@email.com",
  "wedding_name": "Juan y María"
}
```

### Public Endpoints (No Auth Required)

**Get Wedding Information:**
```http
GET /api/wedding/{slug}/

Response:
{
  "id": 1,
  "slug": "juan-y-maria",
  "couple_names": "Juan y María",
  "event_date": "2026-06-15T18:00:00Z",
  "location_name": "Salón Palazzo",
  "location_latitude": "19.432608",
  "location_longitude": "-99.133209",
  "theme_config": {
    "primary_color": "#FF6B9D",
    "font": "Playfair Display"
  }
}
```

**Get Invitation Details:**
```http
GET /api/invitation/{uuid}/

Response:
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "family_name": "Familia López",
  "phone_number": "+5215551234567",
  "email": "lopez@email.com",
  "status": "OPENED",
  "wedding": {
    "slug": "juan-y-maria",
    "couple_names": "Juan y María",
    "event_date": "2026-06-15T18:00:00Z",
    ...
  },
  "guests": [
    {
      "id": 1,
      "full_name": "Juan López",
      "is_child": false,
      "attendance": "ACCEPTED",
      "dietary_restrictions": "Vegetariano"
    },
    {
      "id": 2,
      "full_name": "María López",
      "is_child": false,
      "attendance": "ACCEPTED",
      "dietary_restrictions": ""
    }
  ]
}
```

**Update RSVP:**
```http
PATCH /api/invitation/{uuid}/
Content-Type: application/json

{
  "guests": [
    {
      "id": 1,
      "attendance": "ACCEPTED",
      "dietary_restrictions": "Vegetariano"
    },
    {
      "id": 2,
      "attendance": "DECLINED",
      "dietary_restrictions": ""
    }
  ]
}
```

**Upload Photo:**
```http
POST /api/photos/
Content-Type: multipart/form-data

invitation_uuid: 550e8400-e29b-41d4-a716-446655440000
image: [file]
caption: "¡Qué bonita celebración!"
```

**Get Wedding Photos:**
```http
GET /api/photos/?wedding_slug=juan-y-maria

Response:
{
  "results": [
    {
      "id": 1,
      "image": "https://example.com/media/wedding_photos/2026/01/07/photo.jpg",
      "caption": "¡Qué bonita celebración!",
      "created_at": "2026-01-07T12:00:00Z"
    }
  ]
}
```

### Admin Endpoints (JWT Required)

**List Invitations:**
```http
GET /api/admin/invitations/
Authorization: Bearer {access_token}

Response:
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "family_name": "Familia López",
      "phone_number": "+5215551234567",
      "status": "SENT",
      "guest_count": 2,
      "confirmed_count": 2
    }
  ]
}
```

**Create Invitation:**
```http
POST /api/admin/invitations/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "family_name": "Familia García",
  "phone_number": "+5215559876543",
  "email": "garcia@email.com",
  "guests": [
    {
      "full_name": "Pedro García",
      "is_child": false
    },
    {
      "full_name": "Ana García",
      "is_child": false
    }
  ]
}
```

**Import CSV/Excel:**
```http
POST /api/admin/invitations/import_csv/
Authorization: Bearer {access_token}
Content-Type: multipart/form-data

file: [CSV/Excel file]

Response:
{
  "status": "El archivo se está procesando en segundo plano."
}
```

**CSV Format:**
```csv
telefono,nombre_familia,nombre_invitado,email,es_nino
+5215551234567,Familia López,"Juan López, María López",lopez@email.com,False
+5215559876543,Familia García,Pedro García,garcia@email.com,False
```

**Send WhatsApp Blast:**
```http
POST /api/admin/invitations/send_blast/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "invitation_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440001"
  ]
}

Response:
{
  "status": "Enviando mensajes...",
  "count": 2
}
```

**Manage Guests:**
```http
# List guests
GET /api/admin/guests/
Authorization: Bearer {access_token}

# Create guest
POST /api/admin/guests/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "invitation": 1,
  "full_name": "Carlos López",
  "is_child": true,
  "attendance": "PENDING"
}

# Update guest
PATCH /api/admin/guests/{id}/
Authorization: Bearer {access_token}

# Delete guest
DELETE /api/admin/guests/{id}/
Authorization: Bearer {access_token}
```

## ⚙️ Celery Tasks

### import_guests_task
Processes CSV/Excel files asynchronously to create invitations and guests.

```python
@shared_task
def import_guests_task(wedding_id, file_path)
```

**Features:**
- Reads CSV or Excel files using pandas
- Groups guests by phone number (family)
- Creates/updates Invitation records
- Creates individual Guest records
- Uses transaction.atomic() for data integrity
- Automatically cleans up temporary files

**Error Handling:**
- Validates required columns
- Rolls back on errors
- Logs detailed error messages

### send_whatsapp_blast_task
Sends WhatsApp invitations via Meta Business API.

```python
@shared_task
def send_whatsapp_blast_task(invitation_uuids)
```

**Features:**
- Iterates through invitation list
- Calls Meta WhatsApp Cloud API
- Uses pre-approved message templates
- Updates invitation status
- Stores message IDs for webhook tracking
- Handles API rate limits

**Configuration:**
- Template name: Configure in task (default: "hello_world")
- Template language: "en_US" or "es_MX"
- Dynamic parameters: family_name, invitation URL

## 🔐 Security

### Authentication Layers

1. **Admin Layer (JWT)**
   - Wedding owners authenticate with username/password
   - JWT tokens for API access
   - Token expires after 60 minutes
   - Refresh tokens for extended sessions

2. **Guest Layer (UUID)**
   - No traditional authentication
   - UUID serves as secure access token
   - Public URLs: `/invitacion/{uuid}`

### Multi-Tenant Isolation

All admin queries are automatically filtered by wedding:

```python
def get_queryset(self):
    user = self.request.user
    if hasattr(user, 'wedding'):
        return Invitation.objects.filter(wedding=user.wedding)
    return Invitation.objects.none()
```

### CORS Configuration

```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://palazzoinvites.com",
]
CORS_ALLOW_CREDENTIALS = True
```

## 🔧 Configuration

### Django Settings (`restapi/settings.py`)

**Key Settings:**

```python
# JWT Settings (default - customize in settings)
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# Celery Settings
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_TASK_ALWAYS_EAGER = False  # Set True for synchronous testing

# Meta WhatsApp API
META_ACCESS_TOKEN = "your-access-token"
META_PHONE_ID = "your-phone-number-id"
META_API_VERSION = "v22.0"

# File Upload Settings
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

## 📊 Database Queries

### Common Query Patterns

**Get all invitations for a wedding:**
```python
invitations = Invitation.objects.filter(wedding=request.user.wedding)
```

**Get invitation with guests (optimized):**
```python
invitation = Invitation.objects.prefetch_related('guests').get(uuid=uuid)
```

**Get RSVP statistics:**
```python
from django.db.models import Count, Q

stats = Guest.objects.filter(
    invitation__wedding=wedding
).aggregate(
    total=Count('id'),
    confirmed=Count('id', filter=Q(attendance='ACCEPTED')),
    declined=Count('id', filter=Q(attendance='DECLINED')),
    pending=Count('id', filter=Q(attendance='PENDING'))
)
```

**Get photos pending moderation:**
```python
pending = Photo.objects.filter(
    wedding=wedding,
    is_approved=False
).order_by('-created_at')
```

## 🧪 Testing

### Run Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Celery Tasks

Set synchronous execution in settings for testing:

```python
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG = False`
- [ ] Configure strong `SECRET_KEY`
- [ ] Use PostgreSQL database
- [ ] Configure Redis server (persistent)
- [ ] Set up proper `ALLOWED_HOSTS`
- [ ] Configure static files (collectstatic)
- [ ] Set up media file storage (S3/Cloud Storage)
- [ ] Configure SSL certificates
- [ ] Set up Celery with supervisor/systemd
- [ ] Configure error logging (Sentry)
- [ ] Set up database backups
- [ ] Configure rate limiting
- [ ] Set proper CORS origins
- [ ] Use environment variables for secrets

### Celery in Production

Use supervisor or systemd to manage Celery workers:

```bash
# Example supervisor config
[program:celery-worker]
command=/path/to/venv/bin/celery -A restapi worker --loglevel=info
directory=/path/to/backend
user=webapp
autostart=true
autorestart=true
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker_error.log
```

### Database Migration

For PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'palazzo_invites',
        'USER': 'postgres',
        'PASSWORD': 'your-password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 🐛 Troubleshooting

**Celery tasks not executing:**
```bash
# Check Redis connection
redis-cli ping  # Should return PONG

# Check Celery worker logs
celery -A restapi worker --loglevel=debug

# Verify broker URL
python manage.py shell
>>> from django.conf import settings
>>> print(settings.CELERY_BROKER_URL)
```

**WhatsApp messages not sending:**
- Verify Meta API credentials in settings
- Check message template is approved in Meta Business Manager
- Review Celery worker logs for API errors
- Ensure phone numbers are in E.164 format (+country_code)

**Database migration errors:**
```bash
# Show migration status
python manage.py showmigrations

# Fake a migration if needed
python manage.py migrate --fake core 0001

# Create new migration
python manage.py makemigrations
```

**CORS errors:**
- Ensure frontend URL is in `CORS_ALLOWED_ORIGINS`
- Check middleware order (CorsMiddleware before CommonMiddleware)
- Verify `CORS_ALLOW_CREDENTIALS = True` if using cookies

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [SimpleJWT Documentation](https://django-rest-framework-simplejwt.readthedocs.io/)

## 📝 License

Proprietary - All rights reserved

---

**Last Updated:** January 2026
