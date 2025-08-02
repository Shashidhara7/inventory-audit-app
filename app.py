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

# Ensure headers with Vertical right after WID
expected_headers = ["ShelfLabel", "WID", "Vertical", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
if stock_sheet.row_values(1) != expected_headers:
    stock_sheet.update("A1:H1", [expected_headers])

# Session defaults
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("shelf_label", "")
st.session_state.setdefault("validated_wids", [])
st.session_state.setdefault("username", "")

# Helper functions
def get_login_data():
    return pd.DataFrame(login_sheet.get_all_records())

def validate_login(username, password):
    df = get_login_data()
    if df.empty:
        return False
    username = username.strip().lower()
    password = password.strip()
    for _, row in df.iterrows():
        if username == str(row.get("Username", "")).strip().lower() and password == str(row.get("Password", "")).strip():
            return True
    return False

def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

# -------- LOGIN PAGE --------
if not st.session_state.logged_in:
    st.title("🔐 Login Page")
    tabs = st.tabs(["Login", "Register"])

    with tabs[0]:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if validate_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

    with tabs[1]:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        if st.button("Register"):
            df = get_login_data()
            if new_username.strip().lower() in df["Username"].str.strip().str.lower().values:
                st.warning("⚠️ Username already exists.")
            else:
                now = datetime.now()
                login_sheet.append_row([
                    now.strftime("%Y-%m-%d"),
                    new_username.strip(),
                    new_password.strip(),
                    now.strftime("%H:%M:%S")
                ])
                st.success("✅ Registered successfully! Please login now.")
                st.rerun()

# -------- MAIN APP --------
else:
    st.title("📦 Inventory Stock Count App")
    st.sidebar.success(f"👋 Logged in as `{st.session_state.username}`")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.shelf_label = ""
        st.session_state.validated_wids = []
        st.rerun()

    if not st.session_state.shelf_label:
        shelf_input = st.text_input("Scan or Enter Shelf Label")
        if shelf_input:
            st.session_state.shelf_label = shelf_input
            st.success(f"Shelf Label set: {shelf_input}")
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
                    row = shelf_df[shelf_df["WID"] == selected_wid].iloc[0]
                    vertical = row.get("Vertical", "")
                    st.markdown(f"""
                    ### 🔍 WID Details
                    - **Brand**: `{row['Brand']}`
                    - **Vertical**: `{vertical}`
                    - **Available Qty**: `{row['Quantity']}`
                    """)
                    counted = st.number_input("Enter Counted Quantity", min_value=0, step=1)

                    if st.button("✅ Save This WID"):
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        available = int(row["Quantity"])
                        status = "Short" if counted < available else "Excess" if counted > available else "OK"

                        stock_df = get_stock_data()
                        existing = stock_df[
                            (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                            (stock_df["WID"] == selected_wid)
                        ]

                        if not existing.empty:
                            row_index = existing.index[0] + 2
                            stock_sheet.update_cell(row_index, 3, vertical)
                            stock_sheet.update_cell(row_index, 4, counted)
                            stock_sheet.update_cell(row_index, 6, status)
                            stock_sheet.update_cell(row_index, 7, timestamp)
                            st.success("✅ Updated existing entry.")
                        else:
                            stock_sheet.append_row([
                                st.session_state.shelf_label,
                                selected_wid,
                                vertical,
                                counted,
                                available,
                                status,
                                timestamp,
                                st.session_state.username
                            ])
                            st.success("✅ New WID entry saved.")

                        st.session_state.validated_wids.append(selected_wid)
                        st.rerun()
            else:
                st.success("🎉 All WIDs under this Shelf Label have been validated.")

    if st.button("🔄 Reset Validated WID List"):
        st.session_state.validated_wids = []
        st.rerun()