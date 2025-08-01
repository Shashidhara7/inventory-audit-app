import streamlit as st
from datetime import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Set page config
st.set_page_config(page_title="Inventory Audit", layout="wide")

# Google Sheets authentication
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# Open Google Sheet
sheet = client.open("InventoryStockApp")
raw_ws = sheet.worksheet("Raw")
stock_ws = sheet.worksheet("StockCountDetails")
login_ws = sheet.worksheet("LoginDetails")

# Load Raw and LoginDetails data
raw_df = pd.DataFrame(raw_ws.get_all_records())
login_df = pd.DataFrame(login_ws.get_all_records())
stock_df = pd.DataFrame(stock_ws.get_all_records())

# Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Sidebar Navigation
page = st.sidebar.radio("Navigate", ["Login", "Register New User"] if not st.session_state.logged_in else ["Stock Count", "Logout"])

# ---------------- LOGIN PAGE ----------------
if page == "Login":
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        match = login_df[(login_df["Username"] == username) & (login_df["Password"] == password)]
        if not match.empty:
            st.session_state.logged_in = True
            st.session_state.username = username
            row_idx = match.index[0] + 2  # +2 accounts for 0-index and header
            login_ws.update_cell(row_idx, 3, datetime.now().strftime("%H:%M:%S"))  # Update Time
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

# ---------------- REGISTER PAGE ----------------
elif page == "Register New User":
    st.title("📝 Register New User")
    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    if st.button("Register"):
        if new_user and new_pass:
            login_ws.append_row([new_user, new_pass, datetime.now().strftime("%H:%M:%S")])
            st.success("User registered successfully")
        else:
            st.error("Username and Password required")

# ---------------- STOCK COUNT PAGE ----------------
elif page == "Stock Count" and st.session_state.logged_in:
    st.title("📦 Inventory Stock Count")

    shelf = st.text_input("Enter Shelf Label")
    wid = st.text_input("Scan or Enter WID")
    counted_qty = st.number_input("Enter Counted Quantity", step=1, min_value=0)

    if st.button("Submit Count"):
        if shelf and wid:
            today = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user = st.session_state.username

            match_raw = raw_df[(raw_df["ShelfLabel"] == shelf) & (raw_df["WID"] == wid)]

            if not match_raw.empty:
                available_qty = int(match_raw["Quantity"].values[0])
                vertical = match_raw["Vertical"].values[0]

                if counted_qty > available_qty:
                    status = "Excess"
                    color = "background-color: yellow"
                elif counted_qty < available_qty:
                    status = "Short"
                    color = "background-color: red"
                else:
                    status = "OK"
                    color = "background-color: lightgreen"
            else:
                available_qty = ""
                vertical = ""
                status = "Mismatch"
                color = "background-color: violet"

            # Check if WID already scanned
            existing = stock_df[(stock_df["ShelfLabel"] == shelf) & (stock_df["WID"] == wid)]
            if not existing.empty:
                idx = existing.index[0] + 2  # Header offset
                stock_ws.update(f"C{idx}:I{idx}", [[shelf, wid, counted_qty, available_qty, vertical, status, timestamp, user]])
                st.success("Updated existing entry")
            else:
                stock_ws.append_row([shelf, wid, counted_qty, available_qty, vertical, status, timestamp, user])
                st.success("Recorded new count")

            # Show styled table
            updated_df = pd.DataFrame(stock_ws.get_all_records())
            def highlight_status(val):
                if val == "Excess":
                    return "background-color: yellow"
                elif val == "Short":
                    return "background-color: red"
                elif val == "OK":
                    return "background-color: lightgreen"
                elif val == "Mismatch":
                    return "background-color: violet"
                return ""

            styled = updated_df.style.applymap(highlight_status, subset=["Status"])
            st.dataframe(styled, use_container_width=True)

# ---------------- LOGOUT ----------------
elif page == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()
