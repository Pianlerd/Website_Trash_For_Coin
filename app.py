from flask import Flask, render_template, request, redirect, url_for, session, Response, make_response, flash, jsonify
from xhtml2pdf import pisa
import mysql.connector
import csv
from io import StringIO, BytesIO
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'trash-for-coin-secret-key-2025'

# --- Database Connection ---
def get_db_connection():
    """
    Establishes a connection to the MySQL database.
    Returns the connection object or None if connection fails.
    """
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="project_bin"
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- Role-based Access Control (RBAC) Decorators ---
def role_required(allowed_roles):
    """
    Decorator to restrict access to routes based on user roles.
    If the user is not logged in, they are redirected to the login page.
    If the user's role is not in the allowed_roles list, they are redirected to the index page.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'loggedin' not in session:
                flash('โปรดเข้าสู่ระบบเพื่อเข้าถึงหน้านี้', 'danger')
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash(f'คุณไม่มีสิทธิ์เข้าถึงหน้านี้ ยศของคุณคือ {session.get("role")}', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Routes ---

@app.route("/")
def root_redirect():
    """Redirects the root URL to the index page."""
    return redirect(url_for("index"))

@app.route("/index", methods=["GET", "POST"])
def index():
    """
    Home page of the Trash For Coin system, displaying usage statistics.
    Statistics are only fetched and displayed if a user is logged in.
    """
    stats = {
        'total_products': 0,
        'total_orders': 0,
        'total_categories': 0,
        'total_users': 0
    }
    
    if session.get('loggedin'):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Fetch total products
                cursor.execute("SELECT COUNT(*) FROM tbl_products")
                stats['total_products'] = cursor.fetchone()[0]
                
                # Fetch total orders
                cursor.execute("SELECT COUNT(*) FROM tbl_order")
                stats['total_orders'] = cursor.fetchone()[0]
                
                # Fetch total categories
                cursor.execute("SELECT COUNT(*) FROM tbl_category")
                stats['total_categories'] = cursor.fetchone()[0]

                # Fetch total users (only for admin/moderator roles)
                if session.get('role') in ['root_admin', 'administrator', 'moderator']:
                    cursor.execute("SELECT COUNT(*) FROM tbl_users")
                    stats['total_users'] = cursor.fetchone()[0]
                
            except mysql.connector.Error as err:
                print(f"Error fetching stats: {err}")
            finally:
                cursor.close()
                conn.close()
    
    return render_template("index.html", stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    Authenticates user credentials against tbl_users table.
    Sets session variables upon successful login.
    """
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM tbl_users WHERE email = %s AND password = %s', (email, password,))
            account = cursor.fetchone()
            
            if account:
                session['loggedin'] = True
                session['id'] = account['id']
                session['email'] = account['email']
                session['firstname'] = account['firstname']
                session['lastname'] = account['lastname']
                session['role'] = account['role']
                msg = 'เข้าสู่ระบบสำเร็จ!'
                flash(msg, 'success')
                return redirect(url_for('index'))
            else:
                msg = 'อีเมลหรือรหัสผ่านไม่ถูกต้อง!'
                flash(msg, 'danger')
            cursor.close()
            conn.close()
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration.
    Inserts new user data into tbl_users table with 'member' role by default.
    Checks for existing email addresses.
    """
    msg = ''
    if request.method == 'POST' and 'firstname' in request.form and 'lastname' in request.form and 'email' in request.form and 'password' in request.form:
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM tbl_users WHERE email = %s', (email,))
            account = cursor.fetchone()
            
            if account:
                msg = 'บัญชีนี้มีอยู่แล้ว!'
                flash(msg, 'danger')
            elif not firstname or not lastname or not email or not password:
                msg = 'กรุณากรอกข้อมูลให้ครบถ้วน!'
                flash(msg, 'danger')
            else:
                cursor.execute('INSERT INTO tbl_users (firstname, lastname, email, password, role) VALUES (%s, %s, %s, %s, %s)', (firstname, lastname, email, password, 'member',))
                conn.commit()
                msg = 'คุณสมัครสมาชิกสำเร็จแล้ว!'
                flash(msg, 'success')
                return redirect(url_for('login'))
            cursor.close()
            conn.close()
    elif request.method == 'POST':
        msg = 'กรุณากรอกข้อมูลให้ครบถ้วน!'
        flash(msg, 'danger')
    return render_template('register.html', msg=msg)

@app.route('/profile', methods=['GET', 'POST'])
@role_required(['root_admin', 'administrator', 'moderator', 'member', 'viewer'])
def profile():
    """
    Allows logged-in users to manage their profile information.
    Users can update their first name, last name, email, and optionally password.
    Prevents changing email to an already existing one (excluding their own).
    """
    msg = ''
    if request.method == 'POST' and 'firstname' in request.form and 'lastname' in request.form and 'email' in request.form:
        if 'loggedin' in session:
            new_firstname = request.form['firstname']
            new_lastname = request.form['lastname']
            new_email = request.form['email']
            new_password = request.form['password'] if 'password' in request.form and request.form['password'] else None

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                # Check if the new email already exists for another user
                cursor.execute('SELECT id FROM tbl_users WHERE email = %s AND id != %s', (new_email, session['id'],))
                existing_email = cursor.fetchone()
                if existing_email:
                    msg = 'อีเมลนี้มีผู้ใช้งานอื่นแล้ว!'
                    flash(msg, 'danger')
                    cursor.close()
                    conn.close()
                    return render_template('profile.html', msg=msg, session=session)

                # Update user information
                if new_password:
                    cursor.execute('UPDATE tbl_users SET firstname = %s, lastname = %s, email = %s, password = %s WHERE id = %s', (new_firstname, new_lastname, new_email, new_password, session['id'],))
                else:
                    cursor.execute('UPDATE tbl_users SET firstname = %s, lastname = %s, email = %s WHERE id = %s', (new_firstname, new_lastname, new_email, session['id'],))
                
                conn.commit()
                
                # Update session variables
                session['firstname'] = new_firstname
                session['lastname'] = new_lastname
                session['email'] = new_email
                msg = 'ข้อมูลโปรไฟล์ของคุณได้รับการอัปเดตสำเร็จ!'
                flash(msg, 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('profile'))
        else:
            msg = 'โปรดเข้าสู่ระบบเพื่ออัปเดตโปรไฟล์ของคุณ'
            flash(msg, 'danger')
    return render_template('profile.html', msg=msg, session=session)

@app.route('/logout')
def logout():
    """Logs out the current user by clearing session variables."""
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    session.pop('firstname', None)
    session.pop('lastname', None)
    session.pop('role', None)
    flash('คุณได้ออกจากระบบแล้ว', 'info')
    return redirect(url_for('login'))

@app.route('/about')
def about():
    """Displays the 'About Us' page."""
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    Handles the 'Contact Us' form submission.
    Currently, it just prints the form data and flashes a success message.
    """
    msg = ''
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        
        print(f"Contact Form: Name: {name}, Email: {email}, Subject: {subject}, Message: {message}")
        msg = 'ข้อความของคุณถูกส่งสำเร็จแล้ว!'
        flash(msg, 'success')
    return render_template('contact.html', msg=msg)

