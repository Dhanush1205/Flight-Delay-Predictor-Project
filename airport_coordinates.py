import json
import os

# Load coordinates from JSON file
def load_airport_coordinates():
    try:
        with open('airport_coordinates.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to hardcoded coordinates if JSON file doesn't exist
        return {
            'ATL': (33.6407, -84.4277),  # Atlanta
            'LAX': (33.9416, -118.4085),  # Los Angeles
            'ORD': (41.9742, -87.9073),  # Chicago
            'DFW': (32.8998, -97.0403),  # Dallas
            'DEN': (39.8561, -104.6737),  # Denver
            'JFK': (40.6413, -73.7781),  # New York
            'SFO': (37.6213, -122.3790),  # San Francisco
            'LAS': (36.0840, -115.1537),  # Las Vegas
            'MCO': (28.4312, -81.3081),   # Orlando
            'SEA': (47.4502, -122.3088),  # Seattle
            'MIA': (25.7959, -80.2870),   # Miami
            'BOS': (42.3656, -71.0096),   # Boston
            'CLT': (35.2144, -80.9473),   # Charlotte
            'PHX': (33.4352, -112.0101),  # Phoenix
            'IAH': (29.9902, -95.3368),   # Houston
            'EWR': (40.6895, -74.1745),   # Newark
            'MSP': (44.8848, -93.2223),   # Minneapolis
            'DTW': (42.2162, -83.3554),   # Detroit
            'PHL': (39.8729, -75.2437),   # Philadelphia
            'LGA': (40.7769, -73.8740),   # New York LaGuardia
        }

# Load all airport coordinates
AIRPORT_COORDINATES = load_airport_coordinates()

def get_airport_coordinates(airport_code):
    """Get coordinates for an airport code."""
    return AIRPORT_COORDINATES.get(airport_code.upper())

def get_center_coordinates(origin, destination):
    """Calculate the center point between two airports for map centering."""
    origin_coords = get_airport_coordinates(origin)
    dest_coords = get_airport_coordinates(destination)
    
    if origin_coords and dest_coords:
        center_lat = (origin_coords[0] + dest_coords[0]) / 2
        center_lon = (origin_coords[1] + dest_coords[1]) / 2
        return center_lat, center_lon
    return None 