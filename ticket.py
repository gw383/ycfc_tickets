from PIL import Image
import pytesseract
import re
import json
import os
import smtplib
from email.message import EmailMessage

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

IMAGE_PATH = "fixtures_full.png"
DATA_FILE = "fixtures.json"

EMAIL_FROM = "georgewilliams383@gmail.com"
EMAIL_TO = "georgewilliams383@gmail.com"
EMAIL_PASSWORD = os.getenv("YCFC_GMAIL_PASSWORD")


def extract_text(image_path):
    return pytesseract.image_to_string(Image.open(image_path))


def extract_fixtures(text):
    text = re.sub(r"\s+", " ", text)

    pattern = r"York City\s+v(?:s)?\s+([A-Za-z]+)"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)

    fixtures = []

    for team in matches:
        fixtures.append(f"York City vs {team}")

    return list(dict.fromkeys(fixtures))


def load_previous():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_current(fixtures):
    with open(DATA_FILE, "w") as f:
        json.dump(fixtures, f, indent=2)


def get_new_fixtures(old, new):
    return [fixture for fixture in new if fixture not in old]


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

        print("Email sent.")
    except Exception as e:
        print("Email failed:", e)


def main():
    text = extract_text(IMAGE_PATH)

    fixtures = extract_fixtures(text)

    if not fixtures:
        print("No fixtures detected")
        return

    print("Current fixtures:")
    for fixture in fixtures:
        print("-", fixture)

    previous = load_previous()

    new_fixtures = get_new_fixtures(previous, fixtures)

    if new_fixtures:
        print("\nNEW FIXTURES FOUND:")
        for fixture in new_fixtures:
            print("🚨", fixture)

        send_email(new_fixtures)

    else:
        print("\nNo new fixtures.")

    save_current(fixtures)


if __name__ == "__main__":
    main()