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

# Ensure StockCountDetails headers
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:G1", [expected_headers])
    st.warning("⚠️ 'StockCountDetails' headers were missing or incorrect. They have been reset.")

# Helper Functions
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

def get_login_data():
    return pd.DataFrame(login_sheet.get_all_records())

def login(username, password):
    login_df = get_login_data()
    match = login_df[(login_df["Username"] == username) & (login_df["Password"] == password)]
    return not match.empty

def user_exists(username):
    login_df = get_login_data()
    return username in login_df["Username"].values

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "register" not in st.session_state:
    st.session_state.register = False
if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""
if "validated_wids" not in st.session_state:
    st.session_state.validated_wids = []

# Registration Page
if st.session_state.register:
    st.title("📝 Register New User")
    new_username = st.text_input("Choose a Username")
    new_password = st.text_input("Choose a Password", type="password")
    if st.button("Register"):
        if user_exists(new_username):
            st.warning("⚠️ Username already exists. Choose a different one.")
        else:
            login_sheet.append_row([datetime.now().strftime("%Y-%m-%d"), new_username, new_password, datetime.now().strftime("%H:%M:%S")])
            st.success("✅ Registration successful! Please login.")
            st.session_state.register = False
            st.rerun()
    if st.button("🔙 Back to Login"):
        st.session_state.register = False
        st.rerun()

# Login Page
elif not st.session_state.logged_in:
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
            st.error("❌ Invalid credentials.")
    
    if st.button("Register"):
        st.session_state.register = True
        st.rerun()

# Main App
else:
    st.title("📦 Inventory Stock Count App")

    # Shelf Label
    if not st.session_state.shelf_label:
        shelf_input = st.text_input("Scan or Enter Shelf Label")
        if shelf_input:
            st.session_state.shelf_label = shelf_input
            st.success(f"✅ Shelf Label set: {shelf_input}")
            st.rerun()
    else:
        st.info(f"📌 Active Shelf Label: `{st.session_state.shelf_label}`")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""
            st.session_state.validated_wids = []
            st.rerun()

        raw_df = get_raw_data()
        shelf_df = raw_df[raw_df["ShelfLabel"] == st.session_state.shelf_label]

        if shelf_df.empty:
            st.warning("⚠️ No data found for this Shelf Label.")
        else:
            remaining_wids = shelf_df[~shelf_df["WID"].isin(st.session_state.validated_wids)]["WID"].tolist()

            if remaining_wids:
                selected_wid = st.selectbox("🔽 Select WID to Validate", options=remaining_wids)

                if selected_wid:
                    wid_row = shelf_df[shelf_df["WID"] == selected_wid].iloc[0]
                    brand = wid_row["Brand"]
                    vertical = wid_row["Vertical"]
                    available_qty = int(wid_row["Quantity"])

                    st.markdown(f"""
                    ### 📋 WID Details
                    - **Brand**: `{brand}`
                    - **Vertical**: `{vertical}`
                    - **Available Quantity**: `{available_qty}`
                    """)

                    counted_qty = st.number_input("Enter Counted Quantity", min_value=0, step=1)

                    if st.button("✅ Save This WID"):
                        stock_df = get_stock_data()
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        if counted_qty < available_qty:
                            status = "Short"
                        elif counted_qty > available_qty:
                            status = "Excess"
                        else:
                            status = "OK"

                        existing = stock_df[
                            (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                            (stock_df["WID"] == selected_wid)
                        ]

                        if not existing.empty:
                            row_index = existing.index[0] + 2
                            stock_sheet.update_cell(row_index, 3, counted_qty)
                            stock_sheet.update_cell(row_index, 5, status)
                            stock_sheet.update_cell(row_index, 6, timestamp)
                            st.success(f"✅ Updated WID `{selected_wid}`")
                        else:
                            stock_sheet.append_row([
                                st.session_state.shelf_label,
                                selected_wid,
                                counted_qty,
                                available_qty,
                                status,
                                timestamp,
                                st.session_state.username
                            ])
                            st.success(f"✅ Saved new WID `{selected_wid}`")

                        st.session_state.validated_wids.append(selected_wid)
                        st.rerun()
            else:
                st.success("🎉 All WIDs under this Shelf Label have been validated.")

    if st.button("🔄 Reset Validated WID List"):
        st.session_state.validated_wids = []
        st.rerun()
