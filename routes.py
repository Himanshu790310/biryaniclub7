
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import pytz

# Import app and db from the main app module
from app import app, db
from models import User, MenuItem, CartItem, Order, OrderItem, StoreSettings, Promotion
from utils import (
    is_store_open, get_current_user, get_cart_items, get_cart_total, 
    get_cart_count, clear_user_cart, validate_phone, validate_email,
    find_user_by_login, apply_coupon, get_popular_items, get_categories,
    generate_qr_code, get_order_progress_percentage, calculate_delivery_charges,
    get_ist_time, format_ist_datetime
)

@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    ist_timezone = pytz.timezone('Asia/Kolkata')
    current_ist = datetime.now(ist_timezone)
    return {
        'store_open': is_store_open(),
        'get_current_user': get_current_user,
        'cart_count': get_cart_count(),
        'current_year': datetime.now().year,
        'get_order_progress_percentage': get_order_progress_percentage,
        'current_ist': current_ist
    }

@app.route('/')
def home():
    """Home page with popular items and categories"""
    popular_items = get_popular_items(6)
    categories = get_categories()
    
    return render_template('home.html', 
                         menu_items=popular_items,
                         categories=categories)

@app.route('/menu')
def menu():
    """Menu page with filtering and search"""
    search_term = request.args.get('search', '').strip()
    category_filter = request.args.get('category', 'all')
    
    # Base query
    query = MenuItem.query.filter_by(in_stock=True)
    
    # Apply search filter
    if search_term:
        query = query.filter(MenuItem.name.ilike(f'%{search_term}%'))
    
    # Apply category filter
    if category_filter != 'all':
        query = query.filter_by(category=category_filter)
    
    # Get results
    menu_items = query.order_by(MenuItem.popularity.desc()).all()
    categories = get_categories()
    
    return render_template('menu.html',
                         menu_items=menu_items,
                         categories=categories,
                         search_term=search_term,
                         current_category=category_filter)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """Add item to cart (requires login)"""
    if 'user_id' not in session:
        flash('Please log in to add items to cart', 'warning')
        return redirect(url_for('login'))
    
    if not is_store_open():
        flash('Sorry, we are currently closed', 'error')
        return redirect(url_for('menu'))
    
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    # Validate quantity
    if quantity < 1 or quantity > 10:
        flash('Invalid quantity', 'error')
        return redirect(url_for('menu'))
    
    # Check if item exists
    menu_item = MenuItem.query.get(item_id)
    if not menu_item or not menu_item.in_stock:
        flash('Item not available', 'error')
        return redirect(url_for('menu'))
    
    # Check if item already in cart
    existing_item = CartItem.query.filter_by(
        user_id=session['user_id'],
        menu_item_id=item_id
    ).first()
    
    if existing_item:
        # Update quantity
        existing_item.quantity += quantity
        if existing_item.quantity > 10:
            existing_item.quantity = 10
    else:
        # Add new item
        cart_item = CartItem(
            user_id=session['user_id'],
            menu_item_id=item_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    flash(f'{menu_item.name} added to cart!', 'success')
    return redirect(url_for('menu'))

@app.route('/cart')
def cart():
    """Shopping cart page"""
    if 'user_id' not in session:
        return render_template('cart.html', cart_items=[], subtotal=0, total=0, discount=0)
    
    cart_items = get_cart_items()
    subtotal = sum(item['total'] for item in cart_items)
    discount = 0  # Can be calculated based on coupons
    total = subtotal - discount
    
    return render_template('cart.html',
                         cart_items=cart_items,
                         subtotal=subtotal,
                         discount=discount,
                         total=total)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    """Update cart item quantity"""
    if 'user_id' not in session:
        flash('Please log in first', 'warning')
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 0))
    
    # Find cart item
    cart_item = CartItem.query.filter_by(
        user_id=session['user_id'],
        menu_item_id=item_id
    ).first()
    
    if cart_item:
        if quantity <= 0:
            # Remove item
            db.session.delete(cart_item)
            flash('Item removed from cart', 'info')
        else:
            # Update quantity
            cart_item.quantity = min(quantity, 10)
            flash('Cart updated', 'success')
        
        db.session.commit()
    
    return redirect(url_for('cart'))