# --- Category Management ---
@app.route("/tbl_category", methods=["GET", "POST"])
@role_required(['root_admin', 'administrator', 'moderator'])
def tbl_category():
    """
    Manages product categories (e.g., PET, Aluminum, Glass, Burnable, Contaminated Waste).
    Supports adding, editing, deleting, and searching categories.
    """
    msg = ''
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return render_template("tbl_category.html", categories=[], search='')

    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            category_id = request.form['category_id']
            category_name = request.form['category_name']
            try:
                cursor.execute("INSERT INTO tbl_category (category_id, category_name) VALUES (%s, %s)", (category_id, category_name))
                conn.commit()
                msg = 'เพิ่มหมวดหมู่สำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการเพิ่มหมวดหมู่: {err}"
                flash(msg, 'danger')

        elif action == 'edit':
            cat_id = request.form['cat_id']
            category_id = request.form['category_id']
            category_name = request.form['category_name']
            try:
                cursor.execute("UPDATE tbl_category SET category_id = %s, category_name = %s WHERE id = %s", (category_id, category_name, cat_id))
                conn.commit()
                msg = 'อัปเดตหมวดหมู่สำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการอัปเดตหมวดหมู่: {err}"
                flash(msg, 'danger')

        elif action == 'delete':
            cat_id = request.form['cat_id']
            try:
                cursor.execute("DELETE FROM tbl_category WHERE id = %s", (cat_id,))
                conn.commit()
                msg = 'ลบหมวดหมู่สำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการลบหมวดหมู่: {err}"
                flash(msg, 'danger')
        
        elif 'search' in request.form:
            search_query = request.form['search']
            cursor.execute("SELECT * FROM tbl_category WHERE category_name LIKE %s OR category_id LIKE %s ORDER BY id DESC", ('%' + search_query + '%', '%' + search_query + '%'))
            categories = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template("tbl_category.html", categories=categories, search=search_query, msg=msg)

    # Fetch all categories for initial display
    cursor.execute("SELECT * FROM tbl_category ORDER BY id DESC")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("tbl_category.html", categories=categories, search='', msg=msg)

