import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# 📂 Google Sheets Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# 🔗 Sheet References
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# Initialize WID scan flag
if "wid_scanned" not in st.session_state:
    st.session_state.wid_scanned = False

# 🔍 Shelf Label dropdown
shelf_labels = raw_sheet.col_values(1)[1:]
selected_shelf = st.selectbox("📦 Select Shelf Label", sorted(set(shelf_labels)), key="shelf_label")

# Fetch WIDs for the selected shelf
raw_data = raw_sheet.get_all_records()
shelf_wids = [row["WID"] for row in raw_data if row["ShelfLabel"] == selected_shelf]
selected_wid = st.selectbox("🔄 Select WID (for full info update)", ["-- Select --"] + shelf_wids)

# Fetch data from Raw sheet to DataFrame
raw_df = pd.DataFrame(raw_data)

# WID Scan Input
scanned_wid = st.text_input("🔍 Scan WID", key="scanned_wid")

# Current timestamp
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Automatically process scanned WID
if scanned_wid and not st.session_state.wid_scanned:
    shelf_label = st.session_state.shelf_label
    wid = scanned_wid.strip()

    match = raw_df[(raw_df["ShelfLabel"] == shelf_label) & (raw_df["WID"] == wid)]

    if not match.empty:
        available_qty = match.iloc[0]["Quantity"]
    else:
        available_qty = ""

    stock_data = stock_sheet.get_all_records()
    stock_df = pd.DataFrame(stock_data)

    row_match = stock_df[(stock_df["ShelfLabel"] == shelf_label) & (stock_df["WID"] == wid)]

    if not row_match.empty:
        idx = row_match.index[0] + 2
        current_count = row_match.iloc[0]["CountedQty"]
        stock_sheet.update_cell(idx, 3, current_count + 1)
        stock_sheet.update_cell(idx, 6, timestamp)
        stock_sheet.update_cell(idx, 7, "MISPLACED")
    else:
        stock_sheet.append_row([
            shelf_label,
            wid,
            1,
            available_qty,
            "",
            timestamp,
            "MISPLACED"
        ])

    st.success(f"✅ Scanned WID: {wid} — Counted as 1 and marked MISPLACED")
    st.session_state.wid_scanned = True
    st.rerun()

# Reset flag after rerun
if st.session_state.wid_scanned:
    st.session_state.wid_scanned = False

# Optional: Save full data only when user clicks Save for dropdown WID
if st.button("💾 Save Dropdown WID"):
    if selected_wid != "-- Select --":
        match = raw_df[(raw_df["ShelfLabel"] == selected_shelf) & (raw_df["WID"] == selected_wid)]

        if not match.empty:
            available_qty = match.iloc[0]["Quantity"]
            vertical = match.iloc[0]["Vertical"]
            brand = match.iloc[0]["Brand"]

            stock_data = stock_sheet.get_all_records()
            stock_df = pd.DataFrame(stock_data)

            row_match = stock_df[(stock_df["ShelfLabel"] == selected_shelf) & (stock_df["WID"] == selected_wid)]

            if not row_match.empty:
                idx = row_match.index[0] + 2
                current_count = row_match.iloc[0]["CountedQty"]
                stock_sheet.update_cell(idx, 3, current_count + 1)
                stock_sheet.update_cell(idx, 4, available_qty)
                stock_sheet.update_cell(idx, 5, "")
                stock_sheet.update_cell(idx, 6, timestamp)
                stock_sheet.update_cell(idx, 7, "OK")
            else:
                stock_sheet.append_row([
                    selected_shelf,
                    selected_wid,
                    1,
                    available_qty,
                    "",
                    timestamp,
                    "OK"
                ])
            st.success(f"✅ WID {selected_wid} saved successfully.")
        else:
            st.error("❌ Selected WID not found in Raw data.")
    else:
        st.warning("⚠️ Please select a WID from the dropdown.")
