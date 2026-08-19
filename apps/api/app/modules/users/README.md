# Module Specification: `users`

## 1. Overview & Responsibilities
The `users` module is responsible for user account management, identity authentication, credentials security, and OAuth integration (Google Sign-In). It serves as the primary authorization boundary across the platform, linking users to their owned agents, migration plans, and data sources.

---

## 2. Directory & File Inventory

| File / Subfolder | Layer / Type | Description |
| :--- | :--- | :--- |
| `users_models.py` | Database Models | `User` SQLAlchemy ORM entity definition |
| `users_schemas.py` | Schemas (DTOs) | Pydantic validation models (`UserRegister`, `UserLogin`, `UserUpdate`, `UserResponse`, `GoogleAuthRequest`, `TokenResponse`) |
| `users_services.py` | Business Logic | `UserService` static class with password hashing, account creation, Google auth isolation, and CRUD operations |
| `users_routes.py` | API Controller | FastAPI router defining endpoints for `/api/v1/auth` and `/api/v1/users` |
| `users_dependencies.py` | Auth Middleware | `get_current_user` and `get_current_active_user` FastAPI dependency injectors for JWT verification |

---

## 3. Database Entities & Affected Tables

### Primary Tables Owned
1. **`users`** (`User`)
   - **Primary Key:** `id` (`UUID`)
   - **Unique Constraints:** `email` (unique index), `google_id` (unique index)
   - **Attributes:** `email`, `password_hash` (bcrypt), `google_id`, `name`, `is_active` (boolean), `created_at`, `updated_at`
   - **Cascade Relationships:**
     - `agents` (One-to-Many, CASCADE delete)
     - `migration_plans` (One-to-Many, CASCADE delete)

---

## 4. Service Layer Specification (`UserService`)

### 1. `get_user_by_id(db, user_id)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active SQLAlchemy async database session.
  - `user_id` (`uuid.UUID`): Primary key UUID of target user.
- **Return Value:** `Optional[User]` - Returns `User` ORM object if found; `None` otherwise.
- **Business Logic:**
  1. Executes async SQLAlchemy `select(User).where(User.id == user_id)` query.
  2. Returns single scalar result or `None`.
- **Affected Tables:** `users` (SELECT)
- **Exceptions:** None.

---

### 2. `get_user_by_email(db, email)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `email` (`str`): User email address string.
- **Return Value:** `Optional[User]` - Returns matching `User` record or `None`.
- **Business Logic:**
  1. Normalizes email string by lowercasing and trimming leading/trailing whitespace (`email.lower().strip()`).
  2. Queries `users` table filtering on normalized `email`.
- **Affected Tables:** `users` (SELECT)
- **Exceptions:** None.

---

### 3. `get_user_by_google_id(db, google_id)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `google_id` (`str`): Google OAuth subject ID string (`sub`).
- **Return Value:** `Optional[User]` - Returns linked `User` record or `None`.
- **Business Logic:**
  1. Queries `users` table filtering on `google_id == google_id`.
- **Affected Tables:** `users` (SELECT)
- **Exceptions:** None.

---

### 4. `create_user(db, payload)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `payload` (`UserRegister`): Pydantic DTO containing `email`, `password`, and `name`.
- **Return Value:** `User` - Freshly registered and persisted `User` database record.
- **Business Logic:**
  1. Checks if an account already exists with `payload.email` via `get_user_by_email()`.
  2. If account exists with `google_id` and no `password_hash`, raises `HTTP 409 Conflict` ("Account was created using Google Sign-In").
  3. If account exists with password, raises `HTTP 409 Conflict` ("User with this email address already exists").
  4. Hashes `payload.password` using `passlib` bcrypt (`hash_password`).
  5. Instantiates `User` ORM instance with lowercased email, hashed password, trimmed name, and `is_active=True`.
  6. Adds instance to DB session, commits transaction, and refreshes object state.
- **Affected Tables:** `users` (SELECT, INSERT)
- **Exceptions:**
  - `HTTPException(409 Conflict)`: If email is already registered.

---

### 5. `get_or_create_google_user(db, google_id, email, name, email_verified)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `google_id` (`str`): Google OAuth unique subject identifier.
  - `email` (`str`): User email address provided by Google token.
  - `name` (`str`): Display name from Google profile.
  - `email_verified` (`bool`, default=`True`): Claims flag verifying email authenticity.
