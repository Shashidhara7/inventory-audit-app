import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# Google Sheet Auth
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# Sheet references
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# Define get_raw_data before it's used
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    # Ensure headers first (as done earlier)
    required_headers = ["Date", "ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
    existing_headers = stock_sheet.row_values(1)
    if existing_headers != required_headers:
        stock_sheet.update("A1:H1", [required_headers])

    records = stock_sheet.get_all_records()
    return pd.DataFrame(records)

stock_df = get_stock_data()

# Optional: debug
st.write("✅ Headers in sheet:", stock_df.columns.tolist())


def login(username, password):
    login_df = pd.DataFrame(login_sheet.get_all_records())
    if "Username" in login_df.columns and "Password" in login_df.columns:
        user_record = login_df[login_df["Username"] == username]
        if not user_record.empty and user_record.iloc[0]["Password"] == password:
            return True
    return False

# Session State for login & ShelfLabel
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""

# 🔐 Login Page
if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

# 📦 Main App Page
else:
    st.title("📦 Stock Count App")

    # Load stock data once
    stock_df = get_stock_data()

    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf
            st.success(f"Shelf Label set to: {new_shelf}")
    else:
        st.info(f"📌 Active Shelf Label: `{st.session_state.shelf_label}`")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""

    wid = st.text_input("Scan or Enter WID to count", key="wid_input")

    if wid:
        raw_df = get_raw_data()
        match = raw_df[
            (raw_df["ShelfLabel"] == st.session_state.shelf_label) &
            (raw_df["WID"] == wid)
        ]

        if not match.empty:
            vertical = match.iloc[0]["Vertical"]
            brand = match.iloc[0]["Brand"]
            available_qty = int(match.iloc[0]["Quantity"])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            today = datetime.now().date().isoformat()

            existing = stock_df[
                    (stock_df["Date"] == today) &
                    (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                    (stock_df["WID"] == wid)
                ]


            if not existing.empty:
                idx = stock_df[
                    (stock_df["Date"] == today) &
                    (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                    (stock_df["WID"] == wid)
                ].index[0]
                counted_qty = int(existing.iloc[0]["CountedQty"]) + 1
                stock_sheet.update_cell(idx + 2, 4, counted_qty)
                stock_sheet.update_cell(idx + 2, 7, timestamp)
                st.success("✅ WID already counted — quantity updated")
            else:
                counted_qty = 1
                stock_sheet.append_row([
                    today,
                    st.session_state.shelf_label,
                    wid,
                    counted_qty,
                    available_qty,
                    "",  # Status to be updated below
                    timestamp,
                    st.session_state.username
                ])
                st.success("✅ New WID entry added")

            # Recalculate status
            if counted_qty < available_qty:
                status = "Short"
                required_qty = available_qty - counted_qty
                color = "red"
            elif counted_qty > available_qty:
                status = "Excess"
                required_qty = counted_qty - available_qty
                color = "orange"
            else:
                status = "OK"
                required_qty = 0
                color = "green"

            st.markdown(f"""
            ### 🧾 Scan Result
            - **Brand**: `{brand}`
            - **Vertical**: `{vertical}`
            - **Available Qty**: `{available_qty}`
            - **Counted Qty**: `{counted_qty}`
            - **Required Qty**: `{required_qty}`
            - **Status**: :{color}[**{status}**]
            """)

        else:
            st.error("❌ WID not found for the current Shelf Label")
