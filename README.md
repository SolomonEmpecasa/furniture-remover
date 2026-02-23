# Furniture Mover (Simple Flask scaffold)

This is a minimal Flask scaffold for a furniture moving booking frontend + simple backend.

Features included
- Login / Sign up (Flask-Login + Flask-WTF) with optional driver role selection at signup
- Separate dashboards for Users, Drivers, and Admins
- Home page with navigation and a Leaflet map placeholder
- Booking page with interactive map, location picker, and route preview (Leaflet Routing Machine)
- `models.py` with `User` and `Booking` (ready for MySQL)

Quick start (Windows)

1. Create and activate a virtualenv:
   python -m venv venv
   venv\Scripts\Activate.ps1  # or venv\Scripts\activate

2. Install:
   pip install -r requirements.txt

3. Configure environment (optional):
   - Create a `.env` from `.env.example` and set values, or set environment variables:
     - SECRET_KEY
     - DATABASE_URL (e.g. `mysql+mysqlconnector://user:password@localhost/dbname`)

Note: The app will attempt to create DB tables automatically on startup when `AUTO_CREATE_DB` is enabled (default). You can disable that by setting `AUTO_CREATE_DB=False` in your environment or `.env` file.

4. Run app:
   python app.py

Notes
- Map uses Leaflet + OpenStreetMap tiles (no API key required).
- Home page uses photographic assets hotlinked from Unsplash for decoration (see image credits in the footer/gallery captions). These are public Unsplash images used for demo purposes — replace with your own assets for production if desired.
- The UI now uses a colorful theme with gradient accents, decorative SVG backgrounds (`/static/images/decorative-waves.svg`) and a gradient logo (`/static/images/logo-gradient.svg`). Replace these with your brand assets in `/static/images/` as needed.
- Roles: Users have a `role` field (user / driver / admin). During signup, users can check "Are you a driver?" to register as a driver and be immediately redirected to the driver dashboard. Drivers can accept bookings; admins can view users and bookings.
- Create an admin user by registering normally and then changing the role to `admin` in the database, or seed one directly in your DB.
- Optional web admin signup: set `ADMIN_REG_CODE` (in `.env` or environment) to a secret token. When set, `/admin/signup` will be exposed and will require that token to create an admin account; if `ADMIN_REG_CODE` is unset the web form is disabled and returns 404.
- Users can edit a profile, upload a profile picture (saved to `static/uploads/`) and provide phone/age/vehicle info. Drivers can check their 'Available' checkbox in the profile.
- Routing and directions: the app now includes front-end routing using Leaflet Routing Machine (OSRM demo backend) for route preview. For server-side routing / distance calculation and more advanced features, you can set up an OpenRouteService API key and use the `openrouteservice` Python client (see `templates/_routes_note.html` for example code).
- Live traffic: for real-time traffic-aware routing consider Mapbox or HERE (both require API keys and may have paid plans). Mapbox also provides traffic tiles that can be overlaid on the map.
- Price calculation is a random placeholder—replace with a proper pricing function (you may use distance_km for basic per-km pricing).
- For production, set a secure `SECRET_KEY` and use a proper DB like MySQL.

## Branding

Place your logo file at `static/images/nepal_transport_logo.png` (PNG recommended). A placeholder SVG is included at `static/images/nepal_transport_logo.svg` and will be used if the PNG is not present.

Next improvements you might want: migrations (Flask-Migrate), unit tests, input validation, and secure password policy.

## UI Modernization

- The front-end has been updated to a modern layout using Bootstrap 5 and improved responsive CSS (`static/css/style.css`).
- Home and Vehicles pages include demo photographic assets hotlinked from Unsplash for a more realistic look. Replace these URLs with local files in `static/images/` (recommended) or change the links in the templates if you prefer licensed images.
- If you add local images, remove the Unsplash URLs and use `/static/images/your-image.jpg` paths instead.

