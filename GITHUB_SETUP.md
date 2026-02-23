# GitHub Setup & Deployment Guide

## For Your Friends - Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd furniture-mover
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment** (Optional)
   ```bash
   copy .env.example .env
   # Edit .env and set your values
   ```

5. **Run the application**
   ```bash
   python app.py
   ```
   
   The app will start at `http://127.0.0.1:5000`

## Project Structure

- `app.py` - Main Flask application entry point
- `models.py` - Database models (User, Booking, Rating)
- `routes.py` - Main website routes and pages
- `auth.py` - Authentication and user registration
- `booking.py` - Booking management endpoints
- `admin.py` - Admin dashboard and controls
- `driver.py` - Driver-specific features
- `rating.py` - Rating and feedback system
- `config.py` - Configuration settings
- `templates/` - HTML templates for pages
- `static/` - CSS, images, and client-side files

## Features

- **User Authentication** - Login and signup with role-based access (user, driver, admin)
- **Booking System** - Users can create bookings with interactive map selection
- **Driver Management** - Drivers can accept bookings and provide services
- **Rating System** - Users and drivers can rate each other (1-5 stars)
- **Admin Dashboard** - View statistics, manage users and bookings
- **Responsive UI** - Works on desktop and mobile devices

## Database

- Default: SQLite (in-memory development)
- For production: Use MySQL or PostgreSQL
- Set `DATABASE_URL` in `.env` to use different database

## Troubleshooting

### Database Issues
- If you get database errors, ensure `AUTO_CREATE_DB=True` in config
- Or manually initialize by running `python app.py` which creates tables on startup

### Port Already in Use
- Change port in `app.py` line: `app.run(debug=True, port=5001)`

### Missing Dependencies
- Make sure you activated the virtual environment
- Run `pip install -r requirements.txt` again

## Deployment

For production deployment, use:
- **Gunicorn** - Production WSGI server
- **nginx** - Reverse proxy
- **Heroku** or **PythonAnywhere** - For quick cloud hosting
- **Docker** - For containerization

Example Gunicorn command:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Notes

- This is a fullstack furniture moving/transport booking application
- Built with Flask (backend) and Bootstrap (frontend)
- Includes geolocation and route mapping features
- Implements traffic-aware pricing
- Real-time booking status updates

For questions or issues, please open an issue on GitHub.