@app.route('/clear_cart')
def clear_cart():
    """Clear all items from cart"""
    if 'user_id' in session:
        clear_user_cart(session['user_id'])
        flash('Cart cleared', 'info')
    
    return redirect(url_for('cart'))

@app.route('/checkout')
def checkout():
    """Checkout page - supports guest checkout"""
    cart_items = []
    subtotal = 0
    
    if 'user_id' in session:
        cart_items = get_cart_items()
        subtotal = sum(item['total'] for item in cart_items)
    
    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('menu'))
    
    if not is_store_open():
        flash('Sorry, we are currently closed', 'error')
        return redirect(url_for('cart'))
    
    # Calculate delivery charges
    delivery_charges = calculate_delivery_charges(subtotal)
    
    # Apply coupon if provided
    coupon_code = request.args.get('coupon')
    discount = apply_coupon(coupon_code, subtotal) if coupon_code else 0
    total = subtotal + delivery_charges - discount
    
    # Get available promotions for display
    available_promotions = Promotion.query.filter_by(is_active=True).filter(
        Promotion.expires_at.is_(None) | (Promotion.expires_at > datetime.utcnow())
    ).limit(8).all()
    
    return render_template('checkout.html',
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery_charges=delivery_charges,
                         discount=discount,
                         total=total,
                         coupon_code=coupon_code,
                         available_promotions=available_promotions)

@app.route('/checkout', methods=['POST'])
def process_checkout():
    """Process checkout and create order"""
    if not is_store_open():
        flash('Sorry, we are currently closed', 'error')
        return redirect(url_for('cart'))
    
    # Get form data
    customer_name = request.form.get('customer_name', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    customer_address = request.form.get('customer_address', '').strip()
    payment_method = request.form.get('payment_method', 'cash')
    coupon_code = request.form.get('coupon_code', '').strip()
    
    # Validation
    if not all([customer_name, customer_phone, customer_address]):
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('checkout'))
    
    if not validate_phone(customer_phone):
        flash('Please enter a valid phone number', 'error')
        return redirect(url_for('checkout'))
    
    # Get cart items
    cart_items = []
    user_id = session.get('user_id')
    
    if user_id:
        cart_items = get_cart_items(user_id)
    
    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('menu'))
    
    # Calculate totals
    subtotal = sum(item['total'] for item in cart_items)
    delivery_charges = calculate_delivery_charges(subtotal)
    discount = 0
    
    # Validate and apply coupon
    if coupon_code:
        promotion = Promotion.query.filter_by(code=coupon_code.upper().strip()).first()
        if promotion and promotion.is_valid and subtotal >= promotion.min_order_amount:
            discount = promotion.calculate_discount(subtotal)
            # Mark coupon as used
            promotion.use_promotion()
        else:
            # Invalid coupon, redirect back with error
            flash('Invalid or expired coupon code', 'error')
            return redirect(url_for('checkout'))
    
    total = subtotal + delivery_charges - discount
    
    try:
        # Create order
        order = Order(
            user_id=user_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_address=customer_address,
            subtotal=subtotal,
            delivery_charges=delivery_charges,
            discount=discount,
            total_amount=total,
            payment_method=payment_method,
            coupon_code=coupon_code if coupon_code else None,
            order_number=Order.generate_order_number()
        )
        
        # Add guest info if not logged in
        if not user_id:
            order.guest_name = customer_name
            order.guest_phone = customer_phone
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Create order items
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=cart_item['id'],
                quantity=cart_item['quantity'],
                unit_price=cart_item['price'],
                total_price=cart_item['total']
            )
            db.session.add(order_item)
        
        # Clear cart if user is logged in
        if user_id:
            clear_user_cart(user_id)
        
        db.session.commit()
        
        # Redirect based on payment method
        if payment_method == 'upi':
            return redirect(url_for('upi_payment', order_id=order.id))
        else:
            # Cash on delivery - mark as confirmed
            order.payment_status = 'confirmed'
            order.confirmed_at = datetime.utcnow()
            db.session.commit()
            flash('Order placed successfully!', 'success')
            return redirect(url_for('order_confirmation', order_id=order.id))
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Checkout error: {e}")
        flash('An error occurred while processing your order. Please try again.', 'error')
        return redirect(url_for('checkout'))

