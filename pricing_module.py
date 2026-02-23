"""
ML-based pricing module for TRUCKBID using RandomForest model
Features: distance_km, truck_category, traffic_level, time_of_day, is_peak_hour
Target: accepted_price_npr (price in Nepali Rupees)
"""

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import numpy as np
from typing import cast
from typing import Optional, cast

# Create and train the model with the TRUCKBID-ACADEMIC dataset structure
def create_pricing_model():
    """Create and train the RandomForest pricing model"""
    
    # Initialize model with same parameters as GitHub repo
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    return model

def train_model(model):
    """Train the model with representative pricing data"""
    
    # Create training data based on TRUCKBID patterns
    # Format: distance_km, truck_category (encoded), traffic_level (encoded), time_of_day (encoded), is_peak_hour
    training_data = [
        # Short trips - Small truck
        [3.1, 0, 0, 2, 0, 400],      # Light traffic, Night
        [4.2, 0, 1, 3, 0, 415],      # Medium traffic, Afternoon
        [5.0, 0, 3, 1, 1, 720],      # Heavy traffic, Morning (peak)
        
        # Short trips - Medium truck
        [3.8, 1, 3, 1, 1, 1384],     # Very Heavy traffic, Morning (peak)
        [6.5, 1, 0, 3, 0, 700],      # Light traffic, Afternoon
        [7.2, 1, 2, 0, 0, 900],      # Medium traffic, Evening
        
        # Short trips - Large truck
        [4.5, 2, 1, 2, 0, 1050],     # Medium traffic, Evening
        [6.0, 2, 2, 1, 1, 1800],     # Heavy traffic, Morning (peak)
        
        # Medium trips - Small truck
        [10.1, 0, 3, 1, 1, 1300],    # Very Heavy traffic, Morning (peak)
        [12.5, 0, 1, 3, 0, 850],     # Medium traffic, Afternoon
        [15.0, 0, 0, 2, 0, 900],     # Light traffic, Night
        
        # Medium trips - Medium truck
        [10.1, 1, 3, 1, 1, 1300],    # Very Heavy traffic, Morning
        [12.5, 1, 2, 0, 0, 1650],    # Heavy traffic, Evening
        [15.3, 1, 0, 3, 0, 1050],    # Light traffic, Afternoon
        
        # Medium trips - Large truck
        [9.8, 2, 1, 3, 0, 1380],     # Medium traffic, Afternoon
        [14.0, 2, 2, 1, 1, 2200],    # Heavy traffic, Morning (peak)
        
        # Long trips - Small truck
        [20.0, 0, 1, 0, 0, 1200],    # Medium traffic, Evening
        [25.0, 0, 2, 2, 0, 1400],    # Heavy traffic, Night
        
        # Long trips - Medium truck
        [18.7, 1, 1, 2, 0, 1500],    # Medium traffic, Evening
        [22.5, 1, 2, 1, 1, 2100],    # Heavy traffic, Morning (peak)
        [28.0, 1, 0, 3, 0, 1750],    # Light traffic, Afternoon
        
        # Long trips - Large truck
        [20.0, 2, 1, 0, 0, 1800],    # Medium traffic, Evening
        [25.5, 2, 2, 1, 1, 2700],    # Heavy traffic, Morning (peak)
    ]
    
    # Prepare features and target
    X = np.array([row[:5] for row in training_data])
    y = np.array([row[5] for row in training_data])
    
    # Train model
    model.fit(X, y)
    
    return model

