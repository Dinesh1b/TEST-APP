"""
app.py — Q-Audit Runner Flask Application Factory.

Creates and configures the Flask app with all blueprints registered.
"""

import os
import secrets

from flask import Flask
from flask_cors import CORS



def create_app():
    """Create and configure the Flask application."""
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

    app = Flask(
        __name__,
        template_folder=os.path.join(_PROJECT_ROOT, "frontend", "templates"),
        static_folder=os.path.join(_PROJECT_ROOT, "frontend", "static"),
    )
    CORS(app)
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # Initialize databases
    from backend.services.db import init_db, init_auth_db
    init_db()
    init_auth_db()

    # Register blueprints
    from backend.blueprints.pages import pages_bp
    from backend.blueprints.auth import auth_bp
    from backend.blueprints.runner import runner_bp
    from backend.blueprints.uploads import uploads_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(runner_bp)
    app.register_blueprint(uploads_bp)

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    # Add parent directory to sys.path so 'backend' is findable
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    app = create_app()
    print("\n  Q-Audit Runner  (v10 - Pro Scalable)")
    print("  " + "-" * 57)
    print("  Open in browser ->  http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("FLASK_PORT", 5000)), threaded=True)
