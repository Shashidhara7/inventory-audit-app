import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# --- Google Sheets Authentication ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("InventoryStockApp")  # Ensure spreadsheet name is correct

# --- Sheet References ---
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# --- Local Time Setup ---
tz = pytz.timezone("Asia/Kolkata")
now = datetime.now(tz)

# --- Load Data ---
raw_df = pd.DataFrame(raw_sheet.get_all_records())
stock_df = pd.DataFrame(stock_sheet.get_all_records())
login_df = pd.DataFrame(login_sheet.get_all_records())

# --- Registration Page ---
def register_user():
    st.title("🔐 Register New User")
    new_user = st.text_input("Username")
    new_pass = st.text_input("Password", type="password")
    if st.button("Register"):
        if new_user and new_pass:
            now_time = now.strftime("%H:%M:%S")
            today = now.strftime("%Y-%m-%d")
            login_sheet.append_row([new_user, new_pass, today, now_time])
            st.success("✅ Registered Successfully. Please login.")
            st.session_state.page = "login"
        else:
            st.warning("❗Please enter both username and password.")

# --- Login Page ---
def login_page():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login_records = login_sheet.get_all_values()[1:]  # Skip header
        for idx, row in enumerate(login_records, start=2):  # Row index in sheet
            if row[0] == username and row[1] == password:
                st.session_state.user = username
                # Update timestamp in the same row
                login_sheet.update_cell(idx, 3, now.strftime("%Y-%m-%d"))
                login_sheet.update_cell(idx, 4, now.strftime("%H:%M:%S"))
                st.session_state.page = "main"
                return
        st.error("❌ Invalid Credentials")

# --- Main Inventory Audit App ---
def main_app():
    st.title("📦 Inventory Stock Count")
    st.markdown(f"👤 Logged in as: `{st.session_state.user}`")

    shelf = st.text_input("Scan/Enter Shelf Label", key="shelf_label")
    wid = st.text_input("Scan/Enter WID", key="wid")
    counted_qty = st.number_input("Enter Counted Quantity", min_value=0, step=1)

    if shelf and wid:
        match = raw_df[(raw_df["ShelfLabel"] == shelf) & (raw_df["WID"] == wid)]
        if not match.empty:
            available_qty = int(match["Quantity"].values[0])
            vertical = match["Vertical"].values[0]
            brand = match["Brand"].values[0]

            st.write(f"📦 Available Qty: `{available_qty}`")
            st.write(f"🏷️ Vertical: `{vertical}`")
            st.write(f"🏢 Brand: `{brand}`")

            status = ""
            if counted_qty > available_qty:
                status = "Excess"
                st.markdown("### 🟡 Excess Quantity")
            elif counted_qty < available_qty:
                status = "Short"
                st.markdown("### 🔴 Short Quantity")
            else:
                status = "OK"
                st.markdown("### 🟢 Matched (OK)")
        else:
            available_qty = 0
            vertical = ""
            status = "Location Mismatch"
            st.markdown("### 🟣 Location Mismatch")

        if st.button("Submit Count"):
            timestamp = now.strftime("%H:%M:%S")
            today = now.strftime("%Y-%m-%d")
            stock_sheet.append_row([
                today, shelf, wid, counted_qty, available_qty,
                vertical, status, timestamp, st.session_state.user
            ])
            st.success("✅ Entry Recorded.")

    # --- View Recent Entries with Color ---
    st.subheader("🧾 Recent Entries")
    stock_data = pd.DataFrame(stock_sheet.get_all_records())
    if not stock_data.empty:
        def highlight_status(row):
            color = ""
            if row["Status"] == "Excess":
                color = "background-color: yellow"
            elif row["Status"] == "Short":
                color = "background-color: red; color: white"
            elif row["Status"] == "OK":
                color = "background-color: lightgreen"
            elif row["Status"] == "Location Mismatch":
                color = "background-color: purple; color: white"
            return [color] * len(row)

        styled_df = stock_data.style.apply(highlight_status, axis=1)
        st.dataframe(styled_df, use_container_width=True)

# --- Page Routing ---
if "page" not in st.session_state:
    st.session_state.page = "register"

if st.session_state.page == "register":
    register_user()
elif st.session_state.page == "login":
    login_page()
elif st.session_state.page == "main":
    main_app()
