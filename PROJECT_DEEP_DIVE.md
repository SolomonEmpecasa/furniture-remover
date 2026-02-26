# Furniture Mover — Deep Technical Breakdown

Date: 2026-02-24

This document explains how your project works end-to-end at code level: what each module does, what each function means, and how parts connect to run the full website.

If you are new to coding, start with `PROJECT_BEGINNER_GUIDE.md` first, then come back to this deep dive.

---

## 1) System Architecture at a Glance

Your app is a Flask monolith with server-rendered templates (Jinja2), SQLite via SQLAlchemy ORM, and client-side JS for map/routing + live estimate UX.

**Layers**
1. **Entry/Boot**: `app.py`, `config.py`
2. **Domain/Data**: `models.py`
3. **HTTP Controllers (Blueprints)**:
   - `routes.py` (public pages/profile)
   - `auth.py` (login/signup/profile edit/admin signup)
   - `booking.py` (booking create/detail/price APIs)
   - `driver.py` (driver workflow)
   - `admin.py` (admin dashboard + controls)
   - `rating.py` (driver/user/site ratings)
4. **Pricing Engine**: `pricing_module.py` (ML training + prediction)
5. **Presentation**: `templates/*.html`, `static/css/*.css`

**Execution model**
- Flask handles route requests.
- Each route reads/writes models via SQLAlchemy.
- Route returns Jinja template with context.
- JS on pages performs additional API calls (`/api/price-estimate`) and map operations.

---

## 2) Startup and App Initialization

### File: `app.py`

### `create_app()` — what it does, in order
1. Creates Flask app and loads `Config`.
2. Initializes SQLAlchemy (`db.init_app(app)`).
3. If `AUTO_CREATE_DB` is enabled:
   - calls `db.create_all()` to create tables,
   - inspects existing schema,
   - attempts to add missing columns with `ALTER TABLE` (development-only migration-like behavior),
   - ensures `static/uploads` folder exists.
4. Configures Flask-Login:
   - `login_view = "auth.login"`
   - `user_loader` resolves user by id.
5. Registers all blueprints in one app:
   - `auth_bp`, `booking_bp`, `main_bp`, `admin_bp`, `driver_bp`, `rating_bp`

### Why this matters
- This is the single wiring point for all route modules and auth/session behavior.
- If a blueprint isn’t registered here, its routes are unreachable.

### File: `config.py`
- Defines `Config` class values:
  - `SECRET_KEY`
  - `SQLALCHEMY_DATABASE_URI` (default SQLite at `instance/furniture_mover.db`)
  - `SQLALCHEMY_TRACK_MODIFICATIONS = False`
  - `AUTO_CREATE_DB`
  - `ADMIN_REG_CODE` (gate for admin signup)

---

## 3) Data Model and Relationships

### File: `models.py`

## `User`
Purpose: account identity + role + profile + driver metadata.

Key columns:
- identity: `id`, `username`, `email`, `password_hash`
- profile: `full_name`, `phone`, `age`, `profile_pic`
- role state: `role` (`user|driver|admin`), `driver_status` (`pending|approved|rejected`), `driver_available`
- driver docs: `driver_license_path`, `driver_bluebook_path`, `driver_photo_path`
- vehicle metadata: `vehicle_name`, `vehicle_brand`, `vehicle_plate`, `vehicle_info`

Methods:
- `set_password(password)`: hashes password
- `check_password(password)`: verifies hash
- `get_average_rating()`: aggregates `Rating` where `rated_id=self.id`
- `get_total_ratings()`: count of received ratings

Relationships:
- `bookings` = bookings where user is sender (`Booking.user_id`)
- Also receives `assigned_bookings` backref from `Booking.driver`

## `Booking`
Purpose: one shipment lifecycle.

Key columns:
- parties: `user_id`, `driver_id`
- location: `origin`, `destination`, `origin_lat/lng`, `dest_lat/lng`
- schedule/pricing: `date`, `booking_time`, `distance_km`, `price`
- route and traffic: `route_geojson`, `traffic_level`, `traffic_multiplier`
- payment: `payment_method`, `payment_by`, `payment_received`
- lifecycle: `status`, `created_at`, `delivered_at`
- rating snapshots: `user_rating`, `driver_rating`, `user_feedback`, `driver_feedback`, timestamps

Relationships:
- `user` (sender)
- `driver`
- backrefs from `Rating` and `SiteFeedback`