- **Return Value:** `User` - Authenticated or newly created Google user record.
- **Business Logic:**
  1. **Email Verification Guard:** Rejects authentication if `email_verified` is `False`.
  2. **Lookup by Google ID:** If user exists by `google_id`:
     - Checks `is_active` status. If deactivated, raises `HTTP 400 Bad Request`.
     - Returns user.
  3. **Lookup by Email:** If no user found by `google_id`, checks if user exists by `email`:
     - Checks `is_active`. If deactivated, raises `HTTP 400 Bad Request`.
     - If existing user has a different `google_id`, raises `HTTP 409 Conflict`.
     - If existing user registered via password and has no `google_id`, raises `HTTP 409 Conflict` to prevent silent account takeover.
     - Otherwise, links `google_id` to existing account, commits DB update, and returns user.
  4. **Account Provisioning:** If no account exists by email or Google ID, creates new `User` with `google_id`, `password_hash=None`, and `is_active=True`.
- **Affected Tables:** `users` (SELECT, INSERT, UPDATE)
- **Exceptions:**
  - `HTTPException(400 Bad Request)`: Unverified email or deactivated account.
  - `HTTPException(409 Conflict)`: Email registered via password auth or mismatching Google ID.

---

### 6. `authenticate_user(db, email, password)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `email` (`str`): User login email.
  - `password` (`str`): Raw plaintext login password.
- **Return Value:** `User` - Validated user instance.
- **Business Logic:**
  1. Queries user by email via `get_user_by_email()`.
  2. If user not found, raises `HTTP 401 Unauthorized` ("Invalid email or password").
  3. If user `is_active` is `False`, raises `HTTP 400 Bad Request` ("Account deactivated").
  4. If `user.password_hash` is `None` (Google-only user), raises `HTTP 400 Bad Request` ("Account created using Google Sign-In").
  5. Verifies `password` against `user.password_hash` using bcrypt (`verify_password`). If invalid, raises `HTTP 401 Unauthorized`.
  6. Returns authenticated `User` record upon success.
- **Affected Tables:** `users` (SELECT)
- **Exceptions:**
  - `HTTPException(401 Unauthorized)`: Invalid email or password.
  - `HTTPException(400 Bad Request)`: Deactivated account or Google SSO account.

---

### 7. `update_user(db, user, payload)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `user` (`User`): Active user ORM instance being updated.
  - `payload` (`UserUpdate`): DTO containing optional fields (`email`, `name`, `password`).
- **Return Value:** `User` - Updated and refreshed user instance.
- **Business Logic:**
  1. If `payload.email` provided and differs from current email:
     - Checks if new email is in use by another user (`HTTP 409 Conflict`).
     - Updates `user.email`.
  2. If `payload.name` provided, updates `user.name`.
  3. If `payload.password` provided, re-hashes password via bcrypt and updates `user.password_hash`.
  4. Commits session and refreshes object.
- **Affected Tables:** `users` (SELECT, UPDATE)
- **Exceptions:**
  - `HTTPException(409 Conflict)`: Email address already in use.

---

### 8. `delete_user(db, user)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `user` (`User`): User ORM instance to delete.
- **Return Value:** `None`
- **Business Logic:**
  1. Calls `db.delete(user)`.
  2. Commits session, triggering database foreign key cascade deletion for owned agents, data sources, and migration plans.
- **Affected Tables:** `users` (DELETE, cascades to `agents`, `migration_plans`).
- **Exceptions:** None.

---

### 9. `list_users(db, skip, limit)`
- **Input Parameters:**
  - `db` (`AsyncSession`): Active database session.
  - `skip` (`int`, default=`0`): Offset count for pagination.
  - `limit` (`int`, default=`50`): Max records limit.
- **Return Value:** `List[User]` - List of user records ordered by `created_at desc`.
- **Business Logic:**
  1. Executes `select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)`.
  2. Returns list of matching user models.
- **Affected Tables:** `users` (SELECT)
- **Exceptions:** None.

---

## 5. API Routes Specification (`users_routes.py`)

| HTTP Method | Route Path | Description | Service Function Called | Auth Required |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new email/password user | `UserService.create_user` | No |
| `POST` | `/api/v1/auth/login` | Authenticate user & issue JWT bearer token | `UserService.authenticate_user` | No |
| `POST` | `/api/v1/auth/google` | OAuth authentication via Google id_token | `UserService.get_or_create_google_user` | No |
| `GET` | `/api/v1/users/me` | Fetch active user profile | Direct dependency lookup (`get_current_user`) | Yes (JWT) |
| `PUT` | `/api/v1/users/me` | Update active user profile | `UserService.update_user` | Yes (JWT) |
| `DELETE` | `/api/v1/users/me` | Delete active user account | `UserService.delete_user` | Yes (JWT) |

---

## 6. Inter-Module Dependencies

- **Incoming Dependencies (Modules referencing `users`):**
  - All feature modules (`agents`, `sources`, `metadata`, `migration_plans`, `execution`) depend on `users_dependencies.py` (`get_current_user`) to authenticate requests.
- **Outgoing Dependencies (`users` calls these):**
  - Standard database session (`AsyncSession`) and core security utilities (`app.core.security`).
