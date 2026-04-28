import cgi
import hashlib
import http.cookies
import json
import os
import secrets
import socketserver
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
POSTS_FILE = os.path.join(DATA_DIR, "posts.json")
SESSION_COOKIE = "DSPRSESSION"

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(default, file, indent=2)
        return default
    with open(path, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


USERS = load_json(USERS_FILE, [])
POSTS = load_json(POSTS_FILE, [])
SESSIONS = {}


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def verify_password(stored_password, password):
    try:
        salt, hashed = stored_password.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored_password


def get_cookie_value(headers, name):
    cookie = http.cookies.SimpleCookie()
    if "Cookie" in headers:
        cookie.load(headers["Cookie"])
        if name in cookie:
            return cookie[name].value
    return None


def make_session(username):
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = {
        "username": username,
        "created": datetime.utcnow().isoformat() + "Z"
    }
    return token


def get_user_from_session(headers):
    session_id = get_cookie_value(headers, SESSION_COOKIE)
    session = SESSIONS.get(session_id)
    if session:
        username = session["username"]
        return next((user for user in USERS if user["username"] == username), None)
    return None


class DSPRHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api"):
            self.handle_api_get(parsed)
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api"):
            self.handle_api_post(parsed)
            return
        self.send_error(404, "Not Found")

    def handle_api_get(self, parsed):
        if parsed.path == "/api/posts":
            self.send_json({"posts": POSTS})
        elif parsed.path == "/api/me":
            user = get_user_from_session(self.headers)
            if user:
                self.send_json({"user": {"username": user["username"], "name": user["name"]}})
            else:
                self.send_json({"user": None})
        else:
            self.send_json({"error": "Unknown API endpoint"}, status=404)

    def handle_api_post(self, parsed):
        if parsed.path == "/api/signup":
            self.handle_signup()
        elif parsed.path == "/api/login":
            self.handle_login()
        elif parsed.path == "/api/logout":
            self.handle_logout()
        elif parsed.path == "/api/upload":
            self.handle_upload()
        else:
            self.send_json({"error": "Unknown API endpoint"}, status=404)

    def handle_signup(self):
        data = self.read_json_body()
        if not data:
            return
        username = data.get("username", "").strip()
        password = data.get("password", "")
        name = data.get("name", "").strip() or username
        if not username or not password:
            self.send_json({"error": "Username and password are required."}, status=400)
            return
        if any(user["username"].lower() == username.lower() for user in USERS):
            self.send_json({"error": "Username already exists."}, status=400)
            return
        user = {
            "username": username,
            "name": name,
            "password": hash_password(password),
            "joined": datetime.utcnow().isoformat() + "Z"
        }
        USERS.append(user)
        save_json(USERS_FILE, USERS)
        token = make_session(username)
        self.set_session_cookie(token)
        self.send_json({"success": True, "user": {"username": username, "name": name}})

    def handle_login(self):
        data = self.read_json_body()
        if not data:
            return
        username = data.get("username", "").strip()
        password = data.get("password", "")
        user = next((user for user in USERS if user["username"].lower() == username.lower()), None)
        if not user or not verify_password(user["password"], password):
            self.send_json({"error": "Invalid username or password."}, status=400)
            return
        token = make_session(user["username"])
        self.set_session_cookie(token)
        self.send_json({"success": True, "user": {"username": user["username"], "name": user["name"]}})

    def handle_logout(self):
        cookie = get_cookie_value(self.headers, SESSION_COOKIE)
        if cookie and cookie in SESSIONS:
            del SESSIONS[cookie]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

    def handle_upload(self):
        user = get_user_from_session(self.headers)
        if not user:
            self.send_json({"error": "Must be logged in to upload."}, status=401)
            return
        content_type = self.headers.get("Content-Type", "")
        environ = {"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type, "CONTENT_LENGTH": self.headers.get("Content-Length", "0")}
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ)
        image_field = form["image"] if "image" in form else None
        caption = form.getfirst("caption", "").strip()
        if not image_field or not image_field.filename:
            self.send_json({"error": "Image file is required."}, status=400)
            return
        filename = os.path.basename(image_field.filename)
        extension = os.path.splitext(filename)[1].lower()
        if extension not in [".jpg", ".jpeg", ".png", ".gif"]:
            self.send_json({"error": "Only JPG, PNG, and GIF files are accepted."}, status=400)
            return
        save_name = f"{secrets.token_hex(10)}{extension}"
        save_path = os.path.join(UPLOAD_DIR, save_name)
        with open(save_path, "wb") as file:
            file.write(image_field.file.read())
        post = {
            "id": len(POSTS) + 1,
            "username": user["username"],
            "name": user["name"],
            "caption": caption,
            "image": f"/uploads/{save_name}",
            "created": datetime.utcnow().isoformat() + "Z"
        }
        POSTS.insert(0, post)
        save_json(POSTS_FILE, POSTS)
        self.send_json({"success": True, "post": post})

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self.send_json({"error": "Missing request body."}, status=400)
            return None
        body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Request body must be valid JSON."}, status=400)
            return None

    def set_session_cookie(self, token):
        self._pending_cookie = f"{SESSION_COOKIE}={token}; Path=/; HttpOnly"

    def send_json(self, data, status=200):
        if self.wfile.closed:
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if hasattr(self, "_pending_cookie") and self._pending_cookie:
            self.send_header("Set-Cookie", self._pending_cookie)
            self._pending_cookie = None
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        if path.startswith("/uploads/"):
            file_path = os.path.join(UPLOAD_DIR, os.path.relpath(path[len("/uploads/"):], "/"))
            return self.serve_file(file_path)
        file_path = os.path.join(STATIC_DIR, os.path.normpath(path.lstrip("/")))
        self.serve_file(file_path)

    def serve_file(self, file_path):
        if not os.path.commonpath([os.path.abspath(file_path), os.path.abspath(STATIC_DIR)]) == os.path.abspath(STATIC_DIR) and not os.path.commonpath([os.path.abspath(file_path), os.path.abspath(UPLOAD_DIR)]) == os.path.abspath(UPLOAD_DIR):
            self.send_error(403, "Forbidden")
            return
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "Not Found")
            return
        content_type = self.guess_type(file_path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        with open(file_path, "rb") as file:
            self.wfile.write(file.read())

    def guess_type(self, path):
        if path.endswith(".html"):
            return "text/html; charset=utf-8"
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if path.endswith(".svg"):
            return "image/svg+xml"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".jpg") or path.endswith(".jpeg"):
            return "image/jpeg"
        if path.endswith(".gif"):
            return "image/gif"
        return "application/octet-stream"


if __name__ == "__main__":
    port = 8000
    print(f"Starting DSPR website at http://localhost:{port}")
    with socketserver.TCPServer(("", port), DSPRHandler) as httpd:
        httpd.serve_forever()
