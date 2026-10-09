# Delisted-Stock-Scraper

A legacy script (November 2025) that lists SEC Form 25 filings, the notices that remove a security from
an exchange, for NYSE, NASDAQ and AMEX tickers filed from 2015 to 2024, with an approximate market cap at
filing. It was an early part of Paramo's data work and has been superseded by Paramo's internal pipeline.

## Status: it does not produce a delisted universe

The point of a delisted-stock list is to correct survivorship bias. A backtest that only uses stocks
still trading today never holds the ones that went bankrupt, failed or were bought out, so its results look
better than they would have been. A correct list has to include exactly those companies.

A review on 2026-10-09 found that this script mostly misses them:

- **The company list is today's.** It enumerates companies from SEC's `company_tickers.json`, which maps
  *current* tickers to companies. Most companies that died or were acquired are no longer in it, so their
  Form 25 filings are never looked at.
- **The exchange filter is today's.** Each ticker's exchange comes from Yahoo Finance's current data, and a
  ticker with no exchange is skipped. That is the usual state of a delisted ticker.
- **The output confirms it.** None of these well-known 2015-2024 delistings is in
  `outputs/delisted_all_2015_2024.csv`: Bed Bath & Beyond (BBBY), SVB Financial (SIVB), First Republic
  (FRC), Silvergate (SI), Twitter (TWTR), J.C. Penney (JCP), Sears Holdings (SHLD), Activision (ATVI),
  Credit Suisse (CS), Rite Aid (RAD), Tupperware (TUP) and SunPower (SPWR). Its most recent rows include
  Domino's Pizza (DPZ) and Mister Car Wash (MCW), which still trade.

What the files do hold is Form 25 filings by companies that still have a ticker: exchange transfers and
the delisting of other classes of securities. **Do not use the CSVs as a survivorship-bias correction.**
The repository stays public as the record of a survivorship-bias tool that inherited the bias it was
meant to remove.

## What the script does

1. Loads SEC's current ticker-to-CIK map (`company_tickers.json`).
2. For each company, reads the `recent` block of its EDGAR submissions and keeps forms `25` and `25-NSE`
   filed in the date range. The `recent` block holds only a company's latest filings, so an older Form 25
   of a frequent filer can be missed.
3. Keeps tickers whose current Yahoo Finance exchange maps to NYSE, NASDAQ or AMEX.
4. Estimates market cap as the last adjusted close in the 60 days up to the filing date, times the
   *current* shares outstanding. This is not point-in-time. When that fails it tries the same calculation
   over 90 days, then Yahoo's *current* market cap.
5. Writes one row per ticker (its latest Form 25), plus a small-cap file (under $2 billion) and
   symbol-only files.

Two smaller points: the `exchange` column is the ticker's exchange today, not the one it left, and a
Form 25 takes effect 10 days after it is filed, so `filing_date` is not the delisting date.

## Outputs (from the committed run)

| File | Rows |
|---|---|
| `outputs/delisted_all_2015_2024.csv` | 797 |
| `outputs/delisted_small_caps_2015_2024.csv` | 258 |
| `outputs/*_symbols_only.csv` | the same tickers, one column |

Columns: `ticker`, `company_name`, `cik`, `exchange`, `form_type`, `filing_date`, `accession_number`,
`primary_document`, `market_cap`, `market_cap_source`. In the full file, 561 market caps come from the
historical calculation, 38 are current values and 198 are missing. `verify_data.py` prints these
summaries.

## Running it

```bash
pip install requests pandas yfinance
python Delisted_Stock_Scraper.py
```

Before running, set `USER_AGENT` in `main()` to your own name and email. SEC's fair-access policy asks
for a declared contact and at most 10 requests a second, and the script waits 0.11 s between requests.
It makes one request per company in the ticker map, so a run takes a while. The `.pyproj` and `.sln`
files are Visual Studio project files and are optional.

## What a fix would take

- Enumerate Form 25 filings from EDGAR's quarterly full index, which lists every filer, including
  companies no longer in the ticker map.
- Keep common stock only, using the class of security stated in each filing.
- Take the exchange from the filing, and the ticker as of the filing date.
- Compute market cap from a point-in-time price and the shares outstanding reported before the filing.

## Data sources

SEC EDGAR, used under SEC's fair-access policy. Yahoo Finance through `yfinance`, an unofficial
library: the market caps in `outputs/` come from Yahoo data, so check Yahoo's terms before reusing them.

[antoine-savelli.com](https://antoine-savelli.com)
