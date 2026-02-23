from flask import (  # Flask web framework utilities
    Blueprint,  # For organizing routes
    render_template,  # For rendering HTML templates
    redirect,  # For redirecting to other pages
    url_for,  # For URL generation
    flash,  # For displaying flash messages (sandeshas)
    request,  # For accessing request data
    current_app,  # For accessing current application
    abort,  # For raising HTTP errors
)
from models import db, User  # Database and User model
from flask_login import login_user, logout_user, login_required, current_user  # Login management
from flask_wtf import FlaskForm  # Form handling library
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FileField  # Form field types
from wtforms.validators import DataRequired, Email, EqualTo, Length  # Form validation rules
from sqlalchemy.exc import OperationalError  # Database error handling
from werkzeug.utils import secure_filename  # Secure file upload utilities
import os  # File and directory operations

DB_INIT_ERROR_MSG = "Database not initialized. Run `python init_db.py` or enable `AUTO_CREATE_DB` in config."

auth_bp = Blueprint("auth", __name__, template_folder="templates")  # Authentication blueprint (auth ko route)


class LoginForm(FlaskForm):  # Login form
    username = StringField("Username", validators=[DataRequired()])  # Username field (required)
    password = PasswordField("Password", validators=[DataRequired()])  # Password field (required)
    submit = SubmitField("Login")


class SignupForm(FlaskForm):  # Registration form (signup ko form)
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=80)]  # 3-80 characters
    )
    email = StringField("Email", validators=[DataRequired(), Email()])  # Valid email required
    full_name = StringField("Full name")  # Optional
    phone = StringField("Phone")  # Optional  
    age = StringField("Age")  # Optional
    vehicle_name = StringField("Vehicle name/model")  # For drivers (driver ko lagi)
    vehicle_brand = StringField("Vehicle brand")  # For drivers
    vehicle_plate = StringField("Vehicle plate number")  # For drivers (gaadi ko nambar)
    driver_license = FileField("Driver license (image/pdf)")  # Driver document
    driver_bluebook = FileField("Blue book (image/pdf)")  # Vehicle registration
    driver_photo = FileField("Driver photo")  # Driver photo upload
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])  # Minimum 6 characters
    confirm = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]  # Must match password
    )
    driver = BooleanField("Are you a driver?")  # Driver role checkbox (driver ho bhane check gara)
    submit = SubmitField("Sign Up")


@auth_bp.route("/login", methods=["GET", "POST"])  # Login route - GET: form dikhane ko, POST: login garna ko
def login():  # Login function
    form = LoginForm()  # Login form banao
    if form.validate_on_submit():  # Form valid bhayo ki submit bhayo
        try:  # Database error handling
            user = User.query.filter_by(username=form.username.data).first()  # Username se user khojo
        except OperationalError:  # Database error aye
            flash(DB_INIT_ERROR_MSG, "danger")  # Error message dikha
            return redirect(url_for("main.home"))  # Home page ma ja

        if user and user.check_password(form.password.data):  # User exist karega aur password match bhayo
            login_user(user)  # User ko login session start gara
            flash("Logged in successfully.", "success")  # Success message
            return redirect(url_for("main.home"))  # Home page ma redirect gara
        flash("Invalid username or password", "danger")  # Error message - wrong credentials
    return render_template("login.html", form=form)  # Login page dikha


@auth_bp.route("/signup", methods=["GET", "POST"])  # Signup route - GET: form dikhane ko, POST: register garna ko
def signup():  # Signup function
    form = SignupForm()  # Signup form banao
    if form.validate_on_submit():  # Form valid bhayo
        try:  # Database error handling
            if User.query.filter(  # Check gara ki user already achha ki nai
                (User.username == form.username.data) | (User.email == form.email.data)  # Username ya email match
            ).first():  # First match khojo
                flash("Username or email already exists", "warning")  # Already registered message
                return redirect(url_for("auth.signup"))  # Signup page ma feri ja
        except OperationalError:
            flash(DB_INIT_ERROR_MSG, "danger")
            return redirect(url_for("main.home"))

        user = User(username=form.username.data, email=form.email.data)
        user.full_name = form.full_name.data
        user.phone = form.phone.data
        try:
            user.age = int(form.age.data) if form.age.data else None
        except ValueError:
            user.age = None

        def save_upload(file_field, prefix):
            f = file_field.data
            if not f or not getattr(f, "filename", None):
                return None
            upload_folder = os.path.join(os.path.dirname(__file__), "static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(f.filename)
            name, ext = os.path.splitext(filename)
            safe_name = f"{prefix}_{name}{ext}"
            dest = os.path.join(upload_folder, safe_name)
            f.save(dest)
            return f"/static/uploads/{safe_name}"

        # assign role and default driver availability
        if form.driver.data:
            user.role = "user"  # keep as user until approved
            user.driver_status = "pending"
            user.driver_available = False
            user.vehicle_name = form.vehicle_name.data
            user.vehicle_brand = form.vehicle_brand.data
            user.vehicle_plate = form.vehicle_plate.data
            user.driver_license_path = save_upload(
                form.driver_license, f"license_{user.username}"
            )
            user.driver_bluebook_path = save_upload(
                form.driver_bluebook, f"bluebook_{user.username}"
            )
            user.driver_photo_path = save_upload(
                form.driver_photo, f"driver_{user.username}"
            )
            user.vehicle_info = f"{(form.vehicle_brand.data or '').strip()} {(form.vehicle_name.data or '').strip()}".strip()
        else:
            user.role = "user"
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        if form.driver.data:
            flash("Driver application submitted. Await admin approval.", "info")
            return redirect(url_for("driver.driver_dashboard"))
        flash("Account created and logged in.", "success")
        return redirect(url_for("main.home"))

    return render_template("signup.html", form=form)  # show signup


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        age = request.form.get("age")
        vehicle_info = request.form.get("vehicle_info")
        driver_available = bool(request.form.get("driver_available"))

        current_user.full_name = full_name
        current_user.phone = phone
        current_user.age = int(age) if age else None
        current_user.vehicle_info = vehicle_info
        current_user.driver_available = driver_available

        f = request.files.get("profile_pic")
        if f and f.filename:
            upload_folder = os.path.join(os.path.dirname(__file__), "static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(f.filename)
            dest = os.path.join(upload_folder, filename)
            f.save(dest)
            current_user.profile_pic = f"/static/uploads/{filename}"

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))

    return render_template("edit_profile.html")


@auth_bp.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    token_required = current_app.config.get("ADMIN_REG_CODE")
    if not token_required:
        abort(404)
    if request.method == "POST":
        token = request.form.get("token")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            if User.query.filter(
                (User.username == username) | (User.email == email)
            ).first():
                flash("Username or email already exists", "warning")
                return redirect(url_for("auth.admin_signup"))
        except OperationalError:
            flash(DB_INIT_ERROR_MSG, "danger")
            return redirect(url_for("main.home"))

        if token != token_required:
            flash("Invalid registration token", "danger")
            return redirect(url_for("auth.admin_signup"))
        user = User(username=username, email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Admin account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("admin_signup.html")
