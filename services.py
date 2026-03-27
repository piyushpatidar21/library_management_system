from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd

from database import db_cursor

FINE_PER_DAY = 10


def fetch_df(query: str, params: tuple = ()) -> pd.DataFrame:
    with db_cursor() as (conn, cur):
        return pd.read_sql_query(query, conn, params=params)


def get_dashboard_metrics() -> dict[str, Any]:
    with db_cursor() as (conn, cur):
        cur.execute('SELECT COUNT(*) FROM catalog_items')
        total_items = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM catalog_items WHERE status='Available'")
        available_items = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM issues WHERE status='Issued'")
        active_issues = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM memberships WHERE status='Active'")
        active_memberships = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(fine_pending),0) FROM memberships")
        pending_fines = cur.fetchone()[0]
        return {
            'Total Items': total_items,
            'Available Items': available_items,
            'Active Issues': active_issues,
            'Active Memberships': active_memberships,
            'Pending Fines': pending_fines,
        }


def category_wise_counts() -> pd.DataFrame:
    return fetch_df(
        '''SELECT category, COUNT(*) AS total
           FROM catalog_items
           GROUP BY category
           ORDER BY total DESC'''
    )


def issue_status_counts() -> pd.DataFrame:
    return fetch_df(
        '''SELECT status, COUNT(*) AS total
           FROM issues
           GROUP BY status'''
    )


def search_available_items(title: str = '', author: str = '') -> pd.DataFrame:
    query = '''
        SELECT id, serial_no, item_type, title, author_name, category, status
        FROM catalog_items
        WHERE 1=1
    '''
    params: list[Any] = []
    if title:
        query += ' AND title LIKE ?'
        params.append(f'%{title}%')
    if author:
        query += ' AND author_name LIKE ?'
        params.append(f'%{author}%')
    query += ' ORDER BY title'
    return fetch_df(query, tuple(params))


def get_titles(item_type: Optional[str] = None) -> list[str]:
    query = 'SELECT DISTINCT title FROM catalog_items WHERE 1=1'
    params = []
    if item_type:
        query += ' AND item_type = ?'
        params.append(item_type)
    query += ' ORDER BY title'
    df = fetch_df(query, tuple(params))
    return df['title'].tolist() if not df.empty else []


def get_authors_by_title(title: str) -> list[str]:
    df = fetch_df('SELECT DISTINCT author_name FROM catalog_items WHERE title = ? ORDER BY author_name', (title,))
    return df['author_name'].tolist() if not df.empty else []


def get_serials_for_return(title: str) -> list[str]:
    df = fetch_df(
        '''SELECT c.serial_no
           FROM issues i
           JOIN catalog_items c ON c.id = i.item_id
           WHERE i.status = 'Issued' AND c.title = ?''',
        (title,),
    )
    return df['serial_no'].tolist() if not df.empty else []


def get_membership_codes() -> list[str]:
    df = fetch_df("SELECT membership_code FROM memberships WHERE status='Active' ORDER BY membership_code")
    return df['membership_code'].tolist() if not df.empty else []


