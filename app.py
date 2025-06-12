from flask import Flask, request, jsonify, render_template, url_for, session, redirect, flash
import pickle
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import pandas as pd
import csv
import os
from datetime import datetime, timedelta
import folium
from airport_coordinates import get_airport_coordinates, get_center_coordinates
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import requests  # Add this import at the top with other imports

# Initialize Flask app
app = Flask(__name__, 
    static_url_path='/static',
    static_folder='static',
    template_folder='templates'
)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Configure password hashing
app.config['SECURITY_PASSWORD_HASH'] = 'pbkdf2_sha256'
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT', os.urandom(24).hex())

# Get the absolute path to the Data directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flysense.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Contact Model
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Contact {self.name}>'

# Create database tables
with app.app_context():
    db.create_all()

try:
    # Import dataset with absolute path
    data_file = os.path.join(DATA_DIR, 'Processed_data15.csv')
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Data file not found: {data_file}")
    
    df = pd.read_csv(data_file)
    
    # Set year range (extending to future)
    min_year = df['year'].min()  # 2013
    max_year = 2043  # Extending to 20 years in future

    # Label Encoding
    le_carrier = LabelEncoder()
    df['carrier'] = le_carrier.fit_transform(df['carrier'])

    le_dest = LabelEncoder()
    df['dest'] = le_dest.fit_transform(df['dest'])

    le_origin = LabelEncoder()
    df['origin'] = le_origin.fit_transform(df['origin'])

    # Converting Pandas DataFrame into a Numpy array
    X = df.iloc[:, 0:6].values # from column(years) to column(distance)
    y = df['delayed']

    X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=0.25,random_state=61)

    # Create and train Random Forest
    rf_classifier = RandomForestClassifier(
        n_estimators=200,  # Increase number of trees
        max_depth=10,      # Increase depth
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',  # Handle class imbalance
        random_state=42
    )
    rf_classifier.fit(X_train, y_train)

    model = rf_classifier  # Use Random Forest for predictions
except Exception as e:
    print(f"Error loading data: {str(e)}")
    raise

# Replace Aviationstack with OpenSky configuration
OPENSKY_BASE_URL = 'https://opensky-network.org/api'

