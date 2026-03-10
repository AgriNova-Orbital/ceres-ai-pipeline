# WebUI User-level OAuth Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement User-level Google OAuth in the WebUI to authorize Earth Engine and Google Drive API access per user, removing the need for a global service account.

**Architecture:** Use `Authlib` to handle the OAuth flow in Flask. Store the resulting credentials (access token, refresh token) in the user's session. When enqueuing background tasks (like data export), pass these credentials so the worker can act on behalf of the user. Protect all routes except the login page.

**Tech Stack:** Python 3.12, Flask, Authlib, requests.

---

### Task 1: Add OAuth Dependencies

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_oauth_deps_importable.py`

**Step 1: Write the failing test**

```python
# tests/test_oauth_deps_importable.py
def test_authlib_is_importable():
    import authlib
    assert authlib is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_oauth_deps_importable.py -q`
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

Add `authlib` to `pyproject.toml`.

```toml
# pyproject.toml
[project]
dependencies = [
    # ... existing deps
    "authlib>=1.3.0",
    "requests>=2.31.0", # usually already there, but ensure it
]
```

**Step 4: Run dependency sync**

Run: `uv sync --dev`

**Step 5: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_oauth_deps_importable.py -q`

**Step 6: Commit**

```bash
git add pyproject.toml uv.lock tests/test_oauth_deps_importable.py
git commit -m "feat: add authlib dependency for webui oauth"
```

### Task 2: Implement Flask OAuth Setup and Login Route

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Test: `tests/test_webui_oauth_routes.py`

**Step 1: Write the failing test**

```python
# tests/test_webui_oauth_routes.py
from pathlib import Path
import pytest

@pytest.fixture
def app(tmp_path):
    from apps.wheat_risk_webui import create_app
    app = create_app(repo_root=tmp_path)
    app.config.update({"TESTING": True})
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_login_route_redirects_to_google(client):
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["Location"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_webui_oauth_routes.py -q`

**Step 3: Write minimal implementation**

In `apps/wheat_risk_webui.py`:
1. Import `OAuth` from `authlib.integrations.flask_client`.
2. Initialize `oauth = OAuth(app)`.
3. Register the Google client using `oauth.register()`.  Read `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from environment variables (use dummy defaults for now or load from dotenv). Set the scope to include `openid email profile https://www.googleapis.com/auth/earthengine https://www.googleapis.com/auth/drive`.
4. Create the `/login` route which calls `oauth.google.authorize_redirect(redirect_uri=url_for('auth', _external=True))`.

```python
# snippet for apps/wheat_risk_webui.py
import os
from authlib.integrations.flask_client import OAuth

# inside create_app:
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', 'dummy_id'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', 'dummy_secret'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/earthengine https://www.googleapis.com/auth/drive'
    }
)

@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth():
    return "Callback stub" # implementation in next task
```

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_webui_oauth_routes.py -q`

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py tests/test_webui_oauth_routes.py
git commit -m "feat(webui): configure authlib and add login route"
```

### Task 3: Implement Auth Callback, Logout, and Route Protection

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `tests/test_webui_oauth_routes.py`

**Step 1: Write the failing test**

```python
# append to tests/test_webui_oauth_routes.py
def test_protected_routes_redirect_to_login(client):
    # If not logged in, accessing home should redirect to login (or show login button)
    # Let's enforce redirection for all main routes
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --dev pytest tests/test_webui_oauth_routes.py::test_protected_routes_redirect_to_login -q`

**Step 3: Write minimal implementation**

In `apps/wheat_risk_webui.py`:
1. Implement `/auth/callback`:
   ```python
   from flask import session
   @app.route('/auth/callback')
   def auth():
       token = oauth.google.authorize_access_token()
       user = oauth.google.parse_id_token(token, None)
       session['user'] = user
       session['google_token'] = token # Store the token for API calls
       return redirect('/')
   ```
2. Implement `/logout`:
   ```python
   @app.route('/logout')
   def logout():
       session.pop('user', None)
       session.pop('google_token', None)
       return redirect('/')
   ```
3. Add a `before_request` hook to protect routes:
   ```python
   @app.before_request
   def require_login():
       allowed_routes = ['login', 'auth', 'static']
       if request.endpoint not in allowed_routes and 'user' not in session:
           return redirect(url_for('login'))
   ```

**Step 4: Run test to verify it passes**

Run: `uv run --dev pytest tests/test_webui_oauth_routes.py -q`

**Step 5: Commit**

```bash
git add apps/wheat_risk_webui.py tests/test_webui_oauth_routes.py
git commit -m "feat(webui): implement oauth callback, logout, and route protection"
```

### Task 4: Pass Credentials to Background Jobs

**Files:**
- Modify: `apps/wheat_risk_webui.py`
- Modify: `modules/jobs/tasks.py`

**Step 1: Write the failing test**

(Manual testing required as full integration test with mock redis/rq/oauth is complex. We will verify the logic passes the token in the `enqueue` call).

**Step 2: Write minimal implementation**

1. Modify the enqueuing logic in `apps/wheat_risk_webui.py` (specifically `/run/downloader` for now) to pass the token.
   ```python
   # in run_downloader:
   job_kwargs = dict(request.form)
   job_kwargs['google_token'] = session.get('google_token') # Pass the token!
   ```
2. In `modules/jobs/tasks.py` (specifically `task_run_downloader` or similar if it exists, or update the generic `run_script` task wrapper), extract the token and set up the environment before running the actual script.
   *Note: For the python scripts, it's often easiest to write the token to a temporary JSON file and point `GOOGLE_APPLICATION_CREDENTIALS` to it, or pass it via a specific environment variable if the script is modified to accept it. Since `ee` library usually expects a file or default environment credentials, a temp file is robust.*

   ```python
   # modules/jobs/tasks.py snippet concept
   import tempfile
   import json
   import os
   
   def task_with_credentials(kwargs: dict):
       token = kwargs.pop('google_token', None)
       env = os.environ.copy()
       if token:
           # In a real scenario, you'd format this as a standard service account JSON 
           # or use the user credentials directly if your script supports it.
           # For user oauth tokens, the google-auth library handles them differently 
           # than service accounts.
           pass
       # ... run the underlying service ...
   ```
   *Correction*: Since we are doing user-level OAuth, the `token` dictionary obtained from authlib contains `access_token` and `refresh_token`. The `google-auth` library can construct a `Credentials` object from these. Our `gee_api.py` initialization needs to be updated to accept these credentials directly instead of relying solely on the default environment project setup.
   
   Let's simplify for this task: just ensure the token dictionary is passed into the `job_kwargs` in the WebUI. We will handle the actual credential construction inside the worker task later.

   Update `run_downloader`, `run_build`, `run_train_matrix`, `run_eval` in `wheat_risk_webui.py` to include:
   ```python
   job_kwargs['oauth_token'] = session.get('google_token')
   ```

**Step 3: Commit**

```bash
git add apps/wheat_risk_webui.py modules/jobs/tasks.py
git commit -m "feat(webui): pass user oauth token to background job kwargs"
```
