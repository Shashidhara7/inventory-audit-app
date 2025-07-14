import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
from google.oauth2.service_account import Credentials


# Define the scopes
# scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load credentials from st.secrets
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)


# Scope for Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load credentials from JSON file
#creds = Credentials.from_service_account_file("service_account.json", scopes=scope)

# Google Sheet Auth
client = gspread.authorize(creds)

# Now you can access your sheet
sheet = client.open("InventoryStockApp").sheet1
# Connect to your Google Sheet
# sheet = client.open("InventoryStockApp")  # <--- Change this name
spreadsheet = client.open("InventoryStockApp")

raw_sheet = client.open("InventoryStockApp").worksheet("Raw")
stock_sheet = client.open("InventoryStockApp").worksheet("StockCountDetails")
login_sheet = client.open("InventoryStockApp").worksheet("LoginDetails")



# Get sheet data
def get_raw_data():
    data = raw_sheet.get_all_values()[1:]  # skip Row 1 (header)
    return pd.DataFrame(data, columns=["ShelfLabel", "WID", "Vertical", "Brand", "Quantity", "ATP"])

def get_stock_data():
    data = stock_sheet.get_all_values()[1:]  # Skip header row
    return pd.DataFrame(data, columns=["Date", "ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"])


def login(username, password):
    now = datetime.now()
    login_sheet.append_row([now.date().isoformat(), username, password, now.strftime("%H:%M:%S")])
    return True

# Login session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""

# Login Page
if not st.session_state.logged_in:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        login(username, password)
        st.session_state.logged_in = True
        st.session_state.username = username
        st.success("✅ Login successful!")

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
                counted_qty = 1

            # Calculate status
            if counted_qty < available_qty:
                status = "Short"
                required_qty = available_qty - counted_qty
            elif counted_qty > available_qty:
                status = "Excess"
                required_qty = counted_qty - available_qty
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
