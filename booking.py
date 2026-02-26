from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import Booking, db
import pricing_module as pm
import math

booking_bp = Blueprint("booking", __name__)


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return max(R * c, 1.0)


def _to_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_distance(origin_lat, origin_lng, dest_lat, dest_lng, distance_km):
    if distance_km is not None:
        try:
            return float(distance_km)
        except Exception:
            return 1.0
    if origin_lat and origin_lng and dest_lat and dest_lng:
        return _haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    return 1.0


def _is_peak_hour(time_of_day):
    if isinstance(time_of_day, str) and ":" in time_of_day:
        try:
            h = int(time_of_day.split(":")[0])
            return (8 <= h <= 10) or (16 <= h <= 19)
        except Exception:
            return False
    return False


def _parse_distances(raw_value):
    if not raw_value:
        return [2.0, 5.0, 8.0, 12.0, 15.0]

    parsed = []
    for item in str(raw_value).split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = round(float(item), 2)
            if value > 0:
                parsed.append(value)
        except (TypeError, ValueError):
            continue

    if not parsed:
        return [2.0, 5.0, 8.0, 12.0, 15.0]

    return sorted(set(parsed))


@booking_bp.route("/book", methods=["GET", "POST"])
@login_required
def book():
    if request.method == "POST":
        form = request.form
        origin = form.get("origin", "")
        destination = form.get("destination", "")
        origin_lat = _to_float(form.get("origin_lat"))
        origin_lng = _to_float(form.get("origin_lng"))
        dest_lat = _to_float(form.get("dest_lat"))
        dest_lng = _to_float(form.get("dest_lng"))
        distance_km = _compute_distance(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            form.get("distance_km"),
        )

        vehicle_type = form.get("vehicle_type", "medium_vehicle")
        time_of_day = form.get("time_of_day", "14:00")
        traffic_override = form.get("traffic_level_override")
        traffic_multiplier = form.get("traffic_multiplier_override")

        is_peak = 1 if _is_peak_hour(time_of_day) else 0

        traffic_level = traffic_override or "medium"
        price_details = pm.estimate_price_details(
            distance_km,
            vehicle_type,
            traffic_level,
            time_of_day,
            is_peak,
        )
        price = int(round(price_details.get("final_price", 0)))

        booking = Booking(
            user_id=current_user.id,
            origin=origin,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            destination=destination,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            date=form.get("date"),
            price=price,
            distance_km=distance_km,
            traffic_level=traffic_level,
            traffic_multiplier=float(traffic_multiplier) if traffic_multiplier else None,
            booking_time=time_of_day,
            payment_method=form.get("payment_method"),
            payment_by=form.get("payment_by"),
        )

        db.session.add(booking)
        db.session.commit()
        return redirect(url_for("booking.booking_detail", booking_id=booking.id))

    return render_template("booking.html", ongoing_booking=None)


@booking_bp.route("/booking/<int:booking_id>")
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template("booking_detail.html", booking=booking)


@booking_bp.route("/price-distance")
@login_required
def price_distance_comparison():
    vehicle_type = request.args.get("vehicle_type", "medium_vehicle")
    traffic_level = request.args.get("traffic_level", "medium")
    time_of_day = request.args.get("time_of_day", "14:00")
    distances = _parse_distances(request.args.get("distances"))

    is_peak = 1 if _is_peak_hour(time_of_day) else 0

    raw_prices = []
    for distance in distances:
        raw_price = round(
            float(
                pm.predict_price(
                    distance,
                    vehicle_type,
                    traffic_level,
                    time_of_day,
                    is_peak,
                )
            ),
            2,
        )
        raw_prices.append(raw_price)

    monotonic_prices = []
    running_max = None
    for price in raw_prices:
        if running_max is None:
            running_max = price
        else:
            running_max = max(running_max, price)
        monotonic_prices.append(running_max)

    comparisons = []
    previous_price = None
    for distance, price in zip(distances, monotonic_prices):
        change_from_previous = None
        if previous_price is not None:
            change_from_previous = round(price - previous_price, 2)

        comparisons.append(
            {
                "distance_km": distance,
                "price": price,
                "change_from_previous": change_from_previous,
            }
        )
        previous_price = price

    return render_template(
        "price_distance.html",
        comparisons=comparisons,
        vehicle_type=vehicle_type,
        traffic_level=traffic_level,
        time_of_day=time_of_day,
        distances=", ".join(str(d) for d in distances),
        is_peak=is_peak,
    )


@booking_bp.route("/api/price-estimate", methods=["POST"])
def api_price_estimate():
    data = request.get_json(force=True) or {}
    origin_lat = _to_float(data.get("origin_lat"))
    origin_lng = _to_float(data.get("origin_lng"))
    dest_lat = _to_float(data.get("dest_lat"))
    dest_lng = _to_float(data.get("dest_lng"))
    distance_km = _compute_distance(
        origin_lat,
        origin_lng,
        dest_lat,
        dest_lng,
        data.get("distance_km"),
    )

    vehicle_type = data.get("vehicle_type") or "medium_vehicle"
    time_of_day = data.get("time_of_day") or "14:00"
    traffic_override = data.get("traffic_level_override")
    traffic_multiplier = data.get("traffic_multiplier_override")
    traffic_level = traffic_override or "medium"

    is_peak = 1 if _is_peak_hour(time_of_day) else 0

    price_details = pm.estimate_price_details(
        distance_km,
        vehicle_type,
        traffic_level,
        time_of_day,
        is_peak,
    )
    breakdown = price_details.get("breakdown", {})

    resp = {
        "price": price_details.get("final_price"),
        "distance_km": float(distance_km),
        "traffic_level": traffic_level,
        "traffic_multiplier": float(traffic_multiplier) if traffic_multiplier else 1.0,
        "time_level": "peak" if is_peak else "off-peak",
        "origin_zone": data.get("origin_zone") or "unknown",
        "dest_zone": data.get("dest_zone") or "unknown",
        "price_breakdown": {
            "distance_fare": breakdown.get("distance_fare", 0),
            "fuel_maintenance": breakdown.get("fuel_maintenance", 0),
            "labor": breakdown.get("labor", 0),
            "service_fee": breakdown.get("service_fee", 0),
            "subtotal_before_multiplier": breakdown.get("subtotal_before_multiplier", 0),
            "traffic_factor": breakdown.get("traffic_factor", 1),
            "peak_factor": breakdown.get("peak_factor", 1),
            "time_factor": breakdown.get("time_factor", 1),
            "total_multiplier": breakdown.get("total_multiplier", 1),
            "deterministic_total": breakdown.get("deterministic_total", 0),
            "fair_floor": price_details.get("fair_floor", 0),
            "context_factor": price_details.get("context_factor", 1),
        },
    }

    return jsonify(resp)
