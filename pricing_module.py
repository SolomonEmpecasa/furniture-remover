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
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
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
    
    # Prepare feature array
    features = np.array([[distance_km, truck_encoded, traffic_encoded, time_encoded, is_peak_hour]])
    
    # Make prediction
    predicted_price = float(_model.predict(features)[0])
    
    # Apply min/max charges
    min_charges = {'SMALL': 400, 'MEDIUM': 700, 'LARGE': 1200}
    max_prices = {'SMALL': 1500, 'MEDIUM': 2500, 'LARGE': 4000}
    
    min_charge = min_charges.get(truck_cat, 700)
    max_price = max_prices.get(truck_cat, 2500)
    
    final_price = max(predicted_price, min_charge)
    final_price = min(final_price, max_price)
    
    return int(round(final_price))
