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

# ✅ Ensure StockCountDetails has correct headers (without Date)
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:G1", [expected_headers])
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

# Session state
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

    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf
            st.success(f"Shelf Label set to: {new_shelf}")
    else:
        st.info(f"📌 Active Shelf Label: {st.session_state.shelf_label}")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""

    wid = st.text_input("Scan or Enter WID to count", key="wid_input")

    if wid:
        raw_df = get_raw_data()
        matching = raw_df[
            (raw_df["ShelfLabel"] == st.session_state.shelf_label) &
            (raw_df["WID"] == wid)
        ]

        if not matching.empty:
            brand = matching.iloc[0]["Brand"]
            vertical = matching.iloc[0]["Vertical"]
            available_qty = int(matching.iloc[0]["Quantity"])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            stock_df = get_stock_data()
            existing = stock_df[
                (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                (stock_df["WID"] == wid)
            ]

            if not existing.empty:
                idx = existing.index[0]
                counted_qty = int(existing.iloc[0]["CountedQty"]) + 1
                stock_sheet.update_cell(idx + 2, 3, counted_qty)
                stock_sheet.update_cell(idx + 2, 6, timestamp)
                st.success("✅ WID already counted — quantity updated")
            else:
                counted_qty = 1
                stock_sheet.append_row([
                    st.session_state.shelf_label,
                    wid,
                    counted_qty,
                    available_qty,
                    "",  # Status will be calculated and shown
                    timestamp,
                    st.session_state.username
                ])
                st.success("✅ New WID entry added")

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

            # Show result
            st.markdown(f"""
            ### 🧾 Scan Result
            - **Brand**: {brand}
            - **Vertical**: {vertical}
            - **Available Qty**: {available_qty}
            - **Counted Qty**: {counted_qty}
            - **Required Qty**: {required_qty}
            - **Status**: :{status_color}[**{status}**]
            """)

        else:
            st.error("❌ WID not found for this shelf.")