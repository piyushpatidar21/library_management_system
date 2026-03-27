from __future__ import annotations

from datetime import date, timedelta

from database import db_cursor, init_db, table_has_rows


def seed() -> None:
    init_db()
    if table_has_rows('users'):
        return

    today = date.today()
    with db_cursor() as (conn, cur):
        cur.executemany(
            '''INSERT INTO users (username, password, full_name, is_admin, is_active)
               VALUES (?, ?, ?, ?, ?)''',
            [
                ('adm', 'adm', 'Admin User', 1, 1),
                ('user', 'user', 'General User', 0, 1),
                ('librarian', 'lib123', 'Library Staff', 1, 1),
            ],
        )

        memberships = [
            ('M1001', 'Piyush', 'Patidar', '9999999991', 'Indore', '123412341234', today.isoformat(), (today + timedelta(days=365)).isoformat(), 'One Year', 'Active', 0),
            ('M1002', 'Aman', 'Sharma', '9999999992', 'Bhopal', '123412341235', today.isoformat(), (today + timedelta(days=180)).isoformat(), 'Six Months', 'Active', 0),
            ('M1003', 'Riya', 'Jain', '9999999993', 'Ujjain', '123412341236', today.isoformat(), (today + timedelta(days=730)).isoformat(), 'Two Years', 'Active', 20),
        ]
        cur.executemany(
            '''INSERT INTO memberships (membership_code, first_name, last_name, contact_number, contact_address, aadhaar_no, start_date, end_date, membership_type, status, fine_pending)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            memberships,
        )

        items = [
            ('SCB000001', 'Book', 'Physics Fundamentals', 'A. K. Rao', 'Science', 399, (today - timedelta(days=150)).isoformat(), 'Available'),
            ('SCB000002', 'Book', 'Chemistry Basics', 'S. Mehta', 'Science', 350, (today - timedelta(days=120)).isoformat(), 'Available'),
            ('ECB000001', 'Book', 'Micro Economics', 'R. Sen', 'Economics', 499, (today - timedelta(days=100)).isoformat(), 'Issued'),
            ('FCB000001', 'Book', 'The Silent River', 'N. Kapoor', 'Fiction', 299, (today - timedelta(days=90)).isoformat(), 'Available'),
            ('CHB000001', 'Book', 'Young Explorer', 'T. Verma', 'Children', 250, (today - timedelta(days=80)).isoformat(), 'Available'),
            ('PDB000001', 'Book', 'Atomic Habits', 'James Clear', 'Personal Development', 550, (today - timedelta(days=60)).isoformat(), 'Available'),
            ('SCM000001', 'Movie', 'Interstellar', 'Christopher Nolan', 'Science', 699, (today - timedelta(days=200)).isoformat(), 'Available'),
            ('FCM000001', 'Movie', 'The Great Story', 'A. Director', 'Fiction', 599, (today - timedelta(days=50)).isoformat(), 'Available'),
        ]
        cur.executemany(
            '''INSERT INTO catalog_items (serial_no, item_type, title, author_name, category, cost, procurement_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            items,
        )

        cur.execute('SELECT id FROM memberships WHERE membership_code = ?', ('M1002',))
        membership_id = cur.fetchone()[0]
        cur.execute('SELECT id FROM catalog_items WHERE serial_no = ?', ('ECB000001',))
        item_id = cur.fetchone()[0]
        cur.execute(
            '''INSERT INTO issues (issue_code, membership_id, item_id, issue_date, due_date, remarks, fine_amount, fine_paid, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                'ISS1001', membership_id, item_id,
                (today - timedelta(days=10)).isoformat(),
                (today + timedelta(days=5)).isoformat(),
                'Seed active issue', 0, 0, 'Issued'
            )
        )

        cur.execute(
            '''INSERT INTO issue_requests (membership_id, item_name, requested_date, request_fulfilled_date, status)
               VALUES (?, ?, ?, ?, ?)''',
            (membership_id, 'Data Structures', today.isoformat(), None, 'Pending')
        )


if __name__ == '__main__':
    seed()
