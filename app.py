import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# Google Sheet Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# Sheet references
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# Ensure headers are correct
expected_headers = ["Date", "ShelfLabel", "WID", "CountedQty", "AvailableQty", "Vertical", "Timestamp", "CasperID", "Status"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:I1", [expected_headers])
    st.warning("⚠️ 'StockCountDetails' headers were missing or incorrect. They have been reset.")

# Data functions
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

def login(username, password):
    login_df = pd.DataFrame(login_sheet.get_all_records())
    user_record = login_df[login_df["Username"] == username]
    if not user_record.empty and user_record.iloc[0]["Password"] == password:
        return True
    return False

# Session state initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""

# Login page
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

# Main app
else:
    st.title("📦 Stock Count App")

    raw_df = get_raw_data()
    stock_df = get_stock_data()

    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf
            st.success(f"Shelf Label set to: {new_shelf}")
            st.rerun()
    else:
        st.info(f"📌 Active Shelf Label: `{st.session_state.shelf_label}`")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""
            st.rerun()

        # Filter WIDs in selected shelf
        shelf_wids = raw_df[raw_df["ShelfLabel"] == st.session_state.shelf_label]

        # Remove already counted WIDs
        counted_wids = stock_df[stock_df["ShelfLabel"] == st.session_state.shelf_label]["WID"].tolist()
        remaining_wids = shelf_wids[~shelf_wids["WID"].isin(counted_wids)]

        if remaining_wids.empty:
            st.success("🎉 All WIDs counted for this shelf!")
        else:
            wid = st.selectbox("Select WID to count", remaining_wids["WID"].tolist())
            if wid:
                match = remaining_wids[remaining_wids["WID"] == wid].iloc[0]
                brand = match["Brand"]
                vertical = match["Vertical"]
                available_qty = int(match["Quantity"])
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_date = datetime.now().strftime("%Y-%m-%d")
                counted_qty = 1

                # Append row with correct structure
                stock_sheet.append_row([
                    current_date,                      # Date
                    st.session_state.shelf_label,      # ShelfLabel
                    wid,                               # WID
                    counted_qty,                       # CountedQty
                    available_qty,                     # AvailableQty
                    vertical,                          # Vertical
                    timestamp,                         # Timestamp
                    st.session_state.username,         # CasperID
                    ""                                 # Status (to be updated)
                ])

                # Calculate status
                if counted_qty < available_qty:
                    status = "Short"
                    required_qty = available_qty - counted_qty
                    status_color = "red"
                elif counted_qty > available_qty:
                    status = "Excess"
                    required_qty = counted_qty - available_qty
                    status_color = "orange"
                else:
                    status = "OK"
                    required_qty = 0
                    status_color = "green"

                # Update status in last row
                last_row = len(stock_df) + 2
                stock_sheet.update_cell(last_row, 9, status)

                # Display scan result
                st.markdown(f"""
                ### 🧾 Scan Result
                - **Brand**: `{brand}`
                - **Vertical**: `{vertical}`
                - **Available Qty**: `{available_qty}`
                - **Counted Qty**: `{counted_qty}`
                - **Required Qty**: `{required_qty}`
                - **Status**: :{status_color}[**{status}**]
                """)

                st.rerun()