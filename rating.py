from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Booking, Rating, SiteFeedback
from datetime import datetime

rating_bp = Blueprint("rating", __name__)


@rating_bp.route("/rate-driver/<int:booking_id>", methods=["GET", "POST"])
@login_required
def rate_driver(booking_id):
    """User rates the driver after delivery."""
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash("Not authorized to rate this booking.", "danger")
        return redirect(url_for("main.profile"))

    if booking.status != "delivered":
        flash("Can only rate completed deliveries.", "warning")
        return redirect(url_for("main.profile"))

    if booking.driver_rating:
        flash("You have already rated this driver.", "info")
        return redirect(url_for("main.profile"))

    if request.method == "POST":
        rating_value = request.form.get("rating", type=int)
        feedback_text = request.form.get("feedback", "").strip()
        site_rating_value = request.form.get("site_rating", type=int)
        site_feedback_text = request.form.get("site_feedback", "").strip()

        if not rating_value or rating_value < 1 or rating_value > 5:
            flash("Please provide a valid driver rating (1-5 stars).", "warning")
            return render_template("rate_driver.html", booking=booking)

        if not site_rating_value or site_rating_value < 1 or site_rating_value > 5:
            flash("Please rate the website (1-5 stars) so we can improve.", "warning")
            return render_template("rate_driver.html", booking=booking)

        booking.driver_rating = rating_value
        booking.driver_feedback = feedback_text
        booking.user_rated_at = datetime.utcnow()

        rating = Rating(
            booking_id=booking.id,
            rater_id=current_user.id,
            rated_id=booking.driver_id,
            rating=rating_value,
            feedback=feedback_text,
        )
        db.session.add(rating)

        existing_site_feedback = SiteFeedback.query.filter_by(
            booking_id=booking.id, author_id=current_user.id
        ).first()
        if existing_site_feedback:
            existing_site_feedback.rating = site_rating_value
            existing_site_feedback.feedback = site_feedback_text
            existing_site_feedback.author_role = current_user.role
        else:
            site_feedback = SiteFeedback(
                booking_id=booking.id,
                author_id=current_user.id,
                author_role=current_user.role,
                rating=site_rating_value,
                feedback=site_feedback_text,
            )
            db.session.add(site_feedback)

        db.session.commit()

        flash(
            "Thank you for rating your driver and sharing website feedback!", "success"
        )
        return redirect(url_for("main.profile"))

    return render_template("rate_driver.html", booking=booking)


@rating_bp.route("/rate-user/<int:booking_id>", methods=["GET", "POST"])
@login_required
def rate_user(booking_id):
    """Driver rates the user after delivery."""
    booking = Booking.query.get_or_404(booking_id)

    if booking.driver_id != current_user.id and current_user.role != "admin":
        flash("Not authorized to rate this booking.", "danger")
        return redirect(url_for("driver.driver_dashboard"))

    if booking.status != "delivered":
        flash("Can only rate completed deliveries.", "warning")
        return redirect(url_for("driver.driver_dashboard"))

    if booking.user_rating:
        flash("You have already rated this user.", "info")
        return redirect(url_for("driver.driver_dashboard"))

    if request.method == "POST":
        rating_value = int(request.form.get("rating", 0) or 0)
        feedback_text = request.form.get("feedback", "").strip()
        site_rating_value = int(request.form.get("site_rating", 0) or 0)
        site_feedback_text = request.form.get("site_feedback", "").strip()

        if not rating_value or rating_value < 1 or rating_value > 5:
            flash("Please provide a valid customer rating (1-5 stars).", "warning")
            return render_template("rate_user.html", booking=booking)

        if not site_rating_value or site_rating_value < 1 or site_rating_value > 5:
            flash("Please rate the website (1-5 stars) so we can improve.", "warning")
            return render_template("rate_user.html", booking=booking)

        booking.user_rating = rating_value
        booking.user_feedback = feedback_text
        booking.driver_rated_at = datetime.utcnow()

        rating = Rating(
            booking_id=booking.id,
            rater_id=current_user.id,
            rated_id=booking.user_id,
            rating=rating_value,
            feedback=feedback_text,
        )
        db.session.add(rating)

        existing_site_feedback = SiteFeedback.query.filter_by(
            booking_id=booking.id, author_id=current_user.id
        ).first()
        if existing_site_feedback:
            existing_site_feedback.rating = site_rating_value
            existing_site_feedback.feedback = site_feedback_text
            existing_site_feedback.author_role = current_user.role
        else:
            site_feedback = SiteFeedback(
                booking_id=booking.id,
                author_id=current_user.id,
                author_role=current_user.role,
                rating=site_rating_value,
                feedback=site_feedback_text,
            )
            db.session.add(site_feedback)

        db.session.commit()

        flash(
            "Thank you for rating your customer and sharing website feedback!",
            "success",
        )
        return redirect(url_for("driver.driver_dashboard"))

    return render_template("rate_user.html", booking=booking)


@rating_bp.route("/ratings/<int:user_id>")
@login_required
def view_ratings(user_id):
    """View all ratings for a specific user."""
    user = User.query.get_or_404(user_id)
    ratings = (
        Rating.query.filter_by(rated_id=user_id)
        .order_by(Rating.created_at.desc())
        .all()
    )
    avg_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0
    return render_template(
        "view_ratings.html", user=user, ratings=ratings, avg_rating=avg_rating
    )


@rating_bp.route("/api/user-stats/<int:user_id>")
@login_required
def user_stats(user_id):
    """API endpoint to get user/driver statistics."""
    user = User.query.get_or_404(user_id)
    ratings = Rating.query.filter_by(rated_id=user_id).all()
    avg_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0

    if user.role == "driver":
        total_deliveries = Booking.query.filter_by(
            driver_id=user_id, status="delivered"
        ).count()
    else:
        total_deliveries = Booking.query.filter_by(
            user_id=user_id, status="delivered"
        ).count()

    return jsonify(
        {
            "user_id": user_id,
            "username": user.username,
            "role": user.role,
            "avg_rating": round(avg_rating, 2),
            "total_ratings": len(ratings),
            "total_deliveries": total_deliveries,
        }
    )
