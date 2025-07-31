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

# Ensure headers
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:G1", [expected_headers])
    st.warning("⚠️ 'StockCountDetails' headers were missing or incorrect. They have been reset.")

# Functions
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

if "show_register" not in st.session_state:
    st.session_state.show_register = False

# 🔐 LOGIN / REGISTER PAGE
if not st.session_state.logged_in and not st.session_state.show_register:
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

    st.markdown("---")
    if st.button("🆕 New User? Register here"):
        st.session_state.show_register = True
        st.rerun()

# 📝 NEW USER REGISTRATION
elif st.session_state.show_register:
    st.title("📝 Register New User")
    new_username = st.text_input("Create Username")
    new_password = st.text_input("Create Password", type="password")

    if st.button("✅ Register"):
        login_df = pd.DataFrame(login_sheet.get_all_records())
        if new_username.strip() == "" or new_password.strip() == "":
            st.warning("⚠️ Please fill both fields.")
        elif new_username in login_df["Username"].values:
            st.error("❌ Username already exists. Try a different one.")
        else:
            login_sheet.append_row([new_username, new_password])
            st.success("🎉 Registration successful! Please log in.")
            st.session_state.show_register = False
            st.rerun()

    if st.button("🔙 Back to Login"):
        st.session_state.show_register = False
        st.rerun()

# 📦 MAIN STOCK COUNT APP
elif st.session_state.logged_in:
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

        # Filter WIDs for this shelf
        shelf_wids = raw_df[raw_df["ShelfLabel"] == st.session_state.shelf_label]
        counted_wids = stock_df[stock_df["ShelfLabel"] == st.session_state.shelf_label]["WID"].tolist()
        remaining_wids = shelf_wids[~shelf_wids["WID"].isin(counted_wids)]

        if remaining_wids.empty:
            st.success("🎉 All WIDs counted for this shelf!")
        else:
            wid = st.selectbox("Select WID to count", remaining_wids["WID"].tolist())

            if wid:
                match = raw_df[
                    (raw_df["ShelfLabel"] == st.session_state.shelf_label) &
                    (raw_df["WID"] == wid)
                ].iloc[0]

                brand = match["Brand"]
                vertical = match["Vertical"]
                available_qty = int(match["Quantity"])
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Check if already counted
                existing = stock_df[
                    (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                    (stock_df["WID"] == wid)
                ]
                if not existing.empty:
                    current_count = int(existing.iloc[0]["CountedQty"])
                    idx = existing.index[0] + 2
                else:
                    current_count = 0
                    idx = None

                st.markdown(f"""
                ### 📋 WID Details
                - **Brand**: `{brand}`
                - **Vertical**: `{vertical}`
                - **Available Qty**: `{available_qty}`
                - **Current Counted Qty**: `{current_count}`
                """)

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("➕ Scan / Add 1"):
                        counted_qty = current_count + 1
                        if idx:
                            stock_sheet.update_cell(idx, 3, counted_qty)
                            stock_sheet.update_cell(idx, 6, timestamp)
                        else:
                            stock_sheet.append_row([
                                st.session_state.shelf_label,
                                wid,
                                counted_qty,
                                available_qty,
                                "",
                                timestamp,
                                st.session_state.username
                            ])
                        st.success(f"✅ WID {wid} counted. Updated Qty: {counted_qty}")
                        st.rerun()

                with col2:
                    manual_qty = st.number_input("✍️ Enter manual count", min_value=0, step=1)
                    if st.button("✅ Submit Manual Qty"):
                        if idx:
                            stock_sheet.update_cell(idx, 3, manual_qty)
                            stock_sheet.update_cell(idx, 6, timestamp)
                        else:
                            stock_sheet.append_row([
                                st.session_state.shelf_label,
                                wid,
                                manual_qty,
                                available_qty,
                                "",
                                timestamp,
                                st.session_state.username
                            ])
                        st.success(f"✅ Manual entry saved: {manual_qty} for WID {wid}")
                        st.rerun()
