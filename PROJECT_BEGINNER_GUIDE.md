# Furniture Mover — Beginner Guide (From Zero)

Date: 2026-02-24

This guide explains your project in very simple language.
Think of it as: **what this website is**, **what each file does**, and **how everything connects**.

---

## 1) First, what kind of project is this?

This is a **Flask web application**.

- **Flask** = a Python tool for building websites.
- **Database (SQLite)** = where your app stores users, bookings, ratings.
- **Templates (HTML files)** = what users see in browser.
- **Routes (Python functions)** = what runs when someone opens a URL or submits a form.

Simple idea:
1. User opens a page (example: `/book`).
2. Flask runs a Python function for that URL.
3. Function reads/writes database data.
4. Function sends an HTML page back.
5. Browser shows it.

---

## 2) Project folders and files (what each one means)

### Core Python files

- `app.py` → starts the app and connects all modules.
- `config.py` → app settings (secret key, DB path).
- `models.py` → database tables (User, Booking, Rating, SiteFeedback).
- `auth.py` → login/signup/logout/profile edit.
- `routes.py` → basic pages (home, profile, vehicles).
- `booking.py` → booking creation + price API + distance comparison page.
- `driver.py` → driver dashboard and delivery actions.
- `admin.py` → admin dashboard and management actions.
- `rating.py` → user/driver ratings and site feedback.
- `pricing_module.py` → price prediction model logic.

### Templates (UI pages)

- `templates/base.html` → common layout (navbar/footer).
- `templates/booking.html` → booking form + live map + estimate.
- `templates/driver_dashboard.html` → driver workflow page.
- `templates/admin_dashboard.html` → admin controls + analytics.
- Other templates are supporting pages (login/signup/profile/rating/etc).

### Static files

- `static/css/style.css`, `static/css/styles.css` → styling.
- `static/uploads/` → uploaded profile/doc files.

---

## 3) What happens when the app starts?

### File: `app.py`

Main function: `create_app()`

Beginner meaning:
- Builds the Flask app object.
- Loads settings from `config.py`.
- Connects database (`db.init_app(app)`).
- Creates tables if missing.
- Tries to add missing columns in dev mode.
- Sets login system (`LoginManager`).
- Registers all route groups (blueprints).

Why this matters:
If this file doesn’t register a blueprint, those pages do not exist.

---

## 4) Database tables in plain English

### File: `models.py`

Think of a model as an Excel sheet design.

## `User` table
Stores people using the app.

Important fields:
- `username`, `email`, `password_hash`
- `role` (user / driver / admin)
- profile fields (name, phone, age, pic)
- driver document paths and vehicle fields

Functions:
- `set_password()` → stores password safely (hashed)
- `check_password()` → checks login password
- `get_average_rating()` and `get_total_ratings()`

## `Booking` table
Stores each moving request.

Important fields:
- who booked (`user_id`)
- assigned driver (`driver_id`)
- origin/destination + coordinates
- date/time, distance, price
- payment method and payment status
- booking status (`pending`, `arrived`, `in_transit`, `delivered`)

## `Rating` table
Stores rating from one user to another.

## `SiteFeedback` table
Stores feedback about your website experience.

---

## 5) Authentication (login/signup) step-by-step

### File: `auth.py`

## `login()`
- Shows login form.
- On submit, finds user by username.
- Verifies password using `check_password()`.
- If valid: creates login session and redirects home.

## `signup()`
- Checks if username/email already exists.
- Creates new user.
- If “driver” checked:
  - stores as normal user first,
  - sets `driver_status = pending`,
  - saves uploaded driver documents.
- Logs user in after registration.

## `logout()`
- Ends session.

## `edit_profile()`
- Updates profile fields and profile picture.

## `admin_signup()`
- Creates admin account only if secret token matches config.

---

## 6) Public/main pages

### File: `routes.py`

- `home()` → shows latest website feedback.
- `profile()` → shows logged-in user bookings.
- `vehicles()` → shows available vehicle guidance.

---

## 7) Booking flow (most important business logic)

### File: `booking.py`

### Helper functions (simple meaning)

- `_haversine(...)`
  - math formula to compute distance between two coordinate points.

- `_to_float(value)`
  - safely convert text to number.

- `_compute_distance(...)`
  - if user gave distance manually, use that.
  - else if coordinates exist, calculate distance.
  - else fallback to 1 km.

- `_is_peak_hour(time)`
  - checks if time is in busy traffic hours.

- `_parse_distances(raw_text)`
  - reads values like `2, 5, 10` into a clean number list.

### Main routes

## `/book` → `book()`
GET:
- opens booking form page.

