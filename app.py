from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from auth import authenticate_user
from database import init_db
from seed_data import seed
from services import (
    active_issues_report,
    add_catalog_item,
    add_membership,
    add_or_update_user,
    books_report,
    category_wise_counts,
    create_issue_request,
    extend_or_remove_membership,
    get_authors_by_title,
    get_dashboard_metrics,
    get_issue_details_by_serial,
    get_membership_codes,
    get_serials_for_return,
    get_titles,
    issue_book,
    issue_requests_report,
    issue_status_counts,
    memberships_report,
    movies_report,
    overdue_report,
    pay_fine,
    return_book,
    search_available_items,
    update_catalog_item,
)

st.set_page_config(page_title='Library Management System', page_icon='📚', layout='wide')
seed()
init_db()

if 'user' not in st.session_state:
    st.session_state.user = None
if 'message' not in st.session_state:
    st.session_state.message = None
if 'message_type' not in st.session_state:
    st.session_state.message_type = 'success'
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Login'


def set_message(msg: str, msg_type: str = 'success') -> None:
    st.session_state.message = msg
    st.session_state.message_type = msg_type


def show_message() -> None:
    if st.session_state.message:
        getattr(st, st.session_state.message_type)(st.session_state.message)
        st.session_state.message = None


def logout() -> None:
    st.session_state.user = None
    st.session_state.current_page = 'Login'
    set_message('You have successfully logged out.', 'success')


def back_to_home() -> None:
    st.session_state.current_page = 'Admin Home' if st.session_state.user and st.session_state.user['is_admin'] else 'User Home'


def render_login() -> None:
    st.title('📚 Library Management System')
    # st.caption('Based on the spreadsheet flow: login, instructions, transactions, reports, maintenance, update, cancel and confirmation.')
    tabs = st.tabs(['Instructions', 'Admin Login', 'User Login'])

    with tabs[0]:
        st.subheader('Instructions')
        st.markdown('''
        - Two types of login are available: **Admin** and **User**.
        - Password fields are hidden.
        - Admin can access **Maintenance, Reports, and Transactions**.
        - User can access **Reports and Transactions** only.
        - In **Book Issue**, issue date cannot be earlier than today and return date cannot be more than 15 days after issue date.
        - In **Search Results**, available rows can be selected for issue.
        - In **Pay Fine**, fine is calculated from overdue days and the checkbox marks payment completion.
        - Use **Cancel** to stop a flow and **Confirmation** appears after successful operations.
        ''')

    with tabs[1]:
        st.subheader('Admin Login')
        with st.form('admin_login_form'):
            username = st.text_input('User ID', value='adm')
            password = st.text_input('Password', type='password', value='adm')
            submitted = st.form_submit_button('Login')
            if submitted:
                user = authenticate_user(username, password)
                if user and user['is_admin']:
                    st.session_state.user = user
                    st.session_state.current_page = 'Admin Home'
                    st.rerun()
                st.error('Invalid admin credentials.')

    with tabs[2]:
        st.subheader('User Login')
        with st.form('user_login_form'):
            username = st.text_input('User ID ', value='user')
            password = st.text_input('Password ', type='password', value='user')
            submitted = st.form_submit_button('Login')
            if submitted:
                user = authenticate_user(username, password)
                if user and not user['is_admin']:
                    st.session_state.user = user
                    st.session_state.current_page = 'User Home'
                    st.rerun()
                st.error('Invalid user credentials.')


def render_sidebar() -> None:
    user = st.session_state.user
    with st.sidebar:
        st.markdown(f"### Welcome, {user['full_name']}")
        st.write('Role:', 'Admin' if user['is_admin'] else 'User')
        if st.button('Home'):
            back_to_home()
        if st.button('Chart / Navigation'):
            st.session_state.current_page = 'Chart'
        if st.button('Transactions'):
            st.session_state.current_page = 'Transactions'
        if st.button('Reports'):
            st.session_state.current_page = 'Reports'
        if user['is_admin'] and st.button('Maintenance'):
            st.session_state.current_page = 'Maintenance'
        if st.button('Log Out'):
            logout()
            st.rerun()


