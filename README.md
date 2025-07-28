## Project_ZeroTrace

### ⚙️ Backend Setup

1. Navigate to the backend directory:

   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create and configure development.env (see .env.example)

5. Run database migrations (using SQLAlchemy/Alembic, assuming setup):

   ```bash
   alembic upgrade head
   ```

6. Run tests:
   ```
   python -m pytest -vv
   ```
7. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

### 🖥 Frontend Setup

1. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Start the React development server:

   ```bash
   npm start
   ```

   The frontend will be available at `http://localhost:3000`.

TODO
Fix OAuth2 in login router
Create and update models
UUIDs for IDs
Timestamp convertion to datetime for DB
