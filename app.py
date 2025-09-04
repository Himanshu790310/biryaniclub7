
import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database with UTF-8 encoding
database_url = "sqlite:///biryani_club.db"  # Force SQLite for now
if database_url.startswith("sqlite"):
    database_url += "?charset=utf8mb4"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False} if database_url.startswith("sqlite") else {}
}

# Initialize SQLAlchemy
from models import db
db.init_app(app)

# Create tables and initialize data within app context
with app.app_context():
    # Import models to ensure tables are created
    from models import User, MenuItem, CartItem, Order, OrderItem, StoreSettings, Promotion
    
    # Create all tables
    db.create_all()
    
    # Initialize default data if not exists
    if StoreSettings.query.count() == 0:
        # Add default store settings
        StoreSettings.set_setting('store_open', 'true')
        StoreSettings.set_setting('delivery_radius', '10')
        StoreSettings.set_setting('base_delivery_charge', '30')
        print("Default store settings added")
        
    # Create admin user if not exists
    if User.query.filter_by(role='admin').count() == 0:
        admin_user = User(
            username='admin',
            email='admin@biryaniclub.com',
            full_name='Admin User',
            role='admin',
            phone='9999999999'
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        try:
            db.session.commit()
            print("Admin user created: username=admin, password=admin123")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin user: {e}")
            
    # Create delivery person if not exists
    if User.query.filter_by(role='delivery').count() == 0:
        delivery_user = User(
            username='delivery',
            email='delivery@biryaniclub.com',
            full_name='Delivery Person',
            role='delivery',
            phone='8888888888'
        )
        delivery_user.set_password('delivery123')
        db.session.add(delivery_user)
        try:
            db.session.commit()
            print("Delivery user created: username=delivery, password=delivery123")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating delivery user: {e}")
    
    # Add complete menu items if none exist
    if MenuItem.query.count() == 0:
        menu_items = [
            # Biryani
            MenuItem(name='Veg Biryani', description='Fragrant basmati rice with mixed vegetables', price=99, category='Biryani', emoji='🍛', popularity=8),
            MenuItem(name='Veg Biryani (Large)', description='Fragrant basmati rice with mixed vegetables', price=189, category='Biryani', emoji='🍛', popularity=8),
            MenuItem(name='Egg Biryani', description='Aromatic rice with boiled eggs', price=109, category='Biryani', emoji='🍛', popularity=7),
            MenuItem(name='Egg Biryani (Large)', description='Aromatic rice with boiled eggs', price=199, category='Biryani', emoji='🍛', popularity=7),
            MenuItem(name='Paneer Biryani', description='Premium paneer pieces with fragrant rice', price=129, category='Biryani', emoji='🍛', popularity=9),
            MenuItem(name='Paneer Biryani (Large)', description='Premium paneer pieces with fragrant rice', price=239, category='Biryani', emoji='🍛', popularity=9),
            MenuItem(name='Manchurian Biryani', description='Crispy manchurian with aromatic rice', price=109, category='Biryani', emoji='🍛', popularity=6),
            MenuItem(name='Manchurian Biryani (Large)', description='Crispy manchurian with aromatic rice', price=199, category='Biryani', emoji='🍛', popularity=6),
            MenuItem(name='Mushroom Biryani', description='Fresh mushrooms with spiced rice', price=109, category='Biryani', emoji='🍛', popularity=6),
            MenuItem(name='Mushroom Biryani (Large)', description='Fresh mushrooms with spiced rice', price=199, category='Biryani', emoji='🍛', popularity=6),
            MenuItem(name='Chicken Biryani', description='Tender chicken pieces with aromatic rice', price=119, category='Biryani', emoji='🍛', popularity=10),
            MenuItem(name='Chicken Biryani (Large)', description='Tender chicken pieces with aromatic rice', price=219, category='Biryani', emoji='🍛', popularity=10),
            MenuItem(name='Chicken Biryani (Premium)', description='Premium chicken biryani with extra spices', price=139, category='Biryani', emoji='🍛', popularity=10),
            MenuItem(name='Chicken Biryani (Premium Large)', description='Premium chicken biryani with extra spices', price=249, category='Biryani', emoji='🍛', popularity=10),

            # Rolls & Chowmein
            MenuItem(name='Veg Roll', description='Fresh vegetables wrapped in soft bread', price=29, category='Rolls & Chowmein', emoji='🌯', popularity=7),
            MenuItem(name='Egg Roll', description='Scrambled eggs with onions in roll', price=39, category='Rolls & Chowmein', emoji='🌯', popularity=8),
            MenuItem(name='Paneer Roll', description='Spiced paneer cubes in soft roll', price=79, category='Rolls & Chowmein', emoji='🌯', popularity=6),
            MenuItem(name='Manchurian Roll', description='Crispy manchurian in roll wrap', price=49, category='Rolls & Chowmein', emoji='🌯', popularity=5),
            MenuItem(name='Chicken Roll', description='Tender chicken pieces in roll', price=89, category='Rolls & Chowmein', emoji='🌯', popularity=9),
            MenuItem(name='Chowmein (Small)', description='Stir-fried noodles with vegetables', price=10, category='Rolls & Chowmein', emoji='🍜', popularity=4),
            MenuItem(name='Chowmein (Medium)', description='Stir-fried noodles with vegetables', price=20, category='Rolls & Chowmein', emoji='🍜', popularity=5),
            MenuItem(name='Chowmein (Large)', description='Stir-fried noodles with vegetables', price=40, category='Rolls & Chowmein', emoji='🍜', popularity=6),
            MenuItem(name='Veg Chowmein', description='Vegetable noodles with sauce', price=49, category='Rolls & Chowmein', emoji='🍜', popularity=6),
            MenuItem(name='Veg Chowmein (Large)', description='Vegetable noodles with sauce', price=99, category='Rolls & Chowmein', emoji='🍜', popularity=6),
            MenuItem(name='Paneer Chowmein', description='Paneer cubes with noodles', price=59, category='Rolls & Chowmein', emoji='🍜', popularity=5),
            MenuItem(name='Paneer Chowmein (Large)', description='Paneer cubes with noodles', price=109, category='Rolls & Chowmein', emoji='🍜', popularity=5),
            MenuItem(name='Egg Chowmein', description='Egg noodles with scrambled eggs', price=49, category='Rolls & Chowmein', emoji='🍜', popularity=7),
            MenuItem(name='Egg Chowmein (Large)', description='Egg noodles with scrambled eggs', price=99, category='Rolls & Chowmein', emoji='🍜', popularity=7),
            MenuItem(name='Chicken Chowmein', description='Chicken pieces with noodles', price=79, category='Rolls & Chowmein', emoji='🍜', popularity=8),
            MenuItem(name='Chicken Chowmein (Large)', description='Chicken pieces with noodles', price=149, category='Rolls & Chowmein', emoji='🍜', popularity=8),

            # Bread
            MenuItem(name='Plain Roti', description='Fresh wheat bread', price=12, category='Bread', emoji='🍞', popularity=8),
            MenuItem(name='Butter Roti', description='Roti with butter', price=15, category='Bread', emoji='🍞', popularity=7),
            MenuItem(name='Plain Naan', description='Traditional Indian bread', price=25, category='Bread', emoji='🫓', popularity=9),
            MenuItem(name='Butter Naan', description='Naan with butter', price=35, category='Bread', emoji='🫓', popularity=9),
            MenuItem(name='Garlic Naan', description='Naan with garlic and herbs', price=49, category='Bread', emoji='🫓', popularity=8),
            MenuItem(name='Lachha Paratha', description='Layered wheat bread', price=29, category='Bread', emoji='🫓', popularity=7),

            # Rice
            MenuItem(name='Plain Rice', description='Steamed basmati rice', price=69, category='Rice', emoji='🍚', popularity=6),
            MenuItem(name='Veg Fried Rice', description='Rice with mixed vegetables', price=79, category='Rice', emoji='🍚', popularity=7),
            MenuItem(name='Jeera Rice', description='Cumin flavored rice', price=79, category='Rice', emoji='🍚', popularity=6),
            MenuItem(name='Schezwan Rice', description='Spicy rice with schezwan sauce', price=99, category='Rice', emoji='🍚', popularity=5),
            MenuItem(name='Mix Fried Rice', description='Rice with mixed vegetables and protein', price=119, category='Rice', emoji='🍚', popularity=6),
            MenuItem(name='Egg Fried Rice', description='Rice with scrambled eggs', price=89, category='Rice', emoji='🍚', popularity=7),
            MenuItem(name='Chicken Fried Rice', description='Rice with chicken pieces', price=99, category='Rice', emoji='🍚', popularity=8),

            # Starters
            MenuItem(name='Chilli Potato', description='Crispy potato with spicy sauce', price=69, category='Starters', emoji='🥔', popularity=8),
            MenuItem(name='Chilli Potato (Large)', description='Crispy potato with spicy sauce', price=129, category='Starters', emoji='🥔', popularity=8),
            MenuItem(name='Honey Chilli Potato', description='Sweet and spicy potato', price=89, category='Starters', emoji='🥔', popularity=7),
            MenuItem(name='Honey Chilli Potato (Large)', description='Sweet and spicy potato', price=169, category='Starters', emoji='🥔', popularity=7),
            MenuItem(name='Veg Manchurian', description='Deep fried vegetable balls', price=49, category='Starters', emoji='🥗', popularity=6),
            MenuItem(name='Veg Manchurian (Large)', description='Deep fried vegetable balls', price=99, category='Starters', emoji='🥗', popularity=6),
            MenuItem(name='Paneer Manchurian', description='Paneer cubes in manchurian sauce', price=89, category='Starters', emoji='🧀', popularity=7),
            MenuItem(name='Paneer Manchurian (Large)', description='Paneer cubes in manchurian sauce', price=169, category='Starters', emoji='🧀', popularity=7),
            MenuItem(name='Chicken Manchurian', description='Chicken pieces in spicy sauce', price=119, category='Starters', emoji='🍗', popularity=9),
            MenuItem(name='Chicken Manchurian (Large)', description='Chicken pieces in spicy sauce', price=209, category='Starters', emoji='🍗', popularity=9),
            MenuItem(name='Crispy Baby Corn', description='Crispy baby corn with sauce', price=199, category='Starters', emoji='🌽', popularity=5),
            MenuItem(name='Paneer Chilli', description='Spicy paneer cubes', price=199, category='Starters', emoji='🧀', popularity=7),
            MenuItem(name='Baby Corn Chilli', description='Spicy baby corn preparation', price=189, category='Starters', emoji='🌽', popularity=5),
            MenuItem(name='Chicken Chilli', description='Spicy chicken preparation', price=229, category='Starters', emoji='🍗', popularity=9),
            MenuItem(name='Boneless Chilli', description='Boneless chicken in spicy sauce', price=249, category='Starters', emoji='🍗', popularity=8),
            MenuItem(name='Paneer Tikka', description='Grilled paneer cubes', price=199, category='Starters', emoji='🧀', popularity=8),
            MenuItem(name='Malai Paneer Tikka', description='Creamy paneer tikka', price=229, category='Starters', emoji='🧀', popularity=7),
            MenuItem(name='Chicken Lollipop', description='Chicken drumettes in spicy coating', price=199, category='Starters', emoji='🍗', popularity=8),

            # Main Course
            MenuItem(name='Dal Tadka', description='Yellow lentils with tempering', price=119, category='Main Course', emoji='🍛', popularity=7),
            MenuItem(name='Dal Makhni', description='Creamy black lentils', price=139, category='Main Course', emoji='🍛', popularity=8),
            MenuItem(name='Chana Masala', description='Spiced chickpeas curry', price=119, category='Main Course', emoji='🍛', popularity=6),
            MenuItem(name='Shahi Paneer', description='Paneer in rich tomato gravy', price=199, category='Main Course', emoji='🧀', popularity=9),
            MenuItem(name='Kadhai Paneer', description='Paneer cooked in kadhai style', price=199, category='Main Course', emoji='🧀', popularity=8),
            MenuItem(name='Paneer Butter Masala', description='Paneer in buttery tomato sauce', price=199, category='Main Course', emoji='🧀', popularity=9),
            MenuItem(name='Handi Paneer', description='Paneer cooked in clay pot style', price=209, category='Main Course', emoji='🧀', popularity=7),
            MenuItem(name='Kadhai Chicken', description='Chicken cooked kadhai style', price=249, category='Main Course', emoji='🍗', popularity=9),
            MenuItem(name='Butter Chicken', description='Chicken in creamy tomato sauce', price=269, category='Main Course', emoji='🍗', popularity=10),
            MenuItem(name='Chicken Curry', description='Traditional chicken curry', price=239, category='Main Course', emoji='🍗', popularity=8),
            MenuItem(name='Kaju Butter Masala', description='Cashew nuts in butter sauce', price=199, category='Main Course', emoji='🥜', popularity=6),
            MenuItem(name='Mushroom Masala', description='Mushrooms in spiced gravy', price=189, category='Main Course', emoji='🍄', popularity=5),
            MenuItem(name='Mushroom Curry', description='Mushroom curry with spices', price=189, category='Main Course', emoji='🍄', popularity=5),
        ]
        
        for item in menu_items:
            db.session.add(item)
        
        try:
            db.session.commit()
            print("Complete menu items added")
            
            # Add sample promotions if none exist
            if Promotion.query.count() == 0:
                sample_promotions = [
                    Promotion(
                        code='WELCOME10',
                        description='Welcome offer - 10% off on first order',
                        discount_type='percentage',
                        discount_value=10,
                        min_order_amount=100,
                        max_discount=100,
                        usage_limit=None,
                        expires_at=None,
                        is_active=True
                    ),
                    Promotion(
                        code='SAVE50',
                        description='Get flat ₹50 off on orders above ₹300',
                        discount_type='fixed',
                        discount_value=50,
                        min_order_amount=300,
                        max_discount=None,
                        usage_limit=None,
                        expires_at=None,
                        is_active=True
                    ),
                    Promotion(
                        code='BIRYANI20',
                        description='Special biryani discount - 20% off',
                        discount_type='percentage',
                        discount_value=20,
                        min_order_amount=200,
                        max_discount=150,
                        usage_limit=100,
                        expires_at=None,
                        is_active=True
                    )
                ]
                
                for promo in sample_promotions:
                    db.session.add(promo)
                
                db.session.commit()
                print('Sample promotions added')
        except Exception as e:
            db.session.rollback()
            print(f"Error adding menu items: {e}")
    
    # Import routes after everything is initialized
    import routes
