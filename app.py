import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# Load raw data
raw_df = pd.DataFrame(raw_sheet.get_all_records())

# Load login data
login_df = pd.DataFrame(login_sheet.get_all_records())

# Page selector
page = st.sidebar.selectbox("Select Page", ["Login", "Register", "Inventory Audit"])

# Register Page
if page == "Register":
    st.title("New User Registration")
    new_username = st.text_input("Choose a Username")
    new_password = st.text_input("Choose a Password", type="password")
    if st.button("Register"):
        if new_username and new_password:
            login_sheet.append_row([new_username, new_password, datetime.now().strftime("%H:%M:%S")])
            st.success("Registered successfully. Please go to Login page.")
        else:
            st.warning("Please fill in both fields.")

# Login Page
elif page == "Login":
    st.title("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user_match = login_df[(login_df['Username'] == username) & (login_df['Password'] == password)]
        if not user_match.empty:
            row_number = user_match.index[0] + 2  # Adjusting for header and 1-based index
            login_sheet.update_cell(row_number, 3, datetime.now().strftime("%H:%M:%S"))
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login successful!")
        else:
            st.error("Invalid credentials.")

# Inventory Audit Page
elif page == "Inventory Audit":
    if not st.session_state.get("logged_in"):
        st.warning("Please login to access this page.")
        st.stop()

    st.title("Inventory Stock Count")

    shelf_label = st.text_input("Scan/Enter Shelf Label")
    wid = st.text_input("Enter WID")
    counted_qty = st.number_input("Counted Quantity", min_value=0, step=1)

    if st.button("Submit Count"):
        if not shelf_label or not wid:
            st.warning("Shelf Label and WID are required.")
            st.stop()

        raw_match = raw_df[(raw_df["ShelfLabel"] == shelf_label) & (raw_df["WID"] == wid)]
        if raw_match.empty:
            st.error("WID not found in Raw data.")
            st.stop()

        available_qty = int(raw_match["Quantity"].values[0])
        status = "OK"
        if counted_qty > available_qty:
            status = "Excess"
        elif counted_qty < available_qty:
            status = "Short"

        stock_data = pd.DataFrame(stock_sheet.get_all_records())
        existing_row = stock_data[(stock_data["ShelfLabel"] == shelf_label) & (stock_data["WID"] == wid)]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        casper_id = st.session_state["username"]

        if not existing_row.empty:
            row_num = existing_row.index[0] + 2  # account for header row
            stock_sheet.update(f"C{row_num}:F{row_num}", [[counted_qty, available_qty, status, timestamp]])
            stock_sheet.update_cell(row_num, 6, casper_id)
            st.success("Count updated successfully.")
        else:
            new_row = [shelf_label, wid, counted_qty, available_qty, status, timestamp, casper_id]
            stock_sheet.append_row(new_row)
            st.success("Count submitted successfully.")

        # Display status with color
        if status == "OK":
            st.markdown("✅ **Status: OK**", unsafe_allow_html=True)
        elif status == "Excess":
            st.markdown("<span style='color:orange; font-weight:bold;'>🟠 Status: Excess</span>", unsafe_allow_html=True)
        elif status == "Short":
            st.markdown("<span style='color:red; font-weight:bold;'>🔴 Status: Short</span>", unsafe_allow_html=True)
