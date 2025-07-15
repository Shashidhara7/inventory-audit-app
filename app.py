import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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

# Get dataframes
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())



def get_stock_data():
    stock_df = pd.DataFrame(stock_sheet.get_all_records())

    expected_cols = [
        "Date", "ShelfLabel", "WID", "CountedQty",
        "AvailableQty", "Status", "Timestamp", "CasperID"
    ]
    stock_df = get_stock_data()
    st.write("StockCountDetails headers:", stock_df.columns.tolist())
    
    missing_cols = [col for col in expected_cols if col not in stock_df.columns]

    if missing_cols:
        st.error(f"⚠️ The following required columns are missing from 'StockCountDetails' sheet: {', '.join(missing_cols)}.\n\nPlease correct the sheet headers before proceeding.")
        st.stop()

    return stock_df


def login(username, password):
    login_df = pd.DataFrame(login_sheet.get_all_records())

    # Check if user exists and password matches
    user_record = login_df[login_df["Username"] == username]

    if not user_record.empty and user_record.iloc[0]["Password"] == password:
        now = datetime.now()
        # Optional: Log successful login time in the sheet
        # login_sheet.append_row([now.date().isoformat(), username, "Login", now.strftime("%H:%M:%S")])
        return True
    else:
        return False


# Session State for login & ShelfLabel
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""

if not st.session_state.logged_in:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if login(username, password):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("✅ Login successful!")
            st.rerun()  # 🔁 Force app to rerun and render next screen immediately
        else:
            st.error("❌ Invalid username or password")

else:
    st.title("📦 Stock Count App")

    # Only show ShelfLabel input if it's not already stored
    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf
            st.success(f"Shelf Label set to: {new_shelf}")
    else:
        st.info(f"📌 Active Shelf Label: `{st.session_state.shelf_label}`")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""  # reset

    wid = st.text_input("Scan or Enter WID to count", key="wid_input")

    if wid:
        raw_df = get_raw_data()

        # Match shelf + wid
        matching = raw_df[
            (raw_df["ShelfLabel"] == st.session_state.shelf_label) &
            (raw_df["WID"] == wid)
        ]

        if not matching.empty:
            vertical = matching.iloc[0]["Vertical"]
            brand = matching.iloc[0]["Brand"]
            available_qty = int(matching.iloc[0]["Quantity"])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            stock_df = get_stock_data()
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
                if counted_qty < available_qty:
                    status = "Short"
                elif counted_qty > available_qty:
                    status = "Excess"
                else:
                    status = "OK"

                stock_sheet.append_row([
                    today,
                    st.session_state.shelf_label,
                    wid,
                    counted_qty,
                    available_qty,
                    status,
                    timestamp,
                    st.session_state.username
                ])
                st.success("✅ New WID entry added")

                        # Default counted qty = 1 or from existing row
            if not existing.empty:
                counted_qty = int(existing.iloc[0]["CountedQty"]) + 1
            else:
                counted_qty = 0

            # Calculate status
            if counted_qty < available_qty:
                status = "Short"
                required_qty = available_qty - counted_qty
            elif counted_qty > available_qty:
                status = "Excess"
                required_qty = available_qty - counted_qty
            else:
                status = "OK"
                required_qty = 0

            # Show status block
            st.markdown(f"""
            ### 🧾 Scan Result
            - **Brand**: `{brand}`
            - **Vertical**: `{vertical}`
            - **Available Qty**: `{available_qty}`
            - **Counted Qty**: `{counted_qty}`
            - **Required Qty**: `{required_qty}`
            - **Status**: :{"green" if status == "OK" else "red"}[**{status}**]
            """)
