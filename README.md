# Calendar Scheduler

Connects to your Google Calendar and filters upcoming events based on custom rules, like hiding events without attendees or with certain keywords. Uses Streamlit.

## Features

- OAuth login via Google
- List calendars and upcoming events
- Hide events by keywords or save personal filter rules
- Store user filters in a SQLite database

## Setup

1. Clone the repo
2. Add your OAuth client config to `.streamlit/secrets.toml` like this:

    ```
    GOOGLE_CLIENT_SECRET = \"\"\"
    {
      "installed": {
        "client_id": "YOUR_CLIENT_ID",
        "project_id": "YOUR_PROJECT_ID",
        ...
      }
    }
    \"\"\"
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the app:

    ```bash
    streamlit run app.py
    ```
