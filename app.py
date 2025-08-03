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

# 📂 Google Sheets Auth
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
st.session_state.setdefault("reset_wid", False)

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

def log_daily_summary():
    stock_df = get_stock_data()
    today = datetime.now().strftime("%Y-%m-%d")
    daily_df = stock_df[
        (stock_df["CasperID"] == st.session_state.username) &
        (stock_df["Timestamp"].str.startswith(today))
    ]
    if daily_df.empty:
        st.warning("📥 No entries to summarize for today.")
        return
    summary_df = daily_df.groupby("Status").size().reset_index(name="Count")
    summary_df.insert(0, "CasperID", st.session_state.username)
    summary_df.insert(0, "Date", today)
    try:
        report_sheet = sheet.worksheet("DailyReports")
    except gspread.WorksheetNotFound:
        report_sheet = sheet.add_worksheet(title="DailyReports", rows=1000, cols=10)
    for _, row in summary_df.iterrows():
        report_sheet.append_row(row.tolist())
    st.success("📝 Daily summary saved to DailyReports sheet.")

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
        if st.session_state.get("show_registration", True):
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

# 🛆 MAIN APP
else:
    st.title("🛆 Inventory Stock Count App")
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
        stock_df = get_stock_data()

        if st.session_state.reset_wid:
            st.session_state["scanned_wid"] = ""
            st.session_state.reset_wid = False

        scanned_wid = st.text_input("🧪 Scan WID", key="scanned_wid")
        if scanned_wid:
            wid = scanned_wid.strip()
            shelf = st.session_state.shelf_label.strip()
            matched_row = raw_df[
                (raw_df["ShelfLabel"].astype(str).str.strip() == shelf) &
                (raw_df["WID"].astype(str).str.strip() == wid)
            ]
            if not matched_row.empty:
                row = matched_row.iloc[0]
                vertical = row["Vertical"]
                brand = row["Brand"]
                available_qty = int(row["Quantity"])
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                match = stock_df[
                    (stock_df["ShelfLabel"].astype(str).str.strip() == shelf) &
                    (stock_df["WID"].astype(str).str.strip() == wid)
                ]

                if not match.empty:
                    idx = match.index[0] + 2
                    current_count = int(match.iloc[0]["CountedQty"])
                    new_count = current_count + 1
                else:
                    idx = None
                    new_count = 1

                status = "Short" if new_count < available_qty else "Excess" if new_count > available_qty else "OK"

                if idx:
                    stock_sheet.update_cell(idx, 4, new_count)
                    stock_sheet.update_cell(idx, 6, status)
                    stock_sheet.update_cell(idx, 7, timestamp)
                else:
                    stock_sheet.append_row([
                        shelf,
                        wid,
                        vertical,
                        new_count,
                        available_qty,
                        status,
                        timestamp,
                        st.session_state.username
                    ])
                st.success(f"✅ `{wid}` scanned and updated.")
                st.session_state.reset_wid = True
                st.rerun()

        st.markdown("---")
        st.subheader("🔽 Manual WID Save")
        shelf_df = raw_df[raw_df["ShelfLabel"] == st.session_state.shelf_label]
        wid_options = shelf_df["WID"].unique().tolist()
        selected_wid = st.selectbox("📋 Select WID", wid_options, key="wid_dropdown")

        matched_row = raw_df[
            (raw_df["ShelfLabel"].astype(str).str.strip() == st.session_state.shelf_label.strip()) &
            (raw_df["WID"].astype(str).str.strip() == selected_wid.strip())
        ]

        if not matched_row.empty:
            row = matched_row.iloc[0]
            vertical = row["Vertical"]
            available_qty = int(row["Quantity"])
            st.write(f"**Vertical:** {vertical}")
            st.write(f"**Brand:** {row['Brand']}")
            st.write(f"**Available Qty:** {available_qty}")
            manual_count = st.number_input("Enter Counted Qty", min_value=0, step=1)

            if st.button("📃 Save This WID"):
                match = stock_df[
                    (stock_df["ShelfLabel"].astype(str).str.strip() == st.session_state.shelf_label.strip()) &
                    (stock_df["WID"].astype(str).str.strip() == selected_wid.strip())
                ]
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                status = "Short" if manual_count < available_qty else "Excess" if manual_count > available_qty else "OK"

                if not match.empty:
                    idx = match.index[0] + 2
                    stock_sheet.update_cell(idx, 4, manual_count)
                    stock_sheet.update_cell(idx, 6, status)
                    stock_sheet.update_cell(idx, 7, timestamp)
                else:
                    stock_sheet.append_row([
                        st.session_state.shelf_label,
                        selected_wid,
                        vertical,
                        manual_count,
                        available_qty,
                        status,
                        timestamp,
                        st.session_state.username
                    ])
                st.success(f"✅ `{selected_wid}` manually saved.")
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Save Daily Summary"):
            log_daily_summary()
    with col2:
        if st.button("🔄 Reset Validated WID List"):
            st.session_state.validated_wids = []
            st.rerun()
