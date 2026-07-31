import random
import re
from datetime import datetime
import smtplib
from functools import wraps
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, url_for, request, redirect, session, jsonify, flash, make_response
from DBConnection import Db
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import hmac

def verify_scrypt_manually(pwhash, password):
    try:
        if '$' not in pwhash:
            return False
        parts = pwhash.split('$')
        if len(parts) != 3:
            return False
        method_part, salt, hashval = parts
        
        args = method_part.split(':')
        if len(args) < 4 or args[0] != 'scrypt':
            return False
            
        n = int(args[1])
        r = int(args[2])
        p = int(args[3])
        dklen = len(hashval) // 2
        
        computed = hashlib.scrypt(
            password.encode('utf-8'),
            salt=salt.encode('utf-8'),
            n=n,
            r=r,
            p=p,
            maxmem=128 * 1024 * 1024,
            dklen=dklen
        )
        return hmac.compare_digest(computed.hex(), hashval)
    except Exception as e:
        print(f"Manual scrypt verification failed: {e}")
        return False

app = Flask(__name__)
app.secret_key="123"

# Global after_request handler to set cache headers for all responses
@app.after_request
def set_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Vary'] = 'Accept-Encoding'
    return response

# Decorator to prevent caching of sensitive pages
def no_cache(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/find_your_charger')
def find_your_charger():
    return render_template('find_your_charger.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        feedback = request.form['message']
        db = Db()
        sql = db.insert("INSERT INTO contact_us (Name, Email, feedback_date, feedback) VALUES (%s, %s, NOW(), %s)", (name, email, feedback))
        return render_template('contact_us.html', message='Thank you for your feedback!')
    else:
        return render_template('contact_us.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == "POST":
        # Validate email input
        email = request.form.get('email', '').strip()
        if not email:
            return "Email is required", 400
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "Invalid email format", 400

        # Check if email exists in database
        db = Db()
        user = db.selectOne("SELECT * FROM login WHERE email=%s", (email,))
        if not user:
            return "Sorry, we couldn't find an account associated with that email address.", 400

         # Send email with password reset instructions or link
        password = user['password']
        sender_email = "a97298570@gmail.com"
        sender_password = "56B50C32C322385ED3009518610638823005"
        recipient_email = email
        subject = "Password Reset for EV STATION BOOKING WEBSITE"
        content = "Your password for EV STATION BOOKING WEBSITE has been reset. Please login with your new password."
        host = "smtp.gmail.com"
        port = 465
        message = MIMEMultipart()
        message['From'] = (sender_email)
        message['To'] = (recipient_email)
        message['Subject'] = (subject)
        message.attach(MIMEText(content, 'plain', 'utf-8'))
        try:
            with smtplib.SMTP_SSL(host, port) as server:            
                server.login("a97298570@gmail.com", "56B50C32C322385ED3009518610638823005")
                server.sendmail("a97298570@gmail.com", recipient_email, message.as_string())

                return "An email has been sent to your email address with instructions on how to reset your password."
        except smtplib.SMTPAuthenticationError:
            return "Failed to authenticate with the email server. Please check your email credentials.", 500
        except smtplib.SMTPException as e:
            return f"An error occurred while sending the email: {str(e)}", 500

    return render_template("forgot_password.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_type' in session and session['user_type'] == "admin":
        return redirect('/admin-home')

    if request.method == "POST":
        print('form ', request.form)
        username = request.form['username']
        password = request.form['password']
        db = Db()
        user = db.selectOne("SELECT * FROM login WHERE username=%s", (username,))
        
        if user is not None:
            stored_password = user['password']
            password_valid = False
            
            # Check if the stored password is hashed (starts with pbkdf2:sha256 or scrypt)
            if stored_password.startswith('pbkdf2:sha256:') or stored_password.startswith('scrypt:'):
                # It's a hashed password
                try:
                    password_valid = check_password_hash(stored_password, password)
                except ValueError:
                    # Incompatible hash function config (e.g. scrypt under Python 3.13)
                    if stored_password.startswith('scrypt:'):
                        password_valid = verify_scrypt_manually(stored_password, password)
                    else:
                        password_valid = False
            else:
                # It's plain text password (for existing users like admin)
                password_valid = (stored_password == password)
                
                # If plain text password matches, update it to hashed version for security
                if password_valid:
                    hashed_password = generate_password_hash(password)
                    db.update("UPDATE login SET password = %s WHERE login_id = %s", (hashed_password, user['login_id']))
                    print(f"Updated password for user {username} to hashed version")
            
            if password_valid:
                session['head'] = ""
                session['username'] = username
                session['uid'] = user['login_id']
                
                # Store email in session if it exists in database
                if 'email' in user:
                    session['email'] = user['email']
                
                if user['usertype'] == 'admin':
                    session['user_type'] = 'admin'
                    return redirect('/admin-home')
                elif user['usertype'] == 'user':
                    session['user_type'] = 'user'
                    return redirect('/user-dashboard')
                else:
                    return render_template("login.html", error="Invalid user type")
            else:
                return render_template("login.html", error="Invalid password")
        else:
            return render_template("login.html", error="User not found")
    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('username',None)
    session.pop('user_type',None)
    session.pop('log',None)
    session.pop('usertype',None)

    response = make_response(redirect('/login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/check-session')
def check_session():
    """Check if user session is valid"""
    if 'user_type' in session and 'username' in session:
        return jsonify({'valid': True}), 200
    else:
        return jsonify({'valid': False}), 401


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['signupUsername']
        email = request.form['email']
        password = request.form['password']
        confirmPassword = request.form['confirmPassword']

        # Perform form validation
        if username.strip() == '':
            return redirect(url_for('register', error='Please enter a username', form_id='createAccount'))

        if email.strip() == '':
            return redirect(url_for('register', error='Please enter an email address', form_id='createAccount'))

        if password.strip() == '':
            return redirect(url_for('register', error='Please enter a password', form_id='createAccount'))

        if confirmPassword.strip() == '':
            return redirect(url_for('register', error='Please confirm the password', form_id='createAccount'))

        if password != confirmPassword:
            return redirect(url_for('register', error='Passwords do not match', form_id='createAccount'))

        # Hash the password before storing
        hashed_password = generate_password_hash(password)
        db = Db()
        
        # Check if username already exists
        existing_user = db.selectOne("SELECT * FROM login WHERE username=%s", (username,))
        if existing_user:
            return redirect(url_for('register', error='Username already exists. Please choose another.', form_id='createAccount'))
        
        # Check if email already exists
        existing_email = db.selectOne("SELECT * FROM login WHERE email=%s", (email,))
        if existing_email:
            return redirect(url_for('register', error='Email already registered. Please use another.', form_id='createAccount'))
        
        # Insert into login table
        login_id = db.insert("INSERT INTO login (username, password, usertype, email) VALUES (%s, %s, 'user', %s)", (username, hashed_password, email))
        
        # ALSO insert into user table with the same login_id
        if login_id:
            db.insert("INSERT INTO user (user_id, name, email) VALUES (%s, %s, %s)", (login_id, username, email))
            return redirect(url_for('login', success='User registered successfully! Please login.'))
        else:
            return redirect(url_for('register', error='Registration failed. Please try again.', form_id='createAccount'))
    else:
        error = request.args.get('error')
        return render_template("login.html", error=error, form_id='createAccount')


@app.route('/admin-home')
def admin_home():
    print('session ', session)
    if session.get('user_type') == 'admin':
        username = session.get('username', '')
        db = Db()
        
        total_stations = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list")['count']
        active_stations = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Status = 'active'")['count']
        inactive_stations = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Status = 'inactive' OR Status = ''")['count']
        total_users = db.selectOne("SELECT COUNT(*) as count FROM login WHERE usertype = 'user'")['count']
        admin_count = db.selectOne("SELECT COUNT(*) as count FROM login WHERE usertype = 'admin'")['count']
        total_bookings = db.selectOne("SELECT COUNT(*) as count FROM booking")['count']
        completed_bookings = db.selectOne("SELECT COUNT(*) as count FROM charging_station_booking WHERE status = 'Completed'")['count']
        total_feedbacks = db.selectOne("SELECT COUNT(*) as count FROM contact_us")['count']
        recent_feedbacks = db.selectOne("SELECT COUNT(*) as count FROM contact_us WHERE feedback_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")['count']
        cities_with_stations = db.select("SELECT City, COUNT(*) as station_count FROM admin_charging_station_list GROUP BY City ORDER BY station_count DESC LIMIT 8")
        recent_bookings = db.select("SELECT Station_name, City, Booking_date, Time_from, Time_to FROM booking ORDER BY booking_id DESC LIMIT 5")
        dc_fast_count = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Charger_type LIKE '%DC Fast%'")['count']
        ac_level2_count = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Charger_type LIKE '%AC Level 2%'")['count']
        ac_level1_count = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Charger_type LIKE '%AC Level 1%'")['count']
        maintenance_stations = db.selectOne("SELECT COUNT(*) as count FROM admin_charging_station_list WHERE Status = 'Under Maintenance'")['count']
        
        return render_template('admin/admin-login-dashboard.html', 
                             username=username,
                             total_stations=total_stations,
                             active_stations=active_stations,
                             inactive_stations=inactive_stations,
                             total_users=total_users,
                             admin_count=admin_count,
                             total_bookings=total_bookings,
                             completed_bookings=completed_bookings,
                             total_feedbacks=total_feedbacks,
                             recent_feedbacks=recent_feedbacks,
                             cities_with_stations=cities_with_stations,
                             recent_bookings=recent_bookings,
                             dc_fast_count=dc_fast_count,
                             ac_level2_count=ac_level2_count,
                             ac_level1_count=ac_level1_count,
                             maintenance_stations=maintenance_stations)
    else:
        return redirect('/')


@app.route('/Manage_station')
@no_cache
def Manage_station():
    print('session ', session)
    if session.get('user_type') == 'admin':
        db=Db()
        qry=db.select("select station_id, station_name, address, city, charger_type, available_ports, status from admin_charging_station_list")
        return render_template("admin/Manage_station.html",data=qry)
    else:
        return redirect('/')


@app.route('/view_feedback')
@no_cache
def view_feedback():
    print('session ', session)
    if session.get('user_type') == 'admin':
        db=Db()
        ss=db.select("select * from contact_us")
        return render_template("admin/view_feedback.html",data=ss)
    else:
        return redirect('/')


@app.route('/adm_add_station', methods=['POST'])
@no_cache
def adm_add_station():
    if session.get('user_type') == 'admin':
        station_name = request.form.get('station_name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        charger_type = request.form.get('charger_type', '').strip()
        available_ports = request.form.get('available_ports', '').strip()
        status = request.form.get('status', 'active').strip()

        if station_name and address and city and charger_type and available_ports:
            db = Db()
            existing = db.selectOne("SELECT * FROM admin_charging_station_list WHERE Station_name = %s", (station_name,))
            if existing:
                flash('Station name already exists', 'danger')
            else:
                db.insert("""
                    INSERT INTO admin_charging_station_list (Station_name, Address, City, Charger_type, Available_ports, Status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (station_name, address, city, charger_type, available_ports, status))
                flash('Station added successfully', 'success')
        else:
            flash('Please fill in all fields', 'danger')
        return redirect('/Manage_station')
    else:
        return redirect('/')


@app.route("/adm_delete_station/<station_name>")
@no_cache
def adm_delete_station(station_name):
    print('session ', session)
    if session.get('user_type') == 'admin':
        db = Db()
        qry = db.delete("DELETE FROM admin_charging_station_list WHERE Station_name = %s", (station_name,))
        flash('Station deleted successfully', 'success')
        return redirect('/Manage_station')
    else:
        return redirect('/')


@app.route("/adm_delete_feedback/<feedback>")
@no_cache
def adm_delete_feedback(feedback):
    print('session ', session)
    if session.get('user_type') == 'admin':
        db = Db()
        qry = db.delete("delete from contact_us where Sl_no='"+feedback+"'")
        flash('Feedback deleted successfully', 'success')
        return redirect('/view_feedback')
    else:
        return redirect('/')


@app.route('/user-list')
@no_cache
def user_list():
    print('session ', session)
    if session.get('user_type') == 'admin':
        db = Db()
        qry = db.select("SELECT login_id as user_id, username as name, email FROM login WHERE usertype = 'user'")
        return render_template("admin/user-list.html", data=qry)
    else:
        return redirect('/')


@app.route("/adm_delete_user/<user_id>")
@no_cache
def adm_delete_user(user_id):
    print('session ', session)
    if session.get('user_type') == 'admin':
        db = Db()
        db.delete("DELETE FROM login WHERE login_id = %s", (user_id,))
        flash('User deleted successfully', 'success')
        return redirect('/user-list')
    else:
        return redirect('/')


@app.route('/view_booking')
@no_cache
def view_booking():
    if session.get('user_type') != 'admin':
        return redirect('/')

    db = Db()
    raw_bookings = db.select("""
        SELECT 
            b.booking_id,
            b.Booking_date,
            b.Time_from,
            b.Time_to,
            b.City,
            b.Station_name,
            b.Available_ports,
            b.login_id
        FROM booking b
        ORDER BY b.Booking_date DESC
    """)

    bookings = []
    for b in raw_bookings:
        time_from = (datetime.min + b['Time_from']).time()
        time_to = (datetime.min + b['Time_to']).time()
        
        bookings.append({
            'booking_id': b['booking_id'],
            'booking_date': b['Booking_date'].strftime('%Y-%m-%d'),
            'time_from': time_from.strftime('%H:%M'),
            'time_to': time_to.strftime('%H:%M'),
            'city': b['City'],
            'station_name': b['Station_name'],
            'available_ports': b['Available_ports'],
            'user_name': b['login_id']
        })

    return render_template('admin/view_booking.html', bookings=bookings)


@app.route("/adm_delete_booking/<Booking_id>")
def adm_delete_booking(Booking_id):
    print('session ', session)
    if session.get('user_type') == 'admin':
        db = Db()
        qry = db.delete("delete from booking where Booking_id='"+Booking_id+"'")
        flash('Booking deleted successfully', 'success')
        return redirect('/view_booking')
    else:
        return redirect('/')


@app.route('/user-dashboard')
@no_cache
def user_dashboard():
    if 'user_type' in session and session['user_type'] == "user":
        username = session.get('username', '')
        db = Db()
        
        print(f"User ID from session: {session.get('uid')}")
        
        bookings = db.select("SELECT * FROM booking WHERE login_id = %s ORDER BY Booking_date DESC", (session.get('uid'),))
        
        print(f"Found {len(bookings)} bookings for user {username}")
        for booking in bookings:
            print(f"Booking: {booking}")
        
        return render_template("user/user-login-dashboard.html", bookings=bookings, username=username)
    else:
        return redirect('/')
    
@app.route('/user-profile', methods=['GET', 'POST'])
@no_cache
def user_profile():
    if 'user_type' not in session or session['user_type'] != 'user':
        return redirect('/login')

    db = Db()
    message = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm-password', '').strip()

        if password and password != confirm_password:
            message = "Passwords do not match"
        else:
            try:
                update_data = []
                update_fields = []
                
                if username:
                    update_fields.append("username = %s")
                    update_data.append(username)
                
                if email:
                    update_fields.append("email = %s")
                    update_data.append(email)
                
                if password:
                    hashed_password = generate_password_hash(password)
                    update_fields.append("password = %s")
                    update_data.append(hashed_password)
                
                if update_fields:
                    update_data.append(session.get('uid'))
                    query = f"UPDATE login SET {', '.join(update_fields)} WHERE login_id = %s"
                    db.update(query, tuple(update_data))
                    message = "Profile updated successfully!"
                
            except Exception as e:
                message = f"Error updating profile: {str(e)}"

    user_data = db.selectOne("SELECT username, email FROM login WHERE login_id = %s", (session.get('uid'),))
    
    return render_template('user/user-profile.html', 
                         username=user_data['username'],
                         email=user_data.get('email', ''),
                         message=message)


@app.route('/usr_delete_booking/<int:booking_id>')
@no_cache
def usr_delete_booking(booking_id):
    if session.get('user_type') == "user":
        db = Db()
        db.delete("DELETE FROM booking WHERE booking_id = %s AND login_id = %s", (booking_id, session.get('uid')))
        flash('Booking cancelled successfully', 'success')
        return redirect('/user-dashboard')
    else:
        return redirect('/user-dashboard')


@app.route('/user_find_your_charger', methods=['GET', 'POST'])
@no_cache
def user_find_your_charger():
    if session.get('user_type') == 'user':
        if request.method == 'POST':
            city = request.form.get('City')
            charger_type = request.form.get('Charger_type')
            db = Db()
            qry = db.select("select Station_name, Address, Charger_type, Available_ports from admin_charging_station_list where City = %s and Charger_type = %s", (city, charger_type))
            return render_template('user/station_search.html', data=qry)       
        else:
            return render_template('user/user_find_your_charger.html')
    else:
        return redirect('/')


@app.route('/search_stations', methods=['POST'])
@no_cache
def search_stations():
    City = request.form.get('City')
    Charger_type = request.form.get('Charger_type')
    return redirect(url_for('station_search', City=City, Charger_type=Charger_type))


@app.route('/station_search', methods=['GET'])
@no_cache
def station_search():
    if session.get('user_type') == 'user':
        City = request.args.get('City')
        Charger_type = request.args.get('Charger_type')
        db = Db()
        sql = "select * from admin_charging_station_list where City = %s and Charger_type = %s"
        ss = db.select(sql, (City, Charger_type))
        return render_template('user/station_search.html', data=ss, City=City, Charger_type=Charger_type)
    else:
        return redirect('/')


@app.route('/booking', methods=['GET', 'POST'])
@no_cache
def booking():
    if request.method == 'POST':
        Station_name = request.form['Station_name']
        City = request.form['City']
        Available_ports = request.form['Available_ports']
        return redirect(url_for('booking_form',  Station_name=Station_name, City=City, Available_ports=Available_ports))
    else:
        Station_name = request.args.get('Station_name')
        City = request.args.get('City')
        Available_ports = request.args.get('Available_ports')
        return redirect(url_for('booking_form', Station_name=Station_name, City=City, Available_ports=Available_ports))


@app.route('/booking-form', methods=['GET'])
@no_cache
def booking_form():
    city = request.args.get('City')
    available_ports = request.args.get('Available_ports')
    station_name = request.args.get('Station_name')
    db = Db()
    station_data = db.select("select * from admin_charging_station_list where Station_name = %s", (station_name,))
    session['station_data'] = station_data[0] if station_data else None
    if 'station_data' in session and session['station_data']:
        return render_template('/user/booking_form.html', city=city, available_ports=available_ports)
    else:
        return redirect(url_for('station_search'))


@app.route('/book', methods=['POST'])
@no_cache
def book():
    if session.get('user_type') == 'user':
        station_name = request.form['Station_name']
        city = request.form['City']
        available_ports = request.form['Available_ports']
        booking_date = request.form['Booking_date']
        time_from = request.form['Time_from']
        time_to = request.form['Time_to']
        login_id = session.get('uid')

        db = Db()

        print(f"Booking Data:")
        print(f"Station: {station_name}")
        print(f"City: {city}")
        print(f"Ports: {available_ports}")
        print(f"Date: {booking_date}")
        print(f"Time From: {time_from}")
        print(f"Time To: {time_to}")
        print(f"Login ID: {login_id}")

        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        sql = "INSERT INTO booking (Station_name, City, Available_ports, Booking_date, Time_from, Time_to, Created_id, login_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        booking_id = db.insert(sql, (station_name, city, available_ports, booking_date, time_from, time_to, created_at, login_id))

        print(f"Booking created with ID: {booking_id}")
        
        verify_booking = db.selectOne("SELECT * FROM booking WHERE booking_id = %s", (booking_id,))
        if verify_booking:
            print(f"Booking verified in database: {verify_booking}")
        else:
            print("WARNING: Booking not found after insertion!")

        return redirect('/user-dashboard')
    else:
        return redirect('/booking-form')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)