## `Rating`
Purpose: person-to-person rating tied to booking.
- `booking_id`, `rater_id`, `rated_id`, `rating`, `feedback`, `created_at`

## `SiteFeedback`
Purpose: website experience rating tied to booking+author.
- `booking_id`, `author_id`, `author_role`, `rating`, `feedback`, `created_at`

---

## 4) Backend Modules — Function-by-Function Meaning

### File: `routes.py` (main blueprint)
- `home()` (`/`): fetches latest 6 site feedback entries, renders `home.html`
- `profile()` (`/profile`, login required): loads current user bookings, renders `profile.html`
- `vehicles()` (`/vehicles`): renders `vehicles.html`

### File: `auth.py` (auth blueprint)

Forms:
- `LoginForm`: username/password
- `SignupForm`: user profile + optional driver fields + docs

Routes:
- `login()` (`/login`): validate form, query user, verify password, `login_user`, redirect home
- `signup()` (`/signup`): uniqueness check; create user; if driver checkbox:
  - stores role as `user` + `driver_status=pending`
  - saves optional uploaded docs into `static/uploads`
- `logout()` (`/logout`): clears session
- `edit_profile()` (`/profile/edit`): updates profile fields + profile pic upload
- `admin_signup()` (`/admin/signup`): only available when `ADMIN_REG_CODE` exists and matches token

Helper behavior:
- local `save_upload()` in signup path secures filenames and writes files.

### File: `booking.py` (booking blueprint)

Helpers:
- `_haversine(...)`: geographic distance in km
- `_to_float(value)`: robust float parse
- `_compute_distance(...)`:
  - uses explicit `distance_km` if provided,
  - else computes from coordinates,
  - falls back to 1.0 km
- `_is_peak_hour(time_of_day)`: peak window detection for pricing input
- `_parse_distances(raw_value)`: parse comma-separated distances for comparison view

Routes:
- `book()` (`/book`, GET/POST):
  - POST flow: parse form + coordinates + compute distance + derive `is_peak` + call `pm.predict_price(...)` + save `Booking` + redirect detail
- `booking_detail(booking_id)` (`/booking/<id>`): booking detail page
- `price_distance_comparison()` (`/price-distance`):
  - computes prices for list of distances with fixed other params,
  - applies non-decreasing normalization for display (`running max`),
  - renders `price_distance.html`
- `api_price_estimate()` (`/api/price-estimate`, POST JSON):
  - computes/normalizes inputs,
  - predicts price,
  - returns JSON used by booking page JS live estimate

### File: `driver.py` (driver blueprint)

Guards:
- `driver_required`: only role=driver
- `driver_or_admin_required`: role in {driver, admin}

Helper:
- `_save_upload(...)`: secure file storage to `static/uploads`

Routes:
- `driver_dashboard()` (`/driver`):
  - admin sees all pending + all active/completed bookings
  - driver sees pending + own accepted/active/completed
  - pending/rejected applicant sees application status page state
- `driver_reapply()` (`/driver/reapply`, POST): resubmit driver docs/details after rejection
- `driver_accept(booking_id)` (`/driver/accept/<id>`, POST): assigns driver, sets status `arrived`
- `start_journey(booking_id)` (`/driver/start-journey/<id>`, POST): validates authorization + payment rule, status `in_transit`
- `view_journey(booking_id)` (`/driver/view-journey/<id>`): renders journey simulation
- `mark_delivered(booking_id)` (`/driver/mark-delivered/<id>`, POST): validates payment rule, sets `delivered`

### File: `admin.py` (admin blueprint)

Guard:
- `admin_required`: role=admin enforced after login

Routes:
- `admin_dashboard()` (`/admin`):
  - loads users/bookings
  - computes analytics: avg/median/min/max price, avg distance, avg price/km,
  - computes traffic/time/peak aggregations
  - builds histogram buckets
  - renders `admin_dashboard.html`
- `admin_set_role()` (`/admin/set-role`, POST): bulk role updates from form
- `admin_driver_approve(user_id)` (`/admin/driver-applications/<id>/approve`, POST)
- `admin_driver_reject(user_id)` (`/admin/driver-applications/<id>/reject`, POST)
- `clear_orders()` (`/admin/clear-orders`, POST): deletes all bookings

### File: `rating.py` (rating blueprint)