def issue_book(membership_code: str, title: str, author_name: str, issue_date: date, due_date: date, remarks: str = '') -> tuple[bool, str]:
    today = date.today()
    if issue_date < today:
        return False, 'Issue date cannot be earlier than today.'
    if due_date > issue_date + timedelta(days=15):
        return False, 'Return date cannot be more than 15 days after issue date.'
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id FROM memberships WHERE membership_code = ? AND status = 'Active'", (membership_code,))
        membership = cur.fetchone()
        if not membership:
            return False, 'Valid active membership is required.'

        cur.execute(
            '''SELECT id, serial_no FROM catalog_items
               WHERE title = ? AND author_name = ? AND status = 'Available'
               ORDER BY serial_no LIMIT 1''',
            (title, author_name),
        )
        item = cur.fetchone()
        if not item:
            return False, 'No available copy found for the selected book/movie.'

        cur.execute('SELECT COUNT(*) FROM issues')
        count = cur.fetchone()[0] + 1
        issue_code = f'ISS{1000 + count}'

        cur.execute(
            '''INSERT INTO issues (issue_code, membership_id, item_id, issue_date, due_date, remarks, fine_amount, fine_paid, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (issue_code, membership['id'], item['id'], issue_date.isoformat(), due_date.isoformat(), remarks.strip(), 0, 0, 'Issued')
        )
        cur.execute("UPDATE catalog_items SET status='Issued' WHERE id = ?", (item['id'],))
        return True, f'Book issued successfully. Serial No: {item["serial_no"]}'


def get_issue_details_by_serial(serial_no: str) -> Optional[dict]:
    with db_cursor() as (conn, cur):
        cur.execute(
            '''SELECT i.id as issue_id, c.title, c.author_name, c.serial_no, i.issue_date, i.due_date,
                      i.return_date, i.fine_amount, i.fine_paid, i.status, m.membership_code
               FROM issues i
               JOIN catalog_items c ON c.id = i.item_id
               JOIN memberships m ON m.id = i.membership_id
               WHERE c.serial_no = ? AND i.status = 'Issued' ''',
            (serial_no,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def return_book(serial_no: str, actual_return_date: date, remarks: str = '') -> tuple[bool, str]:
    details = get_issue_details_by_serial(serial_no)
    if not details:
        return False, 'No active issue found for the selected serial number.'
    due_date = datetime.strptime(details['due_date'], '%Y-%m-%d').date()
    fine = max((actual_return_date - due_date).days, 0) * FINE_PER_DAY
    with db_cursor() as (conn, cur):
        cur.execute(
            '''UPDATE issues
               SET return_date = ?, remarks = COALESCE(NULLIF(?, ''), remarks), fine_amount = ?, status = 'Returned'
               WHERE id = ?''',
            (actual_return_date.isoformat(), remarks.strip(), fine, details['issue_id'])
        )
        cur.execute("UPDATE catalog_items SET status='Available' WHERE serial_no = ?", (serial_no,))
        cur.execute(
            '''UPDATE memberships
               SET fine_pending = fine_pending + ?
               WHERE membership_code = ?''',
            (fine, details['membership_code'])
        )
    return True, f'Item returned successfully. Fine calculated: ₹{fine}'


def pay_fine(serial_no: str, actual_return_date: date, fine_paid: bool, remarks: str = '') -> tuple[bool, str, float]:
    details = get_issue_details_by_serial(serial_no)
    if not details:
        return False, 'No active issue found for the selected serial number.', 0.0
    due_date = datetime.strptime(details['due_date'], '%Y-%m-%d').date()
    fine = max((actual_return_date - due_date).days, 0) * FINE_PER_DAY
    with db_cursor() as (conn, cur):
        cur.execute(
            '''UPDATE issues
               SET return_date = ?, fine_amount = ?, fine_paid = ?, remarks = ?, status = ?
               WHERE id = ?''',
            (
                actual_return_date.isoformat(), fine, int(fine_paid), remarks.strip(),
                'Closed' if fine_paid else 'Returned', details['issue_id']
            )
        )
        if fine_paid:
            cur.execute("UPDATE catalog_items SET status='Available' WHERE serial_no = ?", (serial_no,))
            cur.execute(
                '''UPDATE memberships
                   SET fine_pending = CASE WHEN fine_pending - ? < 0 THEN 0 ELSE fine_pending - ? END
                   WHERE membership_code = ?''',
                (fine, fine, details['membership_code'])
            )
            if fine > 0:
                cur.execute(
                    'INSERT INTO payments (issue_id, amount, paid_on, remarks) VALUES (?, ?, ?, ?)',
                    (details['issue_id'], fine, date.today().isoformat(), remarks.strip())
                )
    return True, 'Fine flow processed successfully.', fine


def create_issue_request(membership_code: str, item_name: str) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id FROM memberships WHERE membership_code = ? AND status = 'Active'", (membership_code,))
        member = cur.fetchone()
        if not member:
            return False, 'Active membership is required for issue request.'
        cur.execute(
            '''INSERT INTO issue_requests (membership_id, item_name, requested_date, request_fulfilled_date, status)
               VALUES (?, ?, ?, ?, ?)''',
            (member['id'], item_name.strip(), date.today().isoformat(), None, 'Pending')
        )
        return True, 'Issue request saved successfully.'


def add_membership(data: dict[str, Any]) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        cur.execute('SELECT COUNT(*) FROM memberships')
        code = f"M{1001 + cur.fetchone()[0]}"
        try:
            cur.execute(
                '''INSERT INTO memberships
                   (membership_code, first_name, last_name, contact_number, contact_address, aadhaar_no, start_date, end_date, membership_type, status, fine_pending)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    code, data['first_name'].strip(), data['last_name'].strip(), data['contact_number'].strip(),
                    data['contact_address'].strip(), data['aadhaar_no'].strip(), data['start_date'].isoformat(),
                    data['end_date'].isoformat(), data['membership_type'], 'Active', 0,
                )
            )
            return True, f'Membership created successfully with ID {code}'
        except Exception as exc:
            return False, f'Unable to create membership: {exc}'


def extend_or_remove_membership(membership_code: str, start_date: date, end_date: date, action: str) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        if action == 'Remove Membership':
            cur.execute("UPDATE memberships SET status='Inactive', end_date=? WHERE membership_code=?", (end_date.isoformat(), membership_code))
            return True, 'Membership marked as inactive.'
        cur.execute(
            '''UPDATE memberships
               SET start_date = ?, end_date = ?, membership_type = ?, status='Active'
               WHERE membership_code = ?''',
            (start_date.isoformat(), end_date.isoformat(), action, membership_code)
        )
        return True, 'Membership updated successfully.'


