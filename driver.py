import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Booking
from functools import wraps

driver_bp = Blueprint("driver", __name__)


def driver_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "driver":
            flash("Driver access required", "danger")
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)

    return wrapped


def driver_or_admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in (
            "driver",
            "admin",
        ):
            flash("Driver access required", "danger")
            return redirect(url_for("main.home"))
        return f(*args, **kwargs)

    return wrapped


def _save_upload(file_storage, prefix):
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    upload_folder = os.path.join(os.path.dirname(__file__), "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    name, ext = os.path.splitext(filename)
    safe_name = f"{prefix}_{name}{ext}"
    dest = os.path.join(upload_folder, safe_name)
    file_storage.save(dest)
    return f"/static/uploads/{safe_name}"


@driver_bp.route("/driver")
@login_required
def driver_dashboard():
    if current_user.role == "admin":
        pending_bookings = Booking.query.filter_by(status="pending").all()
        accepted_bookings = Booking.query.filter(
            Booking.status.in_(["arrived", "accepted", "in_transit", "delivered"])
        ).all()
        return render_template(
            "driver_dashboard.html",
            bookings=pending_bookings,
            accepted_bookings=accepted_bookings,
            applicant_status=None,
            applicant_feedback=None,
        )

    if current_user.role == "driver":
        pending_bookings = Booking.query.filter_by(status="pending").all()
        accepted_bookings = Booking.query.filter(
            Booking.driver_id == current_user.id,
            Booking.status.in_(["arrived", "accepted", "in_transit", "delivered"]),
        ).all()
        return render_template(
            "driver_dashboard.html",
            bookings=pending_bookings,
            accepted_bookings=accepted_bookings,
            applicant_status="approved",
            applicant_feedback=None,
        )

    if current_user.driver_status in ("pending", "rejected"):
        return render_template(
            "driver_dashboard.html",
            bookings=[],
            accepted_bookings=[],
            applicant_status=current_user.driver_status,
            applicant_feedback=current_user.driver_feedback,
        )

    flash("Driver access required", "danger")
    return redirect(url_for("main.home"))


@driver_bp.route("/driver/reapply", methods=["POST"])
@login_required
def driver_reapply():
    if current_user.driver_status != "rejected":
        flash("Reapply is only available for rejected applications.", "warning")
        return redirect(url_for("driver.driver_dashboard"))

    current_user.vehicle_name = request.form.get("vehicle_name")
    current_user.vehicle_brand = request.form.get("vehicle_brand")
    current_user.vehicle_plate = request.form.get("vehicle_plate")
    current_user.driver_license_path = (
        _save_upload(
            request.files.get("driver_license"), f"license_{current_user.username}"
        )
        or current_user.driver_license_path
    )
    current_user.driver_bluebook_path = (
        _save_upload(
            request.files.get("driver_bluebook"), f"bluebook_{current_user.username}"
        )
        or current_user.driver_bluebook_path
    )
    current_user.driver_photo_path = (
        _save_upload(
            request.files.get("driver_photo"), f"driver_{current_user.username}"
        )
        or current_user.driver_photo_path
    )
    current_user.vehicle_info = f"{(current_user.vehicle_brand or '').strip()} {(current_user.vehicle_name or '').strip()}".strip()
    current_user.driver_status = "pending"
    current_user.driver_feedback = None
    current_user.role = "user"
    current_user.driver_available = False
    db.session.commit()
    flash("Reapplied. Await admin approval.", "info")
    return redirect(url_for("driver.driver_dashboard"))


@driver_bp.route("/driver/accept/<int:booking_id>", methods=["POST"])
@login_required
@driver_or_admin_required
def driver_accept(booking_id):
    b = Booking.query.get_or_404(booking_id)
    if b.status not in ("pending", "accepted", "arrived"):
        flash("Booking is already in progress or closed.", "warning")
        return redirect(url_for("driver.driver_dashboard"))

    b.driver_id = current_user.id
    b.status = "arrived"
    db.session.commit()
    flash("Booking accepted. You have arrived at pickup.", "success")
    return redirect(url_for("driver.view_journey", booking_id=b.id))


@driver_bp.route("/driver/start-journey/<int:booking_id>", methods=["POST"])
@login_required
@driver_or_admin_required
def start_journey(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.driver_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("driver.driver_dashboard"))
    if booking.status not in ("arrived", "accepted"):
        flash("Journey already started or completed.", "warning")
        return redirect(url_for("driver.driver_dashboard"))
    if booking.payment_method in ("on_delivery", "cash") and booking.payment_by == "sender":
        payment_received = request.form.get("payment_received") == "on"
        if not payment_received:
            flash("Please confirm pickup payment before starting the journey.", "warning")
            return redirect(url_for("driver.view_journey", booking_id=booking.id))
        booking.payment_received = True
    booking.status = "in_transit"
    db.session.commit()
    return redirect(url_for("driver.view_journey", booking_id=booking.id))


@driver_bp.route("/driver/view-journey/<int:booking_id>")
@login_required
@driver_or_admin_required
def view_journey(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.driver_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("driver.driver_dashboard"))
    return render_template("journey_simulation.html", booking=booking)


@driver_bp.route("/driver/mark-delivered/<int:booking_id>", methods=["POST"])
@login_required
@driver_or_admin_required
def mark_delivered(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.driver_id != current_user.id and current_user.role != "admin":
        flash("Not authorized", "danger")
        return redirect(url_for("driver.driver_dashboard"))
    if booking.payment_method in ("on_delivery", "cash") and booking.payment_by == "receiver":
        payment_received = request.form.get("payment_received") == "on"
        if not payment_received:
            flash("Please confirm payment received before marking delivered.", "warning")
            return redirect(url_for("driver.driver_dashboard"))
        booking.payment_received = True
    booking.status = "delivered"
    booking.delivered_at = db.func.now()
    db.session.commit()

    payment_msg = (
        f"Collect payment: {booking.price} NPR from {booking.payment_by}"
        if booking.payment_method == "on_delivery"
        else "Payment already received."
    )
    flash(f"Delivery marked as complete. {payment_msg}", "success")
    return redirect(url_for("driver.driver_dashboard"))
