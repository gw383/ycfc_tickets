# YCFC Ticket Checker

[![CI](https://github.com/gw383/ycfc_tickets/actions/workflows/ci.yml/badge.svg)](https://github.com/gw383/ycfc_tickets/actions/workflows/ci.yml)

Get a push notification on your phone the moment York City FC put a new home fixture on sale, instead of refreshing the tickets page all day.

```
2026-10-02 09:40:03 INFO    Loading https://www.yorkcityfootballclub.co.uk/.../home-tickets
2026-10-02 09:40:06 INFO    On sale: York City v Northampton Town; York City v Accrington Stanley; York City v Barnet
2026-10-02 09:40:07 INFO    ntfy alert sent
```

## How it works

```
Task Scheduler (every 10 min)
        │
        ▼
 Playwright opens the tickets page ──► waits for the Future Ticketing widget (#ft_container)
        │                              to render, then reads its text straight from the page
        ▼
 parser: keep lines like "York City v <opponent>", drop add-ons (": Parking", hospitality…)
        │
        ▼
 state: compare with data/seen_fixtures.json ──► anything not seen before?
        │                                              │
        ▼                                              ▼
 save updated state                          push to your phone (ntfy)
```

The fixtures are rendered by a JavaScript ticketing widget, so a plain HTTP request can't see them. A headless browser loads the page, waits until the widget contains fixtures, and reads the text directly from the DOM.

### What changed from v1

v1 took a full-page screenshot, ran Tesseract OCR over it, and matched single words against a hand-maintained `teams.json`. v2:

| | v1 (screenshot + OCR) | v2 (DOM text) |
|---|---|---|
| Accuracy | OCR guesses; multi-word names split up | exact text from the page |
| New opponents (cup draws) | had to edit `teams.json` | picked up automatically |
| Add-ons like "…: Parking" | could false-alarm | filtered out |
| Waiting | fixed 8 s sleep + `networkidle` | waits only until fixtures appear |
| Downloads | full page incl. images | images/fonts/media blocked |
| Browser | visible window every run | headless by default |
| Extra installs | Tesseract | none beyond Python |
| Duplicate alerts | state overwritten each run, so a flaky load re-alerts | seen fixtures remembered for 180 days |
| Alerts | Gmail email | push notification to your phone via ntfy |
| Failed alert | fixture marked seen anyway | retried next run |
| Secrets | email and Gmail password needed | just a topic name, in `.env` (git-ignored) |

## Setup (Windows)

Needs Python 3.10+ and git.

```powershell
git clone https://github.com/gw383/ycfc_tickets.git
cd ycfc_tickets
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

That creates `venv\`, installs the package and Playwright's Chromium, and copies `.env.example` to `.env`.

<details>
<summary>Manual setup / macOS / Linux</summary>

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```
</details>

### Set up phone alerts (ntfy)

[ntfy](https://ntfy.sh) is a free push-notification service with no account needed. Your phone "subscribes" to a topic name; anything sent to that topic pops up as a notification.

1. Install **ntfy** from the App Store or Google Play.
2. Tap **+**, enter a hard-to-guess topic name (e.g. `ycfc-g7k2q9xm`), and subscribe. Anyone who knows the name can see the alerts, so don't use something obvious.
3. Allow notifications when asked. On Android, also turn off battery optimisation for ntfy so alerts arrive instantly.
4. In `.env`, set `NTFY_TOPIC` to exactly the same name. That's the only required setting; everything else in [`.env.example`](.env.example) has sensible defaults.

Check it works:

```powershell
venv\Scripts\python -m ycfc_tickets --test-alert   # sends a test notification
venv\Scripts\python -m ycfc_tickets --dry-run      # scrapes and shows what it finds
```

The **first real run** records what is currently on sale as a baseline and doesn't alert. After that you only hear about new fixtures. Use `--alert-on-first-run` if you want an alert for everything on that first run.

### Schedule it

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1 -Minutes 10
```

This registers a Windows scheduled task called **YCFC Ticket Checker** that runs silently with `pythonw` (no pop-up window). Output goes to `logs\ycfc_tickets.log`. To remove it:

```powershell
Unregister-ScheduledTask -TaskName "YCFC Ticket Checker" -Confirm:$false
```

## Usage

```
python -m ycfc_tickets [--dry-run] [--headed] [--screenshot PNG] [--alert-on-first-run]
                       [--test-alert] [--env-file PATH] [-v]
```

| Flag | What it does |
|---|---|
| `--dry-run` | Scrapes and reports, but sends nothing and doesn't save state |
| `--headed` | Shows the browser window |
| `--screenshot out.png` | Saves a full-page screenshot as well (debugging) |
| `--test-alert` | Sends a test notification to your phone |
| `-v` | Debug logging, including the raw page text |

Exit codes: `0` OK, `1` page couldn't be loaded, `2` an alert failed to send.

## Troubleshooting

- **"No fixtures on sale right now" but there are.** Run `python -m ycfc_tickets --headed --screenshot debug.png -v` to see what the browser sees. If the site is blocking headless browsers, set `HEADLESS=false` in `.env`. If it needs cookies from an earlier visit, point `BROWSER_PROFILE` at a dedicated folder (not your everyday Chrome profile).
- **The site's layout changed.** The parser only relies on listings reading "York City v <opponent>". If the club renames things, adjust `HOME_TEAM` / `EXCLUDE_KEYWORDS`, or the regex in `src/ycfc_tickets/parser.py`.
- **Test alert doesn't arrive.** Check `NTFY_TOPIC` matches the topic in the app exactly (it's case-sensitive) and that notifications are allowed for ntfy.

## Project layout

```
src/ycfc_tickets/
  cli.py       command-line entry point and the main check-and-alert flow
  config.py    settings from environment / .env
  scraper.py   Playwright: load page, wait for widget, read text
  parser.py    text -> list of fixtures
  state.py     remembers which fixtures have been seen (atomic JSON writes)
  notify.py    ntfy push notifications
tests/          unit tests + a browser test against a local copy of the page layout
scripts/        Windows setup, scheduled task and run helpers
```

## Development

```bash
pip install -e ".[dev]"
python -m playwright install chromium
pytest            # browser tests are skipped if Chromium isn't installed
ruff check . && ruff format --check .
```

CI runs lint and tests on Ubuntu and Windows for every push.

## Notes

Please be considerate: checking every 10 minutes is plenty. This is a personal tool and isn't affiliated with York City FC or Future Ticketing.

## License

[MIT](LICENSE)
