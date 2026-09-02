from PIL import Image
import pytesseract
from pytesseract import Output
import json
import os
import smtplib
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

# ----------------------------
# CONFIGURATION
# ----------------------------

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

IMAGE_PATH = "fixtures_full.png"
DATA_FILE = "fixtures.json"
TEAMS_FILE = "teams.json"

EMAIL_FROM = "georgewilliams383@gmail.com"
EMAIL_TO = "georgewilliams383@gmail.com"
EMAIL_PASSWORD = os.getenv("YCFC_GMAIL_PASSWORD") # this is retrieved from gmail/emailing service and set in the venv

# IMPORTANT:
# Point this at the COPY of your Chrome profile, not your live profile.
CHROME_PROFILE = r"C:\ycfc\ChromeProfile"

TICKETS_URL = "https://www.yorkcityfootballclub.co.uk/tickets-and-hospitality/match-tickets/home-tickets"


# ----------------------------
# TAKE A FRESH SCREENSHOT
# ----------------------------

def take_screenshot():
    print("Opening browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_PROFILE,
            headless=False
        )

        page = browser.new_page()

        print("Loading ticket page...")
        page.goto(TICKETS_URL, wait_until="networkidle")

        # Give Future Ticketing time to render
        page.wait_for_timeout(8000)

        print("Taking screenshot...")
        page.screenshot(path=IMAGE_PATH, full_page=True)

        browser.close()

    print("Screenshot saved.\n")


# ----------------------------
# OCR
# ----------------------------

def extract_text(image_path):
    return pytesseract.image_to_string(Image.open(image_path))


# ----------------------------
# FIND FIXTURES
# ----------------------------

def load_teams():

    if not os.path.exists(TEAMS_FILE):
        print("teams.json not found")
        return []

    with open(TEAMS_FILE, "r") as f:
        return json.load(f)


def extract_fixtures(image_path):

    print("Running OCR...")

    image = Image.open(image_path)

    data = pytesseract.image_to_data(
        image,
        output_type=Output.DICT
    )

    print("\n--- TESSERACT OCR ---")

    for word in data["text"]:

        word = word.strip()

        if word:
            print(word)

    print("---------------------\n")

    teams = load_teams()

    detected = []

    print("\n--- OCR WORDS ---")

    for word in data["text"]:

        word = word.strip()

        if word:
            print(word)

            # remove punctuation
            clean = word.replace(",", "").replace(".", "")

            if clean in teams:
                detected.append(
                    f"York City vs {clean}"
                )

    print("-----------------\n")

    return list(dict.fromkeys(detected))

# ----------------------------
# LOAD PREVIOUS RESULTS
# ----------------------------

def load_previous():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r") as f:
        return json.load(f)


# ----------------------------
# SAVE CURRENT RESULTS
# ----------------------------

def save_current(fixtures):
    with open(DATA_FILE, "w") as f:
        json.dump(fixtures, f, indent=2)


# ----------------------------
# COMPARE
# ----------------------------

def get_new_fixtures(old, new):
    return [fixture for fixture in new if fixture not in old]


# ----------------------------
# EMAIL ALERT
# ----------------------------

def send_email(new_fixtures):

    if not EMAIL_PASSWORD:
        print("Email password not configured.")
        return

    body = "New York City fixture(s) detected:\n\n"
    body += "\n".join(new_fixtures)

    msg = EmailMessage()
    msg["Subject"] = "YCFC New Fixture Alert"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print("Email sent successfully.")

    except Exception as e:
        print("Email failed:", e)


# ----------------------------
# MAIN
# ----------------------------

def main():

    print("Starting YCFC fixture checker...\n")

    # Take new screenshot
    take_screenshot()

    # Extract fixtures from screenshot
    fixtures = extract_fixtures(IMAGE_PATH)

    if not fixtures:
        print("No fixtures detected.")
        return


    print("\n==============================")
    print("CURRENT FIXTURES DETECTED")
    print("==============================")

    for fixture in fixtures:
        print("-", fixture)


    # Load previous stored fixtures
    previous = load_previous()


    print("\n==============================")
    print("PREVIOUSLY SAVED FIXTURES")
    print("==============================")

    if previous:
        for fixture in previous:
            print("-", fixture)
    else:
        print("No previous fixtures found.")


    # Compare old vs new
    new_fixtures = get_new_fixtures(
        previous,
        fixtures
    )


    print("\n==============================")
    print("COMPARISON RESULT")
    print("==============================")


    if new_fixtures:

        print("🚨 NEW FIXTURES FOUND:")

        for fixture in new_fixtures:
            print("-", fixture)


        send_email(new_fixtures)


    else:

        print("No new fixtures detected.")


    # Always update stored fixtures after comparison
    save_current(fixtures)


    print("\n==============================")
    print("SAVED CURRENT FIXTURES")
    print("==============================")

    for fixture in fixtures:
        print("-", fixture)


    print("\nFinished successfully.")


# ----------------------------
# ENTRY POINT
# ----------------------------

if __name__ == "__main__":
    main()