def create_route_map(origin, destination, is_delayed):
    """Create a Folium map with the flight route."""
    # Get coordinates for both airports
    origin_coords = get_airport_coordinates(origin)
    dest_coords = get_airport_coordinates(destination)
    
    if not origin_coords or not dest_coords:
        return None
    
    # Calculate center point for map
    center_lat, center_lon = get_center_coordinates(origin, destination)
    
    # Create map centered between the airports
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=4,
        tiles='OpenStreetMap',
        width='100%',
        height='100%'
    )
    
    # Define colors based on delay status
    line_color = 'red' if is_delayed else 'green'
    
    # Add markers for origin and destination with airport names
    folium.Marker(
        location=origin_coords,
        popup=f'Origin: {origin}',
        icon=folium.Icon(color='blue', icon='plane', prefix='fa'),
        tooltip=f'Origin: {origin}'
    ).add_to(m)
    
    folium.Marker(
        location=dest_coords,
        popup=f'Destination: {destination}',
        icon=folium.Icon(color='blue', icon='plane', prefix='fa'),
        tooltip=f'Destination: {destination}'
    ).add_to(m)
    
    # Draw the route line
    folium.PolyLine(
        locations=[origin_coords, dest_coords],
        color=line_color,
        weight=3,
        opacity=0.8,
        popup=f'Flight Status: {"Delayed" if is_delayed else "On Time"}'
    ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m._repr_html_()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/home')
@login_required
def home():
    if 'predictions' not in session:
        session['predictions'] = []
    return render_template('home.html', 
                         min_year=min_year, 
                         max_year=max_year,
                         prediction_text=None,
                         route_map=None)

@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            message = request.form.get('message')
            
            # Create new contact entry
            new_contact = Contact(
                name=name,
                email=email,
                message=message
            )
            
            # Save to database
            db.session.add(new_contact)
            db.session.commit()
            
            # Flash success message
            flash('Thank you for your message! We will get back to you soon.', 'success')
            return redirect(url_for('contact'))
            
        except Exception as e:
            # Flash error message
            flash('An error occurred. Please try again.', 'error')
            return render_template('contact.html')
            
    return render_template('contact.html')

@app.route('/predict',methods=['POST'])
@login_required
def predict():
    try:
        year = int(request.form['year'])
        month = int(request.form['month'])
        day = int(request.form['day'])
        carrier = str(request.form['carrier'])
        origin = str(request.form['origin'])
        dest = str(request.form['dest'])
        
        # Validate date
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return render_template('home.html', error="Invalid date. Please check month and day values.", min_year=min_year, max_year=max_year)
        
        # Check year range
        if year < 2013:
            return render_template('home.html', error="Please enter a year from 2013 onwards.", min_year=min_year, max_year=max_year)
        if year > max_year:
            return render_template('home.html', error=f"Please enter a year before {max_year}.", min_year=min_year, max_year=max_year)
        
        # First get the ML model prediction
        x1 = [year, month, day]
        x2 = [carrier, origin, dest]
        x1.extend(x2)
        df1 = pd.DataFrame(data=[x1], columns=['year', 'month', 'date', 'carrier', 'origin', 'dest'])
        
        df1['carrier'] = le_carrier.transform(df1['carrier'])
        df1['origin'] = le_origin.transform(df1['origin'])
        df1['dest'] = le_dest.transform(df1['dest'])
        
        x = df1.iloc[:, :6].values
        ans = model.predict(x)
        output = ans[0]  # Get the first prediction
        
        # Get prediction probabilities
        probabilities = model.predict_proba(x)[0]
        on_time_prob = round(probabilities[0] * 100, 2)
        delayed_prob = round(probabilities[1] * 100, 2)
        
        # Print prediction probabilities and class distribution
        print("Prediction probabilities:", model.predict_proba(x))
        print("Training data class distribution:", df['delayed'].value_counts(normalize=True))
        
        # Try to get real-time flight information from OpenSky
        delay_minutes = None
        try:
            # Get current time and time 2 hours ago
            now = datetime.now()
            begin = now - timedelta(hours=2)
            
            # Convert to Unix timestamps
            begin_timestamp = int(begin.timestamp())
            end_timestamp = int(now.timestamp())
            
            # Make API request for flights between these airports
            params = {
                'airport': origin,
                'begin': begin_timestamp,
                'end': end_timestamp
            }
            response = requests.get(f"{OPENSKY_BASE_URL}/flights/arrival", params=params)
            
            if response.status_code == 200:
                flights = response.json()
                # Filter flights going to our destination
                matching_flights = [f for f in flights if f.get('estArrivalAirport') == dest]
                
                if matching_flights:
                    # Get the most recent flight
                    flight = matching_flights[-1]
                    # Calculate delay if we have both scheduled and actual times
                    if 'firstSeen' in flight and 'lastSeen' in flight:
                        actual_duration = flight['lastSeen'] - flight['firstSeen']
                        # Assume average flight time is 2 hours (7200 seconds)
                        # This is a simplified calculation - in a real app you'd want to use actual scheduled times
                        estimated_duration = 7200
                        if actual_duration > estimated_duration:
                            delay_minutes = int((actual_duration - estimated_duration) / 60)
        except Exception as api_error:
            print(f"API Error: {str(api_error)}")
            # Continue with ML prediction if API fails
            pass
        
        # Create route map
        route_map = create_route_map(origin, dest, output == 1)
        
        # Store prediction in session
        if 'predictions' not in session:
            session['predictions'] = []
        
        prediction = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'year': year,
            'month': month,
            'day': day,
            'carrier': carrier,
            'origin': origin,
            'dest': dest,
            'status': 'Delayed' if output == 1 else 'On Time',
            'delay_minutes': delay_minutes,
            'on_time_prob': on_time_prob,
            'delayed_prob': delayed_prob
        }
        
        session['predictions'].append(prediction)
        session.modified = True
        
        return render_template('home.html', 
                             prediction_text=output,
                             delay_minutes=delay_minutes,
                             min_year=min_year, 
                             max_year=max_year,
                             route_map=route_map,
                             on_time_prob=on_time_prob,
                             delayed_prob=delayed_prob)
    except ValueError:
        return render_template('home.html', error="Please enter valid numbers for year, month, and day.", min_year=min_year, max_year=max_year)
    except Exception as e:
        return render_template('home.html', error="An error occurred. Please try again.", min_year=min_year, max_year=max_year)

@app.route('/history')
@login_required
def history():
    predictions = session.get('predictions', [])
    return render_template('history.html', records=predictions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            flash('Welcome back!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)  # Remove admin status from session
    session.pop('predictions', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # If user is already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validate passwords match
            if password != confirm_password:
                flash('Passwords do not match!', 'error')
                return render_template('signup.html')

            # Check if user already exists
            if User.query.filter_by(email=email).first():
                flash('Email already registered!', 'error')
                return render_template('signup.html')

            # Create new user
            new_user = User(name=name, email=email)
            new_user.set_password(password)
            
            # Save to database
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('An error occurred during registration.', 'error')
            return render_template('signup.html')
            
    return render_template('signup.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session and session.get('is_admin'):
        return redirect(url_for('admin'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.is_admin and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = True
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('admin_login.html')

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Please login as admin to access this page', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin():
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin.html', contacts=contacts, users=users)

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('home'))

@app.route('/delete_contact/<int:contact_id>')
@admin_required
def delete_contact(contact_id):
    try:
        contact = Contact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()
        flash(f'Message from {contact.name} has been deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting message. Please try again.', 'error')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('admin'))

@app.route('/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.is_admin:
            flash('Cannot delete admin users.', 'error')
            return redirect(url_for('admin'))
            
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.name} has been deleted successfully.', 'success')
    except Exception as e:
        flash('Error deleting user. Please try again.', 'error')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('admin'))

@app.route('/create_admin')
def create_admin():
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(email='admin@example.com').first()
    if not admin:
        admin = User(
            name='Admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')  # Set a default password
        db.session.add(admin)
        db.session.commit()
        flash('Admin account created successfully!', 'success')
    else:
        flash('Admin account already exists!', 'info')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
	app.run(debug=False)
# For mac, make 'app.run(debug=True)'