def predict_price(distance_km, truck_category, traffic_level, time_of_day, is_peak_hour):
    """
    Predict price using the trained ML model
    
    Args:
        distance_km: float - distance in kilometers
        truck_category: str - 'small_vehicle', 'medium_vehicle', or 'large_vehicle'
        traffic_level: str - 'light', 'medium', 'heavy', or 'very_heavy'
        time_of_day: str - '06:00' format or 'Morning', 'Afternoon', 'Evening', 'Night'
        is_peak_hour: int - 1 if peak hour, 0 otherwise
    
    Returns:
        float - predicted price in Nepali Rupees
    """
    
    # Initialize global model if not exists
    global _model, _truck_encoder, _traffic_encoder, _time_encoder
    
    if _model is None:
        # Create and train model
        _model = create_pricing_model()
        _model = train_model(_model)
        
    # Initialize label encoders for categorical features
    if _truck_encoder is None:
        _truck_encoder = LabelEncoder()
        _truck_encoder.fit(['LARGE', 'MEDIUM', 'SMALL'])  # Same order as GitHub
        
    if _traffic_encoder is None:
        _traffic_encoder = LabelEncoder()
        _traffic_encoder.fit(['Heavy', 'Light', 'Medium', 'Very Heavy'])
        
    if _time_encoder is None:
        _time_encoder = LabelEncoder()
        _time_encoder.fit(['Afternoon', 'Evening', 'Morning', 'Night'])
    
    # Normalize truck category
    truck_map = {
        'small_vehicle': 'SMALL',
        'medium_vehicle': 'MEDIUM',
        'large_vehicle': 'LARGE'
    }
    truck_cat = truck_map.get(truck_category, 'MEDIUM')
    
    # Normalize traffic level
    traffic_map = {
        'light': 'Light',
        'medium': 'Medium',
        'heavy': 'Heavy',
        'very_heavy': 'Very Heavy'
    }
    traffic_lev = traffic_map.get(traffic_level, 'Medium')
    
    # Normalize time of day - convert from HH:MM format or use time name
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
        time_period = time_of_day
    
    # Encode categorical features
    truck_encoder = cast(LabelEncoder, _truck_encoder)
    traffic_encoder = cast(LabelEncoder, _traffic_encoder)
    time_encoder = cast(LabelEncoder, _time_encoder)

    truck_encoded = int(np.asarray(truck_encoder.transform([truck_cat])).item())  # type: ignore[index]
    traffic_encoded = int(np.asarray(traffic_encoder.transform([traffic_lev])).item())  # type: ignore[index]
    time_encoded = int(np.asarray(time_encoder.transform([time_period])).item())  # type: ignore[index]
    
    # Prepare feature array for prediction
    features = np.array([[distance_km, truck_encoded, traffic_encoded, time_encoded, is_peak_hour]])
    
    # Make prediction
    predicted_price: float = float(_model.predict(features)[0])  # type: ignore[index]
    
    # Ensure minimum charges based on vehicle type
    min_charges = {
        'SMALL': 400,
        'MEDIUM': 700,
        'LARGE': 1200
    }
    min_charge = min_charges.get(truck_cat, 700)
    
    # Apply minimum charge
    final_price = max(predicted_price, min_charge)
    
    # Ensure maximum prices based on vehicle type
    max_prices = {
        'SMALL': 1500,
        'MEDIUM': 2500,
        'LARGE': 4000
    }
    max_price = max_prices.get(truck_cat, 2500)
    
    # Apply maximum cap
    final_price = min(final_price, max_price)
    
    return int(round(final_price))


# Initialize model on module load
_model = None
_truck_encoder: Optional[LabelEncoder] = None
_traffic_encoder: Optional[LabelEncoder] = None
_time_encoder: Optional[LabelEncoder] = None

# Train on first import
_model = create_pricing_model()
_model = train_model(_model)

# Initialize encoders
_truck_encoder = LabelEncoder()
_truck_encoder.fit(['LARGE', 'MEDIUM', 'SMALL'])

_traffic_encoder = LabelEncoder()
_traffic_encoder.fit(['Heavy', 'Light', 'Medium', 'Very Heavy'])

_time_encoder = LabelEncoder()
_time_encoder.fit(['Afternoon', 'Evening', 'Morning', 'Night'])
