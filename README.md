# Library Management System

A Streamlit + Python + SQLite project built from the uploaded spreadsheet flow.

## Features covered from spreadsheet
- Admin login and user login
- Instructions page
- Chart/navigation page
- Admin and user home pages
- Transactions
  - Book availability search
  - Search results
  - Book issue
  - Return book
  - Pay fine
  - Cancel and confirmation flow
- Reports
  - Master list of books
  - Master list of movies
  - Master list of memberships
  - Active issues
  - Overdue returns
  - Issue requests
- Maintenance
  - Add membership
  - Update membership
  - Add book/movie
  - Update book/movie
  - User management
- Logout page behavior
- SQLite database with seed data
- Charts on home page

## Default login
- Admin: `adm` / `adm`
- User: `user` / `user`

## Project files
- `app.py` - main Streamlit UI
- `database.py` - SQLite connection and schema
- `seed_data.py` - inserts sample data
- `auth.py` - login check
- `services.py` - business logic for transactions, reports, maintenance
- `requirements.txt` - dependencies

## Run locally
```bash
cd library_management_system
python -m venv venv
# Windows
venv\Scripts\activate
pip install -r requirements.txt
python seed_data.py
streamlit run app.py
```

## Notes
- Passwords are kept plain only for student demo simplicity.
- This is a single Streamlit application with Python service layer and SQLite database.
