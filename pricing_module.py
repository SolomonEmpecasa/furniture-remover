"""
ML-based pricing module using TRUCKBID-ACADEMIC RandomForest model
Features: distance_km, truck_category, traffic_level, time_of_day, is_peak_hour
Target: accepted_price_npr (price in Nepali Rupees)

This module implements the exact same training and prediction logic from:
https://github.com/KushG-1/TRUCKBID-ACADEMIC
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import random
import warnings

warnings.filterwarnings('ignore')

# REALISTIC KATHMANDU PRICING CONSTANTS (from TRUCKBID data generator)
KTM_RATES = {
    "SMALL": {"rate": 18, "min": 400, "max": 1500},
    "MEDIUM": {"rate": 25, "min": 700, "max": 2500},
    "LARGE": {"rate": 35, "min": 1200, "max": 4000}
}

KATHMANDU_AREAS = [
    "Baneshwor", "Koteshwor", "New Road", "Patan", "Bhaktapur",
    "Kalanki", "Swayambhu", "Budhanilkantha", "Kirtipur", "Gaushala",
    "Chabahil", "Thamel", "Maharajgunj", "Lazimpat", "Dillibazar"
]

# Global model and encoders
_model = None
_label_encoders = None
_features = None

LABOR_COST = {
    "SMALL": 120.0,
    "MEDIUM": 180.0,
    "LARGE": 260.0,
}

SERVICE_FEE = {
    "SMALL": 80.0,
    "MEDIUM": 120.0,
    "LARGE": 160.0,
}

FUEL_MAINTENANCE_PER_KM = {
    "SMALL": 8.0,
    "MEDIUM": 12.0,
    "LARGE": 16.0,
}


def _get_runtime_factors(traffic_level, time_period, is_peak_hour):
    """Deterministic runtime multipliers for fair and explainable pricing."""
    traffic_multipliers = {
        "Light": 1.0,
        "Medium": 1.1,
        "Heavy": 1.25,
        "Very Heavy": 1.4,
    }
    traffic_factor = traffic_multipliers.get(traffic_level, 1.1)

    peak_factor = 1.15 if is_peak_hour else 1.0

    time_factor = 1.0
    if time_period == "Night":
        time_factor = 0.95

    return traffic_factor, peak_factor, time_factor


def _deterministic_price(distance_km, truck_cat, traffic_level, time_period, is_peak_hour):
    """Compute transparent baseline price that scales fairly with distance."""
    details = _deterministic_breakdown(
        distance_km=distance_km,
        truck_cat=truck_cat,
        traffic_level=traffic_level,
        time_period=time_period,
        is_peak_hour=is_peak_hour,
    )
    return float(details["deterministic_total"])


def _deterministic_breakdown(distance_km, truck_cat, traffic_level, time_period, is_peak_hour):
    """Return deterministic cost components and total before ML context adjustment."""
    distance = max(float(distance_km), 0.0)
    rate = KTM_RATES[truck_cat]["rate"]
    min_charge = KTM_RATES[truck_cat]["min"]
    max_charge = KTM_RATES[truck_cat]["max"]

    distance_fare = distance * rate
    fuel_maintenance = distance * FUEL_MAINTENANCE_PER_KM.get(truck_cat, 10.0)
    labor = LABOR_COST.get(truck_cat, 180.0)
    service_fee = SERVICE_FEE.get(truck_cat, 120.0)

    subtotal_before_multiplier = distance_fare + fuel_maintenance + labor + service_fee
    traffic_factor, peak_factor, time_factor = _get_runtime_factors(
        traffic_level, time_period, is_peak_hour
    )
    total_multiplier = traffic_factor * peak_factor * time_factor

    deterministic_total = subtotal_before_multiplier * total_multiplier
    deterministic_total = max(deterministic_total, min_charge)
    deterministic_total = min(deterministic_total, max_charge)

    return {
        "distance_fare": float(distance_fare),
        "fuel_maintenance": float(fuel_maintenance),
        "labor": float(labor),
        "service_fee": float(service_fee),
        "subtotal_before_multiplier": float(subtotal_before_multiplier),
        "traffic_factor": float(traffic_factor),
        "peak_factor": float(peak_factor),
        "time_factor": float(time_factor),
        "total_multiplier": float(total_multiplier),
        "deterministic_total": float(deterministic_total),
        "min_charge": float(min_charge),
        "max_charge": float(max_charge),
    }


def _distance_fairness_floor(distance_km, truck_cat):
    """Minimum fair total by distance so extra kilometers are not underpriced."""
    distance = max(float(distance_km), 0.0)
    min_charge = KTM_RATES[truck_cat]["min"]

    # Industry-friendly floor profile: fixed short-trip base + guaranteed per-km growth.
    base_km = 2.0
    base_total = min_charge
    per_km_floor = {
        "SMALL": 40.0,
        "MEDIUM": 60.0,
        "LARGE": 85.0,
    }
    extra_km = max(0.0, distance - base_km)
    floor_total = base_total + (extra_km * per_km_floor.get(truck_cat, 60.0))
    return float(min(floor_total, KTM_RATES[truck_cat]["max"]))

def _calculate_base_price(distance_km, truck_category):
    """Calculate realistic base price for Kathmandu"""
    rate = KTM_RATES[truck_category]["rate"]
    min_charge = KTM_RATES[truck_category]["min"]
    base_price = distance_km * rate
    if base_price < min_charge:
        base_price = min_charge
    return base_price

def _apply_kathmandu_factors(base_price, factors):
    """Apply Kathmandu-specific pricing factors"""
    adjusted = base_price
    
    # Traffic adjustments
    traffic_multipliers = {
        "Light": 1.0,
        "Medium": 1.1,
        "Heavy": 1.3,
        "Very Heavy": 1.5
    }
    traffic = factors.get('traffic_level', 'Medium')
    adjusted *= traffic_multipliers.get(traffic, 1.1)
    
    # Peak hour adjustment
    if factors.get('is_peak_hour', 0):
        adjusted *= 1.2
    
    # Time of day adjustments
    time_of_day = factors.get('time_of_day', 'Afternoon')
    if time_of_day == "Night":
        adjusted *= 0.9
    
    # Distance-based adjustment
    distance = factors.get('distance_km', 0)
    if distance > 15:
        adjusted *= 0.95
    
    # Add small randomness (±10%)
    adjusted *= random.uniform(0.9, 1.1)
    
    # Apply caps
    truck_category = factors.get('truck_category', 'MEDIUM')
    max_price = KTM_RATES[truck_category]["max"]
    if adjusted > max_price:
        adjusted = max_price
    
    return round(adjusted, 2)

def _generate_kathmandu_data(num_samples=500):
    """Generate Kathmandu dataset with REAL prices (from TRUCKBID)"""
    data = []
    
    for i in range(num_samples):
        pickup = random.choice(KATHMANDU_AREAS)
        delivery = random.choice([a for a in KATHMANDU_AREAS if a != pickup])
        
        # Realistic distance (1-20km)
        distance = round(random.uniform(1.5, 18.5), 1)
        
        # Truck distribution
        rand = random.random()
        if rand < 0.6:
            category = "SMALL"
        elif rand < 0.9:
            category = "MEDIUM"
        else:
            category = "LARGE"
        
        # Time of day
        time_options = ["Morning", "Afternoon", "Evening", "Night"]
        time_weights = [0.25, 0.35, 0.30, 0.10]
        time_of_day = random.choices(time_options, weights=time_weights)[0]
        
        # Peak hour
        is_peak = 1 if time_of_day in ["Morning", "Evening"] else 0
        
        # Traffic
        if random.random() > 0.7:
            traffic = random.choice(["Heavy", "Very Heavy"])
        elif is_peak:
            traffic = random.choice(["Heavy", "Very Heavy"])
        elif time_of_day == "Night":
            traffic = "Light"
        else:
            traffic = random.choice(["Light", "Medium"])
        
        # Calculate base price
        base_price = _calculate_base_price(distance, category)
        
        # Apply factors
        factors = {
            'traffic_level': traffic,
            'is_peak_hour': is_peak,
            'time_of_day': time_of_day,
            'distance_km': distance,
            'truck_category': category
        }
        final_price = _apply_kathmandu_factors(base_price, factors)
        
        # Validate price
        if final_price < KTM_RATES[category]["min"]:
            final_price = KTM_RATES[category]["min"]
        if final_price > KTM_RATES[category]["max"]:
            final_price = KTM_RATES[category]["max"]
        
        record = {
            'truck_category': category,
            'distance_km': distance,
            'traffic_level': traffic,
            'time_of_day': time_of_day,
            'is_peak_hour': is_peak,
            'accepted_price_npr': round(final_price, 2),
        }
        data.append(record)
    
    return pd.DataFrame(data)

def _train_pricing_model():
    """Train the RandomForest model (TRUCKBID-ACADEMIC structure)"""
    global _model, _label_encoders, _features
    
    # Generate training data
    df = _generate_kathmandu_data(500)
    
    # Define features and target
    _features = ['distance_km', 'truck_category', 'traffic_level', 'time_of_day', 'is_peak_hour']
    X = df[_features].copy()
    y = df['accepted_price_npr']
    
    # Encode categorical variables
    _label_encoders = {}
    categorical_cols = ['truck_category', 'traffic_level', 'time_of_day']
    
    for col in categorical_cols:
        le = LabelEncoder()
        X[col] = pd.Series(le.fit_transform(X[col]), index=X.index)
        _label_encoders[col] = le
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    _model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    _model.fit(X_train, y_train)
    
    return _model, _label_encoders, _features

def predict_price(distance_km, truck_category, traffic_level, time_of_day, is_peak_hour):
    """
    Predict price using TRUCKBID-ACADEMIC RandomForest model
    
    Args:
        distance_km: float - distance in kilometers
        truck_category: str - 'small_vehicle', 'medium_vehicle', or 'large_vehicle'
        traffic_level: str - 'light', 'medium', 'heavy', or 'very_heavy'
        time_of_day: str - 'Morning', 'Afternoon', 'Evening', 'Night'
        is_peak_hour: int - 1 if peak hour, 0 otherwise
    
    Returns:
        float - predicted price in Nepali Rupees
    """
    global _model, _label_encoders, _features
    
    # Initialize model if not already trained
    if _model is None:
        _model, _label_encoders, _features = _train_pricing_model()
    
    # Type assertion (Pylance)
    assert _label_encoders is not None, "Label encoders not initialized"
    assert _model is not None, "Model not initialized"
    assert _features is not None, "Features not initialized"
    
    # Map vehicle categories
    truck_map = {
        'small_vehicle': 'SMALL',
        'medium_vehicle': 'MEDIUM',
        'large_vehicle': 'LARGE'
    }
    truck_cat = truck_map.get(truck_category, 'MEDIUM')
    
    # Map traffic level
    traffic_map = {
        'light': 'Light',
        'medium': 'Medium',
        'heavy': 'Heavy',
        'very_heavy': 'Very Heavy'
    }
    traffic_lev = traffic_map.get(traffic_level, 'Medium')
    
    # Normalize time of day
    if isinstance(time_of_day, str) and ':' in time_of_day:
        hour = int(time_of_day.split(':')[0])
        if 5 <= hour < 12:
            time_period = 'Morning'
        elif 12 <= hour < 17:
            time_period = 'Afternoon'
        elif 17 <= hour < 20:
            time_period = 'Evening'
        else:
            time_period = 'Night'
    else:
        time_period = time_of_day if time_of_day in ['Morning', 'Afternoon', 'Evening', 'Night'] else 'Afternoon'
    
    # Encode features
    truck_encoded = _label_encoders['truck_category'].transform([truck_cat])[0]
    traffic_encoded = _label_encoders['traffic_level'].transform([traffic_lev])[0]
    time_encoded = _label_encoders['time_of_day'].transform([time_period])[0]
    
    details = estimate_price_details(
        distance_km=distance_km,
        truck_category=truck_category,
        traffic_level=traffic_level,
        time_of_day=time_of_day,
        is_peak_hour=is_peak_hour,
    )
    return int(round(details["final_price"]))


def estimate_price_details(distance_km, truck_category, traffic_level, time_of_day, is_peak_hour):
    """Return final price plus transparent pricing breakdown."""
    global _model, _label_encoders, _features

    if _model is None:
        _model, _label_encoders, _features = _train_pricing_model()

    assert _label_encoders is not None, "Label encoders not initialized"
    assert _model is not None, "Model not initialized"
    assert _features is not None, "Features not initialized"

    truck_map = {
        'small_vehicle': 'SMALL',
        'medium_vehicle': 'MEDIUM',
        'large_vehicle': 'LARGE'
    }
    truck_cat = truck_map.get(truck_category, 'MEDIUM')

    traffic_map = {
        'light': 'Light',
        'medium': 'Medium',
        'heavy': 'Heavy',
        'very_heavy': 'Very Heavy'
    }
    traffic_lev = traffic_map.get(traffic_level, 'Medium')

    if isinstance(time_of_day, str) and ':' in time_of_day:
        hour = int(time_of_day.split(':')[0])
        if 5 <= hour < 12:
            time_period = 'Morning'
        elif 12 <= hour < 17:
            time_period = 'Afternoon'
        elif 17 <= hour < 20:
            time_period = 'Evening'
        else:
            time_period = 'Night'
    else:
        time_period = time_of_day if time_of_day in ['Morning', 'Afternoon', 'Evening', 'Night'] else 'Afternoon'

    truck_encoded = _label_encoders['truck_category'].transform([truck_cat])[0]
    traffic_encoded = _label_encoders['traffic_level'].transform([traffic_lev])[0]
    time_encoded = _label_encoders['time_of_day'].transform([time_period])[0]

    # Deterministic baseline (fair distance scaling)
    breakdown = _deterministic_breakdown(
        distance_km=distance_km,
        truck_cat=truck_cat,
        traffic_level=traffic_lev,
        time_period=time_period,
        is_peak_hour=is_peak_hour,
    )
    deterministic = breakdown["deterministic_total"]

    # ML context factor at fixed reference distance to preserve monotonic distance behavior
    reference_distance = 5.0
    ref_features = np.array([[reference_distance, truck_encoded, traffic_encoded, time_encoded, is_peak_hour]])
    ml_ref = float(_model.predict(ref_features)[0])
    deterministic_ref = _deterministic_price(
        distance_km=reference_distance,
        truck_cat=truck_cat,
        traffic_level=traffic_lev,
        time_period=time_period,
        is_peak_hour=is_peak_hour,
    )

    if deterministic_ref > 0:
        context_factor = ml_ref / deterministic_ref
    else:
        context_factor = 1.0

    # Keep ML influence but prevent extreme distortions
    context_factor = float(np.clip(context_factor, 0.98, 1.08))
    hybrid_price = deterministic * context_factor

    fair_floor = _distance_fairness_floor(distance_km, truck_cat)

    min_charge = KTM_RATES[truck_cat]['min']
    max_price = KTM_RATES[truck_cat]['max']
    final_price = max(hybrid_price, fair_floor, min_charge)
    final_price = min(final_price, max_price)

    return {
        "final_price": float(round(final_price, 2)),
        "truck_category": truck_cat,
        "time_period": time_period,
        "traffic_level": traffic_lev,
        "context_factor": float(round(context_factor, 4)),
        "fair_floor": float(round(fair_floor, 2)),
        "breakdown": {
            "distance_fare": float(round(breakdown["distance_fare"], 2)),
            "fuel_maintenance": float(round(breakdown["fuel_maintenance"], 2)),
            "labor": float(round(breakdown["labor"], 2)),
            "service_fee": float(round(breakdown["service_fee"], 2)),
            "subtotal_before_multiplier": float(round(breakdown["subtotal_before_multiplier"], 2)),
            "traffic_factor": float(round(breakdown["traffic_factor"], 2)),
            "peak_factor": float(round(breakdown["peak_factor"], 2)),
            "time_factor": float(round(breakdown["time_factor"], 2)),
            "total_multiplier": float(round(breakdown["total_multiplier"], 4)),
            "deterministic_total": float(round(breakdown["deterministic_total"], 2)),
        },
    }
