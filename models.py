from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(32))
    age = db.Column(db.Integer)
    profile_pic = db.Column(db.String(255))
    role = db.Column(db.String(20), default="user")
    driver_status = db.Column(db.String(20))
    driver_feedback = db.Column(db.Text)
    vehicle_name = db.Column(db.String(120))
    vehicle_brand = db.Column(db.String(120))
    vehicle_plate = db.Column(db.String(64))
    driver_license_path = db.Column(db.String(255))
    driver_bluebook_path = db.Column(db.String(255))
    driver_photo_path = db.Column(db.String(255))
    vehicle_info = db.Column(db.String(255))
    driver_available = db.Column(db.Boolean, default=False)
    bookings = db.relationship(
        "Booking", back_populates="user", foreign_keys="Booking.user_id", lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_average_rating(self):
        """Calculate average rating for this user from all ratings received"""
        ratings = Rating.query.filter_by(rated_id=self.id).all()
        if not ratings:
            return 0
        return sum(r.rating for r in ratings) / len(ratings)

    def get_total_ratings(self):
        """Get total number of ratings received"""
        return Rating.query.filter_by(rated_id=self.id).count()


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id], back_populates="bookings")
    origin = db.Column(db.String(255))
    origin_lat = db.Column(db.Float)
    origin_lng = db.Column(db.Float)
    destination = db.Column(db.String(255))
    dest_lat = db.Column(db.Float)
    dest_lng = db.Column(db.Float)
    date = db.Column(db.String(40))
    price = db.Column(db.Integer)
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    driver = db.relationship("User", foreign_keys=[driver_id], backref="assigned_bookings")
    status = db.Column(db.String(40), default="pending")
    delivered_at = db.Column(db.DateTime)
    distance_km = db.Column(db.Float)
    route_geojson = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    payment_method = db.Column(db.String(20), default="cash")
    payment_by = db.Column(db.String(20), default="sender")
    payment_received = db.Column(db.Boolean, default=False)
    traffic_level = db.Column(db.String(20))
    traffic_multiplier = db.Column(db.Float)
    booking_time = db.Column(db.String(16))
    user_rating = db.Column(db.Integer)
    user_feedback = db.Column(db.Text)
    driver_rating = db.Column(db.Integer)
    driver_feedback = db.Column(db.Text)
    user_rated_at = db.Column(db.DateTime)
    driver_rated_at = db.Column(db.DateTime)


class Rating(db.Model):
    """Store ratings for users and drivers to track overall performance"""

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rated_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    booking = db.relationship("Booking", backref="ratings")
    rater = db.relationship("User", foreign_keys=[rater_id], backref="ratings_given")
    rated = db.relationship("User", foreign_keys=[rated_id], backref="ratings_received")


class SiteFeedback(db.Model):
    """Website experience feedback from users and drivers"""

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author_role = db.Column(db.String(20))
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    booking = db.relationship("Booking", backref="site_feedbacks")
    author = db.relationship("User", backref="site_feedbacks")
