from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify  # Flask ko tools - pages, forms, redirects
from flask_login import login_required, current_user  # Login check - user logged in hona chaiye
from models import db, Booking  # Database aur Booking model
import math  # Math calculations - distance calculate garna ko
from pricing_module import predict_price  # ML pricing model
import json
import urllib.request

booking_bp = Blueprint("booking", __name__)  # Booking routes blueprint - booking ko sab routes


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points (lat/lng) in kilometers."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

# TRUCKBID-inspired Kathmandu distance mapping - actual distances between areas
KATHMANDU_DISTANCES = {
    # Central to Central areas
    ("New Road", "Asan"): 1.2,
    ("New Road", "Baneshwor"): 3.5,
    ("New Road", "Koteshwor"): 6.2,
    ("New Road", "Patan"): 4.8,
    ("New Road", "Bhaktapur"): 12.7,
    ("New Road", "Kalanki"): 5.8,
    ("Baneshwor", "Koteshwor"): 2.8,
    ("Baneshwor", "Patan"): 8.3,
    ("Koteshwor", "Bhaktapur"): 17.3,
    ("Koteshwor", "Kalanki"): 1.9,
    ("Koteshwor", "Chabahil"): 6.2,
    ("Patan", "Bhaktapur"): 8.9,
    ("Patan", "Kalanki"): 12.8,
    ("Patan", "Kirtipur"): 3.5,
    ("Kalanki", "Swayambhu"): 5.8,
    ("Swayambhu", "Chabahil"): 2.9,
    ("Chabahil", "Gaushala"): 1.5,
}

# TRUCKBID vehicle rates - based on actual Kathmandu prices
VEHICLE_RATES = {
    "small_vehicle": {"rate_per_km": 18, "min_charge": 400, "max_price": 1500},      # Tempo/Small van
    "medium_vehicle": {"rate_per_km": 25, "min_charge": 700, "max_price": 2500},    # Medium truck
    "large_vehicle": {"rate_per_km": 35, "min_charge": 1200, "max_price": 4000},    # Large truck
}

# Traffic multipliers - TRUCKBID system
TRAFFIC_MULTIPLIERS = {
    "light": 1.0,
    "medium": 1.1,
    "heavy": 1.3,
    "very_heavy": 1.5
}

# Traffic zones (aligned with frontend map zones)
TRAFFIC_ZONES = [
    {"name": "Kalanki", "coords": (27.6936, 85.2776), "base": "heavy", "radius_m": 750},
    {"name": "Koteshwor", "coords": (27.6785, 85.3497), "base": "heavy", "radius_m": 750},
    {"name": "Baneshwor", "coords": (27.6895, 85.3420), "base": "heavy", "radius_m": 750},
    {"name": "Gongabu", "coords": (27.7316, 85.3146), "base": "heavy", "radius_m": 750},
    {"name": "Balkhu", "coords": (27.6890, 85.2972), "base": "heavy", "radius_m": 750},
    {"name": "New Road", "coords": (27.7290, 85.3157), "base": "heavy", "radius_m": 750},
    {"name": "Ring Road", "coords": (27.7050, 85.3210), "base": "medium", "radius_m": 600},
    {"name": "Balaju", "coords": (27.7352, 85.3068), "base": "medium", "radius_m": 600},
    {"name": "Chabahil", "coords": (27.7175, 85.3473), "base": "medium", "radius_m": 600},
    {"name": "Lagankhel", "coords": (27.6660, 85.3266), "base": "medium", "radius_m": 600},
    {"name": "Thamel", "coords": (27.7156, 85.3123), "base": "medium", "radius_m": 600},
    {"name": "Patan", "coords": (27.6560, 85.3161), "base": "medium", "radius_m": 600},
    {"name": "Kirtipur", "coords": (27.6355, 85.2927), "base": "medium", "radius_m": 600},
]

# Peak hour surcharge
PEAK_HOUR_MULTIPLIER = 1.2
NIGHT_DISCOUNT = 0.9


