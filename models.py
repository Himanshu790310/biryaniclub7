from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
import re
import random
import string
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_ist_now():
    """Get current IST time"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).replace(tzinfo=None)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(15), unique=True)
    role = db.Column(db.String(20), default='customer')  # customer, admin, delivery
    loyalty_points = db.Column(db.Integer, default=0)
    loyalty_tier = db.Column(db.String(20), default='bronze')  # bronze, silver, gold, platinum
    created_at = db.Column(db.DateTime, default=get_ist_now)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    orders = db.relationship('Order', foreign_keys='Order.user_id', backref='user', lazy=True)
    delivered_orders = db.relationship('Order', foreign_keys='Order.delivery_person_id', backref='delivery_person_user', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_delivery_person(self):
        return self.role == 'delivery'
    
    def get_loyalty_tier_info(self):
        """Get loyalty tier information based on points"""
        tiers = {
            'bronze': {'min_points': 0, 'max_points': 999, 'conversion_rate': 5, 'color': '#CD7F32'},
            'silver': {'min_points': 1000, 'max_points': 2499, 'conversion_rate': 4, 'color': '#C0C0C0'},
            'gold': {'min_points': 2500, 'max_points': 4999, 'conversion_rate': 3, 'color': '#FFD700'},
            'platinum': {'min_points': 5000, 'max_points': float('inf'), 'conversion_rate': 2, 'color': '#E5E4E2'}
        }
        
        # Update tier based on current points
        current_tier = 'bronze'
        for tier, info in tiers.items():
            if info['min_points'] <= self.loyalty_points <= info['max_points']:
                current_tier = tier
                break
        
        # Update tier if changed
        if self.loyalty_tier != current_tier:
            self.loyalty_tier = current_tier
            
        return tiers[current_tier]
    
    def get_redeemable_amount(self):
        """Calculate how much money can be redeemed from points"""
        if self.loyalty_points < 100:  # Minimum redemption is 100 points
            return 0
        
        tier_info = self.get_loyalty_tier_info()
        conversion_rate = tier_info['conversion_rate']  # points needed for 1 rupee
        return self.loyalty_points // conversion_rate
    
    def redeem_points(self, points_to_redeem):
        """Redeem loyalty points for money"""
        if points_to_redeem < 100:
            return False, "Minimum redemption is 100 points"
        
        if points_to_redeem > self.loyalty_points:
            return False, "Insufficient points"
        
        tier_info = self.get_loyalty_tier_info()
        conversion_rate = tier_info['conversion_rate']
        redeemed_amount = points_to_redeem // conversion_rate
        
        self.loyalty_points -= points_to_redeem
        return True, redeemed_amount

    def __repr__(self):
        return f'<User {self.username}>'

class MenuItem(db.Model):
    __tablename__ = 'menu_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    emoji = db.Column(db.String(10))
    in_stock = db.Column(db.Boolean, default=True)
    popularity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_ist_now)

    def __repr__(self):
        return f'<MenuItem {self.name}>'

class CartItem(db.Model):
    __tablename__ = 'cart_item'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=get_ist_now)

    # Relationships
    menu_item = db.relationship('MenuItem', backref='cart_items')

    @property
    def total(self):
        return self.quantity * self.menu_item.price

    def __repr__(self):
        return f'<CartItem {self.menu_item.name} x{self.quantity}>'

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for guest orders
    
    # Guest customer info (for non-registered users)
    guest_name = db.Column(db.String(100))
    guest_phone = db.Column(db.String(15))
    guest_email = db.Column(db.String(120))
    
    # Order details
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(15), nullable=False)
    customer_address = db.Column(db.Text, nullable=False)
    
    # Payment and totals
    subtotal = db.Column(db.Float, nullable=False)
    delivery_charges = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, upi
    payment_status = db.Column(db.String(20), default='pending')  # pending, confirmed, failed
    coupon_code = db.Column(db.String(20))
    
    # Order status and tracking
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    created_at = db.Column(db.DateTime, default=get_ist_now)
    confirmed_at = db.Column(db.DateTime)
    delivery_time = db.Column(db.DateTime)
    
    # Delivery
    delivery_person_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    delivery_notes = db.Column(db.Text)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    @property
    def is_guest_order(self):
        return self.user_id is None

    # Add random order number field
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    
    @staticmethod
    def generate_order_number():
        """Generate random order number"""
        prefix = "BC"
        random_part = ''.join(random.choices(string.digits, k=6))
        return f"{prefix}{random_part}"
    
    @property
    def created_at_ist(self):
        """Return created_at time (already in IST)"""
        return self.created_at
    
    @property
    def confirmed_at_ist(self):
        """Return confirmed_at time (already in IST)"""
        return self.confirmed_at
    
    @property
    def delivery_time_ist(self):
        """Return delivery_time (already in IST)"""
        return self.delivery_time

    @property
    def customer_display_name(self):
        if self.is_guest_order:
            return f"{self.guest_name or self.customer_name} (Guest)"
        return self.user.full_name or self.user.username

    def __repr__(self):
        return f'<Order {self.order_number}>'

class OrderItem(db.Model):
    __tablename__ = 'order_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    # Relationships
    menu_item = db.relationship('MenuItem')

    def __repr__(self):
        return f'<OrderItem {self.menu_item.name} x{self.quantity}>'

class StoreSettings(db.Model):
    __tablename__ = 'store_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=get_ist_now)

    @staticmethod
    def get_setting(key, default_value=None):
        setting = StoreSettings.query.filter_by(key=key).first()
        return setting.value if setting else default_value

    @staticmethod
    def set_setting(key, value):
        setting = StoreSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = get_ist_now()
        else:
            setting = StoreSettings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

    def __repr__(self):
        return f'<StoreSettings {self.key}: {self.value}>'

class Promotion(db.Model):
    __tablename__ = 'promotion'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), nullable=False)  # 'percentage' or 'fixed'
    discount_value = db.Column(db.Float, nullable=False)
    min_order_amount = db.Column(db.Float, default=0)
    max_discount = db.Column(db.Float)  # For percentage discounts
    usage_limit = db.Column(db.Integer)  # Max number of uses
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_ist_now)
    expires_at = db.Column(db.DateTime)

    @property
    def created_at_ist(self):
        """Return created_at time (already in IST)"""
        return self.created_at

    @property
    def expires_at_ist(self):
        """Return expires_at time (already in IST)"""
        return self.expires_at

    @property
    def is_expired(self):
        """Check if promotion has expired"""
        if self.expires_at:
            return get_ist_now() > self.expires_at
        return False

    @property
    def is_usage_exceeded(self):
        """Check if usage limit has been exceeded"""
        if self.usage_limit:
            return self.used_count >= self.usage_limit
        return False

    @property
    def is_valid(self):
        """Check if promotion is valid for use"""
        return (self.is_active and 
                not self.is_expired and 
                not self.is_usage_exceeded)

    def calculate_discount(self, subtotal):
        """Calculate discount amount for given subtotal"""
        if not self.is_valid or subtotal < self.min_order_amount:
            return 0

        if self.discount_type == 'percentage':
            discount = subtotal * (self.discount_value / 100)
            if self.max_discount:
                discount = min(discount, self.max_discount)
            return discount
        else:  # fixed amount
            return min(self.discount_value, subtotal)

    def use_promotion(self):
        """Mark promotion as used"""
        self.used_count += 1
        db.session.commit()

    def __repr__(self):
        return f'<Promotion {self.code}>'

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_ist_now)

    def __repr__(self):
        return f'<Category {self.name}>'
