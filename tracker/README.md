# Bayesian daily tracker

Tracks **sleep, nicotine, porn, reading, expenses, and income**, one row per
day in `data/daily.csv`, and rebuilds `report.md` with Bayesian estimates:

- **Nicotine / porn** — Beta-Bernoulli posterior with exponential recency
  weighting (half-life 21 days), so the "current use rate" follows behavior
  change instead of averaging your whole history. Trend = P(last-14-days
  rate < baseline rate), plus your current clean streak.
- **Sleep / reading / expenses / income** — Normal model with unknown mean
  and variance (Normal-Inverse-Gamma). Reports the credible interval for
  your true daily average, the "normal single-day range" (posterior
  predictive), trend vs baseline, and flags anomalous days.
- **Interaction** — once there's enough overlapping data: P(habit | short
  sleep) vs P(habit | decent sleep).

## Automation (the point)

Three input paths, so daily manual entry is mostly eliminated:

| Input | How | Effort |
|---|---|---|
| Sleep | Oura API, pulled daily by GitHub Actions | zero after setup |
| Expenses / income | SimpleFIN Bridge (or Plaid), pulled daily | zero after setup |
| Nicotine / porn / reading | "Tracker quick log" workflow from the GitHub mobile app | ~2 taps |

### 1. Oura (sleep)

1. Go to <https://cloud.ouraring.com/personal-access-tokens> and create a
   personal access token.
2. In this repo: **Settings → Secrets and variables → Actions → New
   repository secret**, name `OURA_TOKEN`, paste the token.

### 2. Banking (expenses / income)

**Plaid:**

1. Sign up at <https://dashboard.plaid.com> (free account; Transactions
   in Production is pay-as-you-go with a small monthly fee per connected
   bank). Grab your **client_id** and **Production secret** from
   Developers → Keys.
2. On your own computer, connect your bank with the included helper
   (it runs Plaid's bank-login window locally and prints the token):

   ```bash
   pip install requests
   python tracker/connectors/plaid_setup.py --client-id <ID> --secret <SECRET>
   ```

3. Add `PLAID_CLIENT_ID`, `PLAID_SECRET`, and the printed
   `PLAID_ACCESS_TOKEN` as repo secrets.

**Alternative: SimpleFIN Bridge** (~$1.50/mo, simpler and made for
personal use): sign up at <https://bridge.simplefin.org>, connect your
bank, create a setup token, exchange it once with
`python tracker/track.py claim-simplefin <setup-token>`, and save the
printed URL as the `SIMPLEFIN_ACCESS_URL` repo secret (it's shown once —
it can't be re-claimed).

Money flow is aggregated per day: total outflow → `expenses`, total
inflow → `income`.

### 3. Daily sync

`.github/workflows/tracker-daily.yml` runs at 12:00 UTC daily: fetches
Oura + bank for the last 7 days (so late-posting transactions and
re-synced sleep self-heal), rebuilds the report, commits. Connectors whose
secrets aren't set are skipped, so you can enable them one at a time.

First run: **Actions → Tracker daily sync → Run workflow** with days = 90
to backfill history — the models are useful immediately instead of after
weeks of logging.

### 4. Quick log (the non-automatable bits)

From the GitHub mobile app: **Actions → Tracker quick log → Run
workflow** — two dropdowns (nicotine/porn) defaulting to "no", optional
reading minutes and notes. Under 10 seconds. It commits the entry and
rebuilds the report.

## Local / manual use

```bash
pip install -r tracker/requirements.txt
python tracker/track.py log --nicotine n --porn n --reading 25
python tracker/track.py fetch --days 90     # needs env vars set locally
python tracker/track.py report
```

Manual `log` values override fetched ones for the same day (useful for
correcting a bad Oura night or a cash purchase).

## Privacy note

The data in `data/daily.csv` is sensitive. Keep this repository
**private**. Secrets (Oura token, bank access URL) live only in GitHub
Actions secrets, never in the repo.
