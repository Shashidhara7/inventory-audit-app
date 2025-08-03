import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# 📂 Google Sheets Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# 🔗 Sheet References
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# 📅 Timestamp
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 🧠 Session State
if "shelf_label" not in st.session_state:
    st.session_state.shelf_label = ""
if "scanned_wid" not in st.session_state:
    st.session_state.scanned_wid = ""

st.title("📦 Inventory Stock Count")

# 🔲 Shelf Label Input
shelf_label = st.text_input("Scan Shelf Label", key="shelf_label_input")
if shelf_label:
    st.session_state.shelf_label = shelf_label.strip()

# 📥 Scan WID (Auto Trigger)
scanned_wid = st.text_input("📮 Scan WID", key="scanned_wid_input")

if scanned_wid and st.session_state.shelf_label:
    raw_data = raw_sheet.get_all_records()
    stock_data = stock_sheet.get_all_records()
    raw_df = pd.DataFrame(raw_data)
    stock_df = pd.DataFrame(stock_data)

    existing_rows = stock_df[
        (stock_df["ShelfLabel"].astype(str).str.strip() == st.session_state.shelf_label) &
        (stock_df["WID"].astype(str).str.strip() == scanned_wid.strip())
    ]

    if not existing_rows.empty:
        row_index = existing_rows.index[0] + 2  # +2 for header and 1-based indexing
        stock_sheet.update_cell(row_index, 3, 1)  # CountedQty
        stock_sheet.update_cell(row_index, 6, timestamp)  # Timestamp
        stock_sheet.update_cell(row_index, 7, "MISPLACED")  # Status
    else:
        stock_sheet.append_row([
            st.session_state.shelf_label,
            scanned_wid.strip(),
            1,                # CountedQty
            "",               # AvailableQty
            "",               # Brand
            timestamp,
            "MISPLACED"       # Status
        ])

    st.success(f"✅ Scanned WID: {scanned_wid} — MISPLACED added with Qty: 1")
    st.rerun()

# 🔻 Manual WID Selection & Save
st.markdown("---")
st.subheader("🔧 Manual WID Save")

wid_options = raw_sheet.col_values(2)[1:]  # Skipping header
selected_wid = st.selectbox("Select WID", wid_options)

if selected_wid:
    raw_data = raw_sheet.get_all_records()
    stock_data = stock_sheet.get_all_records()
    raw_df = pd.DataFrame(raw_data)
    stock_df = pd.DataFrame(stock_data)

    # Get from Raw
    raw_row = raw_df[raw_df["WID"].astype(str).str.strip() == selected_wid.strip()]
    if not raw_row.empty:
        vertical = raw_row["Vertical"].values[0]
        brand = raw_row["Brand"].values[0]
        available_qty = raw_row["Quantity"].values[0]
        st.markdown(f"**Brand:** {brand}  \n**Vertical:** {vertical}  \n**Available Qty:** {available_qty}")
        counted_qty = st.number_input("Enter Counted Qty", min_value=0, step=1)

        if st.button("💾 Save This WID"):
            existing_rows = stock_df[
                (stock_df["ShelfLabel"].astype(str).str.strip() == st.session_state.shelf_label) &
                (stock_df["WID"].astype(str).str.strip() == selected_wid.strip())
            ]

            if not existing_rows.empty:
                row_index = existing_rows.index[0] + 2
                stock_sheet.update_cell(row_index, 3, counted_qty)
                stock_sheet.update_cell(row_index, 4, available_qty)
                stock_sheet.update_cell(row_index, 5, brand)
                stock_sheet.update_cell(row_index, 6, timestamp)
                stock_sheet.update_cell(row_index, 7, "OK")
                st.success(f"✅ Updated {selected_wid} with new count: {counted_qty}")
            else:
                stock_sheet.append_row([
                    st.session_state.shelf_label,
                    selected_wid,
                    counted_qty,
                    available_qty,
                    brand,
                    timestamp,
                    "OK"
                ])
                st.success(f"✅ Added new entry for {selected_wid} with count: {counted_qty}")