def add_catalog_item(data: dict[str, Any]) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        cur.execute('SELECT COUNT(*) FROM catalog_items')
        base_no = cur.fetchone()[0] + 1
        prefix = 'B' if data['item_type'] == 'Book' else 'M'
        for i in range(data['quantity']):
            serial = f"{data['category'][:2].upper()}{prefix}{base_no + i:06d}"
            cur.execute(
                '''INSERT INTO catalog_items
                   (serial_no, item_type, title, author_name, category, cost, procurement_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    serial, data['item_type'], data['title'].strip(), data['author_name'].strip(), data['category'],
                    data['cost'], data['procurement_date'].isoformat(), 'Available'
                )
            )
        return True, 'Book/Movie added successfully.'


def update_catalog_item(serial_no: str, status: str, item_date: date) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        cur.execute(
            '''UPDATE catalog_items SET status = ?, procurement_date = ? WHERE serial_no = ?''',
            (status, item_date.isoformat(), serial_no)
        )
        if cur.rowcount == 0:
            return False, 'Serial number not found.'
        return True, 'Book/Movie updated successfully.'


def add_or_update_user(username: str, password: str, full_name: str, is_active: bool, is_admin: bool, existing: bool) -> tuple[bool, str]:
    with db_cursor() as (conn, cur):
        if existing:
            cur.execute(
                '''UPDATE users
                   SET password = ?, full_name = ?, is_active = ?, is_admin = ?
                   WHERE username = ?''',
                (password.strip(), full_name.strip(), int(is_active), int(is_admin), username.strip())
            )
            if cur.rowcount == 0:
                return False, 'Existing user not found.'
            return True, 'User updated successfully.'
        try:
            cur.execute(
                '''INSERT INTO users (username, password, full_name, is_admin, is_active)
                   VALUES (?, ?, ?, ?, ?)''',
                (username.strip(), password.strip(), full_name.strip(), int(is_admin), int(is_active))
            )
            return True, 'User added successfully.'
        except Exception as exc:
            return False, f'Unable to add user: {exc}'


def books_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT serial_no AS "Serial No", title AS "Name of Book", author_name AS "Author Name", category AS Category,
                  status AS Status, cost AS Cost, procurement_date AS "Procurement Date"
           FROM catalog_items WHERE item_type='Book' ORDER BY title'''
    )


def movies_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT serial_no AS "Serial No", title AS "Name of Movie", author_name AS "Author Name", category AS Category,
                  status AS Status, cost AS Cost, procurement_date AS "Procurement Date"
           FROM catalog_items WHERE item_type='Movie' ORDER BY title'''
    )


def memberships_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT membership_code AS "Membership Id",
                  first_name || ' ' || last_name AS "Name of Member",
                  contact_number AS "Contact Number",
                  contact_address AS "Contact Address",
                  aadhaar_no AS "Aadhar Card No",
                  start_date AS "Start Date of Membership",
                  end_date AS "End Date of Membership",
                  status AS "Status (Active/Inactive)",
                  fine_pending AS "Amount Pending(Fine)"
           FROM memberships ORDER BY membership_code'''
    )


def active_issues_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT c.serial_no AS "Serial No Book/Movie", c.title AS "Name of Book/Movie", m.membership_code AS "Membership Id",
                  i.issue_date AS "Date of Issue", i.due_date AS "Date of Return"
           FROM issues i
           JOIN catalog_items c ON c.id = i.item_id
           JOIN memberships m ON m.id = i.membership_id
           WHERE i.status = 'Issued'
           ORDER BY i.issue_date DESC'''
    )


def overdue_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT c.serial_no AS "Serial No Book", c.title AS "Name of Book", m.membership_code AS "Membership Id",
                  i.issue_date AS "Date of Issue", i.due_date AS "Date of Return",
                  CASE WHEN julianday('now') - julianday(i.due_date) > 0 THEN CAST((julianday('now') - julianday(i.due_date)) AS INTEGER) * ? ELSE 0 END AS "Fine Calculations"
           FROM issues i
           JOIN catalog_items c ON c.id = i.item_id
           JOIN memberships m ON m.id = i.membership_id
           WHERE i.status = 'Issued' AND date(i.due_date) < date('now')''',
        (FINE_PER_DAY,),
    )


def issue_requests_report() -> pd.DataFrame:
    return fetch_df(
        '''SELECT m.membership_code AS "Membership Id", ir.item_name AS "Name of Book/Movie",
                  ir.requested_date AS "Requested Date", ir.request_fulfilled_date AS "Request Fulfilled Date", ir.status AS Status
           FROM issue_requests ir
           JOIN memberships m ON m.id = ir.membership_id
           ORDER BY ir.requested_date DESC'''
    )
