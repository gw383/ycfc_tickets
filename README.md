# York City FC Ticket Checker

A Python-based monitoring tool that checks the York City FC ticketing page for newly released fixtures and sends an email alert whenever a new fixture appears.

The project was built to monitor fixture releases automatically without needing to manually check the website throughout the day.

## How It Works

The script:

1. Opens the York City FC ticketing page using Playwright.
2. Captures a screenshot of the fixture area.
3. Uses OCR (Tesseract) to extract text from the screenshot.
4. Identifies fixtures using pattern matching.
5. Compares the current fixture list against previously stored fixtures.
6. Sends an email alert if a new fixture is detected.
7. Updates the stored fixture list for future checks.


