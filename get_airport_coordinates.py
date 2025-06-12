import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
import json

# Read the dataset
df = pd.read_csv('Data/Processed_data15.csv')

# Get unique airports from both origin and destination columns
unique_airports = set(df['origin'].unique()) | set(df['dest'].unique())

# Initialize geocoder
geolocator = Nominatim(user_agent="flight_delay_prediction")

# Dictionary to store airport coordinates
airport_coordinates = {}

# Function to get coordinates with retry
def get_coordinates(airport_code, max_retries=3):
    for attempt in range(max_retries):
        try:
            # Try to get coordinates using airport code
            location = geolocator.geocode(f"{airport_code} airport")
            if location:
                return (location.latitude, location.longitude)
            time.sleep(1)  # Wait between requests
        except GeocoderTimedOut:
            if attempt == max_retries - 1:
                return None
            time.sleep(1)
    return None

# Get coordinates for each airport
for airport in unique_airports:
    print(f"Getting coordinates for {airport}...")
    coords = get_coordinates(airport)
    if coords:
        airport_coordinates[airport] = coords
        print(f"Found coordinates for {airport}: {coords}")
    else:
        print(f"Could not find coordinates for {airport}")
    time.sleep(1)  # Be nice to the geocoding service

# Save coordinates to a JSON file
with open('airport_coordinates.json', 'w') as f:
    json.dump(airport_coordinates, f, indent=4)

print(f"\nTotal airports processed: {len(unique_airports)}")
print(f"Successfully found coordinates for: {len(airport_coordinates)} airports") 