POST:
- reads form values,
- computes distance,
- chooses traffic/time/peak inputs,
- calls price predictor,
- creates booking row in database,
- redirects to booking detail page.

## `/booking/<id>` → `booking_detail()`
Shows one booking details page.

## `/api/price-estimate` → `api_price_estimate()`
Used by JavaScript in booking page.
Returns JSON estimate without saving booking.

## `/price-distance` → `price_distance_comparison()`
Shows “same settings, different distances” price table.

---

## 8) Driver workflow (delivery lifecycle)

### File: `driver.py`

### Access checks
- `driver_required` → only drivers.
- `driver_or_admin_required` → drivers or admin.

### Routes

## `/driver` → `driver_dashboard()`
- driver sees pending + assigned bookings
- admin sees wider list
- rejected/pending applicants see application state

## `/driver/accept/<booking_id>`
Driver accepts booking.
Status becomes `arrived`.

## `/driver/start-journey/<booking_id>`
Checks payment rule (if sender pays at pickup).
Status becomes `in_transit`.

## `/driver/view-journey/<booking_id>`
Opens map simulation page.

## `/driver/mark-delivered/<booking_id>`
Checks receiver payment rule when required.
Sets status to `delivered` and save delivered time.

## `/driver/reapply`
Rejected driver re-submits docs/info.

---

## 9) Admin workflow

### File: `admin.py`

## `/admin` → `admin_dashboard()`
Loads:
- all users
- all bookings
- analytics: avg price, median, traffic-based averages, peak/off-peak stats, etc.

## `/admin/set-role`
Bulk role changes.

## `/admin/driver-applications/<id>/approve`
Approves driver application.

## `/admin/driver-applications/<id>/reject`
Rejects with feedback.

## `/admin/clear-orders`
Deletes all bookings (dangerous action).

---

## 10) Ratings workflow

### File: `rating.py`

## `rate_driver()`
User rates driver after delivered booking.
Also asks website rating.

## `rate_user()`
Driver rates customer after delivered booking.
Also asks website rating.

## `view_ratings(user_id)`
Shows all ratings for a user.

## `user_stats(user_id)`
Returns JSON stats (avg rating, total ratings, deliveries).

---

## 11) Pricing module in beginner language

### File: `pricing_module.py`

Your pricing has two parts:

1. **Training data generator**
   - Creates fake Kathmandu booking records.
   - Applies rules (distance, traffic, time, peak, random noise).

2. **ML prediction function**
   - Trains RandomForest model (first time only in runtime memory).
   - Encodes text categories to numbers.
   - Predicts price.
   - Applies min/max limits by vehicle type.

Current limits:
- Small: min 400, max 1500
- Medium: min 700, max 2500
- Large: min 1200, max 4000

Important beginner note:
- Because it is ML over synthetic/noisy data, price is not always perfectly intuitive.

---

## 12) How frontend pages connect to backend

### Template: `base.html`
- shared navbar links are built with `url_for(...)`
- pages extend this file

### Template: `booking.html`
- booking form submits to `/book`
- JS calls `/api/price-estimate` for live estimate
- links to distance comparison page

### Template: `journey_simulation.html`
- buttons post to `start_journey` and `mark_delivered`
- JS fetches route path and animates map movement

### Template: `profile.html`
- displays user bookings and links to booking details/rating actions

---

## 13) One complete real example (easy to follow)

Example: user books furniture move.

1. User logs in (`/login`).
2. Opens `/book`.
3. Selects pickup and destination on map.
4. JS gets estimate from `/api/price-estimate`.
5. User submits form.
6. `book()` saves booking with status `pending`.
7. Driver opens `/driver`, accepts booking.
8. Driver starts journey → `in_transit`.
9. Driver marks delivered → `delivered`.
10. User rates driver, driver rates user.
11. Ratings appear in profile/ratings pages.

---

## 14) Known gaps you should know as a beginner

1. `profile.html` has a cancel button targeting `booking.cancel_booking`, but that route is currently missing.
2. Pricing model is trained at runtime and not persisted to file.
3. Model behavior can feel flat or odd for distance in some cases.

---

## 15) Quick glossary (easy words)

- **Route**: URL + Python function pair.
- **Blueprint**: group of related routes.
- **Template**: HTML page with Jinja placeholders.
- **ORM**: Python way to read/write DB without raw SQL.
- **Session**: login state stored across requests.
- **API endpoint**: route that returns JSON instead of full page.

---

## 16) If you want next-level beginner help

You can now ask for one of these and I can generate it:
1. “Teach me file by file in learning order.”
2. “Give me a flowchart for booking lifecycle.”
3. “Explain each template variable used in one page.”
4. “Show me where to add one new feature step-by-step.”
