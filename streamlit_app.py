import json
import streamlit as st

client_config = json.loads(st.secrets["GOOGLE_CLIENT_SECRET"])
with open("credentials.json", "w") as f:
    json.dump(client_config, f)
import os
import sqlite3
from datetime import datetime, timedelta, timezone
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── CONFIG ─────────────────────────────────────────────────────────────────────
SCOPES           = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token-personal.json"   # ← update if you renamed your token

def get_token_filename(user_email):
    safe_email = user_email.replace("@", "_at_").replace(".", "_dot_")
    return f"token_{safe_email}.json"

# ── GOOGLE SERVICE SETUP ────────────────────────────────────────────────────────
def get_service(user_email=None):
    creds = None
    token_file = get_token_filename(user_email) if user_email else TOKEN_FILE
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def get_user_email(service):
    """Fetch the authenticated user's email using the primary calendar ID."""
    calendar = service.calendarList().get(calendarId="primary").execute()
    return calendar.get("id", "unknown@example.com")

def init_db():
    conn = sqlite3.connect("filters.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS exclusions (
            user_id TEXT PRIMARY KEY,
            exclusions TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user_exclusions(user_id, exclusion_list):
    joined = ",".join(exclusion_list)
    with sqlite3.connect("filters.db") as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO exclusions (user_id, exclusions)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET exclusions=excluded.exclusions
        """, (user_id, joined))
        conn.commit()

def load_user_exclusions(user_id):
    with sqlite3.connect("filters.db") as conn:
        c = conn.cursor()
        c.execute("SELECT exclusions FROM exclusions WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            return [e.strip() for e in row[0].split(",") if e.strip()]
        return []

def list_calendars(service):
    resp = service.calendarList().list().execute()
    return [c["id"] for c in resp.get("items", [])]

def get_events(service, calendar_id: str, days: int):
    now_iso = datetime.utcnow().isoformat() + "Z"
    max_iso = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=now_iso,
        timeMax=max_iso,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    items = resp.get("items", [])
    st.sidebar.write(f"➤ API returned {len(items)} events from `{calendar_id}`")
    return items

# ── STREAMLIT UI ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Google Calendar Event Filter", layout="wide")
st.title("Google Calendar Important Event Filter")
st.write("Find and prepare for important events coming up in your calendar by hiding the ones that don't matter.")

if "user_email" not in st.session_state:
    st.title("Login Required")
    st.write("To continue, please log in with your Google account.")
    if st.button("🔐 Login with Google"):
        temp_service = get_service()  # uses default token
        user_email = get_user_email(temp_service)

        # Now get user-specific service
        service = get_service(user_email)

        # Save to session
        st.session_state.service = service
        st.session_state.user_email = user_email
        st.rerun()
    st.stop()
else:
    service = st.session_state.service
    user_email = st.session_state.user_email

st.sidebar.write(f"Logged in as: {user_email}")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

init_db()

# Sidebar: calendar selector + date range + basic filters
all_cals = list_calendars(service)
calendar_id = st.sidebar.selectbox("Which calendar to pull from:", ["primary"] + all_cals, index=0)

date_range = st.sidebar.radio(
    "Pull from:",
    ["Next Week", "Next Month", "Next Quarter"],
    index=2
)
days_lookup = {"Next Week": 7, "Next Month": 30, "Next Quarter": 90}
days = days_lookup[date_range]

exclude_no_attendees = st.sidebar.checkbox("Exclude events with no attendees", value=True)

# Always fetch events on every rerun
events = get_events(service, calendar_id, days)

# Uncomment lines below to see full JSON to debug
# st.subheader("🔍 Raw API Events")
# st.json(events)


# Build the list of all events passing the basic filters
flagged = []
now = datetime.now(timezone.utc)

for e in events:
    raw = e["start"].get("dateTime", e["start"].get("date"))
    try:
        start_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except:
        start_dt = datetime.strptime(raw, "%Y-%m-%d")
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    # Skip out-of-range
    if (start_dt - now).days > days:
        continue

    # Skip no-attendees
    attendees = [a["email"] for a in e.get("attendees", [])]
    if exclude_no_attendees and not attendees:
        continue

    # Keep the event
    summary_lower = e.get("summary", "").lower()
    flagged.append({
        "Event":       summary_lower.title(),
        "Start":       start_dt.strftime("%-m/%-d %-I%p").lower(),
        "Attendees":   ", ".join(attendees),
        "Description": e.get("description", "")
    })

# ── NEGATION SEARCH FILTER & DISPLAY ────────────────────────────────────────────

# 1) On load, grab the current “hide” value from the URL (or default to empty)
initial_hide = st.query_params.get("hide", "")

saved_filters_exist = bool(load_user_exclusions(user_email))

negation_input = st.text_input(
    'Hide events by name (prefix with "-")',
    initial_hide,
    key="negation_input"
)

# 1. Define negatives before rendering save/load filter buttons
negatives = [
    token.strip()
         .lstrip('-')
         .strip()
         .lower()
    for token in negation_input.split(',')
    if token.strip().startswith('-')
]

# 2. Render Save/Load filter buttons
spacer, col2, col3 = st.columns([7, 1, 1])
with col2:
    if negatives:
        if st.button("💾 Save these filters"):
            save_user_exclusions(user_email, negatives)
            st.toast("✅ Saved successfully.")
with col3:
    if saved_filters_exist:
        if st.button("📂 Load saved filters"):
            loaded = load_user_exclusions(user_email)
            negation_input = ",".join(f"-{e}" for e in loaded)
            st.query_params.hide = negation_input
            st.rerun()

# 3) Immediately write back any changes to the URL
#    Assigning to st.query_params.hide updates the browser’s query string
st.query_params.hide = negation_input

display_events = [
    ev for ev in flagged
    if not any(
        neg in ev["Event"].lower() or neg in ev["Description"].lower()
        for neg in negatives
    )
]

if display_events:
    st.dataframe(pd.DataFrame(display_events), height=600)
else:
    st.write("No events matched the criteria.")

#Debugging 
#df_debug = pd.DataFrame([{
#    "Event":      e.get("summary","(no title)"),
#    "Start":      e["start"].get("dateTime", e["start"].get("date")),
#    "Attendees":  len(e.get("attendees", []))
#} for e in events])
#st.dataframe(df_debug, height=300)