Routes:
- `rate_driver(booking_id)` (`/rate-driver/<id>`, GET/POST): sender rates driver + site
- `rate_user(booking_id)` (`/rate-user/<id>`, GET/POST): driver/admin rates sender + site
- `view_ratings(user_id)` (`/ratings/<id>`): user’s received ratings page
- `user_stats(user_id)` (`/api/user-stats/<id>`): JSON aggregates

Authorization logic patterns:
- sender can rate driver only if booking delivered and not already rated
- assigned driver/admin can rate sender only if delivered and not already rated

---

## 5) Pricing Engine Deep Dive

### File: `pricing_module.py`

This module has **two layers**:

1) **Synthetic data generation / training layer**
- `_calculate_base_price(distance_km, truck_category)`:
  - base = distance × rate
  - floor at category min
- `_apply_kathmandu_factors(base_price, factors)`:
  - multiplies traffic factor
  - peak-hour multiplier
  - night discount
  - distance>15 slight discount
  - random ±10%
  - cap at category max
- `_generate_kathmandu_data(num_samples=500)`:
  - creates random records with categories/time/traffic/distance
  - target label `accepted_price_npr`
- `_train_pricing_model()`:
  - label-encodes categorical cols
  - train/test split
  - trains `RandomForestRegressor`

2) **Runtime prediction layer**
- `predict_price(distance_km, truck_category, traffic_level, time_of_day, is_peak_hour)`:
  - lazy-trains model on first call
  - maps frontend values to training labels
  - normalizes `time_of_day` to Morning/Afternoon/Evening/Night
  - encodes categorical features
  - predicts via RF
  - applies hard min/max clamp per vehicle class
  - returns rounded integer NPR

**Important implication**
- Price is not guaranteed monotonic by distance because model is unconstrained RF trained on noisy synthetic labels.

---

## 6) Route Map (Complete)

## Public/User
- `/` → `main.home`
- `/vehicles` → `main.vehicles`
- `/login` → `auth.login`
- `/signup` → `auth.signup`
- `/logout` → `auth.logout`
- `/profile` → `main.profile`
- `/profile/edit` → `auth.edit_profile`

## Booking
- `/book` (GET/POST) → `booking.book`
- `/booking/<int:booking_id>` → `booking.booking_detail`
- `/price-distance` → `booking.price_distance_comparison`
- `/api/price-estimate` (POST JSON) → `booking.api_price_estimate`

## Driver
- `/driver` → `driver.driver_dashboard`
- `/driver/reapply` (POST)
- `/driver/accept/<int:booking_id>` (POST)
- `/driver/start-journey/<int:booking_id>` (POST)
- `/driver/view-journey/<int:booking_id>`
- `/driver/mark-delivered/<int:booking_id>` (POST)

## Admin
- `/admin`
- `/admin/set-role` (POST)
- `/admin/driver-applications/<int:user_id>/approve` (POST)
- `/admin/driver-applications/<int:user_id>/reject` (POST)
- `/admin/clear-orders` (POST)

## Ratings/API
- `/rate-driver/<int:booking_id>`
- `/rate-user/<int:booking_id>`
- `/ratings/<int:user_id>`
- `/api/user-stats/<int:user_id>`

---

## 7) Template-to-Backend Connection Matrix

Each template is server-rendered and extends `base.html` unless standalone behavior is explicit.

- `base.html`
  - global nav to home/vehicles/profile/book/driver/admin/login/signup/logout
  - shared flash rendering
  - shared JS and stylesheet loading

- `home.html`
  - consumes `site_feedbacks` from `main.home`

- `vehicles.html`
  - static explanatory vehicle page

- `login.html`
  - form for `auth.login`

- `signup.html`
  - form for `auth.signup`; includes optional driver application fields

- `admin_signup.html`
  - form for `auth.admin_signup`

- `profile.html`
  - consumes `bookings` from `main.profile`
  - links to booking detail and rating pages
  - includes action target to `booking.cancel_booking` (see known issues below)

- `edit_profile.html`
  - form posts to `auth.edit_profile`

- `booking.html`
  - POST booking form to `/book`
  - map/coordinate selection + route calculations (client-side)
  - live estimate via fetch `POST /api/price-estimate`
  - links to booking detail and `/price-distance`

- `booking_detail.html`
  - shows booking summary

- `price_distance.html`
  - GET form to `/price-distance`
  - shows distance-only comparison rows