@app.route('/upi_payment/<int:order_id>')
def upi_payment(order_id):
    """UPI payment page with QR code"""
    order = Order.query.get_or_404(order_id)
    
    # Generate QR code for payment
    qr_code = generate_qr_code(order.order_number, order.total_amount)
    
    return render_template('upi_payment.html', 
                         order=order,
                         qr_code=qr_code)

@app.route('/confirm_payment/<int:order_id>', methods=['POST'])
def confirm_payment(order_id):
    """Confirm UPI payment"""
    order = Order.query.get_or_404(order_id)
    
    # Update order status
    order.payment_status = 'confirmed'
    order.confirmed_at = datetime.utcnow()
    db.session.commit()
    
    flash('Payment confirmed! Your order is being prepared.', 'success')
    return redirect(url_for('order_confirmation', order_id=order.id))

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    """Order confirmation page"""
    order = Order.query.get_or_404(order_id)
    return render_template('order_confirmation.html', order=order)

@app.route('/my_orders')
def my_orders():
    """User's order history (requires login)"""
    if 'user_id' not in session:
        flash('Please log in to view your orders', 'warning')
        return redirect(url_for('login'))
    
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    
    # Get current IST time for last updated
    ist_timezone = pytz.timezone('Asia/Kolkata')
    current_ist = datetime.now(ist_timezone)
    
    return render_template('my_orders.html', orders=orders, current_ist=current_ist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - supports username or phone number"""
    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()  # Can be username or phone
        password = request.form.get('password', '')
        next_page = request.form.get('next')
        
        if not identifier or not password:
            flash('Please enter both username/phone and password', 'error')
            return render_template('login.html', next=next_page)
        
        # Find user by username or phone
        user = find_user_by_login(identifier)
        
        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_role'] = user.role
            
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            
            # Redirect to next page or appropriate dashboard
            if next_page:
                return redirect(next_page)
            elif user.is_admin():
                return redirect(url_for('admin'))
            elif user.is_delivery_person():
                return redirect(url_for('delivery_dashboard'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid username/phone or password', 'error')
    
    next_page = request.args.get('next')
    return render_template('login.html', next=next_page)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters')
        
        if not email or not validate_email(email):
            errors.append('Please enter a valid email address')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if phone and not validate_phone(phone):
            errors.append('Please enter a valid phone number')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if phone and User.query.filter_by(phone=phone).first():
            errors.append('Phone number already registered')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Create user
        try:
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                phone=phone.replace(' ', '').replace('-', '') if phone else None
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Registration error: {e}")
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    """Admin dashboard"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    # Get dashboard statistics
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    today_orders = Order.query.filter(Order.created_at >= datetime.now().date()).count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).filter_by(payment_status='confirmed').scalar() or 0
    
    # Recent orders
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    
    return render_template('admin.html',
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         today_orders=today_orders,
                         total_revenue=total_revenue,
                         recent_orders=recent_orders)

@app.route('/admin/toggle_store', methods=['POST'])
def toggle_store():
    """Toggle store open/close status"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    current_status = is_store_open()
    new_status = 'false' if current_status else 'true'
    
    StoreSettings.set_setting('store_open', new_status)
    
    status_text = 'opened' if new_status == 'true' else 'closed'
    flash(f'Store has been {status_text}', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/orders')
def admin_orders():
    """Admin orders management"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    status_filter = request.args.get('status', 'all')
    
    # Base query
    query = Order.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return render_template('admin_orders.html', orders=orders, status_filter=status_filter)

