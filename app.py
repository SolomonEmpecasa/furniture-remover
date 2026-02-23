import os

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import User, db


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # Auto-create database tables and handle migrations (development mode)
    if app.config.get("AUTO_CREATE_DB", True):
        with app.app_context():
            try:
                db.create_all()
                app.logger.info("Database tables ensured/created.")

                # Auto-add missing columns for development
                from sqlalchemy import inspect, text as sa_text, types as sqltypes

                from models import Booking, SiteFeedback

                engine = db.engine
                inspector = inspect(engine)
                models_to_check = [Booking, User, SiteFeedback]
                existing_cols_map = {}

                for m in models_to_check:
                    tname = m.__table__.name
                    try:
                        cols = inspector.get_columns(tname)
                        existing_cols_map[tname] = set(c["name"] for c in cols)
                    except Exception:
                        existing_cols_map[tname] = set()

                for m in models_to_check:
                    tname = m.__table__.name
                    existing_cols = existing_cols_map.get(tname, set())
                    for col in m.__table__.columns:
                        if col.name in existing_cols:
                            continue

                        ctype = col.type
                        if isinstance(ctype, sqltypes.Integer):
                            sqltype = "INTEGER"
                        elif isinstance(ctype, sqltypes.Float):
                            sqltype = "REAL"
                        elif isinstance(ctype, sqltypes.String):
                            sqltype = (
                                f"VARCHAR({ctype.length})"
                                if getattr(ctype, "length", None)
                                else "VARCHAR"
                            )
                        elif isinstance(ctype, sqltypes.Text):
                            sqltype = "TEXT"
                        elif isinstance(ctype, sqltypes.DateTime):
                            sqltype = "DATETIME"
                        else:
                            sqltype = "TEXT"

                        stmt = f"ALTER TABLE {tname} ADD COLUMN {col.name} {sqltype};"
                        try:
                            with engine.connect() as conn:
                                conn.execute(sa_text(stmt))
                                app.logger.info(
                                    "Added missing column to %s: %s %s",
                                    tname,
                                    col.name,
                                    sqltype,
                                )
                        except Exception as e:
                            app.logger.warning(
                                "Could not add column %s to %s: %s", col.name, tname, e
                            )

                # Ensure upload folder exists
                upload_folder = os.path.join(
                    os.path.dirname(__file__), "static", "uploads"
                )
                os.makedirs(upload_folder, exist_ok=True)
                app.logger.info("Ensured upload folder exists: %s", upload_folder)

            except Exception as e:
                app.logger.error("Failed to create DB tables: %s", e)

    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"  # type: ignore[assignment]
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from admin import admin_bp
    from auth import auth_bp
    from booking import booking_bp
    from driver import driver_bp
    from rating import rating_bp
    from routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(rating_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
