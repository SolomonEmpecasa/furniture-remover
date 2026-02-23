from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, User, Booking
from functools import wraps
from statistics import mean, median

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required", "danger")
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)

    return wrapped


@admin_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    prices = [b.price for b in bookings if b.price is not None]
    distances = [b.distance_km for b in bookings if b.distance_km]
    price_per_km = [
        (b.price / b.distance_km)
        for b in bookings
        if b.price is not None and b.distance_km
    ]

    def time_band(time_str: str | None) -> str:
        if not time_str:
            return "Unknown"
        try:
            hours, minutes = [int(x) for x in time_str.split(":")]
            total_minutes = hours * 60 + minutes
        except Exception:
            return "Unknown"
        if 5 * 60 <= total_minutes < 12 * 60:
            return "Morning"
        if 12 * 60 <= total_minutes < 17 * 60:
            return "Afternoon"
        if 17 * 60 <= total_minutes < 21 * 60:
            return "Evening"
        return "Night"

    def is_peak_hour(time_str: str | None) -> bool:
        if not time_str:
            return False
        try:
            hours, minutes = [int(x) for x in time_str.split(":")]
            total_minutes = hours * 60 + minutes
        except Exception:
            return False
        return (6 * 60 <= total_minutes <= 9 * 60) or (17 * 60 <= total_minutes <= 20 * 60)

    traffic_price_map: dict[str, list[float]] = {}
    traffic_count_map: dict[str, int] = {}
    time_price_map: dict[str, list[float]] = {}
    peak_prices: list[float] = []
    offpeak_prices: list[float] = []
    for b in bookings:
        if b.price is None:
            continue
        if b.traffic_level:
            key = b.traffic_level.title().replace("_", " ")
            traffic_price_map.setdefault(key, []).append(b.price)
            traffic_count_map[key] = traffic_count_map.get(key, 0) + 1
        band = time_band(b.booking_time)
        time_price_map.setdefault(band, []).append(b.price)
        if is_peak_hour(b.booking_time):
            peak_prices.append(b.price)
        else:
            offpeak_prices.append(b.price)

    price_buckets = [
        {"label": "Under 1,000", "min": 0, "max": 1000, "count": 0},
        {"label": "1,000-1,500", "min": 1000, "max": 1500, "count": 0},
        {"label": "1,500-2,000", "min": 1500, "max": 2000, "count": 0},
        {"label": "Over 2,000", "min": 2000, "max": None, "count": 0},
    ]
    for price in prices:
        placed = False
        for bucket in price_buckets:
            if bucket["max"] is None:
                bucket["count"] += 1
                placed = True
                break
            if bucket["min"] <= price < bucket["max"]:
                bucket["count"] += 1
                placed = True
                break
        if not placed:
            price_buckets[-1]["count"] += 1

    peak_avg = round(mean(peak_prices), 2) if peak_prices else None
    offpeak_avg = round(mean(offpeak_prices), 2) if offpeak_prices else None
    if peak_avg is not None and offpeak_avg:
        peak_premium = round(((peak_avg - offpeak_avg) / offpeak_avg) * 100, 1)
    else:
        peak_premium = None

    pricing_stats = {
        "total_bookings": len(bookings),
        "avg_price": round(mean(prices), 2) if prices else None,
        "median_price": round(median(prices), 2) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_distance": round(mean(distances), 2) if distances else None,
        "avg_price_per_km": round(mean(price_per_km), 2) if price_per_km else None,
        "traffic_avg": {k: round(mean(v), 2) for k, v in traffic_price_map.items()},
        "traffic_counts": traffic_count_map,
        "time_avg": {k: round(mean(v), 2) for k, v in time_price_map.items()},
        "peak_avg": peak_avg,
        "offpeak_avg": offpeak_avg,
        "peak_premium": peak_premium,
        "price_buckets": price_buckets,
    }

    return render_template(
        "admin_dashboard.html",
        users=users,
        bookings=bookings,
        pricing_stats=pricing_stats,
    )


@admin_bp.route("/admin/set-role", methods=["POST"])
@login_required
@admin_required
def admin_set_role():
    for user in User.query.all():
        field = f"role_{user.id}"
        if field in request.form:
            new_role = request.form.get(field)
            if new_role != user.role:
                user.role = new_role
                if new_role == "driver":
                    user.driver_status = "approved"
                    user.driver_available = True
                elif new_role != "driver":
                    user.driver_available = False
    db.session.commit()
    flash("Roles updated.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/driver-applications/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def admin_driver_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.role = "driver"
    user.driver_status = "approved"
    user.driver_available = True
    user.driver_feedback = request.form.get("feedback")
    db.session.commit()
    flash(f"Driver {user.username} approved.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/driver-applications/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_driver_reject(user_id):
    user = User.query.get_or_404(user_id)
    user.role = "user"
    user.driver_status = "rejected"
    user.driver_available = False
    user.driver_feedback = request.form.get("feedback") or "No feedback provided."
    db.session.commit()
    flash(f"Driver application for {user.username} rejected.", "warning")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/clear-orders", methods=["POST"])
@login_required
@admin_required
def clear_orders():
    Booking.query.delete()
    db.session.commit()
    flash("All orders cleared successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))
