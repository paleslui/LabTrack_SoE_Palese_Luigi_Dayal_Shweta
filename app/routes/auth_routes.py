"""
app/routes/auth_routes.py
==========================
ARCHITECTURE LAYER: Presentation (Flask Blueprint)
----------------------------------------------------
Handles user authentication. Sits at the top of the three-tier stack:
  Browser → [Auth routes] → SampleService/UserRepository → SQLite

All business logic (password verification, session creation) is delegated
downward to the Application Layer. This file contains ONLY HTTP plumbing:
parsing request data, calling services, and formatting JSON responses.

API Endpoints
-------------
POST /api/auth/login    — Authenticate user, start session
POST /api/auth/logout   — Invalidate session
GET  /api/auth/me       — Return the currently authenticated user's profile
"""

from flask import Blueprint, request, jsonify, session, abort, g
from functools import wraps

auth_bp = Blueprint("auth", __name__)

# ---------------------------------------------------------------------------
# Authentication helper — used by all route modules
# ---------------------------------------------------------------------------

def login_required(f):
    """
    Decorator that aborts with 401 if no valid session exists.

    Usage:
        @sample_bp.route("/")
        @login_required
        def list_samples():
            user = g.current_user  # injected by this decorator
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            abort(401)

        # In Stage 7 (DB integration) this will query the real DB.
        # For now, g.current_user carries the session user_id.
        g.current_user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """
    Decorator that aborts with 403 if the session user's role is not in *roles*.

    Usage:
        @user_bp.route("/", methods=["POST"])
        @login_required
        @require_role("admin")
        def create_user():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_role = session.get("user_role", "")
            if user_role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.post("/login")
def login():
    """
    POST /api/auth/login
    --------------------
    Authenticate a user by username and password.

    Request body (JSON):
        { "username": str, "password": str }

    Response (200 OK):
        { "user_id": int, "username": str, "role": str }

    Response (401 Unauthorized):
        { "error": "Invalid credentials" }

    Communication flow (Architecture Stage 6):
        Browser → POST /api/auth/login
               → [Auth routes parse JSON]
               → UserRepository.get_by_username()  [Data layer]
               → bcrypt.verify(password, hash)      [Application layer]
               → session["user_id"] = id
               ← 200 { user_id, username, role }
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    # ── Delegate to Application / Data layer ─────────────────────────────
    # Stage 7 will replace this stub with real DB lookup and bcrypt verify.
    # from patterns.singleton_meta import UserRepository
    # from patterns.user_factory    import UserFactory
    # user = UserRepository().get_by_username(username)
    # if not user or not bcrypt.checkpw(password.encode(), user._password_hash):
    #     return jsonify({"error": "Invalid credentials"}), 401

    # Stub: accept any credentials for scaffolding purposes.
    session["user_id"]   = 1
    session["user_role"] = "researcher"
    session["username"]  = username

    return jsonify({
        "user_id":  session["user_id"],
        "username": session["username"],
        "role":     session["user_role"],
    }), 200


@auth_bp.post("/logout")
@login_required
def logout():
    """
    POST /api/auth/logout
    ---------------------
    Clear the current user's session.

    Response (200 OK):
        { "message": "Logged out successfully" }
    """
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.get("/me")
@login_required
def me():
    """
    GET /api/auth/me
    ----------------
    Return the profile of the currently authenticated user.

    Response (200 OK):
        { "user_id": int, "username": str, "role": str }
    """
    return jsonify({
        "user_id":  g.current_user_id,
        "username": session.get("username"),
        "role":     session.get("user_role"),
    }), 200