- `driver_dashboard.html`
  - accepts bookings, starts journey, marks delivered, reapply driver docs
  - links to journey view and rating routes

- `journey_simulation.html`
  - map animation and route line
  - form actions:
    - `driver.start_journey`
    - `driver.mark_delivered`

- `rate_driver.html`, `rate_user.html`
  - POST rating + site feedback into `rating` routes

- `view_ratings.html`
  - renders ratings list from `rating.view_ratings`

---

## 8) End-to-End Runtime Flows

## A) New booking flow
1. User logs in.
2. Opens `/book`, picks origin/destination/date/time/vehicle/payment.
3. JS calls `/api/price-estimate` during interaction.
4. On submit, backend computes final price using `pricing_module.predict_price`.
5. `Booking` saved with status `pending`.
6. Redirect to `/booking/<id>`.

## B) Driver fulfillment flow
1. Driver opens `/driver`, sees pending.
2. Accepts booking (`/driver/accept/<id>`), status→`arrived`.
3. Starts journey (`/driver/start-journey/<id>`), status→`in_transit`.
4. Marks delivered (`/driver/mark-delivered/<id>`), status→`delivered`.

## C) Ratings flow
1. After delivery, sender can rate driver (`/rate-driver/<id>`).
2. Driver can rate sender (`/rate-user/<id>`).
3. Both may write website feedback (`SiteFeedback`).
4. Home page surfaces latest site feedback.

## D) Admin governance flow
1. Admin opens `/admin` for system analytics.
2. Approves/rejects driver applications.
3. Can bulk update roles.
4. Can clear all bookings.

---

## 9) External Integrations / Front-End Runtime Services

- **Leaflet** for maps and markers.
- **OSRM public API** used client-side for route geometry in journey and booking UI.
- `openrouteservice` package is present in requirements, but active route logic is currently OSRM-based in templates.

---

## 10) Security and Access Control Model

- Flask-Login session-based auth.
- Route-level decorators enforce:
  - login required (`@login_required`)
  - role checks (admin/driver)
- Passwords hashed with Werkzeug.
- Upload filenames sanitized with `secure_filename`.

Potential hardening areas:
- No explicit CSRF review documented for all forms (Flask-WTF present but not uniformly form-class-driven).
- Development schema auto-alter logic is convenient but risky outside development.

---

## 11) Known Inconsistencies / Gaps Found in Current Code

1. **Dangling template action**:
   - `profile.html` references `booking.cancel_booking`
   - No such route exists in `booking.py`

2. **Pricing behavior expectations vs model**:
   - RF model can produce near-flat/non-monotonic distance response.
   - Distance comparison page currently applies monotonic display adjustment for readability.

3. **Runtime training**:
   - model trains lazily in memory at first call;
   - no persisted artifact/versioning.

---

## 12) Testing Surface

### File: `test_pricing.py`
- Manual script-style tests printing pricing outputs under different conditions.
- Useful for exploratory checks, not integrated as formal test assertions.

---

## 13) Dependency Meaning (`requirements.txt`)

- Core web/app: Flask, Werkzeug, Flask-SQLAlchemy, Flask-Login, Flask-WTF, WTForms
- Validation: email-validator
- Data/ML: scikit-learn, numpy, pandas
- DB connectors beyond SQLite: mysql-connector-python, pymysql
- Env management: python-dotenv
- Routing client package available: openrouteservice

---

## 14) How to Debug Any Feature by Trace Path

For any feature, follow this deterministic chain:
1. Find route decorator in blueprint (`*.py`).
2. Read route function to identify:
   - request inputs,
   - helper calls,
   - model queries/writes,
   - `render_template` target.
3. Open template and identify:
   - context variables consumed,
   - links/forms (`url_for` targets),
   - JS fetch endpoints.
4. Confirm model fields touched in `models.py`.
5. For price-related behavior, inspect `pricing_module.predict_price` input mapping + clamping.

This pattern explains almost every website behavior in your codebase.

---

## 15) If You Want “Even Deeper” Next Layer

You can extend this doc with:
- per-template variable dictionary (every Jinja variable and source)
- sequence diagrams for each workflow (booking/driver/admin/rating)
- database ER diagram (User/Booking/Rating/SiteFeedback)
- API contract specs for JSON endpoints
- production-readiness checklist (migrations, model persistence, observability)
