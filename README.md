# YCFC Ticket & News Alerts

[![CI](https://github.com/gw383/ycfc_tickets/actions/workflows/ci.yml/badge.svg)](https://github.com/gw383/ycfc_tickets/actions/workflows/ci.yml)
[![Check tickets and news](https://github.com/gw383/ycfc_tickets/actions/workflows/check.yml/badge.svg)](https://github.com/gw383/ycfc_tickets/actions/workflows/check.yml)

Get a notification on your phone the moment York City FC put a new home fixture on sale or publish a news article. It runs on GitHub every few minutes, so nothing needs to be left switched on at home.

Each notification has a headline, a short second line, the club crest as its icon, the fixture or article picture, and a button that opens the right page:

```
🎫 Tickets on sale: York City v Port Vale          📰 Ticket News | Newport County (A)
Saturday 24th October · Kick-off 3pm               Ticket News · Wed 30 Sep
League Fixture                                     [ picture ]
[ picture ]                                        [ Read article ]
[ Buy tickets ]
```

## How it works

```
GitHub Actions (about every 5 minutes)
        │
        ├─► ticket list ── the same feed the club's ticket page uses ──► fixtures on sale
        │                  (parking, hospitality and other add-ons filtered out)
        │
        ├─► news feed ──── the same feed the club's News page uses ────► latest articles
        │
        ▼
 compare with what has been seen before (saved on the repo's "state" branch)
        │
        ▼
 anything new ──► push notification to your phone via ntfy
```

Things it takes care of:

- **No duplicate alerts.** Everything it has seen is remembered, so an item that briefly drops off the site isn't announced again.
- **No spam on day one.** The first run just records what's already there.
- **Nothing is lost if a notification fails.** It's retried on the next run.
- **It tells you if it breaks.** If the club site can't be read three checks in a row you get a "needs a look" notification, and another when it's working again.

## Set it up (about 5 minutes, all in the browser)

### 1. Get the ntfy app

[ntfy](https://ntfy.sh) is a free push-notification service with no account needed. Your phone subscribes to a topic name; anything sent to that topic pops up as a notification.

1. Install **ntfy** from the App Store or Google Play.
2. Tap **+**, enter a hard-to-guess topic name (e.g. `ycfc-g7k2q9xm`) and subscribe. Anyone who knows the name can see the alerts, so don't use something obvious.
3. Allow notifications when asked. On Android, also turn off battery optimisation for ntfy so alerts arrive straight away.

### 2. Tell GitHub your topic name

Fork this repo (or use your own copy), then in the repo on GitHub:

**Settings → Secrets and variables → Actions → New repository secret**

- Name: `NTFY_TOPIC`
- Secret: the topic name from step 1

Secrets are hidden from everyone, including in the run logs, so this is safe in a public repo.

### 3. Switch it on and test it

1. Open the **Actions** tab. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
2. Pick **Check tickets and news** on the left → **Run workflow** → tick **Send a test notification** → **Run workflow**.
3. Within a minute your phone should get two notifications: the latest fixture on sale and the latest article.

That's it. From now on it checks by itself.

### Optional settings

Under **Settings → Secrets and variables → Actions → Variables** you can add:

| Variable | What it does |
|---|---|
| `NEWS_CATEGORIES` | Only notify for these news categories, comma separated, e.g. `Club News,Mens,Ticket News`. Blank means all. The club uses: Club News, Mens, Womens, Academy, Ticket News, Commercial, Events, Community, General. |
| `TICKETS_SOURCE` | `api` (default) reads the ticket feed directly. `browser` loads the page in a real browser instead: slower, but a fallback if the feed ever stops working. |

## Good to know about the schedule

- **"Every 5 minutes" is approximate.** GitHub runs scheduled jobs when it has spare capacity, so checks are usually 5 to 15 minutes apart and occasionally longer at busy times.
- **GitHub pauses schedules on quiet repos.** If a public repo has no activity for 60 days, scheduled workflows are switched off and GitHub emails you. Re-enable it from the Actions tab.
- **It's free.** GitHub Actions costs nothing for public repositories.
- **Where the memory lives.** The list of things already seen is a small file on a branch called `state`. Delete that branch to start again from a clean slate.

## Run it on your own computer

Useful for trying changes. Needs Python 3.10+.

```powershell
git clone https://github.com/gw383/ycfc_tickets.git
cd ycfc_tickets
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1    # Windows
```

<details>
<summary>macOS / Linux</summary>

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```
</details>

Put your topic name in `.env` (every option is described in [`.env.example`](.env.example)), then:

```
python -m ycfc_tickets --test-alert   # send the latest fixture and article to your phone
python -m ycfc_tickets --dry-run      # show what it finds; send and save nothing
python -m ycfc_tickets                # a real check
```

| Flag | What it does |
|---|---|
| `--dry-run` | Checks and reports, but sends nothing and doesn't save state |
| `--test-alert` | Sends the latest fixture and article as test notifications |
| `--alert-on-first-run` | Alert for everything on the very first run instead of just recording it |
| `-v` | Debug logging |

Exit codes: `0` OK, `3` the club site couldn't be read, `4` a notification failed to send.

## Troubleshooting

- **Test notification doesn't arrive.** Check the `NTFY_TOPIC` secret matches the topic in the app exactly (it's case-sensitive) and that notifications are allowed for ntfy.
- **"YCFC checker needs a look" notification.** Tap it to open the run log. Usually the club site was down or has changed. If the ticket feed keeps failing, set the `TICKETS_SOURCE` variable to `browser`.
- **No icon on iPhone.** ntfy only shows custom icons on Android. Pictures and buttons work on both.

## Project layout

```
src/ycfc_tickets/
  cli.py       command-line entry point and the check-and-notify flow
  config.py    settings from environment variables / .env
  tickets.py   fixtures on sale, from the ticket widget's feed
  news.py      latest articles, from the club's news feed
  notify.py    builds and sends the ntfy notifications
  state.py     remembers what has been seen
  http.py      small web-request helper
  parser.py    decides which ticket listings are real fixtures
  scraper.py   browser fallback (optional, needs Playwright)
tests/                        unit tests with sample feed data
.github/workflows/check.yml   the every-5-minutes schedule
.github/workflows/ci.yml      lint + tests on every push
```

## Development

```bash
pip install -e ".[dev,browser]"
python -m playwright install chromium   # only for the browser-fallback tests
pytest
ruff check . && ruff format --check .
```

## Notes

This is a personal fan project and isn't affiliated with York City FC or Future Ticketing. It makes two small requests per check to feeds the club's own website uses; please don't run it more often than every few minutes.

## License

[MIT](LICENSE)
