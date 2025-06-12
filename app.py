from flask import Flask, request, jsonify, render_template, url_for, session, redirect, flash
import json
import os
from datetime import datetime, timedelta
import folium
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load model data
with open('static/model_data.json', 'r') as f:
    model_data = json.load(f)

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
        self.password_hash = generate_password_hash(password)

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

# Set year range (extending to future)
min_year = 2013
max_year = 2043  # Extending to 20 years in future

# Get airport coordinates
def get_airport_coordinates(airport_code):
    airports = {
        "ATL": (33.6407, -84.4277),
        "DFW": (32.8969, -97.0404),
        "ORD": (41.9786, -87.9048),
        "DEN": (39.8561, -104.6737),
        "LAX": (33.9416, -118.4085),
        "CLT": (35.2140, -80.9431),
        "LAS": (36.0801, -115.1523),
        "PHX": (33.4343, -112.0116),
        "IAH": (29.9864, -95.3414),
        "MCO": (28.4293, -81.3089)
    }
    return airports.get(airport_code, None)

# Create route map
def create_route_map(origin, dest, is_delayed):
    origin_coords = get_airport_coordinates(origin)
    dest_coords = get_airport_coordinates(dest)
    
    if not origin_coords or not dest_coords:
        return None
        
    m = folium.Map(location=get_center_coordinates(origin_coords, dest_coords), zoom_start=4)
    
    # Add markers
    folium.Marker(
        origin_coords,
        popup=f"{origin}",
        icon=folium.Icon(color='green' if not is_delayed else 'red')
    ).add_to(m)
    
    folium.Marker(
        dest_coords,
        popup=f"{dest}",
        icon=folium.Icon(color='green' if not is_delayed else 'red')
    ).add_to(m)
    
    # Add route line
    folium.PolyLine(
        [origin_coords, dest_coords],
        color='red' if is_delayed else 'green',
        weight=2.5,
        opacity=0.8
    ).add_to(m)
    
    return m._repr_html_()

model = rf_classifier  # Use Random Forest for predictions

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
    return redirect(url_for('login'))

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
        
        # Get encoded values from model data
        carrier_idx = model_data['carriers']['values'][model_data['carriers']['labels'].index(carrier)]
        origin_idx = model_data['airports']['origin']['values'][model_data['airports']['origin']['labels'].index(origin)]
        dest_idx = model_data['airports']['dest']['values'][model_data['airports']['dest']['labels'].index(dest)]
        
        # Simulate prediction (using static probabilities)
        output = 1 if np.random.random() < model_data['class_distribution']['1'] else 0
        
        # Get prediction probabilities
        on_time_prob = model_data['class_distribution']['0'] * 100
        delayed_prob = model_data['class_distribution']['1'] * 100
        
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
    # If user is already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin  # Store admin status in session
            flash('Welcome back!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
            return render_template('login.html')
            
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.is_admin and user.check_password(password):
            session['admin_id'] = user.id
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid email or password', 'error')
            return render_template('admin_login.html')
    
    return render_template('admin_login.html')

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            flash('Please login as admin first', 'error')
            return redirect(url_for('admin_login'))
        
        admin_user = User.query.get(admin_id)
        if not admin_user or not admin_user.is_admin:
            flash('Unauthorized access', 'error')
            return redirect(url_for('home'))
            
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
    try:
        # Check if admin already exists
        admin = User.query.filter_by(email='admin@flysense.com').first()
        if admin:
            return 'Admin account already exists!'
        
        # Create admin user with simple credentials
        admin = User(
            name='Admin',
            email='admin@flysense.com',
            is_admin=True
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.commit()
        return 'Admin account created successfully! Email: admin@flysense.com, Password: admin123'
    except Exception as e:
        return f'Error creating admin account: {str(e)}'

if __name__ == '__main__':
	app.run(debug=False)
# For mac, make 'app.run(debug=True)'