def render_home(admin: bool) -> None:
    st.title('Admin Home Page' if admin else 'User Home Page')
    metrics = get_dashboard_metrics()
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)

    st.subheader('Product Details')
    product_df = pd.DataFrame(
        [
            ['SC(B/M)000001', 'SC(B/M)000004', 'Science'],
            ['EC(B/M)000001', 'EC(B/M)000004', 'Economics'],
            ['FC(B/M)000001', 'FC(B/M)000004', 'Fiction'],
            ['CH(B/M)000001', 'CH(B/M)000004', 'Children'],
            ['PD(B/M)000001', 'PD(B/M)000004', 'Personal Development'],
        ],
        columns=['Code No From', 'Code No To', 'Category'],
    )
    st.dataframe(product_df, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader('Category Chart')
        st.bar_chart(category_wise_counts().set_index('category'))
    with c2:
        st.subheader('Issue Status Chart')
        chart_df = issue_status_counts()
        if not chart_df.empty:
            st.bar_chart(chart_df.set_index('status'))
        else:
            st.info('No issue data available yet.')


def render_chart() -> None:
    st.title('Chart / Navigation')
    flow = pd.DataFrame(
        [
            ['Login', 'Admin Login / User Login'],
            ['Admin Home', 'Maintenance, Reports, Transactions'],
            ['User Home', 'Reports, Transactions'],
            ['Transactions', 'Book Available, Book Issue, Return Book, Pay Fine'],
            ['Reports', 'Books, Movies, Memberships, Active Issues, Overdue, Requests'],
            ['Maintenance', 'Membership, Books/Movies, User Management'],
            ['Final Pages', 'Cancel, Confirmation, Log Out'],
        ],
        columns=['Page', 'Links'],
    )
    st.dataframe(flow, use_container_width=True)


def render_transactions() -> None:
    st.title('Transactions')
    tab1, tab2, tab3, tab4 = st.tabs(['Is book available?', 'Issue book?', 'Return book?', 'Pay Fine?'])

    with tab1:
        st.subheader('Book Availability')
        title = st.text_input('Enter Book Name', key='txn_search_book_name')
        author = st.text_input('Enter Author', key='txn_search_author')
        if st.button('Search Availability', key='txn_search_btn'):
            if not title and not author:
                st.warning('One of the text box or drop down must be filled before submitting the form.')
            else:
                results = search_available_items(title, author)
                st.session_state.search_results = results
        results = st.session_state.get('search_results', pd.DataFrame())
        if not results.empty:
            st.subheader('Search Results')
            st.dataframe(results, use_container_width=True)
            available = results[results['status'] == 'Available']
            if not available.empty:
                selected_serial = st.selectbox(
                    'Select available serial to issue',
                    available['serial_no'].tolist(),
                    key='txn_available_serial'
                )
                selected_row = available[available['serial_no'] == selected_serial].iloc[0]
                st.info(f"Selected: {selected_row['title']} | {selected_row['author_name']} | Available: {selected_row['status']}")
            membership_code = st.selectbox(
                'Membership Id for request/issue',
                get_membership_codes(),
                key='txn_request_membership'
            )
            request_item = st.text_input('Request item name if not available', key='txn_request_item')
            c1, c2 = st.columns(2)
            with c1:
                if st.button('Create Issue Request', key='txn_create_request_btn'):
                    if not request_item:
                        st.warning('Enter item name for issue request.')
                    else:
                        ok, msg = create_issue_request(membership_code, request_item)
                        set_message(msg, 'success' if ok else 'error')
                        st.rerun()
            with c2:
                if st.button('Cancel Search Transaction', key='txn_cancel_search_btn'):
                    st.session_state.current_page = 'Cancel'
                    st.rerun()

    with tab2:
        st.subheader('Book Issue')
        title_options = get_titles()
        selected_title = st.selectbox('Enter Book Name', [''] + title_options, key='txn_issue_title')
        authors = get_authors_by_title(selected_title) if selected_title else []
        selected_author = st.selectbox('Enter Author', authors if authors else [''], key='txn_issue_author')
        membership_code = st.selectbox('Membership Code', get_membership_codes(), key='txn_issue_membership')
        issue_date = st.date_input('Issue Date', min_value=date.today(), value=date.today(), key='txn_issue_date')
        return_date = st.date_input(
            'Return Date',
            value=date.today() + timedelta(days=15),
            min_value=date.today(),
            max_value=date.today() + timedelta(days=15),
            key='txn_issue_return_date'
        )
        remarks = st.text_area('Remarks (Non Mandatory)', key='txn_issue_remarks')
        c1, c2 = st.columns(2)
        with c1:
            if st.button('Submit Issue', key='txn_submit_issue_btn'):
                if not selected_title or not selected_author:
                    st.error('Name of book required and author is mandatory.')
                else:
                    ok, msg = issue_book(membership_code, selected_title, selected_author, issue_date, return_date, remarks)
                    st.session_state.current_page = 'Confirmation' if ok else 'Transactions'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()
        with c2:
            if st.button('Cancel Issue', key='txn_cancel_issue_btn'):
                st.session_state.current_page = 'Cancel'
                st.rerun()

    with tab3:
        st.subheader('Return Book')
        titles = get_titles()
        return_title = st.selectbox('Enter Book Name ', [''] + titles, key='txn_return_title')
        authors = get_authors_by_title(return_title) if return_title else []
        st.text_input('Enter Author', value=authors[0] if authors else '', disabled=True, key='txn_return_author')
        serials = get_serials_for_return(return_title) if return_title else []
        serial_no = st.selectbox('Serial No', [''] + serials, key='txn_return_serial')
        details = get_issue_details_by_serial(serial_no) if serial_no else None
        issue_date_text = details['issue_date'] if details else ''
        due_date_default = date.fromisoformat(details['due_date']) if details else date.today()
        st.text_input('Issue Date', value=issue_date_text, disabled=True, key='txn_return_issue_date')
        return_date = st.date_input('Return Date', value=due_date_default, key='txn_return_date')
        remarks = st.text_area('Remarks', key='txn_return_remarks')
        c1, c2 = st.columns(2)
        with c1:
            if st.button('Submit Return', key='txn_submit_return_btn'):
                if not serial_no:
                    st.error('Serial No of the book is a mandatory field.')
                else:
                    ok, msg = return_book(serial_no, return_date, remarks)
                    st.session_state.current_page = 'Confirmation' if ok else 'Transactions'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()
        with c2:
            if st.button('Cancel Return', key='txn_cancel_return_btn'):
                st.session_state.current_page = 'Cancel'
                st.rerun()

    with tab4:
        st.subheader('Pay Fine')
        serial_options_df = active_issues_report()
        serial_options = serial_options_df['Serial No Book/Movie'].tolist() if not serial_options_df.empty else []
        pay_serial = st.selectbox('Serial No', [''] + serial_options, key='txn_pay_serial')
        detail = get_issue_details_by_serial(pay_serial) if pay_serial else None
        title_value = detail['title'] if detail else ''
        author_value = detail['author_name'] if detail else ''
        issue_date_val = date.fromisoformat(detail['issue_date']) if detail else date.today()
        due_date_val = date.fromisoformat(detail['due_date']) if detail else date.today()
        st.text_input('Enter Book Name', value=title_value, disabled=True, key='txn_pay_title')
        st.text_input('Enter Author', value=author_value, disabled=True, key='txn_pay_author')
        st.date_input('Issue Date', value=issue_date_val, disabled=True, key='txn_pay_issue_date')
        st.date_input('Return Date', value=due_date_val, disabled=True, key='txn_pay_due_date')
        actual_return_date = st.date_input('Actual Return Date', value=date.today(), key='txn_actual_return_date')
        fine = max((actual_return_date - due_date_val).days, 0) * 10 if detail else 0
        st.text_input('Fine Calculated', value=str(fine), disabled=True, key='txn_fine_calculated')
        fine_paid = st.checkbox('Fine Paid', value=False, key='txn_fine_paid')
        remarks = st.text_area('Remarks', key='txn_pay_remarks')
        c1, c2 = st.columns(2)
        with c1:
            if st.button('Submit Fine Payment', key='txn_submit_fine_btn'):
                if not pay_serial:
                    st.error('Valid serial number is required.')
                else:
                    ok, msg, _ = pay_fine(pay_serial, actual_return_date, fine_paid, remarks)
                    st.session_state.current_page = 'Confirmation' if ok else 'Transactions'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()
        with c2:
            if st.button('Cancel Fine Payment', key='txn_cancel_fine_btn'):
                st.session_state.current_page = 'Cancel'
                st.rerun()


def render_reports() -> None:
    st.title('Reports')
    report_name = st.selectbox(
        'Available Reports',
        ['Master List of Books', 'Master List of Movies', 'Master List of Memberships', 'Active Issues', 'Overdue Returns', 'Issue Requests']
    )
    mapping = {
        'Master List of Books': books_report,
        'Master List of Movies': movies_report,
        'Master List of Memberships': memberships_report,
        'Active Issues': active_issues_report,
        'Overdue Returns': overdue_report,
        'Issue Requests': issue_requests_report,
    }
    df = mapping[report_name]()
    st.subheader(report_name)
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button('Download CSV', csv, file_name=f"{report_name.lower().replace(' ', '_')}.csv", mime='text/csv')


def render_maintenance() -> None:
    st.title('Maintenance')
    tabs = st.tabs(['Add Membership', 'Update Membership', 'Add Book/Movie', 'Update Book/Movie', 'User Management'])

    with tabs[0]:
        st.subheader('Add Membership')
        with st.form('add_membership_form'):
            c1, c2 = st.columns(2)
            with c1:
                first_name = st.text_input('First Name')
                contact_number = st.text_input('Contact Number')
                aadhaar_no = st.text_input('Aadhar Card No')
                membership_type = st.radio('Membership', ['Six Months', 'One Year', 'Two Years'])
            with c2:
                last_name = st.text_input('Last Name')
                contact_address = st.text_input('Contact Address')
                start_date = st.date_input('Start Date', value=date.today())
                days = {'Six Months': 180, 'One Year': 365, 'Two Years': 730}[membership_type]
                end_date = st.date_input('End Date', value=date.today() + timedelta(days=days))
            submitted = st.form_submit_button('Add Membership')
            if submitted:
                if not all([first_name, last_name, contact_number, contact_address, aadhaar_no]):
                    st.error('All fields required.')
                else:
                    ok, msg = add_membership({
                        'first_name': first_name,
                        'last_name': last_name,
                        'contact_number': contact_number,
                        'contact_address': contact_address,
                        'aadhaar_no': aadhaar_no,
                        'start_date': start_date,
                        'end_date': end_date,
                        'membership_type': membership_type,
                    })
                    st.session_state.current_page = 'Confirmation' if ok else 'Maintenance'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()

    with tabs[1]:
        st.subheader('Update Membership')
        membership_code = st.selectbox('Membership Number', get_membership_codes())
        start_date = st.date_input('Start Date ', value=date.today())
        end_date = st.date_input('End Date ', value=date.today() + timedelta(days=365))
        action = st.radio('Membership Action', ['Six Months', 'One Year', 'Two Years', 'Remove Membership'])
        c1, c2 = st.columns(2)
        with c1:
            if st.button('Update Membership Action'):
                ok, msg = extend_or_remove_membership(membership_code, start_date, end_date, action)
                st.session_state.current_page = 'Confirmation' if ok else 'Maintenance'
                set_message(msg, 'success' if ok else 'error')
                st.rerun()
        with c2:
            if st.button('Cancel Membership Update'):
                st.session_state.current_page = 'Cancel'
                st.rerun()

    with tabs[2]:
        st.subheader('Add Book/Movie')
        with st.form('add_book_form'):
            item_type = st.radio('Type', ['Book', 'Movie'], horizontal=True)
            c1, c2 = st.columns(2)
            with c1:
                title = st.text_input('Book/Movie Name')
                procurement_date = st.date_input('Date of Procurement', value=date.today())
                quantity = st.number_input('Quantity/Copies', min_value=1, value=1)
            with c2:
                author_name = st.text_input('Author Name')
                category = st.selectbox('Category', ['Science', 'Economics', 'Fiction', 'Children', 'Personal Development'])
                cost = st.number_input('Cost', min_value=0.0, value=100.0, step=10.0)
            submitted = st.form_submit_button('Add Book/Movie')
            if submitted:
                if not title or not author_name:
                    st.error('All fields required to submit the form.')
                else:
                    ok, msg = add_catalog_item({
                        'item_type': item_type,
                        'title': title,
                        'author_name': author_name,
                        'procurement_date': procurement_date,
                        'quantity': int(quantity),
                        'category': category,
                        'cost': float(cost),
                    })
                    st.session_state.current_page = 'Confirmation' if ok else 'Maintenance'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()

    with tabs[3]:
        st.subheader('Update Book/Movie')
        item_type = st.radio('Update Type', ['Book', 'Movie'], horizontal=True)
        selected_title = st.selectbox('Book/Movie Name', [''] + get_titles(item_type))
        title_df = search_available_items(selected_title, '') if selected_title else pd.DataFrame()
        serials = title_df['serial_no'].tolist() if not title_df.empty else []
        serial_no = st.selectbox('Serial No', [''] + serials)
        status = st.selectbox('Status', ['Available', 'Issued', 'Maintenance', 'Inactive'])
        item_date = st.date_input('Date', value=date.today())
        c1, c2 = st.columns(2)
        with c1:
            if st.button('Update Book/Movie Action'):
                if not serial_no:
                    st.error('Select serial number first.')
                else:
                    ok, msg = update_catalog_item(serial_no, status, item_date)
                    st.session_state.current_page = 'Confirmation' if ok else 'Maintenance'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()
        with c2:
            if st.button('Cancel Book Update'):
                st.session_state.current_page = 'Cancel'
                st.rerun()

    with tabs[4]:
        st.subheader('User Management')
        mode = st.radio('User Mode', ['New User', 'Existing User'], horizontal=True)
        with st.form('user_form'):
            full_name = st.text_input('Name')
            username = st.text_input('Username')
            password = st.text_input('Password', type='password')
            is_active = st.checkbox('Status - Active', value=True)
            is_admin = st.checkbox('Admin')
            submitted = st.form_submit_button('Save User')
            if submitted:
                if not full_name or not username or not password:
                    st.error('All fields required to submit the form.')
                else:
                    ok, msg = add_or_update_user(username, password, full_name, is_active, is_admin, mode == 'Existing User')
                    st.session_state.current_page = 'Confirmation' if ok else 'Maintenance'
                    set_message(msg, 'success' if ok else 'error')
                    st.rerun()


def render_cancel() -> None:
    st.title('Cancel')
    st.warning('Transaction cancelled')
    c1, c2 = st.columns(2)
    if c1.button('Home'):
        back_to_home()
        st.rerun()
    if c2.button('Log Out'):
        logout()
        st.rerun()


def render_confirmation() -> None:
    st.title('Confirmation')
    st.success('Transaction completed successfully.')
    c1, c2 = st.columns(2)
    if c1.button('Home '):
        back_to_home()
        st.rerun()
    if c2.button('Log Out '):
        logout()
        st.rerun()


if not st.session_state.user:
    show_message()
    render_login()
else:
    render_sidebar()
    show_message()
    page = st.session_state.current_page
    if page == 'Chart':
        render_chart()
    elif page == 'Transactions':
        render_transactions()
    elif page == 'Reports':
        render_reports()
    elif page == 'Maintenance' and st.session_state.user['is_admin']:
        render_maintenance()
    elif page == 'Cancel':
        render_cancel()
    elif page == 'Confirmation':
        render_confirmation()
    elif page == 'Admin Home':
        render_home(True)
    else:
        render_home(False)
