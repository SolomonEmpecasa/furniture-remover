from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Booking, SiteFeedback

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    feedbacks = SiteFeedback.query.order_by(SiteFeedback.created_at.desc()).limit(6).all()
    return render_template("home.html", site_feedbacks=feedbacks)


@main_bp.route("/profile")
@login_required
def profile():
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    return render_template("profile.html", bookings=bookings)


@main_bp.route("/vehicles")
def vehicles():
    return render_template("vehicles.html")
