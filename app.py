import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("gcreds.json", scope)
client = gspread.authorize(creds)

# Sheet references
login_sheet = client.open("InventoryStockApp").worksheet("LoginDetails")
stock_sheet = client.open("InventoryStockApp").worksheet("StockCountDetails")
raw_sheet = client.open("InventoryStockApp").worksheet("Raw")

# Helper functions
def authenticate(username, password):
    users = login_sheet.get_all_records()
    for user in users:
        if user["Username"] == username and user["Password"] == password:
            return True
    return False

def register_user(username, password):
    login_sheet.append_row([datetime.date.today().isoformat(), username, password, datetime.datetime.now().isoformat()])

def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    data = stock_sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def update_stock_count(date, shelf, wid, counted_qty, available_qty, vertical, status, casper_id):
    stock_df = get_stock_data()
    existing = stock_df[(stock_df["ShelfLabel"] == shelf) & (stock_df["WID"] == wid)]
    timestamp = datetime.datetime.now().isoformat()

    if not existing.empty:
        index = existing.index[0] + 2  # offset for header
        stock_sheet.update(f"C{index}:I{index}", [[wid, counted_qty, available_qty, vertical, status, timestamp, casper_id]])
    else:
        stock_sheet.append_row([date, shelf, wid, counted_qty, available_qty, vertical, status, timestamp, casper_id])

def get_status(counted, available):
    if counted > available:
        return "Excess"
    elif counted < available:
        return "Short"
    else:
        return "OK"

def get_color(status):
    if status == "Excess":
        return "#fff3cd"  # yellow
    elif status == "Short":
        return "#f8d7da"  # red
    elif status == "Location Mismatch":
        return "#d1c4e9"  # purple
    else:
        return "#d4edda"  # green

# Session state for login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Sidebar navigation
st.sidebar.title("Inventory App")
page = st.sidebar.radio("Navigation", ["Login", "Register New User", "Stock Count Details"])

if page == "Login":
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login successful!")
        else:
            st.error("Invalid credentials")

elif page == "Register New User":
    st.title("Register")
    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    if st.button("Register"):
        register_user(new_user, new_pass)
        st.success("User registered!")

elif page == "Stock Count Details":
    if not st.session_state.logged_in:
        st.warning("Please login first.")
    else:
        st.title("Stock Count Details")
        shelf = st.text_input("Scan Shelf Label")
        wid = st.text_input("Scan WID")

        if shelf and wid:
            raw_df = get_raw_data()
            match = raw_df[(raw_df["ShelfLabel"] == shelf) & (raw_df["WID"] == wid)]
            if not match.empty:
                vertical = match.iloc[0]["Vertical"]
                brand = match.iloc[0]["Brand"]
                available_qty = int(match.iloc[0]["Quantity"])
                st.write(f"**Vertical:** {vertical}")
                st.write(f"**Brand:** {brand}")
                st.write(f"**Available Qty:** {available_qty}")

                counted_qty = st.number_input("Enter Counted Quantity", min_value=0, step=1)
                if st.button("Submit Count"):
                    status = get_status(counted_qty, available_qty)
                    update_stock_count(datetime.date.today().isoformat(), shelf, wid, counted_qty, available_qty, vertical, status, datetime.datetime.now().isoformat(), st.session_state.username)
                    st.success(f"Stock count updated. Status: {status}")
            else:
                st.error("WID not found in this shelf or mismatch")

        # Display data table with color-coded status
        stock_df = get_stock_data()
        if not stock_df.empty:
            def highlight_row(row):
                return [f"background-color: {get_color(row['Status'])}" for _ in row]
            st.dataframe(stock_df.style.apply(highlight_row, axis=1))
