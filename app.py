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

# ✅ Ensure StockCountDetails has correct headers (without Date)
expected_headers = ["ShelfLabel", "WID", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
actual_headers = stock_sheet.row_values(1)
if actual_headers != expected_headers:
    stock_sheet.update("A1:G1", [expected_headers])
    st.warning("⚠️ 'StockCountDetails' headers were missing or incorrect. They have been reset.")

# Data functions
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

# Login page
if not st.session_state.logged_in:
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

# Main app
else:
    st.title("📦 Stock Count App")

    raw_df = get_raw_data()

    if not st.session_state.shelf_label:
        new_shelf = st.text_input("Scan or Enter NEW Shelf Label")
        if new_shelf:
            st.session_state.shelf_label = new_shelf
            st.success(f"Shelf Label set to: {new_shelf}")
            st.rerun()
    else:
        st.info(f"📌 Active Shelf Label: {st.session_state.shelf_label}")
        if st.button("🔁 Change Shelf Label"):
            st.session_state.shelf_label = ""
            st.rerun()

        # Filter WIDs by shelf label
        filtered_raw = raw_df[raw_df["ShelfLabel"] == st.session_state.shelf_label]

        if not filtered_raw.empty:
            st.subheader("📝 Counted Quantities")

            # Dictionary to collect inputs
            counted_inputs = {}
            for idx, row in filtered_raw.iterrows():
                wid = row["WID"]
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**WID**: {wid} — Brand: {row['Brand']}, Vertical: {row['Vertical']}, Available: {row['Quantity']}")
                with col2:
                    qty = st.number_input(f"Counted Qty for {wid}", min_value=0, step=1, key=f"counted_{wid}")
                    counted_inputs[wid] = qty

            if st.button("💾 Save Counted Data"):
                stock_df = get_stock_data()
                updated_rows = []

                for wid, counted_qty in counted_inputs.items():
                    raw_row = filtered_raw[filtered_raw["WID"] == wid].iloc[0]
                    brand = raw_row["Brand"]
                    vertical = raw_row["Vertical"]
                    available_qty = int(raw_row["Quantity"])
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Status calc
                    if counted_qty < available_qty:
                        status = "Short"
                    elif counted_qty > available_qty:
                        status = "Excess"
                    else:
                        status = "OK"

                    existing = stock_df[
                        (stock_df["ShelfLabel"] == st.session_state.shelf_label) &
                        (stock_df["WID"] == wid)
                    ]

                    if not existing.empty:
                        row_index = existing.index[0] + 2
                        stock_sheet.update_cell(row_index, 3, counted_qty)
                        stock_sheet.update_cell(row_index, 5, status)
                        stock_sheet.update_cell(row_index, 6, timestamp)
                    else:
                        stock_sheet.append_row([
                            st.session_state.shelf_label,
                            wid,
                            counted_qty,
                            available_qty,
                            status,
                            timestamp,
                            st.session_state.username
                        ])

                    updated_rows.append({
                        "WID": wid,
                        "Brand": brand,
                        "Vertical": vertical,
                        "AvailableQty": available_qty,
                        "CountedQty": counted_qty,
                        "Status": status
                    })

                # Show summary table
                st.success("✅ All entries saved successfully!")
                summary_df = pd.DataFrame(updated_rows)
                st.subheader("📋 Summary of This Entry")
                st.dataframe(summary_df)
        else:
            st.warning("⚠️ No WIDs found for this Shelf Label.")