from flask import Blueprint, render_template  # Flask ka routes - web pages dikhane ko
from flask_login import login_required, current_user  # Login check - user login bhayeko check garna ko
from models import Booking, SiteFeedback  # Models import - database sanga data pauney

main_bp = Blueprint("main", __name__)  # Main blueprint - website ko main routes


@main_bp.route("/")  # Home page - website ko main page
def home():  # Home function
    feedbacks = (  # Website ko feedback
        SiteFeedback.query.order_by(SiteFeedback.created_at.desc()).limit(6).all()  # 6 latest feedbacks pauney - newest pehla
    )
    return render_template("home.html", site_feedbacks=feedbacks)  # Home page dikhauney feedbacks saha


@main_bp.route("/profile")  # User ko profile page
@login_required  # Login hona chaiye - user logged in hona chaiye
def profile():  # Profile function
    bookings = Booking.query.filter_by(user_id=current_user.id).all()  # Yo user ko sab bookings khojo
    return render_template("profile.html", bookings=bookings)  # Profile page dikhauney bookings saha


@main_bp.route("/vehicles")  # Vehicles listing page
def vehicles():  # Vehicles function
    return render_template("vehicles.html")  # Vehicles page dikhauney
