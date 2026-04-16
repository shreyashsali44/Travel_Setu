from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import os
import random

# ==================== APP CONFIG ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'TravelSetu_Secret_Key_2024_Maroon_Theme'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travelsetu.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'warning'


# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    role = db.Column(db.String(20), default='user')
    is_verified = db.Column(db.Boolean, default=True)
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    preferences = db.Column(db.String(500), default='beaches,adventure')

    bookings = db.relationship('Booking', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)


class Destination(db.Model):
    __tablename__ = 'destinations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    location = db.Column(db.String(150))
    latitude = db.Column(db.Float, default=20.5937)
    longitude = db.Column(db.Float, default=78.9629)
    price_per_day = db.Column(db.Float, default=0)
    best_season = db.Column(db.String(50))
    image_url = db.Column(db.String(300))
    rating = db.Column(db.Float, default=4.0)
    total_visits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='destination', lazy=True)
    reviews = db.relationship('Review', backref='destination', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destinations.id'), nullable=True)
    booking_type = db.Column(db.String(30), default='hotel')
    booking_ref = db.Column(db.String(100))
    check_in = db.Column(db.Date)
    check_out = db.Column(db.Date)
    guests = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    payment_status = db.Column(db.String(20), default='unpaid')
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    destination_id = db.Column(db.Integer, db.ForeignKey('destinations.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    sentiment = db.Column(db.String(20), default='neutral')
    is_fake = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Blog(db.Model):
    __tablename__ = 'blogs'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    tags = db.Column(db.String(200))
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref='blogs')


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== LOGIN MANAGER ====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== AI FUNCTIONS ====================
def analyze_sentiment(text):
    if not text:
        return 'neutral'
    positive_words = ['amazing', 'excellent', 'beautiful', 'wonderful', 'great',
                      'awesome', 'fantastic', 'love', 'best', 'perfect', 'good', 'nice']
    negative_words = ['bad', 'terrible', 'worst', 'awful', 'horrible',
                      'hate', 'poor', 'disappointing', 'dirty', 'waste']
    text_lower = text.lower()
    pos = sum(1 for w in positive_words if w in text_lower)
    neg = sum(1 for w in negative_words if w in text_lower)
    if pos > neg:
        return 'positive'
    elif neg > pos:
        return 'negative'
    return 'neutral'


def detect_fake_review(text, rating):
    if not text:
        return False
    text_lower = text.lower()
    for pattern in ['buy now', 'click here', 'http://', 'https://', 'www.']:
        if pattern in text_lower:
            return True
    if len(text.split()) < 3 and (rating == 1 or rating == 5):
        return True
    return False


def get_ai_recommendations(user_id, limit=6):
    user = User.query.get(user_id)
    if not user:
        return Destination.query.order_by(Destination.rating.desc()).limit(limit).all()
    prefs = user.preferences.lower() if user.preferences else 'beaches,adventure'
    pref_list = [p.strip() for p in prefs.split(',')]
    all_dests = Destination.query.all()
    scored = []
    for dest in all_dests:
        score = 0
        cat = dest.category.lower() if dest.category else ''
        desc = dest.description.lower() if dest.description else ''
        for pref in pref_list:
            if pref in cat:
                score += 10
            if pref in desc:
                score += 5
        score += dest.rating * 2
        scored.append((dest, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored[:limit]]


def get_collaborative_recommendations(user_id, limit=6):
    user_bookings = Booking.query.filter_by(user_id=user_id).all()
    if not user_bookings:
        return get_ai_recommendations(user_id, limit)
    user_dest_ids = set(b.destination_id for b in user_bookings if b.destination_id)
    similar_user_ids = set()
    for dest_id in user_dest_ids:
        bks = Booking.query.filter_by(destination_id=dest_id).filter(Booking.user_id != user_id).all()
        for b in bks:
            similar_user_ids.add(b.user_id)
    recommended = set()
    for uid in similar_user_ids:
        for b in Booking.query.filter_by(user_id=uid).all():
            if b.destination_id and b.destination_id not in user_dest_ids:
                recommended.add(b.destination_id)
    if not recommended:
        return get_ai_recommendations(user_id, limit)
    return Destination.query.filter(Destination.id.in_(list(recommended))).limit(limit).all()


def smart_search(budget=None, location=None, interests=None, category=None):
    query = Destination.query
    if category and category.strip():
        query = query.filter(Destination.category.ilike(f'%{category}%'))
    if location and location.strip():
        query = query.filter(Destination.location.ilike(f'%{location}%'))
    if budget and str(budget).strip():
        try:
            query = query.filter(Destination.price_per_day <= float(budget))
        except:
            pass
    if interests and interests.strip():
        for interest in [i.strip() for i in interests.split(',')]:
            query = query.filter(
                db.or_(
                    Destination.category.ilike(f'%{interest}%'),
                    Destination.description.ilike(f'%{interest}%'),
                    Destination.name.ilike(f'%{interest}%')
                )
            )
    return query.order_by(Destination.rating.desc()).all()


def generate_itinerary(destination, days):
    activities_by_category = {
        'beaches': [
            ('🏖️ Morning beach walk & sunrise', '6:00 AM'),
            ('🏊 Swimming & water sports', '9:00 AM'),
            ('🍽️ Seafood lunch at beach shack', '12:30 PM'),
            ('😴 Afternoon rest', '2:00 PM'),
            ('🐚 Shell collecting & beach games', '4:00 PM'),
            ('🌅 Sunset watching', '6:00 PM'),
            ('🍹 Dinner & nightlife', '8:00 PM'),
            ('🚤 Island hopping tour', '9:00 AM'),
            ('🤿 Scuba diving', '10:00 AM'),
            ('🎣 Fishing trip', '3:00 PM'),
            ('🧘 Beach yoga', '6:00 AM'),
            ('📸 Photography walk', '5:00 PM'),
        ],
        'adventure': [
            ('⛰️ Early morning trek', '5:00 AM'),
            ('🏕️ Reach base camp', '10:00 AM'),
            ('🍳 Outdoor breakfast', '8:00 AM'),
            ('🧗 Rock climbing', '11:00 AM'),
            ('🌊 River rafting', '2:00 PM'),
            ('🪂 Paragliding', '4:00 PM'),
            ('🏕️ Campfire & stories', '7:00 PM'),
            ('⭐ Stargazing', '9:00 PM'),
            ('🚴 Mountain biking', '9:00 AM'),
            ('🌄 Summit hike', '4:00 AM'),
            ('🦅 Wildlife spotting', '6:00 AM'),
            ('🎿 Adventure sports', '3:00 PM'),
        ],
        'religious': [
            ('🙏 Early morning prayers', '5:00 AM'),
            ('🛕 Main temple darshan', '6:00 AM'),
            ('🍲 Prasad breakfast', '8:00 AM'),
            ('📖 Religious discourse', '10:00 AM'),
            ('🚶 Parikrama', '11:00 AM'),
            ('🍛 Community meal', '12:30 PM'),
            ('😴 Rest time', '2:00 PM'),
            ('🪔 Evening aarti', '6:00 PM'),
            ('📿 Meditation', '7:00 PM'),
            ('🎵 Bhajan / Kirtan', '8:00 PM'),
            ('🌅 Holy river bath', '5:00 AM'),
            ('🕯️ Candle ceremony', '7:00 PM'),
        ],
        'heritage': [
            ('🏰 Fort/Palace tour', '9:00 AM'),
            ('📸 Monument photography', '10:00 AM'),
            ('🎧 Audio guide tour', '11:00 AM'),
            ('🍽️ Traditional lunch', '1:00 PM'),
            ('🏛️ Museum visit', '3:00 PM'),
            ('🎭 Cultural show', '5:00 PM'),
            ('🌙 Heritage walk', '6:30 PM'),
            ('🍛 Royal dinner', '8:00 PM'),
            ('🛍️ Market shopping', '4:00 PM'),
            ('🎨 Art gallery', '11:00 AM'),
            ('🐘 Heritage ride', '10:00 AM'),
            ('📜 History session', '3:00 PM'),
        ]
    }
    cat = destination.category.lower() if destination.category else 'beaches'
    activities = activities_by_category.get(cat, activities_by_category['beaches'])
    itinerary = []
    idx = 0
    for day_num in range(1, days + 1):
        day_date = date.today() + timedelta(days=day_num)
        day_acts = []
        for _ in range(4):
            act, time = activities[idx % len(activities)]
            day_acts.append({'activity': act, 'time': time})
            idx += 1
        itinerary.append({
            'day': day_num,
            'date': day_date.strftime('%B %d, %Y'),
            'day_name': day_date.strftime('%A'),
            'activities': day_acts
        })
    return itinerary


# ==================== FLIGHT DATA GENERATOR ====================
def generate_flights(from_city, to_city, travel_date):
    airlines = [
        {"name": "IndiGo", "code": "6E", "icon": "✈️"},
        {"name": "Air India", "code": "AI", "icon": "🛩️"},
        {"name": "SpiceJet", "code": "SG", "icon": "✈️"},
        {"name": "Vistara", "code": "UK", "icon": "🛩️"},
        {"name": "GoAir", "code": "G8", "icon": "✈️"},
        {"name": "AirAsia India", "code": "I5", "icon": "✈️"},
    ]
    flights = []
    for i, al in enumerate(random.sample(airlines, min(5, len(airlines)))):
        dep_h = random.randint(5, 22)
        dep_m = random.choice([0, 15, 30, 45])
        dur_h = random.randint(1, 4)
        dur_m = random.choice([0, 15, 30, 45])
        arr_h = (dep_h + dur_h) % 24
        arr_m = (dep_m + dur_m) % 60
        base = random.randint(2500, 9000)
        flights.append({
            'id': i + 1,
            'airline': al['name'],
            'code': al['code'],
            'icon': al['icon'],
            'flight_no': f"{al['code']}-{random.randint(100,999)}",
            'departure': f"{dep_h:02d}:{dep_m:02d}",
            'arrival': f"{arr_h:02d}:{arr_m:02d}",
            'duration': f"{dur_h}h {dur_m}m",
            'stops': random.choice(['Non-stop', '1 Stop', 'Non-stop', 'Non-stop']),
            'price': base,
            'from_city': from_city,
            'to_city': to_city,
            'date': travel_date,
            'class': random.choice(['Economy', 'Premium Economy', 'Business']),
            'seats': random.randint(2, 45),
            'baggage': '15 Kg + 7 Kg Cabin',
            'meal': random.choice(['Included', 'Paid', 'Not Included']),
            'refundable': random.choice([True, False]),
        })
    flights.sort(key=lambda x: x['price'])
    return flights


def generate_trains(from_city, to_city):
    train_data = [
        ("Rajdhani Express", "12301", "Rajdhani"),
        ("Shatabdi Express", "12002", "Shatabdi"),
        ("Duronto Express", "12213", "Duronto"),
        ("Vande Bharat", "22436", "Vande Bharat"),
        ("Garib Rath", "12216", "Garib Rath"),
        ("Jan Shatabdi", "12055", "Jan Shatabdi"),
        ("Humsafar Express", "22221", "Humsafar"),
        ("Superfast Express", "12345", "SF"),
    ]
    trains = []
    for name, number, ttype in random.sample(train_data, min(5, len(train_data))):
        dep_h = random.randint(5, 22)
        dep_m = random.choice([0, 15, 30, 45])
        dur = random.randint(6, 20)
        trains.append({
            'name': f"{from_city}-{to_city} {name}",
            'number': number,
            'type': ttype,
            'departure': f"{dep_h:02d}:{dep_m:02d}",
            'arrival': f"{(dep_h+dur)%24:02d}:{dep_m:02d}",
            'duration': f"{dur}h {random.randint(0,59)}m",
            'from_city': from_city,
            'to_city': to_city,
            'classes': [
                {'name': '1A', 'price': random.randint(2500, 5000), 'available': random.randint(0, 20)},
                {'name': '2A', 'price': random.randint(1500, 2500), 'available': random.randint(0, 40)},
                {'name': '3A', 'price': random.randint(800, 1500), 'available': random.randint(0, 60)},
                {'name': 'SL', 'price': random.randint(300, 800), 'available': random.randint(0, 100)},
            ],
            'days': random.sample(['M', 'T', 'W', 'T', 'F', 'S', 'S'], random.randint(4, 7)),
        })
    return trains


def generate_buses(from_city, to_city):
    operators = ['VRL Travels', 'SRS Travels', 'Neeta Travels', 'Orange Travels',
                 'Paulo Travels', 'Kallada Travels', 'KPN Travels', 'Greenline']
    bus_types = ['AC Sleeper', 'AC Seater', 'Non-AC Sleeper', 'Volvo Multi-Axle',
                 'Mercedes Multi-Axle', 'Scania Multi-Axle']
    buses = []
    for i in range(random.randint(6, 12)):
        dep_h = random.randint(17, 23)
        dur = random.randint(5, 14)
        buses.append({
            'id': i + 1,
            'operator': random.choice(operators),
            'type': random.choice(bus_types),
            'departure': f"{dep_h:02d}:{random.choice(['00','15','30','45'])}",
            'arrival': f"{(dep_h+dur)%24:02d}:{random.choice(['00','15','30','45'])}",
            'duration': f"{dur}h {random.randint(0,59)}m",
            'price': random.randint(400, 2500),
            'rating': round(random.uniform(3.5, 5.0), 1),
            'seats': random.randint(3, 40),
            'amenities': random.sample(['WiFi', 'Charging', 'Blanket', 'Water', 'Entertainment'], random.randint(2, 4)),
            'from_city': from_city,
            'to_city': to_city,
        })
    buses.sort(key=lambda x: x['price'])
    return buses


def generate_cabs(pickup, drop):
    cabs = [
        {'id': 1, 'type': 'Mini', 'model': 'WagonR / Alto', 'capacity': 4,
         'price': random.randint(400, 700), 'per_km': 9, 'icon': '🚗'},
        {'id': 2, 'type': 'Sedan', 'model': 'Swift Dzire / Amaze', 'capacity': 4,
         'price': random.randint(700, 1200), 'per_km': 12, 'icon': '🚙'},
        {'id': 3, 'type': 'SUV', 'model': 'Innova / Ertiga', 'capacity': 6,
         'price': random.randint(1200, 2000), 'per_km': 16, 'icon': '🚐'},
        {'id': 4, 'type': 'Premium', 'model': 'Honda City / Verna', 'capacity': 4,
         'price': random.randint(1500, 2500), 'per_km': 18, 'icon': '🚘'},
        {'id': 5, 'type': 'Luxury', 'model': 'BMW / Mercedes', 'capacity': 4,
         'price': random.randint(4000, 8000), 'per_km': 35, 'icon': '🏎️'},
    ]
    for c in cabs:
        c['pickup'] = pickup
        c['drop'] = drop
    return cabs


# ==================== IMAGE HELPER ====================
def get_destination_image(destination, width=800, height=600):
    category_images = {
        'beaches': f'https://picsum.photos/seed/beach{destination.id}/{width}/{height}',
        'adventure': f'https://picsum.photos/seed/mountain{destination.id}/{width}/{height}',
        'religious': f'https://picsum.photos/seed/temple{destination.id}/{width}/{height}',
        'heritage': f'https://picsum.photos/seed/palace{destination.id}/{width}/{height}',
    }
    cat = destination.category.lower() if destination.category else 'beaches'
    return category_images.get(cat, category_images['beaches'])


# ==================== CONTEXT PROCESSORS ====================
@app.context_processor
def inject_globals():
    unread_count = 0
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(
            user_id=current_user.id, is_read=False).count()
    return {
        'unread_notifications': unread_count,
        'current_year': datetime.now().year,
        'all_categories': ['adventure', 'religious', 'beaches', 'heritage'],
        'get_destination_image': get_destination_image,
    }


# ==================== ROUTES ====================

# HOME PAGE
@app.route('/')
def index():
    featured = Destination.query.order_by(Destination.rating.desc()).limit(4).all()
    categories = ['adventure', 'religious', 'beaches', 'heritage']
    total_destinations = Destination.query.count()
    total_users = User.query.count()
    return render_template('index.html',
                           featured=featured,
                           categories=categories,
                           total_destinations=total_destinations,
                           total_users=total_users)


# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        if len(password) < 4:
            flash('Password must be at least 4 characters!', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email,
                    full_name=full_name if full_name else username, is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        notif = Notification(user_id=user.id, title='Welcome to TravelSetu! 🎉',
                             message='Your account has been created successfully.')
        db.session.add(notif)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Please enter username and password!', 'danger')
            return redirect(url_for('login'))
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            notif = Notification(user_id=user.id, title='Login Successful',
                                 message=f'Welcome back, {user.full_name}!')
            db.session.add(notif)
            db.session.commit()
            flash(f'Welcome back, {user.full_name}! 👋', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')


# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('index'))


# USER DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.created_at.desc()).limit(10).all()
    recommendations = get_ai_recommendations(current_user.id, 4)
    total_bookings = Booking.query.filter_by(user_id=current_user.id).count()
    confirmed_bookings = Booking.query.filter_by(
        user_id=current_user.id, status='confirmed').count()
    total_spent = db.session.query(db.func.sum(Booking.total_price)).filter_by(
        user_id=current_user.id, status='confirmed').scalar() or 0
    return render_template('dashboard.html',
                           bookings=user_bookings,
                           recommendations=recommendations,
                           total_bookings=total_bookings,
                           confirmed_bookings=confirmed_bookings,
                           total_spent=total_spent)


# ADMIN DASHBOARD
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied! Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    stats = {
        'total_users': User.query.count(),
        'total_destinations': Destination.query.count(),
        'total_bookings': Booking.query.count(),
        'total_revenue': db.session.query(db.func.sum(Booking.total_price)).filter_by(
            status='confirmed').scalar() or 0,
        'pending_bookings': Booking.query.filter_by(status='pending').count(),
        'recent_bookings': Booking.query.order_by(Booking.created_at.desc()).limit(10).all(),
        'recent_users': User.query.order_by(User.created_at.desc()).limit(10).all(),
        'all_destinations': Destination.query.order_by(Destination.created_at.desc()).all()
    }
    return render_template('admin_dashboard.html', stats=stats)


# ALL DESTINATIONS
@app.route('/destinations')
def destinations():
    category = request.args.get('category', '')
    sort_by = request.args.get('sort', 'rating')
    query = Destination.query
    if category:
        query = query.filter_by(category=category)
    if sort_by == 'price_low':
        query = query.order_by(Destination.price_per_day.asc())
    elif sort_by == 'price_high':
        query = query.order_by(Destination.price_per_day.desc())
    elif sort_by == 'name':
        query = query.order_by(Destination.name.asc())
    else:
        query = query.order_by(Destination.rating.desc())
    all_destinations = query.all()
    return render_template('destinations.html',
                           destinations=all_destinations,
                           categories=['adventure', 'religious', 'beaches', 'heritage'],
                           current_category=category,
                           current_sort=sort_by)


# DESTINATION DETAIL
@app.route('/destination/<int:id>')
def destination_detail(id):
    dest = Destination.query.get_or_404(id)
    dest.total_visits += 1
    db.session.commit()
    reviews = Review.query.filter_by(destination_id=id).order_by(Review.created_at.desc()).all()
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else dest.rating
    similar = Destination.query.filter_by(category=dest.category).filter(
        Destination.id != id).limit(3).all()
    return render_template('destination_detail.html',
                           destination=dest, reviews=reviews,
                           avg_rating=avg_rating, similar=similar)


# SEARCH
@app.route('/search')
def search():
    budget = request.args.get('budget', '')
    location = request.args.get('location', '')
    interests = request.args.get('interests', '')
    category = request.args.get('category', '')
    if budget or location or interests or category:
        results = smart_search(budget=budget, location=location,
                               interests=interests, category=category)
    else:
        results = Destination.query.order_by(Destination.rating.desc()).all()
    return render_template('search.html', results=results,
                           budget=budget, location=location,
                           interests=interests, category=category)


# AI RECOMMENDATIONS
@app.route('/recommend')
@login_required
def recommend():
    content_recs = get_ai_recommendations(current_user.id, 6)
    collab_recs = get_collaborative_recommendations(current_user.id, 6)
    return render_template('recommend.html',
                           content_recs=content_recs, collab_recs=collab_recs)


# BOOK DESTINATION
@app.route('/book/<int:dest_id>', methods=['GET', 'POST'])
@login_required
def book_destination(dest_id):
    dest = Destination.query.get_or_404(dest_id)
    if request.method == 'POST':
        try:
            check_in = datetime.strptime(request.form.get('check_in'), '%Y-%m-%d').date()
            check_out = datetime.strptime(request.form.get('check_out'), '%Y-%m-%d').date()
        except:
            flash('Invalid date format!', 'danger')
            return redirect(url_for('book_destination', dest_id=dest_id))
        if check_out <= check_in:
            flash('Check-out must be after check-in!', 'danger')
            return redirect(url_for('book_destination', dest_id=dest_id))
        guests = int(request.form.get('guests', 1))
        nights = (check_out - check_in).days
        total_price = nights * dest.price_per_day * guests
        booking = Booking(
            user_id=current_user.id, destination_id=dest.id,
            booking_type=request.form.get('booking_type', 'hotel'),
            check_in=check_in, check_out=check_out,
            guests=guests, total_price=total_price,
            status='pending', payment_status='unpaid')
        db.session.add(booking)
        db.session.commit()
        flash('Booking created! Please complete payment.', 'success')
        return redirect(url_for('payment_page', booking_id=booking.id))
    today = date.today().strftime('%Y-%m-%d')
    return render_template('booking.html', destination=dest, today=today)


# PAYMENT PAGE
@app.route('/payment/<int:booking_id>')
@login_required
def payment_page(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('payment.html', booking=booking)


# CONFIRM PAYMENT
@app.route('/confirm-payment/<int:booking_id>')
@login_required
def confirm_payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    booking.payment_status = 'paid'
    booking.status = 'confirmed'
    db.session.commit()
    dest_name = booking.destination.name if booking.destination else booking.booking_type
    notif = Notification(
        user_id=current_user.id, title='🎉 Booking Confirmed!',
        message=f'Your booking for {dest_name} has been confirmed. Total: ₹{booking.total_price}')
    db.session.add(notif)
    db.session.commit()
    flash('Payment successful! Booking confirmed. 🎉', 'success')
    return redirect(url_for('dashboard'))


# CANCEL BOOKING
@app.route('/cancel-booking/<int:booking_id>')
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('dashboard'))
    booking.status = 'cancelled'
    db.session.commit()
    notif = Notification(user_id=booking.user_id, title='Booking Cancelled',
                         message='Your booking has been cancelled.')
    db.session.add(notif)
    db.session.commit()
    flash('Booking cancelled.', 'warning')
    return redirect(url_for('dashboard'))


# ADD REVIEW
@app.route('/add-review/<int:dest_id>', methods=['POST'])
@login_required
def add_review(dest_id):
    dest = Destination.query.get_or_404(dest_id)
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '').strip()
    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5!', 'danger')
        return redirect(url_for('destination_detail', id=dest_id))
    sentiment = analyze_sentiment(comment)
    is_fake = detect_fake_review(comment, rating)
    review = Review(user_id=current_user.id, destination_id=dest_id,
                    rating=rating, comment=comment,
                    sentiment=sentiment, is_fake=is_fake)
    db.session.add(review)
    all_reviews = Review.query.filter_by(destination_id=dest_id).all()
    all_reviews.append(review)
    dest.rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)
    db.session.commit()
    if is_fake:
        flash('Review submitted but flagged for verification.', 'warning')
    else:
        flash('Thank you for your review! 🙏', 'success')
    return redirect(url_for('destination_detail', id=dest_id))


# ITINERARY
@app.route('/itinerary', methods=['GET', 'POST'])
@login_required
def itinerary():
    all_dests = Destination.query.order_by(Destination.name).all()
    dest_id = None
    days = 3
    if request.method == 'POST':
        dest_id = request.form.get('destination_id')
        days = int(request.form.get('days', 3))
    else:
        dest_id = request.args.get('destination_id')
        days = int(request.args.get('days', 3))
    if dest_id:
        dest = Destination.query.get(dest_id)
        if dest:
            itin = generate_itinerary(dest, days)
            return render_template('itinerary.html', itinerary=itin,
                                   destination=dest, days=days,
                                   all_destinations=all_dests)
    return render_template('itinerary.html', itinerary=None,
                           destination=None, all_destinations=all_dests)


# PROFILE
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.email = request.form.get('email', current_user.email)
        current_user.phone = request.form.get('phone', '')
        current_user.preferences = request.form.get('preferences', 'beaches,adventure')
        db.session.commit()
        flash('Profile updated! ✅', 'success')
        return redirect(url_for('profile'))
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.created_at.desc()).all()
    user_reviews = Review.query.filter_by(user_id=current_user.id).order_by(
        Review.created_at.desc()).all()
    return render_template('profile.html', bookings=user_bookings, reviews=user_reviews)


# NOTIFICATIONS
@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)


@app.route('/clear-notifications')
@login_required
def clear_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('All notifications cleared!', 'info')
    return redirect(url_for('notifications'))


# BLOG
@app.route('/blog')
def blog():
    all_blogs = Blog.query.order_by(Blog.created_at.desc()).all()
    return render_template('blog.html', blogs=all_blogs)


@app.route('/blog/<int:id>')
def blog_detail(id):
    blog_post = Blog.query.get_or_404(id)
    blog_post.views += 1
    db.session.commit()
    return render_template('blog_detail.html', blog=blog_post)


# WEATHER API
@app.route('/api/weather/<lat>/<lon>')
def get_weather(lat, lon):
    try:
        import requests as req
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true'
        response = req.get(url, timeout=5)
        data = response.json()
        return jsonify(data.get('current_weather', {}))
    except:
        return jsonify({'temperature': 'N/A', 'windspeed': 'N/A', 'error': True})


# ADMIN: ADD DESTINATION
@app.route('/admin/add-destination', methods=['POST'])
@login_required
def add_destination():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    if not name or not location:
        flash('Name and location required!', 'danger')
        return redirect(url_for('admin_dashboard'))
    dest = Destination(
        name=name,
        description=request.form.get('description', '').strip(),
        category=request.form.get('category', 'beaches'),
        location=location,
        price_per_day=float(request.form.get('price', 0)),
        best_season=request.form.get('season', 'All Year'),
        rating=4.0)
    db.session.add(dest)
    db.session.commit()
    flash(f'Destination "{name}" added! ✅', 'success')
    return redirect(url_for('admin_dashboard'))


# ADMIN: DELETE DESTINATION
@app.route('/admin/delete-destination/<int:id>')
@login_required
def delete_destination(id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    dest = Destination.query.get_or_404(id)
    Booking.query.filter_by(destination_id=id).delete()
    Review.query.filter_by(destination_id=id).delete()
    db.session.delete(dest)
    db.session.commit()
    flash(f'Destination deleted!', 'warning')
    return redirect(url_for('admin_dashboard'))


# ADMIN: ADD BLOG
@app.route('/admin/add-blog', methods=['POST'])
@login_required
def add_blog():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    if not title or not content:
        flash('Title and content required!', 'danger')
        return redirect(url_for('admin_dashboard'))
    blog_post = Blog(author_id=current_user.id, title=title,
                     content=content, tags=request.form.get('tags', '').strip())
    db.session.add(blog_post)
    db.session.commit()
    flash(f'Blog published! ✅', 'success')
    return redirect(url_for('admin_dashboard'))


# ==================== TRAVEL SERVICES ROUTES ====================

# FLIGHTS
@app.route('/flights', methods=['GET', 'POST'])
def flights():
    results = []
    from_city = ''
    to_city = ''
    travel_date = ''
    if request.method == 'POST':
        from_city = request.form.get('from', '').strip()
        to_city = request.form.get('to', '').strip()
        travel_date = request.form.get('date', '')
        if from_city and to_city:
            results = generate_flights(from_city, to_city, travel_date)
    return render_template('flights.html', results=results,
                           from_city=from_city, to_city=to_city,
                           travel_date=travel_date)


# BOOK FLIGHT
@app.route('/book-flight/<int:flight_id>', methods=['GET', 'POST'])
@login_required
def book_flight(flight_id):
    if request.method == 'POST':
        airline = request.form.get('airline', 'Airline')
        price = float(request.form.get('price', 0))
        from_city = request.form.get('from_city', '')
        to_city = request.form.get('to_city', '')
        travel_date = request.form.get('date', '')
        passengers = int(request.form.get('passengers', 1))
        total = price * passengers
        booking = Booking(
            user_id=current_user.id,
            booking_type='flight',
            booking_ref=f"FLT-{random.randint(10000,99999)}",
            total_price=total,
            guests=passengers,
            status='pending',
            payment_status='unpaid',
            details=f"{airline} | {from_city} → {to_city} | {travel_date} | {passengers} pax"
        )
        if travel_date:
            try:
                booking.check_in = datetime.strptime(travel_date, '%Y-%m-%d').date()
            except:
                pass
        db.session.add(booking)
        db.session.commit()
        flash('Flight booking created! Complete payment.', 'success')
        return redirect(url_for('payment_page', booking_id=booking.id))
    return redirect(url_for('flights'))


# HOTELS
@app.route('/hotels', methods=['GET', 'POST'])
def hotels():
    hotel_list = []
    city = ''
    if request.method == 'POST':
        city = request.form.get('city', '').strip()
        if city:
            hotel_list = [
                {"id": 1, "name": f"Taj {city}", "price": 8000, "rating": 4.8,
                 "stars": 5, "amenities": "WiFi, Pool, Spa, Gym"},
                {"id": 2, "name": f"ITC Grand {city}", "price": 6500, "rating": 4.6,
                 "stars": 5, "amenities": "WiFi, Pool, Restaurant"},
                {"id": 3, "name": f"Marriott {city}", "price": 5500, "rating": 4.5,
                 "stars": 4, "amenities": "WiFi, Gym, Restaurant"},
                {"id": 4, "name": f"Radisson {city}", "price": 4000, "rating": 4.3,
                 "stars": 4, "amenities": "WiFi, Pool"},
                {"id": 5, "name": f"OYO Premium {city}", "price": 1500, "rating": 3.8,
                 "stars": 3, "amenities": "WiFi, AC"},
                {"id": 6, "name": f"Treebo {city}", "price": 1200, "rating": 3.6,
                 "stars": 3, "amenities": "WiFi, AC, Breakfast"},
            ]
    return render_template('hotels.html', hotels=hotel_list, city=city)


# BOOK HOTEL
@app.route('/book-hotel/<int:hotel_id>', methods=['POST'])
@login_required
def book_hotel(hotel_id):
    hotel_name = request.form.get('hotel_name', 'Hotel')
    price = float(request.form.get('price', 0))
    city = request.form.get('city', '')
    checkin = request.form.get('checkin', '')
    checkout = request.form.get('checkout', '')
    rooms = int(request.form.get('rooms', 1))

    nights = 1
    if checkin and checkout:
        try:
            ci = datetime.strptime(checkin, '%Y-%m-%d').date()
            co = datetime.strptime(checkout, '%Y-%m-%d').date()
            nights = max((co - ci).days, 1)
        except:
            pass

    total = price * nights * rooms
    booking = Booking(
        user_id=current_user.id,
        booking_type='hotel',
        booking_ref=f"HTL-{random.randint(10000,99999)}",
        total_price=total,
        guests=rooms,
        status='pending',
        payment_status='unpaid',
        details=f"{hotel_name} | {city} | {checkin} to {checkout} | {rooms} room(s) | {nights} night(s)"
    )
    if checkin:
        try:
            booking.check_in = datetime.strptime(checkin, '%Y-%m-%d').date()
        except:
            pass
    if checkout:
        try:
            booking.check_out = datetime.strptime(checkout, '%Y-%m-%d').date()
        except:
            pass
    db.session.add(booking)
    db.session.commit()
    flash('Hotel booking created! Complete payment.', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# VILLAS
@app.route('/villas')
def villas():
    villa_list = [
        {"id": 1, "name": "Beach Villa Goa", "price": 12000, "location": "Candolim, Goa",
         "bedrooms": 3, "guests": 6, "rating": 4.7, "amenities": "Pool, Garden, Kitchen, WiFi"},
        {"id": 2, "name": "Mountain Villa Manali", "price": 9000, "location": "Old Manali",
         "bedrooms": 4, "guests": 8, "rating": 4.5, "amenities": "Fireplace, Garden, Kitchen"},
        {"id": 3, "name": "Heritage Haveli Udaipur", "price": 15000, "location": "Lake Pichola",
         "bedrooms": 5, "guests": 10, "rating": 4.9, "amenities": "Lake View, Pool, Heritage"},
        {"id": 4, "name": "Hillside Villa Munnar", "price": 8000, "location": "Munnar, Kerala",
         "bedrooms": 2, "guests": 4, "rating": 4.6, "amenities": "Tea Garden View, Kitchen"},
        {"id": 5, "name": "Lakefront Cottage Nainital", "price": 7000, "location": "Nainital",
         "bedrooms": 2, "guests": 4, "rating": 4.4, "amenities": "Lake View, Bonfire, Kitchen"},
    ]
    return render_template('villas.html', villas=villa_list)


# BOOK VILLA
@app.route('/book-villa/<int:villa_id>', methods=['POST'])
@login_required
def book_villa(villa_id):
    villa_name = request.form.get('villa_name', 'Villa')
    price = float(request.form.get('price', 0))
    checkin = request.form.get('checkin', '')
    checkout = request.form.get('checkout', '')
    nights = 1
    if checkin and checkout:
        try:
            ci = datetime.strptime(checkin, '%Y-%m-%d').date()
            co = datetime.strptime(checkout, '%Y-%m-%d').date()
            nights = max((co - ci).days, 1)
        except:
            pass
    total = price * nights
    booking = Booking(
        user_id=current_user.id, booking_type='villa',
        booking_ref=f"VLA-{random.randint(10000,99999)}",
        total_price=total, status='pending', payment_status='unpaid',
        details=f"{villa_name} | {checkin} to {checkout} | {nights} night(s)")
    db.session.add(booking)
    db.session.commit()
    flash('Villa booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# PACKAGES
@app.route('/packages')
def packages():
    package_list = [
        {"id": 1, "name": "Goa Beach Escape", "price": 15000, "duration": "4N/5D",
         "destinations": "North Goa, South Goa", "includes": "Hotel, Sightseeing, Transfers",
         "rating": 4.7},
        {"id": 2, "name": "Kashmir Paradise", "price": 25000, "duration": "6N/7D",
         "destinations": "Srinagar, Gulmarg, Pahalgam", "includes": "Hotel, Meals, Shikara",
         "rating": 4.9},
        {"id": 3, "name": "Kerala Backwaters", "price": 22000, "duration": "5N/6D",
         "destinations": "Kochi, Munnar, Alleppey", "includes": "Hotel, Houseboat, Meals",
         "rating": 4.8},
        {"id": 4, "name": "Rajasthan Royal Tour", "price": 28000, "duration": "7N/8D",
         "destinations": "Jaipur, Udaipur, Jodhpur", "includes": "Hotel, Safari, Cultural Show",
         "rating": 4.6},
        {"id": 5, "name": "Ladakh Adventure", "price": 32000, "duration": "6N/7D",
         "destinations": "Leh, Nubra, Pangong", "includes": "Hotel, Permits, Transport",
         "rating": 4.8},
        {"id": 6, "name": "Andaman Beach Holiday", "price": 30000, "duration": "5N/6D",
         "destinations": "Port Blair, Havelock, Neil", "includes": "Hotel, Ferry, Scuba",
         "rating": 4.7},
    ]
    return render_template('packages.html', packages=package_list)


# BOOK PACKAGE
@app.route('/book-package/<int:package_id>', methods=['POST'])
@login_required
def book_package(package_id):
    pkg_name = request.form.get('package_name', 'Package')
    price = float(request.form.get('price', 0))
    travelers = int(request.form.get('travelers', 1))
    travel_date = request.form.get('travel_date', '')
    total = price * travelers
    booking = Booking(
        user_id=current_user.id, booking_type='package',
        booking_ref=f"PKG-{random.randint(10000,99999)}",
        total_price=total, guests=travelers,
        status='pending', payment_status='unpaid',
        details=f"{pkg_name} | {travel_date} | {travelers} traveler(s)")
    if travel_date:
        try:
            booking.check_in = datetime.strptime(travel_date, '%Y-%m-%d').date()
        except:
            pass
    db.session.add(booking)
    db.session.commit()
    flash('Package booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# TRAINS
@app.route('/trains', methods=['GET', 'POST'])
def trains():
    train_list = []
    from_city = ''
    to_city = ''
    if request.method == 'POST':
        from_city = request.form.get('from', '').strip()
        to_city = request.form.get('to', '').strip()
        if from_city and to_city:
            train_list = generate_trains(from_city, to_city)
    return render_template('trains.html', trains=train_list,
                           from_city=from_city, to_city=to_city)


# BOOK TRAIN
@app.route('/book-train', methods=['POST'])
@login_required
def book_train():
    train_name = request.form.get('train_name', 'Train')
    price = float(request.form.get('price', 0))
    train_class = request.form.get('train_class', 'SL')
    passengers = int(request.form.get('passengers', 1))
    travel_date = request.form.get('date', '')
    total = price * passengers
    booking = Booking(
        user_id=current_user.id, booking_type='train',
        booking_ref=f"TRN-{random.randint(10000,99999)}",
        total_price=total, guests=passengers,
        status='pending', payment_status='unpaid',
        details=f"{train_name} | {train_class} | {travel_date} | {passengers} pax")
    db.session.add(booking)
    db.session.commit()
    flash('Train booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# BUSES
@app.route('/buses', methods=['GET', 'POST'])
def buses():
    bus_list = []
    from_city = ''
    to_city = ''
    if request.method == 'POST':
        from_city = request.form.get('from', '').strip()
        to_city = request.form.get('to', '').strip()
        if from_city and to_city:
            bus_list = generate_buses(from_city, to_city)
    return render_template('buses.html', buses=bus_list,
                           from_city=from_city, to_city=to_city)


# BOOK BUS
@app.route('/book-bus/<int:bus_id>', methods=['POST'])
@login_required
def book_bus(bus_id):
    operator = request.form.get('operator', 'Bus')
    price = float(request.form.get('price', 0))
    seats = int(request.form.get('seats', 1))
    travel_date = request.form.get('date', '')
    total = price * seats
    booking = Booking(
        user_id=current_user.id, booking_type='bus',
        booking_ref=f"BUS-{random.randint(10000,99999)}",
        total_price=total, guests=seats,
        status='pending', payment_status='unpaid',
        details=f"{operator} | {travel_date} | {seats} seat(s)")
    db.session.add(booking)
    db.session.commit()
    flash('Bus booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# CABS
@app.route('/cabs', methods=['GET', 'POST'])
def cabs():
    cab_list = []
    pickup = ''
    drop = ''
    if request.method == 'POST':
        pickup = request.form.get('pickup', '').strip()
        drop = request.form.get('drop', '').strip()
        if pickup and drop:
            cab_list = generate_cabs(pickup, drop)
    return render_template('cabs.html', cabs=cab_list, pickup=pickup, drop=drop)


# BOOK CAB
@app.route('/book-cab/<int:cab_id>', methods=['POST'])
@login_required
def book_cab(cab_id):
    cab_type = request.form.get('cab_type', 'Cab')
    price = float(request.form.get('price', 0))
    pickup = request.form.get('pickup', '')
    drop = request.form.get('drop', '')
    travel_date = request.form.get('date', '')
    booking = Booking(
        user_id=current_user.id, booking_type='cab',
        booking_ref=f"CAB-{random.randint(10000,99999)}",
        total_price=price, status='pending', payment_status='unpaid',
        details=f"{cab_type} | {pickup} → {drop} | {travel_date}")
    db.session.add(booking)
    db.session.commit()
    flash('Cab booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# TOURS
@app.route('/tours')
def tours():
    tour_list = [
        {"id": 1, "name": "Goa Adventure Tour", "price": 10000, "duration": "Full Day",
         "location": "Goa", "includes": "Water Sports, Sightseeing, Lunch", "rating": 4.6},
        {"id": 2, "name": "Rajasthan Heritage Walk", "price": 7000, "duration": "Full Day",
         "location": "Jaipur", "includes": "Guide, Entry Tickets, Lunch", "rating": 4.7},
        {"id": 3, "name": "Kerala Backwater Cruise", "price": 5000, "duration": "6 Hours",
         "location": "Alleppey", "includes": "Houseboat, Lunch, Guide", "rating": 4.8},
        {"id": 4, "name": "Varanasi Spiritual Tour", "price": 3500, "duration": "Full Day",
         "location": "Varanasi", "includes": "Boat Ride, Temple Visit, Aarti", "rating": 4.5},
        {"id": 5, "name": "Manali Adventure Pack", "price": 8000, "duration": "Full Day",
         "location": "Manali", "includes": "Rafting, Paragliding, Camping", "rating": 4.7},
        {"id": 6, "name": "Andaman Scuba Diving", "price": 6000, "duration": "3 Hours",
         "location": "Havelock", "includes": "Equipment, Instructor, Photos", "rating": 4.9},
    ]
    return render_template('tours.html', tours=tour_list)


# BOOK TOUR
@app.route('/book-tour/<int:tour_id>', methods=['POST'])
@login_required
def book_tour(tour_id):
    tour_name = request.form.get('tour_name', 'Tour')
    price = float(request.form.get('price', 0))
    participants = int(request.form.get('participants', 1))
    tour_date = request.form.get('tour_date', '')
    total = price * participants
    booking = Booking(
        user_id=current_user.id, booking_type='tour',
        booking_ref=f"TUR-{random.randint(10000,99999)}",
        total_price=total, guests=participants,
        status='pending', payment_status='unpaid',
        details=f"{tour_name} | {tour_date} | {participants} person(s)")
    db.session.add(booking)
    db.session.commit()
    flash('Tour booking created!', 'success')
    return redirect(url_for('payment_page', booking_id=booking.id))


# ==================== CREATE SAMPLE DATA ====================
def create_sample_data():
    with app.app_context():
        db.create_all()
        if User.query.first():
            print("✅ Database already has data!")
            return
        print("📦 Creating sample data...")

        admin = User(username='admin', email='admin@travelsetu.com',
                     full_name='Admin User', role='admin', is_verified=True,
                     preferences='adventure,heritage,beaches,religious')
        admin.set_password('admin123')
        db.session.add(admin)

        users_data = [
            ('raj', 'raj@example.com', 'Raj Kumar', 'beaches,adventure'),
            ('vaishnavi', 'vaishnavi@example.com', 'Vaishnavi Dahiphale', 'adventure,heritage'),
        ]
        for uname, email, fname, prefs in users_data:
            u = User(username=uname, email=email, full_name=fname,
                     role='user', is_verified=True, preferences=prefs)
            u.set_password(uname + '123')
            db.session.add(u)

        destinations_data = [
            ('Goa Beaches', 'Famous beaches with vibrant nightlife and water sports.', 'beaches', 'Goa, India', 15.2993, 74.1240, 3500, 'October - March', 4.5),
            ('Leh Ladakh', 'Adventure paradise with mountain passes and monasteries.', 'adventure', 'Ladakh, India', 34.1526, 77.5770, 4500, 'June - September', 4.8),
            ('Varanasi Ghats', 'Sacred city on the banks of Ganga with ancient temples.', 'religious', 'Varanasi, UP', 25.3176, 83.0059, 1500, 'October - March', 4.3),
            ('Jaipur Heritage', 'Pink city with magnificent forts and palaces.', 'heritage', 'Rajasthan, India', 26.9124, 75.7873, 2800, 'November - March', 4.6),
            ('Andaman Islands', 'Tropical paradise with pristine beaches and diving.', 'beaches', 'Andaman, India', 11.6234, 92.7265, 5500, 'November - April', 4.7),
            ('Rishikesh', 'Yoga capital with river rafting and spiritual retreats.', 'adventure', 'Uttarakhand, India', 30.0869, 78.2676, 2000, 'September - June', 4.4),
            ('Tirupati Temple', 'One of the most visited pilgrimage destinations.', 'religious', 'Andhra Pradesh', 13.6288, 79.4192, 1200, 'All Year', 4.2),
            ('Mysore Palace', 'Stunning architecture and Dasara celebrations.', 'heritage', 'Karnataka, India', 12.3051, 76.6551, 2200, 'October - March', 4.5),
            ('Manali', 'Snow-capped mountains and adventure sports.', 'adventure', 'Himachal Pradesh', 32.2396, 77.1887, 3000, 'March - June', 4.6),
            ('Puri Temple', 'One of the four dhams, famous for Rath Yatra.', 'religious', 'Odisha, India', 19.8050, 85.8177, 1800, 'October - March', 4.4),
            ('Udaipur', 'City of Lakes with magnificent palaces.', 'heritage', 'Rajasthan, India', 24.5854, 73.7125, 3200, 'September - March', 4.7),
            ('Kovalam Beach', 'Crescent beach with lighthouse and ayurveda.', 'beaches', 'Kerala, India', 8.4004, 76.9787, 2800, 'September - March', 4.3),
        ]
        for name, desc, cat, loc, lat, lon, price, season, rating in destinations_data:
            d = Destination(name=name, description=desc, category=cat,
                            location=loc, latitude=lat, longitude=lon,
                            price_per_day=price, best_season=season, rating=rating)
            db.session.add(d)
        db.session.commit()

        blogs_data = [
            ('Top 10 Beaches in India', 'India has amazing beaches from Goa to Andaman...', 'beaches,travel'),
            ('Ladakh Road Trip Guide', 'Planning a Ladakh trip? Here is everything...', 'adventure,ladakh'),
            ('Spiritual Varanasi', 'Varanasi offers unique spiritual experiences...', 'religious,varanasi'),
            ('Rajasthan Heritage', 'Explore the royal legacy of Rajasthan...', 'heritage,rajasthan'),
        ]
        for title, content, tags in blogs_data:
            b = Blog(author_id=1, title=title, content=content, tags=tags)
            db.session.add(b)
        db.session.commit()

        print("✅ Sample data created!")
        print("\n📋 LOGIN CREDENTIALS:")
        print("=" * 40)
        print("Admin:  admin / admin123")
        print("User 1: raj / raj123")
        print("User 2: vaishnavi / vaishnavi123")
        print("=" * 40)


# ==================== RUN ====================
if __name__ == '__main__':
    create_sample_data()
    print("\n🚀 Starting TravelSetu...")
    print("🌐 Open: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)