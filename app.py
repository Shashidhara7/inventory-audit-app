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

# Ensure StockCountDetails has correct headers
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:G1", [expected_headers])
    st.warning("⚠️ 'StockCountDetails' headers were missing or incorrect. They have been reset.")

# Helper functions
def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

def get_login_data():
    df = pd.DataFrame(login_sheet.get_all_records())
    df.columns = [col.strip() for col in df.columns]  # Clean header spaces
    return df

def login(username, password):
    login_df = get_login_data()
    # Ensure column names are matched
    if "Username" in login_df.columns and "Password" in login_df.columns:
        match = login_df[
            (login_df["Username"].astype(str).str.strip() == username.strip()) &
            (login_df["Password"].astype(str).str.strip() == password.strip())
        ]
        return not match.empty
    return False

# Session state defaults
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""

if "validated_wids" not in st.session_state:
    st.session_state.validated_wids = []

# --- Login Page ---
if not st.session_state.logged_in:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Login"):
            if login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials. Please register if you're a new user.")

    with col2:
        if st.button("Register"):
            login_df = get_login_data()
            if "Username" in login_df.columns and username.strip() in login_df["Username"].astype(str).str.strip().values:
                st.warning("⚠️ Username already exists.")
            else:
                login_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    username.strip(),
                    password.strip(),
                    datetime.now().strftime("%H:%M:%S")
                ])
                st.success("✅ Registered successfully. Please login now.")
                st.rerun()

# --- Main App ---
else:
    st.title("📦 Inventory Stock Count App")

    # Shelf Label input
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

        # Fetch data
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

                        # Determine status
                        if counted_qty < available_qty:
                            status = "Short"
                        elif counted_qty > available_qty:
                            status = "Excess"
                        else:
                            status = "OK"

                        # Check if already exists
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

    # Reset WID button
    if st.button("🔄 Reset Validated WID List"):
        st.session_state.validated_wids = []
        st.rerun()
