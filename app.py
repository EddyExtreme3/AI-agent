import json
import base64
from pathlib import Path
from email.message import EmailMessage

import streamlit as st
import lmstudio as lms

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


MODEL_NAME = "qwen2.5-vl-3b-instruct"
PLANNING_FILE = Path("planning.txt")
TOKEN_FILE = Path("token.json")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]

model = lms.llm(MODEL_NAME)


def google_service(api_name: str, api_version: str):
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build(api_name, api_version, credentials=creds)


def maak_planning_met_ai(vakken: str, tijdslots: str) -> dict:
    chat = lms.Chat("""
Je bent een studieplanner.

BELANGRIJK:

Geef ALLEEN geldige JSON terug.

Begin NOOIT met:
<thinking>
<thought>
<channel-thought>

Geef GEEN uitleg.

Gebruik exact dit formaat:

{
  "planning_tekst": "...",
  "calendar_events": [
    {
      "titel": "...",
      "beschrijving": "...",
      "start": "2026-06-20T13:00:00",
      "einde": "2026-06-20T15:00:00"
    }
  ]
}
""")

    prompt = f"""
Vakken, deadlines en moeilijkheid:
{vakken}

Beschikbare studietijd:
{tijdslots}
"""

    chat.add_user_message(prompt)
    response = model.respond(chat)
    raw_output = response.content.strip()
    print("RAW OUTPUT:")
    print(raw_output)

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {
            "planning_tekst": raw_output,
            "calendar_events": []
        }


def sla_planning_op(planning_tekst: str):
    PLANNING_FILE.write_text(planning_tekst, encoding="utf-8")


def verstuur_planning_per_mail(ontvanger_email: str):
    service = google_service("gmail", "v1")

    inhoud = PLANNING_FILE.read_text(encoding="utf-8")

    bericht = EmailMessage()
    bericht["To"] = ontvanger_email
    bericht["Subject"] = "Jouw studieplanning"
    bericht.set_content(
        "Hoi,\n\nIn de bijlage staat jouw studieplanning.\n\nGroetjes,\nSlimme Studie-Agent"
    )

    bericht.add_attachment(
        inhoud.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename="planning.txt"
    )

    encoded_message = base64.urlsafe_b64encode(
        bericht.as_bytes()
    ).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": encoded_message}
    ).execute()


def zet_planning_in_google_calendar(events: list):
    service = google_service("calendar", "v3")

    for event in events:
        calendar_event = {
            "summary": event["titel"],
            "description": event.get("beschrijving", ""),
            "start": {
                "dateTime": event["start"],
                "timeZone": "Europe/Amsterdam"
            },
            "end": {
                "dateTime": event["einde"],
                "timeZone": "Europe/Amsterdam"
            }
        }

        service.events().insert(
            calendarId="primary",
            body=calendar_event
        ).execute()


st.set_page_config(
    page_title="Slimme Studie-Agent",
    page_icon="📚"
)

st.title("📚 Slimme Studie-Agent")
st.write("Vul je vakken, deadlines, moeilijkheid en beschikbare tijd in.")

with st.form("studie_formulier"):
    email = st.text_input("E-mailadres")

    vakken = st.text_area(
        "Vakken, deadlines en moeilijkheid",
        placeholder="Bijvoorbeeld: AI deadline vrijdag moeilijkheid 4, Power BI deadline maandag moeilijkheid 3"
    )

    tijdslots = st.text_area(
        "Beschikbare studietijd",
        placeholder="Bijvoorbeeld: maandag 2 uur, dinsdag 3 uur, donderdag 1 uur"
    )

    knop = st.form_submit_button("Maak planning")

if knop:
    if not email or not vakken or not tijdslots:
        st.error("Vul alle velden in.")
    else:
        with st.spinner("🤖 Agent maakt je planning..."):
            resultaat = maak_planning_met_ai(vakken, tijdslots)

            planning_tekst = resultaat.get("planning_tekst", "")
            calendar_events = resultaat.get("calendar_events", [])

            sla_planning_op(planning_tekst)

        st.success("✅ Planning gemaakt en opgeslagen als planning.txt")
        st.text_area("Jouw planning", planning_tekst, height=400)

    with st.spinner("📅 Planning wordt in Google Calendar gezet..."):
        st.write("Calendar events:")
        st.json(calendar_events)

        if calendar_events:
            zet_planning_in_google_calendar(calendar_events)
            st.success("✅ Planning toegevoegd aan Google Calendar")
        else:
            st.error("❌ Geen calendar events gevonden. Er is dus niets in Google Calendar gezet.")

        with st.spinner("📧 Planning wordt per mail verstuurd..."):
            verstuur_planning_per_mail(email)

        st.success("✅ Planning is per mail verstuurd")


        # voorbeeld input: 