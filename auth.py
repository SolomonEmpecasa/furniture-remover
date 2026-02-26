import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from models import User, db
from sqlalchemy.exc import OperationalError
from werkzeug.utils import secure_filename
from wtforms import BooleanField, FileField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

DB_INIT_ERROR_MSG = "Database not initialized. Run `python init_db.py` or enable `AUTO_CREATE_DB` in config."

auth_bp = Blueprint("auth", __name__, template_folder="templates")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class SignupForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=80)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    full_name = StringField("Full name")
    phone = StringField("Phone")
    age = StringField("Age")
    vehicle_name = StringField("Vehicle name/model")
    vehicle_brand = StringField("Vehicle brand")
    vehicle_plate = StringField("Vehicle plate number")
    driver_license = FileField("Driver license (image/pdf)")
    driver_bluebook = FileField("Blue book (image/pdf)")
    driver_photo = FileField("Driver photo")
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    driver = BooleanField("Are you a driver?")
    submit = SubmitField("Sign Up")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
        except OperationalError:
            flash(DB_INIT_ERROR_MSG, "danger")
            return redirect(url_for("main.home"))

        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("main.home"))
        flash("Invalid username or password", "danger")
    return render_template("login.html", form=form)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        try:
            if User.query.filter(
                (User.username == form.username.data) | (User.email == form.email.data)
            ).first():
                flash("Username or email already exists", "warning")
                return redirect(url_for("auth.signup"))
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

        if form.driver.data:
            user.role = "user"
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

    return render_template("signup.html", form=form)


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
