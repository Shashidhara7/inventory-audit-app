import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# 🔐 Google Sheet Authentication
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
if "GOOGLE_CREDS" not in st.secrets:
    st.error("Missing Google credentials in secrets.")
    st.stop()

creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# 📄 Sheet references
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# ✅ Validate StockCountDetails headers
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if set(actual_headers) != set(expected_headers):
    stock_sheet.update("A1:G1", [expected_headers])
    st.warning("⚠️ Sheet headers were auto-corrected.")

# 🧠 Data loaders
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

def login(username, password):
    login_df = pd.DataFrame(login_sheet.get_all_records())
    user_record = login_df[login_df["Username"] == username]
    return not user_record.empty and user_record.iloc[0]["Password"] == password

# 🔄 Session state
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("shelf_label", "")

# 🔐 Login interface
if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username.strip(), password.strip()):
            st.session_state.logged_in = True
            st.session_state.username = username.strip()
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

# 📦 Main app interface
else:
    st.title("📦 Stock Count App")

    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf.strip()
            st.success(f"Shelf Label set to: {st.session_state.shelf_label}")
    else:
        st.info(f"📌 Active Shelf Label: `{st.session_state.shelf_label}`")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""

    wid = st.text_input("Scan or Enter WID to count", key="wid_input").strip()

    if wid:
        raw_df = get_raw_data()
        matching = raw_df[
            (raw_df["ShelfLabel"].str.strip() == st.session_state.shelf_label) &
            (raw_df["WID"].astype(str).str.strip() == wid)
        ]

        if not matching.empty:
            brand = matching.iloc[0]["Brand"]
            vertical = matching.iloc[0]["Vertical"]
            available_qty = int(matching.iloc[0]["Quantity"])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            stock_df = get_stock_data()
            existing = stock_df[
                (stock_df["ShelfLabel"].str.strip() == st.session_state.shelf_label) &
                (stock_df["WID"].astype(str).str.strip() == wid)
            ]

            if not existing.empty:
                row_number = existing.index[0] + 2  # Header = row 1
                counted_qty = int(existing.iloc[0]["CountedQty"]) + 1
                stock_sheet.update_cell(row_number, 3, counted_qty)
                stock_sheet.update_cell(row_number, 6, timestamp)
                st.success("✅ WID already counted — quantity updated")
            else:
                counted_qty = 1
                stock_sheet.append_row([
                    st.session_state.shelf_label,
                    wid,
                    counted_qty,
                    available_qty,
                    "",  # Status to be calculated
                    timestamp,
                    st.session_state.username
                ])
                st.success("✅ New WID entry added")

            # 🔍 Status logic
            if counted_qty < available_qty:
                status, required_qty, status_color = "Short", available_qty - counted_qty, "red"
            elif counted_qty > available_qty:
                status, required_qty, status_color = "Excess", counted_qty - available_qty, "orange"
            else:
                status, required_qty, status_color = "OK", 0, "green"

          
            # Show result
            st.markdown(f"""
            ### 🧾 Scan Result
            - **Brand**: `{brand}`
            - **Vertical**: `{vertical}`
            - **Available Qty**: `{available_qty}`
            - **Counted Qty**: `{counted_qty}`
            - **Required Qty**: `{required_qty}`
            - **Status**: :{status_color}[**{status}**]
            """)

        else:
            st.error("❌ WID not found for this shelf.")