@app.route('/admin/update_order_status', methods=['POST'])
def update_order_status():
    """Update order status"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    order = Order.query.get_or_404(order_id)
    order.status = new_status
    
    if new_status == 'delivered':
        order.delivery_time = datetime.utcnow()
    
    db.session.commit()
    
    flash(f'Order {order.order_number} status updated to {new_status}', 'success')
    return redirect(url_for('admin_orders'))

# User Management Routes
@app.route('/admin/users')
def admin_users():
    """Admin user management"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    # Get all users with filtering
    role_filter = request.args.get('role', 'all')
    status_filter = request.args.get('status', 'all')
    
    query = User.query
    
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    users = query.order_by(User.created_at.desc()).all()
    
    return render_template('admin_users.html', 
                         users=users, 
                         role_filter=role_filter,
                         status_filter=status_filter)

@app.route('/admin/users/<int:user_id>/toggle_status', methods=['POST'])
def toggle_user_status(user_id):
    """Toggle user active/inactive status"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    current_user = get_current_user()
    if not current_user or not current_user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    user_to_toggle = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user_to_toggle.id == current_user.id:
        flash('You cannot deactivate your own account', 'error')
        return redirect(url_for('admin_users'))
    
    user_to_toggle.is_active = not user_to_toggle.is_active
    db.session.commit()
    
    status_text = 'activated' if user_to_toggle.is_active else 'deactivated'
    flash(f'User {user_to_toggle.username} has been {status_text}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    """Edit user details"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    current_user = get_current_user()
    if not current_user or not current_user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    user_to_edit = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            user_to_edit.full_name = request.form.get('full_name', '').strip()
            user_to_edit.email = request.form.get('email', '').strip().lower()
            user_to_edit.phone = request.form.get('phone', '').strip()
            
            # Only allow role change if not editing own account
            if user_to_edit.id != current_user.id:
                user_to_edit.role = request.form.get('role', 'customer')
            
            db.session.commit()
            flash(f'User {user_to_edit.username} updated successfully', 'success')
            return redirect(url_for('admin_users'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"User edit error: {e}")
            flash('Error updating user. Please try again.', 'error')
    
    return render_template('admin_edit_user.html', user_to_edit=user_to_edit)

# Menu Management Routes
@app.route('/admin/menu')
def admin_menu():
    """Admin menu management"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    # Get all menu items
    category_filter = request.args.get('category', 'all')
    status_filter = request.args.get('status', 'all')
    
    query = MenuItem.query
    
    if category_filter != 'all':
        query = query.filter_by(category=category_filter)
    
    if status_filter == 'available':
        query = query.filter_by(in_stock=True)
    elif status_filter == 'unavailable':
        query = query.filter_by(in_stock=False)
    
    menu_items = query.order_by(MenuItem.category, MenuItem.name).all()
    categories = get_categories()
    
    return render_template('admin_menu.html', 
                         menu_items=menu_items,
                         categories=categories,
                         category_filter=category_filter,
                         status_filter=status_filter)

@app.route('/admin/menu/<int:item_id>/toggle_stock', methods=['POST'])
def toggle_menu_item_stock(item_id):
    """Toggle menu item in_stock status"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    menu_item = MenuItem.query.get_or_404(item_id)
    menu_item.in_stock = not menu_item.in_stock
    db.session.commit()
    
    status_text = 'listed' if menu_item.in_stock else 'delisted'
    flash(f'{menu_item.name} has been {status_text}', 'success')
    return redirect(url_for('admin_menu'))

@app.route('/admin/menu/add', methods=['GET', 'POST'])
def add_menu_item():
    """Add new menu item"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            new_item = MenuItem(
                name=request.form.get('name', '').strip(),
                description=request.form.get('description', '').strip(),
                price=float(request.form.get('price', 0)),
                category=request.form.get('category', ''),
                emoji=request.form.get('emoji', ''),
                in_stock=True,
                popularity=0
            )
            
            db.session.add(new_item)
            db.session.commit()
            
            flash(f'{new_item.name} added to menu successfully', 'success')
            return redirect(url_for('admin_menu'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Add menu item error: {e}")
            flash('Error adding menu item. Please try again.', 'error')
    
    categories = get_categories()
    return render_template('admin_add_menu_item.html', categories=categories)

@app.route('/admin/menu/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_menu_item(item_id):
    """Edit menu item"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    menu_item = MenuItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        try:
            menu_item.name = request.form.get('name', '').strip()
            menu_item.description = request.form.get('description', '').strip()
            menu_item.price = float(request.form.get('price', 0))
            menu_item.category = request.form.get('category', '')
            menu_item.emoji = request.form.get('emoji', '')
            
            db.session.commit()
            flash(f'{menu_item.name} updated successfully', 'success')
            return redirect(url_for('admin_menu'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Edit menu item error: {e}")
            flash('Error updating menu item. Please try again.', 'error')
    
    categories = get_categories()
    return render_template('admin_edit_menu_item.html', menu_item=menu_item, categories=categories)

# Promotion Management Routes
@app.route('/admin/promotions')
def admin_promotions():
    """Admin promotion management"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    # Get all promotions
    status_filter = request.args.get('status', 'all')
    
    query = Promotion.query
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'expired':
        query = query.filter(Promotion.expires_at < datetime.utcnow())
    
    promotions = query.order_by(Promotion.created_at.desc()).all()
    
    return render_template('admin_promotions.html', 
                         promotions=promotions,
                         status_filter=status_filter)

@app.route('/admin/promotions/add', methods=['GET', 'POST'])
def add_promotion():
    """Add new promotion"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            code = request.form.get('code', '').upper().strip()
            
            # Check if code already exists
            existing = Promotion.query.filter_by(code=code).first()
            if existing:
                flash('Promotion code already exists', 'error')
                return render_template('admin_add_promotion.html')
            
            expires_at = None
            if request.form.get('expires_at'):
                expires_at = datetime.strptime(request.form.get('expires_at'), '%Y-%m-%d')
            
            new_promotion = Promotion(
                code=code,
                description=request.form.get('description', '').strip(),
                discount_type=request.form.get('discount_type'),
                discount_value=float(request.form.get('discount_value', 0)),
                min_order_amount=float(request.form.get('min_order_amount', 0)),
                max_discount=float(request.form.get('max_discount')) if request.form.get('max_discount') else None,
                usage_limit=int(request.form.get('usage_limit')) if request.form.get('usage_limit') else None,
                expires_at=expires_at,
                is_active=True
            )
            
            db.session.add(new_promotion)
            db.session.commit()
            
            flash(f'Promotion {new_promotion.code} created successfully', 'success')
            return redirect(url_for('admin_promotions'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Add promotion error: {e}")
            flash('Error creating promotion. Please try again.', 'error')
    
    return render_template('admin_add_promotion.html')

@app.route('/admin/promotions/<int:promotion_id>/edit', methods=['GET', 'POST'])
def edit_promotion(promotion_id):
    """Edit promotion"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    promotion = Promotion.query.get_or_404(promotion_id)
    
    if request.method == 'POST':
        try:
            promotion.description = request.form.get('description', '').strip()
            promotion.discount_type = request.form.get('discount_type')
            promotion.discount_value = float(request.form.get('discount_value', 0))
            promotion.min_order_amount = float(request.form.get('min_order_amount', 0))
            promotion.max_discount = float(request.form.get('max_discount')) if request.form.get('max_discount') else None
            promotion.usage_limit = int(request.form.get('usage_limit')) if request.form.get('usage_limit') else None
            
            if request.form.get('expires_at'):
                promotion.expires_at = datetime.strptime(request.form.get('expires_at'), '%Y-%m-%d')
            else:
                promotion.expires_at = None
            
            db.session.commit()
            flash(f'Promotion {promotion.code} updated successfully', 'success')
            return redirect(url_for('admin_promotions'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Edit promotion error: {e}")
            flash('Error updating promotion. Please try again.', 'error')
    
    return render_template('admin_edit_promotion.html', promotion=promotion)

# =============================================================================
# DELIVERY PERSON ROUTES
# =============================================================================

@app.route('/delivery')
def delivery_dashboard():
    """Delivery person dashboard"""
    if 'user_id' not in session:
        flash('Please log in as delivery person', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_delivery_person():
        flash('Access denied - Delivery personnel only', 'error')
        return redirect(url_for('home'))
    
    # Get orders assigned to this delivery person
    assigned_orders = Order.query.filter_by(delivery_person_id=user.id).order_by(Order.created_at.desc()).all()
    
    # Get orders ready for delivery (confirmed/preparing status) that are unassigned
    available_orders = Order.query.filter(
        Order.status.in_(['confirmed', 'preparing']),
        Order.delivery_person_id.is_(None)
    ).order_by(Order.created_at.asc()).all()
    
    # Get dashboard statistics
    total_assigned = len(assigned_orders)
    delivered_today = Order.query.filter(
        Order.delivery_person_id == user.id,
        Order.status == 'delivered',
        Order.delivery_time >= datetime.now().date()
    ).count()
    
    return render_template('delivery_dashboard.html',
                         assigned_orders=assigned_orders,
                         available_orders=available_orders,
                         total_assigned=total_assigned,
                         delivered_today=delivered_today)

@app.route('/delivery/assign/<int:order_id>')
def assign_order(order_id):
    """Assign an order to the current delivery person"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_delivery_person():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.delivery_person_id:
        flash('Order already assigned to another delivery person', 'warning')
    else:
        order.delivery_person_id = user.id
        if order.status == 'confirmed':
            order.status = 'preparing'
        
        db.session.commit()
        flash(f'Order #{order.order_number} assigned to you', 'success')
    
    return redirect(url_for('delivery_dashboard'))

@app.route('/delivery/pickup/<int:order_id>')
def pickup_order(order_id):
    """Mark order as picked up (out for delivery)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_delivery_person():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.delivery_person_id != user.id:
        flash('You can only pick up orders assigned to you', 'error')
    else:
        order.status = 'out_for_delivery'
        db.session.commit()
        flash(f'Order #{order.order_number} marked as out for delivery', 'success')
    
    return redirect(url_for('delivery_dashboard'))

@app.route('/delivery/complete/<int:order_id>')
def complete_delivery(order_id):
    """Mark order as delivered"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_delivery_person():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.delivery_person_id != user.id:
        flash('You can only deliver orders assigned to you', 'error')
    else:
        from models import get_ist_now
        order.status = 'delivered'
        order.delivery_time = get_ist_now()
        order.payment_status = 'confirmed'  # Mark payment as confirmed on delivery
        
        # Add loyalty points to user (if registered user)
        if order.user_id:
            customer = User.query.get(order.user_id)
            if customer:
                points_earned = int(order.total_amount // 10)  # 1 point per 10rs spent
                customer.loyalty_points += points_earned
        
        db.session.commit()
        flash(f'Order #{order.order_number} marked as delivered!', 'success')
    
    return redirect(url_for('delivery_dashboard'))

# =============================================================================
# LOYALTY POINTS ROUTES
# =============================================================================

@app.route('/loyalty')
def loyalty_dashboard():
    """Loyalty points dashboard for customers"""
    if 'user_id' not in session:
        flash('Please log in to view your loyalty points', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('home'))
    
    tier_info = user.get_loyalty_tier_info()
    redeemable_amount = user.get_redeemable_amount()
    
    # Calculate points needed for next tier
    next_tier_points = 0
    if user.loyalty_tier == 'bronze':
        next_tier_points = 1000 - user.loyalty_points
    elif user.loyalty_tier == 'silver':
        next_tier_points = 2500 - user.loyalty_points
    elif user.loyalty_tier == 'gold':
        next_tier_points = 5000 - user.loyalty_points
    
    return render_template('loyalty_dashboard.html',
                         user=user,
                         tier_info=tier_info,
                         redeemable_amount=redeemable_amount,
                         next_tier_points=max(0, next_tier_points))

@app.route('/loyalty/redeem', methods=['POST'])
def redeem_loyalty_points():
    """Redeem loyalty points for discount"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('home'))
    
    try:
        points_to_redeem = int(request.form.get('points_to_redeem', 0))
        success, result = user.redeem_points(points_to_redeem)
        
        if success:
            db.session.commit()
            flash(f'Successfully redeemed {points_to_redeem} points for ₹{result}!', 'success')
        else:
            flash(result, 'error')
            
    except (ValueError, TypeError):
        flash('Invalid points amount', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Error processing redemption. Please try again.', 'error')
        app.logger.error(f"Points redemption error: {e}")
    
    return redirect(url_for('loyalty_dashboard'))



@app.route('/admin/promotions/<int:promotion_id>/toggle_status', methods=['POST'])
def toggle_promotion_status(promotion_id):
    """Toggle promotion active/inactive status"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    promotion = Promotion.query.get_or_404(promotion_id)
    promotion.is_active = not promotion.is_active
    db.session.commit()
    
    status_text = 'activated' if promotion.is_active else 'deactivated'
    flash(f'Promotion {promotion.code} has been {status_text}', 'success')
    return redirect(url_for('admin_promotions'))

@app.route('/admin/promotions/<int:promotion_id>/delete', methods=['POST'])
def delete_promotion(promotion_id):
    """Delete promotion"""
    if 'user_id' not in session:
        flash('Please log in as admin', 'warning')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user or not user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('home'))
    
    promotion = Promotion.query.get_or_404(promotion_id)
    code = promotion.code
    
    db.session.delete(promotion)
    db.session.commit()
    
    flash(f'Promotion {code} has been deleted', 'success')
    return redirect(url_for('admin_promotions'))

# API Routes for AJAX calls (minimal usage as per guidelines)

@app.route('/api/cart_count')
def api_cart_count():
    """API endpoint for cart count"""
    count = get_cart_count()
    return jsonify({'count': count})

@app.route('/api/order_status/<order_number>')
def api_order_status(order_number):
    """API endpoint for real-time order status"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    
    return jsonify({
        'status': order.status,
        'status_display': order.status.title().replace('_', ' '),
        'progress_percentage': get_order_progress_percentage(order.status),
        'payment_status': order.payment_status,
        'estimated_time': '30-45 minutes',
        'last_updated': order.created_at_ist.strftime('%I:%M %p IST'),
        'order_items_count': len(order.order_items),
        'total_amount': order.total_amount
    })

@app.route('/api/validate_coupon', methods=['POST'])
def api_validate_coupon():
    """API endpoint for coupon validation"""
    try:
        data = request.get_json()
        coupon_code = data.get('coupon_code', '').upper().strip()
        subtotal = float(data.get('subtotal', 0))
        
        if not coupon_code:
            return jsonify({
                'valid': False,
                'message': 'Please enter a coupon code'
            })
        
        # Find promotion
        promotion = Promotion.query.filter_by(code=coupon_code).first()
        
        if not promotion:
            return jsonify({
                'valid': False,
                'message': 'Coupon code not found'
            })
        
        if not promotion.is_valid:
            if not promotion.is_active:
                return jsonify({
                    'valid': False,
                    'message': 'This coupon is no longer active'
                })
            elif promotion.is_expired:
                return jsonify({
                    'valid': False,
                    'message': 'This coupon has expired'
                })
            elif promotion.is_usage_exceeded:
                return jsonify({
                    'valid': False,
                    'message': 'This coupon has reached its usage limit'
                })
        
        if subtotal < promotion.min_order_amount:
            return jsonify({
                'valid': False,
                'message': f'Minimum order amount is ₹{promotion.min_order_amount:.0f}'
            })
        
        discount = promotion.calculate_discount(subtotal)
        
        # Format discount message
        if promotion.discount_type == 'percentage':
            discount_text = f'{promotion.discount_value:.0f}% discount'
        else:
            discount_text = f'₹{discount:.0f} discount'
        
        return jsonify({
            'valid': True,
            'message': f'Success! {discount_text} applied to your order',
            'discount': discount,
            'new_total': subtotal - discount,
            'code': coupon_code
        })
            
    except Exception as e:
        app.logger.error(f"Coupon validation error: {e}")
        return jsonify({
            'valid': False,
            'message': 'Error validating coupon. Please try again.'
        })

# Error handlers

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