@booking_bp.route("/book", methods=["GET", "POST"])  # Book route - GET: form dikhane ko, POST: booking garna ko
@login_required  # User login hona chaiye
def book():  # Booking function - safar book garna ko
    if request.method == "POST":  # Form submit bhayo
        origin = request.form.get("origin", "")  # Shuru ki jagah - kaha se start
        destination = request.form.get("destination", "")  # Destination - kaha tak jana
        date = request.form.get("date")  # Date - kaun din
        time_of_day = request.form.get("time_of_day")  # Time - kaun samay
        origin_lat = request.form.get("origin_lat")  # Starting latitude - map location
        origin_lng = request.form.get("origin_lng")  # Starting longitude - map location
        dest_lat = request.form.get("dest_lat")  # Destination latitude - map location
        dest_lng = request.form.get("dest_lng")  # Destination longitude - map location
        vehicle_type = request.form.get("vehicle_type", "medium_vehicle")  # Vehicle category - small/medium/large
        traffic_level_override = request.form.get("traffic_level_override")
        traffic_multiplier_override = request.form.get("traffic_multiplier_override")
        
        # DEBUG: Log form data
        import sys
        print(f"\n[DEBUG FORM] Origin: {origin}, Dest: {destination}", file=sys.stderr)
        print(f"[DEBUG FORM] Lats: {origin_lat} → {dest_lat}, Lngs: {origin_lng} → {dest_lng}", file=sys.stderr)
        print(f"[DEBUG FORM] Vehicle: {vehicle_type}, Time: {time_of_day}", file=sys.stderr)

        def osrm_route_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float | None:
            """Get road distance from OSRM (public) in kilometers."""
            try:
                url = (
                    "https://router.project-osrm.org/route/v1/driving/"
                    f"{lng1},{lat1};{lng2},{lat2}?overview=false"
                )
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                routes = data.get("routes") or []
                if not routes:
                    return None
                distance_m = routes[0].get("distance")
                if distance_m is None:
                    return None
                return float(distance_m) / 1000.0
            except Exception:
                return None

        def get_distance_from_map(origin: str | None, destination: str | None, origin_lat: str | None, origin_lng: str | None, dest_lat: str | None, dest_lng: str | None) -> float | None:
            """Get distance from map using OSRM route distance (road path)."""
            try:
                if origin_lat and origin_lng and dest_lat and dest_lng:
                    lat1, lng1 = float(origin_lat), float(origin_lng)
                    lat2, lng2 = float(dest_lat), float(dest_lng)
                    return osrm_route_km(lat1, lng1, lat2, lng2)
            except Exception:
                pass
            return None

        def suggest_traffic_level(time_str: str | None) -> str:  # Traffic level by time - samay ko base par traffic
            """Infer traffic level from Kathmandu time bands - TRUCKBID system."""
            if not time_str:  # Ager time nai nai de
                return "medium"  # Default medium traffic
            try:  # Time ko parsing try gara
                hours, minutes = [int(x) for x in time_str.split(":")]  # Hour aur minute separate gara
                total_minutes = hours * 60 + minutes  # Total minutes nikalo
            except Exception:  # Error aye parsing ma
                return "medium"  # Default medium return gara

            # Peak hours: 8-10:30 AM, 4:30-7:30 PM
            if (8 * 60 <= total_minutes <= 10 * 60 + 30) or (16 * 60 + 30 <= total_minutes <= 19 * 60 + 30):
                return "heavy"  # Heavy traffic during peak
            # Mid-day: 11 AM - 3:30 PM
            if 11 * 60 <= total_minutes <= 15 * 60 + 30:
                return "medium"  # Medium traffic
            # Night: 8 PM - 6 AM
            if 20 * 60 <= total_minutes or total_minutes < 6 * 60:
                return "light"  # Light traffic at night
            return "light"  # Otherwise light traffic

        def zone_traffic_level(address: str | None) -> str:
            """Fallback zone-based traffic from address keywords."""
            if not address:
                return "medium"
            addr = address.lower()
            heavy_keywords = [
                "kalanki", "koteshwor", "baneshwor", "gongabu", "balkhu", "new road",
            ]
            medium_keywords = [
                "ring road", "balaju", "chabahil", "lagankhel", "kirtipur", "thamel", "patan",
            ]
            if any(k in addr for k in heavy_keywords):
                return "heavy"
            if any(k in addr for k in medium_keywords):
                return "medium"
            return "light"

        def zone_traffic_level_from_coords(lat: str | None, lng: str | None) -> str | None:
            """Zone traffic from coordinates using configured zones."""
            try:
                if not lat or not lng:
                    return None
                lat_f, lng_f = float(lat), float(lng)
                level_order = {"light": 1, "medium": 2, "heavy": 3}
                best_level = None
                best_rank = 0
                for zone in TRAFFIC_ZONES:
                    zlat, zlng = zone["coords"]
                    distance_m = haversine_km(lat_f, lng_f, zlat, zlng) * 1000
                    if distance_m <= zone["radius_m"]:
                        rank = level_order.get(zone["base"], 0)
                        if rank > best_rank:
                            best_rank = rank
                            best_level = zone["base"]
                return best_level
            except Exception:
                return None

        def map_vehicle_category(vehicle_type: str | None) -> str:
            """Map vehicle form value to ML model category - vehicle type map gara"""
            mapping = {
                "small_vehicle": "SMALL",
                "medium_vehicle": "MEDIUM",
                "large_vehicle": "LARGE"
            }
            return mapping.get(vehicle_type, "MEDIUM") if vehicle_type else "MEDIUM"  # type: ignore[arg-type]

        def map_traffic_level(traffic_level):
            """Map traffic level to ML model format - traffic level ML ko format ma convert gara"""
            mapping = {
                "light": "Light",
                "medium": "Medium",
                "heavy": "Heavy",
                "very_heavy": "Very Heavy"
            }
            return mapping.get(traffic_level, "Medium")

        def get_time_period(time_str: str | None) -> str:
            """Convert HH:MM to time period for ML model - time ko HH:MM ko base par period nikalo"""
            try:
                hours, minutes = [int(x) for x in time_str.split(":")] if time_str else (14, 0)
            except:
                hours = 14
            
            if 5 <= hours < 12:
                return "Morning"
            elif 12 <= hours < 17:
                return "Afternoon"
            elif 17 <= hours < 21:
                return "Evening"
            else:
                return "Night"

        def is_peak_hour(time_str: str | None) -> int:
            """Check if time is peak hour (6-9 AM or 5-8 PM) - peak hour cha ki nai check gara"""
            try:
                hours, minutes = [int(x) for x in time_str.split(":")] if time_str else (14, 0)
                total_minutes = hours * 60 + minutes
                return 1 if ((6 * 60 <= total_minutes <= 9 * 60) or (17 * 60 <= total_minutes <= 20 * 60)) else 0
            except:
                return 0

        # Get traffic levels
        time_level = suggest_traffic_level(time_of_day)
        origin_level = zone_traffic_level_from_coords(origin_lat, origin_lng) or zone_traffic_level(origin)
        dest_level = zone_traffic_level_from_coords(dest_lat, dest_lng) or zone_traffic_level(destination)

        level_order = {"light": 0, "medium": 1, "heavy": 2}
        if traffic_level_override in {"light", "medium", "heavy"}:
            chosen_level = traffic_level_override
        else:
            chosen_level = max(
                (origin_level, dest_level, time_level),
                key=lambda lv: level_order.get(lv, 1),
            )

        # Calculate distance from coordinates
        distance = get_distance_from_map(origin, destination, origin_lat, origin_lng, dest_lat, dest_lng)
        if not distance:
            flash("Unable to calculate route distance. Please select locations again.", "warning")
            return redirect(url_for("booking.book"))
        
        # Calculate price using ML model from TRUCKBID-ACADEMIC
        truck_category = map_vehicle_category(vehicle_type)
        traffic_category = map_traffic_level(chosen_level)
        time_period = get_time_period(time_of_day)
        peak_hour = is_peak_hour(time_of_day)
        
        # DEBUG: Log all parameters before prediction
        import sys
        print(f"[DEBUG BOOKING] Distance: {distance} km", file=sys.stderr)
        print(f"[DEBUG BOOKING] Truck: {truck_category}, Traffic: {traffic_category}", file=sys.stderr)
        print(f"[DEBUG BOOKING] Time: {time_period}, Peak: {peak_hour}", file=sys.stderr)
        
        price = predict_price(
            distance_km=distance,
            truck_category=truck_category,
            traffic_level=traffic_category,
            time_of_day=time_period,
            is_peak_hour=peak_hour
        )
        
        print(f"[DEBUG BOOKING] Predicted Price: Rs{price}", file=sys.stderr)
        
        # For display purposes, calculate traffic multiplier based on chosen level
        try:
            traffic_multiplier = float(traffic_multiplier_override) if traffic_multiplier_override else None
        except Exception:
            traffic_multiplier = None
        if not traffic_multiplier:
            traffic_multiplier = TRAFFIC_MULTIPLIERS.get(chosen_level, 1.1)

        payment_method = request.form.get("payment_method", "cash")
        payment_by = request.form.get("payment_by", "sender")

        booking = Booking(
            user_id=current_user.id,
            origin=origin,
            origin_lat=float(origin_lat) if origin_lat else None,
            origin_lng=float(origin_lng) if origin_lng else None,
            destination=destination,
            dest_lat=float(dest_lat) if dest_lat else None,
            dest_lng=float(dest_lng) if dest_lng else None,
            date=date,
            booking_time=time_of_day,
            price=price,
            traffic_level=chosen_level,
            traffic_multiplier=traffic_multiplier,
            payment_method=payment_method,
            payment_by=payment_by,
            payment_received=False,
        )
        db.session.add(booking)
        db.session.commit()
        flash(
            f"Booking created! ML-calculated price: Rs{price} ({chosen_level.title()} traffic, {traffic_multiplier}x multiplier)",
            "success",
        )
        return redirect(url_for("booking.booking_detail", booking_id=booking.id))

    origin = request.args.get("origin", "")
    destination = request.args.get("destination", "")
    origin_lat = request.args.get("origin_lat", "")
    origin_lng = request.args.get("origin_lng", "")
    dest_lat = request.args.get("dest_lat", "")
    dest_lng = request.args.get("dest_lng", "")
    ongoing_booking = (
        Booking.query.filter_by(user_id=current_user.id)
        .filter(Booking.status.in_(["arrived", "accepted", "in_transit"]))
        .order_by(Booking.created_at.desc())
        .first()
    )
    return render_template(
        "booking.html",
        origin=origin,
        destination=destination,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        vehicle_types=VEHICLE_RATES.keys(),
        ongoing_booking=ongoing_booking,
    )


