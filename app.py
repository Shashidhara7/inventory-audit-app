import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# 🌄 Supply Chain Theme Background
st.markdown("""
    <style>
    .stApp {
        background-image: url("https://images.unsplash.com/photo-1581092160611-1c67e48ea8f3?auto=format&fit=crop&w=1400&q=80");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    .stButton>button, .stTextInput>div>div>input {
        background-color: #005f73;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# 🗂️ Google Sheets Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDS"], scopes=scope)
client = gspread.authorize(creds)

# 🔗 Sheet References
sheet = client.open("InventoryStockApp")
raw_sheet = sheet.worksheet("Raw")
stock_sheet = sheet.worksheet("StockCountDetails")
login_sheet = sheet.worksheet("LoginDetails")

# 📋 Ensure Updated Headers
expected_headers = ["ShelfLabel", "WID", "Vertical", "CountedQty", "AvailableQty", "Status", "Timestamp", "CasperID"]
if stock_sheet.row_values(1) != expected_headers:
    stock_sheet.update("A1:H1", [expected_headers])

# 🧠 Session Defaults
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("shelf_label", "")
st.session_state.setdefault("validated_wids", [])
st.session_state.setdefault("username", "")
st.session_state.setdefault("show_registration", False)
st.session_state.setdefault("scanned_misplaced_wid", "")

# 🔧 Helper Functions
def get_login_data():
    return pd.DataFrame(login_sheet.get_all_records())

def validate_login(username, password):
    df = get_login_data()
    if df.empty:
        return "deleted"
    username = username.strip().lower()
    password = password.strip()
    match = df[df["Username"].str.strip().str.lower() == username]
    if match.empty:
        return "deleted"
    elif password == str(match.iloc[0]["Password"]).strip():
        return "valid"
    else:
        return "invalid"

def get_raw_data():
    return pd.DataFrame(raw_sheet.get_all_records())

def get_stock_data():
    return pd.DataFrame(stock_sheet.get_all_records())

def clear_misplaced_input():
    st.session_state.scanned_misplaced_wid = ""

def process_misplaced_wid():
    """Handles scanning of WIDs not expected on the shelf."""
    wid = st.session_state.scanned_misplaced_wid.strip()
    if not wid:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    shelf_label = st.session_state.shelf_label
    
    if wid in st.session_state.validated_wids:
        st.warning(f"⚠️ WID `{wid}` has already been processed.")
        clear_misplaced_input()
        return

    stock_sheet.append_row([
        shelf_label,
        wid,
        "",
        1,
        "",
        "MISPLACED",
        timestamp,
        st.session_state.username
    ])
    st.success(f"✅ WID `{wid}` marked as MISPLACED on shelf `{shelf_label}`.")
    st.session_state.validated_wids.append(wid)
    clear_misplaced_input()

def save_summary_report():
    """Generates and saves a detailed summary report to a new worksheet."""
    try:
        report_sheet = sheet.worksheet("SummaryReport")
    except gspread.WorksheetNotFound:
        report_sheet = sheet.add_worksheet(title="SummaryReport", rows=1000, cols=10)
    
    report_sheet.clear()

    stock_df = get_stock_data()
    if stock_df.empty:
        st.warning("No data to save.")
        return

    user_stock_df = stock_df[stock_df["CasperID"] == st.session_state.username].copy()
    if user_stock_df.empty:
        st.warning("No data to save for your user account.")
        return

    user_stock_df["Date"] = pd.to_datetime(user_stock_df["Timestamp"]).dt.date
    
    # 1. Generate and save the summary table
    summary_table = user_stock_df.groupby(["Date", "CasperID", "Status"]).size().reset_index(name="Count")
    summary_data = [["Daily Status Summary"]]
    summary_data.extend([summary_table.columns.tolist()])
    summary_data.extend(summary_table.values.tolist())
    report_sheet.append_rows(summary_data)

    # 2. Generate and save the detailed discrepancies table
    discrepancy_table = user_stock_df[user_stock_df["Status"] != "OK"]
    if not discrepancy_table.empty:
        discrepancy_table = discrepancy_table[[
            "ShelfLabel",
            "WID",
            "AvailableQty",
            "CountedQty",
            "CasperID",
            "Date"
        ]].rename(columns={"AvailableQty": "Available Qty", "CountedQty": "Counted Qty", "CasperID": "Username"})
        
        discrepancy_data = [[]]
        discrepancy_data.extend([["Detailed Discrepancies"]])
        discrepancy_data.extend([discrepancy_table.columns.tolist()])
        discrepancy_data.extend(discrepancy_table.values.tolist())
        report_sheet.append_rows(discrepancy_data)

    st.success("✅ Summary report successfully saved to the 'SummaryReport' worksheet!")

# 🔐 LOGIN PAGE
if not st.session_state.logged_in:
    st.title("🔐 Login Page")
    tabs = st.tabs(["Login", "Register"])
    with tabs[0]:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            login_status = validate_login(username, password)
            if login_status == "valid":
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.rerun()
            elif login_status == "invalid":
                st.error("❌ Incorrect password. Please try again.")
            elif login_status == "deleted":
                st.warning("⚠️ Account not found. Please register below.")
                st.session_state.show_registration = True
    with tabs[1]:
        if st.session_state.show_registration:
            new_username = st.text_input("New Username", key="reg_user")
            new_password = st.text_input("New Password", type="password", key="reg_pass")
            if st.button("Register"):
                df = get_login_data()
                if "Username" in df.columns and new_username.strip().lower() in df["Username"].astype(str).str.strip().str.lower().values:
                    st.warning("⚠️ Username already exists. Try a different one.")
                else:
                    now = datetime.now()
                    login_sheet.append_row([
                        now.strftime("%Y-%m-%d"),
                        new_username.strip(),
                        new_password.strip(),
                        now.strftime("%H:%M:%S")
                    ])
                    st.success("✅ Registered successfully! Please login.")
                    st.session_state.show_registration = False
                    st.rerun()
        else:
            st.info("✅ You can now login with your new credentials.")

# 📦 MAIN APP
else:
    st.sidebar.success(f"👋 Logged in as `{st.session_state.username}`")
    page = st.sidebar.radio("Navigation", ["Stock Count", "Summary"])
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.shelf_label = ""
        st.session_state.validated_wids = []
        st.rerun()

    if page == "Stock Count":
        st.title("📦 Inventory Stock Count App")
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

            st.subheader("Scan Misplaced WIDs")
            st.info("Use this box for items that are on the shelf but not in the list below.")
            st.text_input(
                "🔍 Scan a WID (for misplaced items)",
                key="scanned_misplaced_wid",
                on_change=process_misplaced_wid
            )

            if shelf_df.empty:
                st.warning("⚠️ No data found for this Shelf Label.")
            else:
                st.subheader("Count Expected WIDs")
                st.info("Select a WID from the list to count items expected on this shelf.")
                remaining_wids = shelf_df[~shelf_df["WID"].isin(st.session_state.validated_wids)]["WID"].tolist()
                
                if remaining_wids:
                    selected_wid = st.selectbox("🔽 Select WID to Validate", options=remaining_wids, key="wid_selector")
                    if selected_wid:
                        row = shelf_df[shelf_df["WID"] == selected_wid].iloc[0]
                        vertical = row.get("Vertical", "")
                        st.markdown(f"""
                        ### 🔍 WID Details
                        - **Brand**: `{row['Brand']}`
                        - **Vertical**: `{vertical}`
                        - **Available Qty**: `{row['Quantity']}`
                        """)
                        counted = st.number_input("Enter Counted Quantity", min_value=0, step=1, key="counted_qty")
                        
                        if st.button("✅ Save This WID"):
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            available = int(row["Quantity"])
                            status = "Short" if counted < available else "Excess" if counted > available else "OK"
                            
                            stock_df = get_stock_data()
                            if "ShelfLabel" in stock_df.columns and "WID" in stock_df.columns:
                                existing = stock_df[
                                    (stock_df["ShelfLabel"].astype(str).str.strip() == str(st.session_state.shelf_label).strip()) &
                                    (stock_df["WID"].astype(str).str.strip() == str(selected_wid).strip())
                                ]
                            else:
                                st.error("🛑 'ShelfLabel' or 'WID' column not found in stock_df. Please check your data source.")
                                existing = pd.DataFrame()
                            
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

            st.markdown("---")
            if st.button("🔄 Reset Validated WID List"):
                st.session_state.validated_wids = []
                st.rerun()
            if st.button("📤 Save Summary Report"): # Changed button text
                save_summary_report()

    elif page == "Summary":
        st.title("📊 Inventory Count Summary")
        st.markdown("---")
        
        stock_df = get_stock_data()
        
        if stock_df.empty:
            st.info("No stock count data available yet.")
        else:
            user_stock_df = stock_df[stock_df["CasperID"] == st.session_state.username].copy()
            user_stock_df["Date"] = pd.to_datetime(user_stock_df["Timestamp"]).dt.date
            
            if user_stock_df.empty:
                st.info("You have not recorded any counts yet.")
            else:
                st.subheader("Daily Status Summary")
                summary_table = user_stock_df.groupby(["Date", "CasperID", "Status"]).size().reset_index(name="Count")
                st.dataframe(summary_table, use_container_width=True)
                
                st.markdown("---")
                
                st.subheader("Detailed Discrepancies")
                discrepancy_table = user_stock_df[user_stock_df["Status"] != "OK"]
                
                if discrepancy_table.empty:
                    st.info("All items you have counted are 'OK'!")
                else:
                    discrepancy_table = discrepancy_table[[
                        "ShelfLabel",
                        "WID",
                        "AvailableQty",
                        "CountedQty",
                        "CasperID",
                        "Date"
                    ]].rename(columns={"AvailableQty": "Available Qty", "CountedQty": "Counted Qty", "CasperID": "Username"})
                    st.dataframe(discrepancy_table, use_container_width=True)

        st.markdown("---")
        if st.button("📤 Save Summary Report"):
            save_summary_report()