# --- Product Management ---
@app.route("/tbl_products", methods=["GET", "POST"])
@role_required(['root_admin', 'administrator', 'moderator'])
def tbl_products():
    """
    Manages products, including barcode system and stock tracking.
    Supports adding, editing, deleting, and searching products.
    """
    msg = ''
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return render_template("tbl_products.html", products=[], categories=[], search='')

    cursor = conn.cursor(dictionary=True)
    
    # Fetch all categories for the product dropdown
    cursor.execute("SELECT category_id, category_name FROM tbl_category ORDER BY category_name")
    categories = cursor.fetchall()

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            products_id = request.form['products_id']
            product_name = request.form['product_name']
            stock = request.form['stock']
            price = request.form['price']
            category_id = request.form['category_id']
            description = request.form['description']
            try:
                cursor.execute("INSERT INTO tbl_products (products_id, products_name, stock, price, category_id, description) VALUES (%s, %s, %s, %s, %s, %s)", 
                               (products_id, product_name, stock, price, category_id, description))
                conn.commit()
                msg = 'เพิ่มสินค้าสำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการเพิ่มสินค้า: {err}"
                flash(msg, 'danger')

        elif action == 'edit':
            product_id = request.form['product_id']
            products_id = request.form['products_id']
            product_name = request.form['product_name']
            stock = request.form['stock']
            price = request.form['price']
            category_id = request.form['category_id']
            description = request.form['description']
            try:
                cursor.execute("UPDATE tbl_products SET products_id = %s, products_name = %s, stock = %s, price = %s, category_id = %s, description = %s WHERE id = %s", 
                               (products_id, product_name, stock, price, category_id, description, product_id))
                conn.commit()
                msg = 'อัปเดตสินค้าสำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการอัปเดตสินค้า: {err}"
                flash(msg, 'danger')

        elif action == 'delete':
            product_id = request.form['product_id']
            try:
                cursor.execute("DELETE FROM tbl_products WHERE id = %s", (product_id,))
                conn.commit()
                msg = 'ลบสินค้าสำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการลบสินค้า: {err}"
                flash(msg, 'danger')

        elif 'search' in request.form:
            search_query = request.form['search']
            cursor.execute("""
                SELECT p.*, c.category_name 
                FROM tbl_products p
                LEFT JOIN tbl_category c ON p.category_id = c.category_id
                WHERE p.products_name LIKE %s OR p.products_id LIKE %s OR c.category_name LIKE %s
                ORDER BY p.id DESC
            """, ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'))
            products = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template("tbl_products.html", products=products, categories=categories, search=search_query, msg=msg)

    # Fetch all products for initial display
    cursor.execute("""
        SELECT p.*, c.category_name 
        FROM tbl_products p
        LEFT JOIN tbl_category c ON p.category_id = c.category_id
        ORDER BY p.id DESC
    """)
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("tbl_products.html", products=products, categories=categories, search='', msg=msg)

# --- Order Management ---
@app.route("/tbl_order", methods=["GET", "POST"])
@role_required(['root_admin', 'administrator', 'moderator', 'member', 'viewer'])
def tbl_order():
    """
    Manages customer orders, including quantity tracking and disposed quantity.
    Supports adding, editing, deleting, and searching orders.
    Stock is updated based on ordered quantity.
    """
    msg = ''
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return render_template("tbl_order.html", orders=[], products=[], users=[], search='')

    cursor = conn.cursor(dictionary=True)

    # Fetch all products for the product dropdowns in modals
    cursor.execute("SELECT products_id, products_name, stock, price, barcode_id FROM tbl_products ORDER BY products_name")
    products_data = cursor.fetchall()

    users_data = []
    # Fetch all users for the email dropdown in modals (if admin/moderator)
    if session.get('role') in ['root_admin', 'administrator', 'moderator']:
        cursor.execute("SELECT email, CONCAT(firstname, ' ', lastname) as fullname FROM tbl_users ORDER BY firstname")
        users_data = cursor.fetchall()

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            # Check permissions for adding orders
            if session.get('role') in ['root_admin', 'administrator', 'moderator', 'member']:
                order_id = request.form['order_id']
                products_id = request.form['products_id']
                quantity = int(request.form['quantity'])
                # Receive disquantity and barcode_id directly from the form
                disquantity = int(request.form['disquantity'])
                # Strip whitespace from barcode_id; convert empty string to None if desired
                barcode_id = request.form['barcode_id'].strip() if request.form['barcode_id'] else None 
                
                # Determine order email based on user role
                email = request.form['email'] if session.get('role') in ['root_admin', 'administrator', 'moderator'] else session['email']

                try:
                    # Validate product existence and stock availability
                    cursor.execute("SELECT products_name, stock, price FROM tbl_products WHERE products_id = %s", (products_id,))
                    product_info = cursor.fetchone()

                    if not product_info:
                        msg = "ไม่พบสินค้า!"
                        flash(msg, 'danger')
                    elif quantity > product_info['stock']:
                        msg = f"สินค้า {product_info['products_name']} มีสต็อกไม่พอ. มีในสต็อก: {product_info['stock']}"
                        flash(msg, 'danger')
                    else:
                        products_name = product_info['products_name']
                        
                        # Insert new order with user-provided disquantity and barcode_id
                        cursor.execute("""
                            INSERT INTO tbl_order (order_id, products_id, products_name, quantity, disquantity, email, barcode_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (order_id, products_id, products_name, quantity, disquantity, email, barcode_id))

                        # Update product stock (deduct ordered quantity)
                        cursor.execute("UPDATE tbl_products SET stock = stock - %s WHERE products_id = %s", (quantity, products_id))

                        conn.commit()
                        msg = 'เพิ่มคำสั่งซื้อสำเร็จและอัปเดตสต็อกสินค้าแล้ว!'
                        flash(msg, 'success')
                except mysql.connector.Error as err:
                    msg = f"เกิดข้อผิดพลาดในการเพิ่มคำสั่งซื้อ: {err}"
                    flash(msg, 'danger')
            else:
                msg = "คุณไม่มีสิทธิ์เพิ่มคำสั่งซื้อ"
                flash(msg, 'danger')

        elif action == 'edit':
            ord_id = request.form['ord_id']
            order_id = request.form['order_id']
            products_id = request.form['products_id']
            quantity = int(request.form['quantity'])
            # Receive disquantity and barcode_id directly from the form
            disquantity = int(request.form['disquantity']) 
            barcode_id = request.form['barcode_id'].strip() if request.form['barcode_id'] else None 
            email = request.form['email'] # Email from form, which might be read-only for members

            # --- DEBUG PRINT (for troubleshooting) ---
            print(f"DEBUG: Edit Order - ord_id: {ord_id}, order_id: {order_id}, products_id: {products_id}, quantity: {quantity}, disquantity: {disquantity}, barcode_id: {barcode_id}, email: {email}")
            # --- END DEBUG PRINT ---

            # Check permissions for editing
            if session.get('role') in ['root_admin', 'administrator', 'moderator'] or \
               (session.get('role') == 'member' and session.get('email') == email):
                try:
                    # Get current order information to calculate stock change
                    cursor.execute("SELECT products_id, quantity FROM tbl_order WHERE id = %s", (ord_id,))
                    old_order_info = cursor.fetchone()

                    if not old_order_info:
                        msg = "ไม่พบคำสั่งซื้อที่ต้องการแก้ไข!"
                        flash(msg, 'danger')
                    else:
                        old_products_id = old_order_info['products_id']
                        old_quantity = old_order_info['quantity']

                        # Get new product information and its current stock
                        cursor.execute("SELECT products_name, stock FROM tbl_products WHERE products_id = %s", (products_id,))
                        new_product_info = cursor.fetchone()

                        if not new_product_info:
                            msg = "ไม่พบสินค้าใหม่ที่เลือก!"
                            flash(msg, 'danger')
                        else:
                            products_name = new_product_info['products_name']
                            current_stock_of_new_product = new_product_info['stock']

                            # --- Stock Adjustment Logic ---
                            if products_id != old_products_id:
                                # If product ID changes, restore old product's stock
                                cursor.execute("UPDATE tbl_products SET stock = stock + %s WHERE products_id = %s", (old_quantity, old_products_id))
                                
                                # Then deduct from the new product's stock
                                if quantity > current_stock_of_new_product: # Check if new quantity exceeds available stock
                                    msg = f"สินค้า {products_name} มีสต็อกไม่พอสำหรับการสั่งซื้อใหม่. มีในสต็อก: {current_stock_of_new_product}"
                                    flash(msg, 'danger')
                                    conn.rollback() # Rollback if stock is insufficient
                                    return redirect(url_for('tbl_order'))
                                cursor.execute("UPDATE tbl_products SET stock = stock - %s WHERE products_id = %s", (quantity, products_id))
                            else:
                                # If product ID is the same, adjust stock based on the difference in quantity
                                quantity_difference = quantity - old_quantity
                                if current_stock_of_new_product - quantity_difference < 0: # Check if stock becomes negative
                                    msg = f"สินค้า {products_name} มีสต็อกไม่พอสำหรับการเปลี่ยนแปลงจำนวน. มีในสต็อก: {current_stock_of_new_product}"
                                    flash(msg, 'danger')
                                    conn.rollback() # Rollback if stock is insufficient
                                    return redirect(url_for('tbl_order'))
                                cursor.execute("UPDATE tbl_products SET stock = stock - %s WHERE products_id = %s", (quantity_difference, products_id))
                            
                            # Update the order in tbl_order with new values, including disquantity and barcode_id
                            cursor.execute("""
                                UPDATE tbl_order SET order_id = %s, products_id = %s, products_name = %s, quantity = %s, disquantity = %s, email = %s, barcode_id = %s
                                WHERE id = %s
                            """, (order_id, products_id, products_name, quantity, disquantity, email, barcode_id, ord_id))

                            conn.commit()
                            msg = 'อัปเดตคำสั่งซื้อสำเร็จและอัปเดตสต็อกสินค้าแล้ว!'
                            flash(msg, 'success')
                except mysql.connector.Error as err:
                    msg = f"เกิดข้อผิดพลาดในการอัปเดตคำสั่งซื้อ: {err}"
                    flash(msg, 'danger')
                    conn.rollback() # Rollback in case of error
            else:
                msg = "คุณไม่มีสิทธิ์แก้ไขคำสั่งซื้อนี้"
                flash(msg, 'danger')

        elif action == 'delete':
            ord_id = request.form['ord_id']
            order_email = request.form['email'] # Email from the form for permission check

            # Check permissions for deleting
            if session.get('role') in ['root_admin', 'administrator', 'moderator'] or \
               (session.get('role') == 'member' and session.get('email') == order_email):
                try:
                    # Get order information before deleting to restore stock
                    cursor.execute("SELECT products_id, quantity FROM tbl_order WHERE id = %s", (ord_id,))
                    order_to_delete = cursor.fetchone()

                    if not order_to_delete:
                        msg = "ไม่พบคำสั่งซื้อที่ต้องการลบ!"
                        flash(msg, 'danger')
                    else:
                        product_id_to_restore = order_to_delete['products_id']
                        quantity_to_restore = order_to_delete['quantity']

                        # Delete the order from tbl_order
                        cursor.execute("DELETE FROM tbl_order WHERE id = %s", (ord_id,))

                        # Restore product stock in tbl_products (based on original ordered quantity)
                        cursor.execute("UPDATE tbl_products SET stock = stock + %s WHERE products_id = %s", (quantity_to_restore, product_id_to_restore))

                        conn.commit()
                        msg = 'ลบคำสั่งซื้อสำเร็จและคืนสต็อกสินค้าแล้ว!'
                        flash(msg, 'success')
                except mysql.connector.Error as err:
                    msg = f"เกิดข้อผิดพลาดในการลบคำสั่งซื้อ: {err}"
                    flash(msg, 'danger')
                    conn.rollback() # Rollback in case of error
            else:
                msg = "คุณไม่มีสิทธิ์ลบคำสั่งซื้อนี้"
                flash(msg, 'danger')

        elif 'search' in request.form:
            search_query = request.form['search']
            query_params = ['%' + search_query + '%'] * 3

            # SQL query for searching orders, explicitly selecting barcode_id from tbl_order
            base_query = """
                SELECT 
                    o.id, 
                    o.order_id, 
                    o.products_id, 
                    o.products_name, 
                    o.quantity, 
                    o.disquantity, 
                    o.email, 
                    o.order_date,
                    o.barcode_id, -- Explicitly select barcode_id from tbl_order
                    p.category_id 
                FROM tbl_order o
                LEFT JOIN tbl_products p ON o.products_id = p.products_id
                WHERE o.order_id LIKE %s OR o.products_name LIKE %s OR o.email LIKE %s
            """
            if session.get('role') == 'member':
                base_query += " AND o.email = %s"
                query_params.append(session['email'])

            base_query += " ORDER BY o.id DESC"

            cursor.execute(base_query, tuple(query_params))
            orders = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template("tbl_order.html", orders=orders, products=products_data, users=users_data, search=search_query, msg=msg)

    # SQL query for initial display of orders, explicitly selecting barcode_id from tbl_order
    base_query = """
        SELECT 
            o.id, 
            o.order_id, 
            o.products_id, 
            o.products_name, 
            o.quantity, 
            o.disquantity, 
            o.email, 
            o.order_date,
            o.barcode_id, -- Explicitly select barcode_id from tbl_order
            p.category_id 
        FROM tbl_order o
        LEFT JOIN tbl_products p ON o.products_id = p.products_id
    """
    if session.get('role') == 'member':
        base_query += f" WHERE o.email = '{session['email']}'"

    base_query += " ORDER BY o.id DESC"

    cursor.execute(base_query)
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("tbl_order.html", orders=orders, products=products_data, users=users_data, search='', msg=msg)

# --- User Management ---
@app.route("/tbl_users", methods=["GET", "POST"])
@role_required(['root_admin', 'administrator'])
def tbl_users():
    """
    Manages user accounts and their roles (root_admin, administrator, moderator, member, viewer).
    Supports adding, searching, editing, and deleting users.
    Root admin cannot be deleted. Administrators cannot create/edit root_admin users.
    """
    msg = ''
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return render_template("tbl_users.html", users=[], search='')

    cursor = conn.cursor(dictionary=True)

    root_admin_id = None
    try:
        cursor.execute("SELECT id FROM tbl_users WHERE role = 'root_admin' LIMIT 1")
        result = cursor.fetchone()
        if result:
            root_admin_id = result['id']
    except mysql.connector.Error as err:
        print(f"Error fetching root_admin_id: {err}")

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            # Permission check for adding users
            if session.get('role') == 'root_admin' or \
               (session.get('role') == 'administrator' and request.form.get('role') != 'root_admin'):
                
                firstname = request.form['firstname']
                lastname = request.form['lastname']
                email = request.form['email']
                password = request.form['password']
                role = request.form['role']
                
                try:
                    cursor.execute('INSERT INTO tbl_users (firstname, lastname, email, password, role) VALUES (%s, %s, %s, %s, %s)', (firstname, lastname, email, password, role))
                    conn.commit()
                    msg = 'เพิ่มผู้ใช้งานสำเร็จ!'
                    flash(msg, 'success')
                except mysql.connector.Error as err:
                    msg = f"เกิดข้อผิดพลาดในการเพิ่มผู้ใช้งาน: {err}"
                    flash(msg, 'danger')
            else:
                msg = "คุณไม่มีสิทธิ์เพิ่มผู้ใช้งานด้วยยศนี้"
                flash(msg, 'danger')

        elif action == 'edit':
            user_id = request.form['user_id']
            firstname = request.form['firstname']
            lastname = request.form['lastname']
            email = request.form['email']
            password = request.form['password'] if 'password' in request.form and request.form['password'] else None
            role = request.form['role']

            # Prevent editing root_admin role by non-root_admin or changing root_admin's role
            cursor.execute("SELECT role FROM tbl_users WHERE id = %s", (user_id,))
            target_user_role = cursor.fetchone()['role']

            if session.get('role') == 'root_admin':
                # Root admin can edit anyone, even other root admins, but cannot change their own role to non-root admin
                if target_user_role == 'root_admin' and role != 'root_admin' and str(user_id) == str(session['id']):
                    msg = "คุณไม่สามารถเปลี่ยนยศของ Root Admin ที่เข้าสู่ระบบอยู่ได้"
                    flash(msg, 'danger')
                    conn.rollback()
                    return redirect(url_for('tbl_users'))
                pass # Root admin has full permission
            elif session.get('role') == 'administrator':
                if target_user_role == 'root_admin' or role == 'root_admin':
                    msg = "คุณไม่มีสิทธิ์แก้ไขผู้ใช้งาน Root Admin หรือกำหนดให้เป็น Root Admin"
                    flash(msg, 'danger')
                    conn.rollback()
                    return redirect(url_for('tbl_users'))
            else: # Moderator, Member, Viewer cannot edit users via this route (already handled by role_required)
                msg = "คุณไม่มีสิทธิ์แก้ไขผู้ใช้งาน"
                flash(msg, 'danger')
                conn.rollback()
                return redirect(url_for('tbl_users'))

            try:
                # Check for duplicate email (excluding current user)
                cursor.execute('SELECT id FROM tbl_users WHERE email = %s AND id != %s', (email, user_id,))
                existing_email = cursor.fetchone()
                if existing_email:
                    msg = 'อีเมลนี้มีผู้ใช้งานอื่นแล้ว!'
                    flash(msg, 'danger')
                    conn.rollback()
                    return redirect(url_for('tbl_users'))

                if password:
                    cursor.execute('UPDATE tbl_users SET firstname = %s, lastname = %s, email = %s, password = %s, role = %s WHERE id = %s', 
                                   (firstname, lastname, email, password, role, user_id))
                else:
                    cursor.execute('UPDATE tbl_users SET firstname = %s, lastname = %s, email = %s, role = %s WHERE id = %s', 
                                   (firstname, lastname, email, role, user_id))
                conn.commit()
                msg = 'อัปเดตผู้ใช้งานสำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการอัปเดตผู้ใช้งาน: {err}"
                flash(msg, 'danger')
                conn.rollback()

        elif action == 'delete':
            user_id = request.form['user_id']
            
            # Prevent deleting the currently logged-in user
            if str(user_id) == str(session['id']):
                msg = "คุณไม่สามารถลบบัญชีผู้ใช้ของคุณเองได้!"
                flash(msg, 'danger')
                return redirect(url_for('tbl_users'))

            # Prevent deleting the root_admin by anyone other than root_admin (or even by root_admin if only one exists)
            cursor.execute("SELECT role FROM tbl_users WHERE id = %s", (user_id,))
            target_user_role = cursor.fetchone()['role']
            
            if target_user_role == 'root_admin':
                cursor.execute("SELECT COUNT(*) FROM tbl_users WHERE role = 'root_admin'")
                root_admin_count = cursor.fetchone()[0]
                if root_admin_count <= 1: # Prevent deleting the last root_admin
                    msg = "ไม่สามารถลบ Root Admin คนสุดท้ายได้!"
                    flash(msg, 'danger')
                    return redirect(url_for('tbl_users'))
                if session.get('role') != 'root_admin':
                    msg = "คุณไม่มีสิทธิ์ลบผู้ใช้งาน Root Admin"
                    flash(msg, 'danger')
                    return redirect(url_for('tbl_users'))
            
            if session.get('role') == 'administrator' and target_user_role == 'administrator':
                msg = "Administrator ไม่สามารถลบ Administrator ด้วยกันได้"
                flash(msg, 'danger')
                return redirect(url_for('tbl_users'))

            try:
                cursor.execute("DELETE FROM tbl_users WHERE id = %s", (user_id,))
                conn.commit()
                msg = 'ลบผู้ใช้งานสำเร็จ!'
                flash(msg, 'success')
            except mysql.connector.Error as err:
                msg = f"เกิดข้อผิดพลาดในการลบผู้ใช้งาน: {err}"
                flash(msg, 'danger')

        elif 'search' in request.form:
            search_query = request.form['search']
            cursor.execute("SELECT * FROM tbl_users WHERE firstname LIKE %s OR lastname LIKE %s OR email LIKE %s OR role LIKE %s ORDER BY id DESC", 
                           ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'))
            users = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template("tbl_users.html", users=users, search=search_query, msg=msg)

    # Fetch all users for initial display
    cursor.execute("SELECT * FROM tbl_users ORDER BY id DESC")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("tbl_users.html", users=users, search='', msg=msg)

# --- Report Generation ---
@app.route("/export_products_csv")
@role_required(['root_admin', 'administrator', 'moderator'])
def export_products_csv():
    """Exports product data to a CSV file."""
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return redirect(url_for('tbl_products'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT products_id, products_name, stock, price, category_id, description FROM tbl_products")
        products = cursor.fetchall()
        
        si = StringIO()
        cw = csv.writer(si)
        
        cw.writerow(['Product ID', 'Product Name', 'Stock', 'Price', 'Category ID', 'Description'])
        
        for product in products:
            cw.writerow([product['products_id'], product['products_name'], product['stock'], product['price'], product['category_id'], product['description']])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=products_report.csv"
        output.headers["Content-type"] = "text/csv"
        return output
    except mysql.connector.Error as err:
        flash(f"เกิดข้อผิดพลาดในการส่งออกข้อมูลสินค้า: {err}", 'danger')
        return redirect(url_for('tbl_products'))
    finally:
        cursor.close()
        conn.close()

@app.route("/export_orders_pdf")
@role_required(['root_admin', 'administrator', 'moderator', 'member'])
def export_orders_pdf():
    """Exports order data to a PDF file."""
    conn = get_db_connection()
    if not conn:
        flash("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล.", 'danger')
        return redirect(url_for('tbl_order'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch orders, ensuring barcode_id is from tbl_order
        base_query = """
            SELECT 
                o.id, 
                o.order_id, 
                o.products_id, 
                o.products_name, 
                o.quantity, 
                o.disquantity, 
                o.email, 
                o.order_date,
                o.barcode_id, 
                p.category_id 
            FROM tbl_order o
            LEFT JOIN tbl_products p ON o.products_id = p.products_id
        """
        query_params = []
        if session.get('role') == 'member':
            base_query += " WHERE o.email = %s"
            query_params.append(session['email'])
        
        base_query += " ORDER BY o.order_date DESC"
        
        cursor.execute(base_query, tuple(query_params))
        orders = cursor.fetchall()

        # Render HTML template for PDF
        html = render_template("pdf_template_orders.html", orders=orders)
        
        # Create a PDF from HTML
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            html,                # the HTML to convert
            dest=pdf_buffer)     # file handle to receive result

        if pisa_status.err:
            flash(f"เกิดข้อผิดพลาดในการสร้าง PDF: {pisa_status.err}", 'danger')
            return redirect(url_for('tbl_order'))

        pdf_buffer.seek(0)
        
        response = make_response(pdf_buffer.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=orders_report.pdf"
        response.headers["Content-type"] = "application/pdf"
        return response
    except mysql.connector.Error as err:
        flash(f"เกิดข้อผิดพลาดในการส่งออกรายงานคำสั่งซื้อ: {err}", 'danger')
        return redirect(url_for('tbl_order'))
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
