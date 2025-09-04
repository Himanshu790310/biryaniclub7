import qrcode
from io import BytesIO
import base64
from datetime import datetime, timedelta
import re
import pytz
from flask import session
from models import User, StoreSettings, CartItem, MenuItem, Promotion
from app import db

def generate_qr_code(data, amount=None):
    """Generate QR code for UPI payment"""
    if amount:
        # UPI payment string format
        upi_string = f"upi://pay?pa=7903102794@ptsbi&pn=Biryani Club&am={amount}&cu=INR&tn=Order Payment"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upi_string)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        # Convert to base64 for HTML embedding
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    return None

def is_store_open():
    """Check if store is currently open"""
    try:
        store_status = StoreSettings.get_setting('store_open', 'true')
        return store_status and store_status.lower() == 'true'
    except:
        return True

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def get_cart_items(user_id=None):
    """Get cart items for a user"""
    if not user_id and 'user_id' in session:
        user_id = session['user_id']

    if user_id:
        cart_items = CartItem.query.filter_by(user_id=user_id).join(MenuItem).all()
        return [
            {
                'id': item.menu_item.id,
                'name': item.menu_item.name,
                'price': item.menu_item.price,
                'quantity': item.quantity,
                'total': item.total,
                'emoji': item.menu_item.emoji
            }
            for item in cart_items
        ]
    return []

def get_cart_total(user_id=None):
    """Calculate cart total for a user"""
    cart_items = get_cart_items(user_id)
    return sum(item['total'] for item in cart_items)

def get_cart_count(user_id=None):
    """Get cart items count"""
    cart_items = get_cart_items(user_id)
    return sum(item['quantity'] for item in cart_items)

def clear_user_cart(user_id):
    """Clear all items from user's cart"""
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()

def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return False
    # Remove all non-digits
    cleaned = re.sub(r'\D', '', phone)
    # Check if it's between 10-15 digits
    return 10 <= len(cleaned) <= 15

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def find_user_by_login(identifier):
    """Find user by username or phone number"""
    # First try to find by username
    user = User.query.filter_by(username=identifier).first()
    if user:
        return user

    # Clean the identifier and check if it looks like a phone number
    cleaned_identifier = re.sub(r'\D', '', identifier)

    # If it's likely a phone number, search by phone
    if len(cleaned_identifier) >= 10 and len(cleaned_identifier) <= 15:
        # Try exact match first
        user = User.query.filter_by(phone=cleaned_identifier).first()
        if user:
            return user

        # Try with original input (in case it has formatting)
        user = User.query.filter_by(phone=identifier).first()
        if user:
            return user

    return None

def apply_coupon(coupon_code, subtotal):
    """Apply coupon and return discount amount"""
    if not coupon_code:
        return 0

    from models import Promotion

    # Find promotion in database
    promotion = Promotion.query.filter_by(code=coupon_code.upper().strip()).first()

    if not promotion:
        return 0

    if not promotion.is_valid:
        return 0

    # Check minimum order amount
    if subtotal < promotion.min_order_amount:
        return 0

    return promotion.calculate_discount(subtotal)

def calculate_delivery_charges(subtotal):
    """Calculate delivery charges based on order amount"""
    if subtotal >= 200:
        return 0  # Free delivery for orders 200rs and above
    elif subtotal >= 150:
        return 15  # 15rs delivery for orders 150rs and above
    elif subtotal >= 100:
        return 25  # 25rs delivery for orders 100rs and above
    else:
        return 25  # Default delivery charge for orders below 100rs

def get_popular_items(limit=6):
    """Get popular menu items"""
    try:
        return MenuItem.query.filter_by(in_stock=True).order_by(MenuItem.popularity.desc()).limit(limit).all()
    except:
        return []

def get_categories():
    """Get all menu categories"""
    try:
        categories = db.session.query(MenuItem.category).distinct().all()
        return [cat[0] for cat in categories]
    except:
        return []

def format_phone_display(phone):
    """Format phone number for display"""
    if not phone:
        return ""

    cleaned = re.sub(r'\D', '', phone)
    if len(cleaned) == 10:
        return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
    return phone

def get_order_progress_percentage(status):
    """Get order progress percentage based on status"""
    status_progress = {
        'pending': 10,
        'confirmed': 25,
        'preparing': 50,
        'out_for_delivery': 75,
        'delivered': 100,
        'cancelled': 0
    }
    return status_progress.get(status, 0)

def generate_random_order_id():
    """Generate a random 8-digit order ID"""
    import random
    return str(random.randint(10000000, 99999999))

def get_ist_time():
    """Get current time in IST timezone"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def utc_to_ist(utc_datetime):
    """Convert UTC datetime to IST"""
    if not utc_datetime:
        return None
    ist = pytz.timezone('Asia/Kolkata')
    utc_time = utc_datetime.replace(tzinfo=pytz.utc)
    return utc_time.astimezone(ist)

def format_ist_datetime(dt, format_str='%d %b %Y, %I:%M %p IST'):
    """Format datetime in IST with default format"""
    if not dt:
        return ''
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = utc_to_ist(dt)
    elif dt.tzinfo != pytz.timezone('Asia/Kolkata'):
        # Convert to IST if different timezone
        dt = dt.astimezone(pytz.timezone('Asia/Kolkata'))
    return dt.strftime(format_str) if dt else ''