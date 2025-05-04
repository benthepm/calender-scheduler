import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

# Fake event generator
def generate_fake_events():
    names = ["Quarterly Roadmap Review", "Weekly Sync", "Leadership Offsite", "Monthly Demo", "Update Call"]
    descriptions = ["Discuss roadmap", "General sync", "Strategy planning", "Demo to team", "Project update"]
    attendees_pool = ["you@company.com", "boss@company.com", "ceo@company.com", "pm@company.com", "eng@company.com"]

    events = []
    for _ in range(10):
        name = random.choice(names)
        description = random.choice(descriptions)
        start = datetime.now() + timedelta(days=random.randint(0, 21))
        attendees = random.sample(attendees_pool, random.randint(1, 8))
        recurrence = random.choice([None, "RRULE:FREQ=DAILY", "RRULE:FREQ=WEEKLY", "RRULE:FREQ=MONTHLY"])
        events.append({
            "event_name": name,
            "description": description,
            "start_time": start,
            "attendees": attendees,
            "recurrence": recurrence
        })
    return events

# App UI
st.set_page_config(page_title="Meetings to Prep For")
st.title("Meetings to Prep for:")

col1, col2 = st.columns([1, 2])
with col1:
    date_range = st.radio("Pull from", ["Next Week", "Next Month", "Next Quarter"])
    days_lookup = {"Next Week": 7, "Next Month": 30, "Next Quarter": 90}
    range_days = days_lookup[date_range]

    important_emails = st.text_input("Flag when attended by:", "boss@company.com, ceo@company.com")
    important_emails = [e.strip().lower() for e in important_emails.split(",")]

    threshold = st.selectbox("Flag when number attendees exceeds:", list(range(1, 21)), index=4)

    keywords = st.text_area("Flag when containing words", "Leadership, Roadmap, Update, Demo")
    keyword_list = [k.strip().lower() for k in keywords.split(",")]

    ignore_daily = st.toggle("Ignore daily recurring meetings", value=True)
    ignore_weekly = st.toggle("Ignore weekly recurring meetings")
    ignore_all = st.toggle("Ignore all recurring meetings")

# Event logic
events = generate_fake_events()
flagged = []
for e in events:
    if (e["start_time"] - datetime.now()).days > range_days:
        continue

    if ignore_all and e["recurrence"]:
        continue
    if ignore_daily and e["recurrence"] and "DAILY" in e["recurrence"]:
        continue
    if ignore_weekly and e["recurrence"] and "WEEKLY" in e["recurrence"]:
        continue

    should_flag = (
        any(att.lower() in important_emails for att in e["attendees"]) or
        len(e["attendees"]) > threshold or
        any(k in e["event_name"].lower() for k in keyword_list)
    )

    if should_flag:
        flagged.append({
            "Event Name": e["event_name"],
            "Description": e["description"],
            "Attendees": ", ".join(e["attendees"]),
            "Recurrence Schedule": e["recurrence"].replace("RRULE:FREQ=", "every ").lower() if e["recurrence"] else "none"
        })

with col2:
    st.subheader("Flagged Meetings")
    if flagged:
        st.dataframe(pd.DataFrame(flagged))
    else:
        st.write("No meetings flagged.")
