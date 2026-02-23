from flask_sqlalchemy import SQLAlchemy  # Database ORM library
from flask_login import UserMixin  # User authentication and session management  
from werkzeug.security import generate_password_hash, check_password_hash  # Password hashing utilities

db = SQLAlchemy()  # Initialize SQLAlchemy ORM


class User(db.Model, UserMixin):  # User model - stores user information (user ko jaankari)
    id = db.Column(db.Integer, primary_key=True)  # Unique user identifier
    username = db.Column(db.String(80), unique=True, nullable=False)  # Username - patro (required)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email address - email (required)
    password_hash = db.Column(db.String(128), nullable=False)  # Encrypted password - guffera password
    full_name = db.Column(db.String(120))  # Full name (pura naam)
    phone = db.Column(db.String(32))  # Phone number (phone number)
    age = db.Column(db.Integer)  # Age (umar)
    profile_pic = db.Column(db.String(255))  # Profile picture path - photo ko sthan
    role = db.Column(db.String(20), default="user")  # User role - user, driver, admin (rol)
    driver_status = db.Column(db.String(20))  # Driver status - pending, approved, rejected
    driver_feedback = db.Column(db.Text)  # Admin feedback for driver
    vehicle_name = db.Column(db.String(120))  # Vehicle name (gaadi ko naam)
    vehicle_brand = db.Column(db.String(120))  # Vehicle brand (gaadi ko brand)
    vehicle_plate = db.Column(db.String(64))  # License plate (gaadi ko nambar)
    driver_license_path = db.Column(db.String(255))  # Driver license document path
    driver_bluebook_path = db.Column(db.String(255))  # Vehicle registration document path
    driver_photo_path = db.Column(db.String(255))  # Driver profile photo path
    vehicle_info = db.Column(db.String(255))  # Vehicle specifications (gaadi ko bivaraṇ)
    driver_available = db.Column(db.Boolean, default=False)  # Driver availability (upalabdha)
    bookings = db.relationship(  # Relationship to bookings
        "Booking", back_populates="user", foreign_keys="Booking.user_id", lazy=True
    )

    def set_password(self, password):  # Hash and store password
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):  # Verify password during login
        return check_password_hash(self.password_hash, password)

    def get_average_rating(self):  # Calculate average rating (mukhya rating)
        """Calculate average rating for this user from all ratings received"""
        ratings = Rating.query.filter_by(rated_id=self.id).all()
        if not ratings:
            return 0
        return sum(r.rating for r in ratings) / len(ratings)

    def get_total_ratings(self):  # Get total count of ratings received (rating ko sankhya)
        """Get total number of ratings received"""
        return Rating.query.filter_by(rated_id=self.id).count()


class Booking(db.Model):  # Booking model - stores transportation requests (yatra ko nivedan)
    id = db.Column(db.Integer, primary_key=True)  # Unique booking identifier
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # Sender user ID (bhejne ko ID)
    user = db.relationship("User", foreign_keys=[user_id], back_populates="bookings")  # Relationship to sender
    origin = db.Column(db.String(255))  # Starting location (suru ko sthan)
    origin_lat = db.Column(db.Float)  # Starting latitude
    origin_lng = db.Column(db.Float)  # Starting longitude
    destination = db.Column(db.String(255))  # Destination location (manzil)
    dest_lat = db.Column(db.Float)  # Destination latitude
    dest_lng = db.Column(db.Float)  # Destination longitude
    date = db.Column(db.String(40))  # Booking date (din)
    price = db.Column(db.Integer)  # Price in Nepali Rupees (mulya)
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"))  # Assigned driver ID (driver ko ID)
    driver = db.relationship("User", foreign_keys=[driver_id], backref="assigned_bookings")  # Relationship to driver
    status = db.Column(db.String(40), default="pending")  # Status - pending/accepted/in_transit/delivered/cancelled
    delivered_at = db.Column(db.DateTime)  # Delivery completion time (pathe ayako samay)
    distance_km = db.Column(db.Float)  # Distance in kilometers (duri)
    route_geojson = db.Column(db.Text)  # Route map as GeoJSON (rasta ko map)
    created_at = db.Column(db.DateTime, server_default=db.func.now())  # Creation timestamp (banayako samay)
    payment_method = db.Column(db.String(20), default="cash")  # Payment method - cash or online
    payment_by = db.Column(db.String(20), default="sender")  # Who pays - sender or receiver
    payment_received = db.Column(db.Boolean, default=False)  # Payment receipt status
    traffic_level = db.Column(db.String(20))  # Traffic condition - light/medium/heavy
    traffic_multiplier = db.Column(db.Float)  # Price adjustment for traffic (traffic ko asar)
    booking_time = db.Column(db.String(16))  # Time of journey (samay)
    user_rating = db.Column(db.Integer)  # Rating given by driver to sender (1-5)
    user_feedback = db.Column(db.Text)  # Driver feedback about sender
    driver_rating = db.Column(db.Integer)  # Rating given by sender to driver (1-5)
    driver_feedback = db.Column(db.Text)  # Sender feedback about driver
    user_rated_at = db.Column(db.DateTime)  # When driver rated sender
    driver_rated_at = db.Column(db.DateTime)  # When sender rated driver


class Rating(db.Model):  # Rating model - stores user and driver ratings (mukhya)
    """Store ratings for users and drivers to track overall performance"""

    id = db.Column(db.Integer, primary_key=True)  # Unique rating identifier
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)  # Related booking
    rater_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # Who gave rating (rating dene wala)
    rated_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # Who received rating (rating pane wala)
    rating = db.Column(db.Integer, nullable=False)  # Rating value - 1 to 5 stars
    feedback = db.Column(db.Text)  # Written feedback/comment (komentt)
    created_at = db.Column(db.DateTime, server_default=db.func.now())  # Timestamp (samay)
    booking = db.relationship("Booking", backref="ratings")  # Link to booking
    rater = db.relationship("User", foreign_keys=[rater_id], backref="ratings_given")  # Rater relationship
    rated = db.relationship("User", foreign_keys=[rated_id], backref="ratings_received")  # Rated person relationship


class SiteFeedback(db.Model):  # Site feedback model - website experience feedback (website ko feedback)
    """Website experience feedback from users and drivers"""

    id = db.Column(db.Integer, primary_key=True)  # Unique feedback identifier
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)  # Related booking
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # Feedback author (feedback dene wala)
    author_role = db.Column(db.String(20))  # Author type - user or driver
    rating = db.Column(db.Integer, nullable=False)  # Website rating - 1 to 5
    feedback = db.Column(db.Text)  # Feedback text/comment (komentt)
    created_at = db.Column(db.DateTime, server_default=db.func.now())  # Timestamp (samay)
    booking = db.relationship("Booking", backref="site_feedbacks")  # Link to booking
    author = db.relationship("User", backref="site_feedbacks")  # Link to feedback author
