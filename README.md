# YY yfinance collector for GitHub Actions

This repository runs only the **market-data collection / financial-ratio preparation** part outside ChatGPT.  
YY Weekly keeps the primary screen decision and Yanagishita Agent secondary selection.

## Data flow

1. `input.lst` contains TSE security codes.
2. GitHub Actions runs at **Saturday 04:00 JST** (`Friday 19:00 UTC`).
3. The list is split into 8 shards; at most 4 run concurrently.
4. Each shard calls the existing yfinance-based analyzer.
5. Shards are merged and validated.
6. The newest snapshot is committed to:
   - `data/latest/yy_market_data_latest.csv`
   - `data/latest/yy_market_data_latest.meta.json`
7. YY Weekly (Saturday 08:00 JST) reads the latest snapshot and performs:
   - ROIC / operating-margin / FCF-yield high-or-rising primary screen
   - existing Bucket matching
   - latest Active Yanagishita Agent secondary selection

## Repository layout

```text
.github/workflows/yy-yfinance-weekly.yml
src/fcf5y_roic_core.py
scripts/collect_shard.py
scripts/merge_shards.py
input.lst
requirements.txt
data/latest/
```

## First setup

1. Create a GitHub repository and copy these files into it.
2. In **Settings > Actions > General > Workflow permissions**, allow **Read and write permissions** if the repository policy does not already allow the workflow's `contents: write` permission.
3. Open **Actions > YY yfinance weekly collection > Run workflow** once manually.
4. Confirm that `data/latest/yy_market_data_latest.csv` and `.meta.json` are committed.
5. For the easiest YY Weekly integration, use a public repository (the data is derived from public market data). If the repo is private, YY Weekly needs an authenticated GitHub connector instead of ordinary web retrieval.

## Failure policy

- Individual tickers may fail without killing a shard.
- The merged run fails if the total row count does not match `input.lst`.
- The merged run fails if more than 25% of rows are acquisition errors.
- On a failed run, the previously committed `data/latest` remains untouched, so YY Weekly can detect stale data from the metadata timestamp rather than consuming a partial snapshot.

## Current ROIC definition

`ROIC = NOPAT / (Equity + Short-term interest-bearing debt + Long-term interest-bearing debt - Cash & cash equivalents)`

Cash uses the existing yfinance fallback keys in the core analyzer.
