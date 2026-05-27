# BookMyShow — Movie Ticket Booking System

A high-performance, full-stack movie ticket booking web application built using the Django framework. The project replicates the core architectural workflows of BookMyShow, focusing on database data integrity, secure transactional payment flows, and asynchronous background operations.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Local Setup](#local-setup)
- [Payment Flow](#payment-flow)
- [Security Implementation](#security-implementation)
- [Admin Dashboard](#admin-dashboard)
- [Project Structure](#project-structure)
- [Author](#author)

---

## Overview

This project was developed as part of the Summer Internship 2026 program. It implements a production-grade movie ticket booking system with a focus on concurrency safety, secure payment processing, background task management, and real-time analytics. The system is designed to handle simultaneous requests from multiple users without data inconsistency or double booking.

---

## Features

**Movie Management**
- Browse movies with search, genre and language filters
- Sorting by rating, latest, and oldest
- Pagination for large datasets
- Movie detail page with lazy-loaded YouTube trailer embedding

**Seat Selection and Reservation**
- Interactive seat map with real-time availability
- Concurrency-safe seat reservation using database row-level locking
- Seats temporarily locked for 2 minutes during payment
- Automatic release of expired reservations via background scheduler
- Three seat states: Available, Reserved, Booked

**Payment Gateway**
- Razorpay integration with server-side order creation
- Server-side signature verification to prevent fraud
- Idempotency keys to prevent duplicate transactions
- Webhook handling for payment captured and payment failed events
- Graceful handling of payment timeouts and cancellations

**Email Notifications**
- Automated booking confirmation emails using Django template engine
- Background processing via Celery and Redis to prevent blocking
- Retry logic for failed email deliveries
- Logging and monitoring of all failed email attempts

**Admin Analytics Dashboard**
- Real-time revenue analytics: daily, weekly, and monthly
- Most popular movies ranked by booking count
- Busiest theaters ranked by seat occupancy rate
- Peak booking hours analysis
- Cancellation and payment failure rates
- Redis caching with 5 minute TTL to prevent performance degradation

**Security**
- Role-based access control using Django staff authentication
- XSS prevention on YouTube trailer embedding
- Secure credential storage using environment variables
- CSRF protection on all forms

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | Django 5.2 |
| Database (Production) | PostgreSQL |
| Database (Development) | SQLite |
| Cache and Message Broker | Redis |
| Task Queue | Celery |
| Task Scheduler | Celery Beat |
| Payment Gateway | Razorpay |
| Email | Gmail SMTP |
| Frontend | Bootstrap 5 |
| Deployment | Render |

---

## System Architecture

```
Client Request
      |
Django Views (Authentication + Business Logic)
      |
      |--- PostgreSQL (Bookings, Payments, Seats)
      |
      |--- Redis (Cache + Celery Broker)
                |
                |--- Celery Worker (Email Confirmation)
                |
                |--- Celery Beat (Reservation Expiry Every 60s)
```

---

## Local Setup

**Prerequisites**
- Python 3.11
- Redis Server
- Git

**Step 1 — Clone the repository:**
```bash
git clone https://github.com/abstark-3000/BookMyShow.git
cd BookMyShow
```

**Step 2 — Create and activate virtual environment:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Step 3 — Install dependencies:**
```bash
pip install -r requirements.txt
```

**Step 4 — Create .env file in project root:**
```
SECRET_KEY=your-secret-key
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxx
RAZORPAY_KEY_SECRET=your-razorpay-secret
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEBUG=True
```

**Step 5 — Run database migrations:**
```bash
python manage.py migrate
python manage.py createsuperuser
```

**Step 6 — Start Redis server:**
```bash
redis-server
```

**Step 7 — Start Celery worker (new terminal):**
```bash
celery -A bookmyseat worker --pool=solo -l info
```

**Step 8 — Start Celery Beat scheduler (new terminal):**
```bash
celery -A bookmyseat beat -l info
```

**Step 9 — Start Django development server:**
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Payment Flow

```
1.  User selects seats
2.  System locks seats at database level for 2 minutes (select_for_update)
3.  Razorpay order created server-side via API
4.  User completes payment on Razorpay checkout
5.  Razorpay returns payment credentials to frontend handler
6.  Frontend submits credentials to server via POST
7.  Server verifies Razorpay signature using HMAC SHA256
8.  On verification success, Booking records created atomically
9.  Seat marked as is_booked=True, reservation fields cleared
10. Confirmation email dispatched to Celery queue
11. User redirected to movie list
```

---

## Security Implementation

**Payment Security**
- All Razorpay orders created server-side, never on frontend
- Payment signature verified server-side using HMAC SHA256 before booking is confirmed
- Idempotency keys built from user ID, theater ID, and seat IDs to prevent duplicate bookings
- Webhook signature validated to prevent replay attacks

**Concurrency Safety**
- select_for_update() with transaction.atomic() used for all seat operations
- Row-level database locking prevents simultaneous booking of the same seat
- Celery Beat releases expired reservations every 60 seconds automatically

**Application Security**
- YouTube trailer URLs validated against regex before embedding
- Embed URLs read from data attributes, never from innerHTML
- All credentials stored in environment variables, never hardcoded
- Staff-only admin dashboard using Django built-in role-based access control
- CSRF tokens on all POST forms

**Email Security**
- Gmail App Password used instead of account password
- TLS encryption enforced on all SMTP connections

---

## Admin Dashboard

Access at `/movies/admin-dashboard/`

Requires a staff account. To grant staff access:

```bash
python manage.py shell
from django.contrib.auth.models import User
u = User.objects.get(username='your_username')
u.is_staff = True
u.save()
```

**Analytics displayed:**
- Daily, weekly, and monthly revenue from successful payments
- Top 10 movies by total booking count
- Top 10 theaters by seat occupancy rate with progress bars
- Peak booking hours ranked by booking volume
- Payment cancellation rate and failure rate as percentages

**Performance optimization:**
- All queries use database-level aggregation (Sum, Count, TruncDay, ExtractHour)
- No entire datasets loaded into memory
- Results cached in Redis for 5 minutes
- Proper database indexes on booked_at, movie, theater, status, and created_at fields

---

## Project Structure

```
BookMyShow/
    bookmyseat/
        settings.py
        urls.py
        celery.py
        wsgi.py
    movies/
        models.py
        views.py
        tasks.py
        urls.py
        admin.py
    users/
        models.py
        views.py
        urls.py
    templates/
        movies/
            movie_list.html
            movie_detail.html
            theater_list.html
            seat_selection.html
            payment.html
            admin_dashboard.html
            emails/
                booking_confirmation.html
        users/
            login.html
            register.html
            basic.html
    requirements.txt
    Procfile
    render.yaml
    manage.py
```

---

## Author

Arnav Bhardwaj
Summer Internship 2026
BookMyShow Project