@booking_bp.route("/api/price-estimate", methods=["POST"])
@login_required
def price_estimate():
    data = request.get_json(silent=True) or request.form
    origin = data.get("origin", "")
    destination = data.get("destination", "")
    origin_lat = data.get("origin_lat")
    origin_lng = data.get("origin_lng")
    dest_lat = data.get("dest_lat")
    dest_lng = data.get("dest_lng")
    vehicle_type = data.get("vehicle_type", "medium_vehicle")
    time_of_day = data.get("time_of_day")
    traffic_level_override = data.get("traffic_level_override")
    traffic_multiplier_override = data.get("traffic_multiplier_override")

    def osrm_route_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float | None:
        try:
            url = (
                "https://router.project-osrm.org/route/v1/driving/"
                f"{lng1},{lat1};{lng2},{lat2}?overview=false"
            )
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            routes = data.get("routes") or []
            if not routes:
                return None
            distance_m = routes[0].get("distance")
            if distance_m is None:
                return None
            return float(distance_m) / 1000.0
        except Exception:
            return None

    def get_distance_from_map(origin_lat: str | None, origin_lng: str | None, dest_lat: str | None, dest_lng: str | None) -> float | None:
        try:
            if origin_lat and origin_lng and dest_lat and dest_lng:
                lat1, lng1 = float(origin_lat), float(origin_lng)
                lat2, lng2 = float(dest_lat), float(dest_lng)
                return osrm_route_km(lat1, lng1, lat2, lng2)
        except Exception:
            pass
        return None

    def suggest_traffic_level(time_str: str | None) -> str:
        if not time_str:
            return "medium"
        try:
            hours, minutes = [int(x) for x in time_str.split(":")]
            total_minutes = hours * 60 + minutes
        except Exception:
            return "medium"
        if (8 * 60 <= total_minutes <= 10 * 60 + 30) or (16 * 60 + 30 <= total_minutes <= 19 * 60 + 30):
            return "heavy"
        if 11 * 60 <= total_minutes <= 15 * 60 + 30:
            return "medium"
        if 20 * 60 <= total_minutes or total_minutes < 6 * 60:
            return "light"
        return "light"

    def zone_traffic_level(address: str | None) -> str:
        if not address:
            return "medium"
        addr = address.lower()
        heavy_keywords = [
            "kalanki", "koteshwor", "baneshwor", "gongabu", "balkhu", "new road",
        ]
        medium_keywords = [
            "ring road", "balaju", "chabahil", "lagankhel", "kirtipur", "thamel", "patan",
        ]
        if any(k in addr for k in heavy_keywords):
            return "heavy"
        if any(k in addr for k in medium_keywords):
            return "medium"
        return "light"

    def zone_traffic_level_from_coords(lat: str | None, lng: str | None) -> str | None:
        try:
            if not lat or not lng:
                return None
            lat_f, lng_f = float(lat), float(lng)
            level_order = {"light": 1, "medium": 2, "heavy": 3}
            best_level = None
            best_rank = 0
            for zone in TRAFFIC_ZONES:
                zlat, zlng = zone["coords"]
                distance_m = haversine_km(lat_f, lng_f, zlat, zlng) * 1000
                if distance_m <= zone["radius_m"]:
                    rank = level_order.get(zone["base"], 0)
                    if rank > best_rank:
                        best_rank = rank
                        best_level = zone["base"]
            return best_level
        except Exception:
            return None

    def map_vehicle_category(vehicle_type: str | None) -> str:
        mapping = {
            "small_vehicle": "SMALL",
            "medium_vehicle": "MEDIUM",
            "large_vehicle": "LARGE"
        }
        return mapping.get(vehicle_type, "MEDIUM") if vehicle_type else "MEDIUM"

    def map_traffic_level(traffic_level: str) -> str:
        mapping = {
            "light": "Light",
            "medium": "Medium",
            "heavy": "Heavy",
            "very_heavy": "Very Heavy"
        }
        return mapping.get(traffic_level, "Medium")

    def get_time_period(time_str: str | None) -> str:
        try:
            hours, minutes = [int(x) for x in time_str.split(":")] if time_str else (14, 0)
        except Exception:
            hours = 14
        if 5 <= hours < 12:
            return "Morning"
        if 12 <= hours < 17:
            return "Afternoon"
        if 17 <= hours < 21:
            return "Evening"
        return "Night"

    def is_peak_hour(time_str: str | None) -> int:
        try:
            hours, minutes = [int(x) for x in time_str.split(":")] if time_str else (14, 0)
            total_minutes = hours * 60 + minutes
            return 1 if ((6 * 60 <= total_minutes <= 9 * 60) or (17 * 60 <= total_minutes <= 20 * 60)) else 0
        except Exception:
            return 0

    time_level = suggest_traffic_level(time_of_day)
    origin_level = zone_traffic_level_from_coords(origin_lat, origin_lng) or zone_traffic_level(origin)
    dest_level = zone_traffic_level_from_coords(dest_lat, dest_lng) or zone_traffic_level(destination)

    level_order = {"light": 0, "medium": 1, "heavy": 2}
    if traffic_level_override in {"light", "medium", "heavy"}:
        chosen_level = traffic_level_override
    else:
        chosen_level = max(
            (origin_level, dest_level, time_level),
            key=lambda lv: level_order.get(lv, 1),
        )

    distance_override = data.get("distance_km")
    try:
        distance_override = float(distance_override) if distance_override is not None else None
    except Exception:
        distance_override = None

    distance = distance_override or get_distance_from_map(origin_lat, origin_lng, dest_lat, dest_lng)
    if not distance:
        return jsonify({"error": "Unable to calculate route distance"}), 400

    truck_category = map_vehicle_category(vehicle_type)
    traffic_category = map_traffic_level(chosen_level)
    time_period = get_time_period(time_of_day)
    peak_hour = is_peak_hour(time_of_day)

    price = predict_price(
        distance_km=distance,
        truck_category=truck_category,
        traffic_level=traffic_category,
        time_of_day=time_period,
        is_peak_hour=peak_hour
    )

    try:
        traffic_multiplier = float(traffic_multiplier_override) if traffic_multiplier_override else None
    except Exception:
        traffic_multiplier = None
    if not traffic_multiplier:
        traffic_multiplier = TRAFFIC_MULTIPLIERS.get(chosen_level, 1.1)

    return jsonify({
        "price": int(price),
        "distance_km": float(distance),
        "traffic_level": chosen_level,
        "traffic_multiplier": float(traffic_multiplier),
        "time_level": time_level,
        "origin_zone": origin_level,
        "dest_zone": dest_level,
    })


@booking_bp.route("/booking/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash("Not authorized to cancel this booking.", "danger")
        return redirect(url_for("main.profile"))
    if booking.status in ("cancelled", "finished"):
        flash("Booking cannot be canceled.", "warning")
        return redirect(url_for("main.profile"))
    booking.status = "cancelled"
    db.session.commit()
    flash("Booking canceled.", "info")
    return redirect(url_for("main.profile"))


@booking_bp.route("/booking/<int:booking_id>")
@login_required
def booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and booking.driver_id != current_user.id and current_user.role != "admin":
        flash("Not authorized to view this booking.", "danger")
        return redirect(url_for("main.profile"))
    return render_template("booking_detail.html", booking=booking)


@booking_bp.route("/booking/<int:booking_id>/mark-delivered", methods=["POST"])
@login_required
def mark_delivered(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role != "admin":
        flash("Not authorized to update this booking.", "danger")
        return redirect(url_for("main.profile"))
    booking.status = "delivered"
    booking.delivered_at = db.func.now()
    db.session.commit()
    flash("✅ Driver has reached the destination.", "success")
    return redirect(url_for("booking.booking_detail", booking_id=booking.id))
