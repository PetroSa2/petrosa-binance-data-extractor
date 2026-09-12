# MySQL Klines Retention

## Background

`db/mysql_adapter.py` implements `delete_range()`, but until
[#282](https://github.com/PetroSa2/petrosa-binance-data-extractor/issues/282)
it had zero call sites anywhere in this repo. MySQL klines tables
(`klines_m1`, `klines_m5`, `klines_h1`, ...) grew unbounded, while the
deployed gap-filler CronJob keeps writing to them with a 3000-day
`--max-gap-size-days` window.

The MongoDB path has a separate pruning mechanism: petrosa-data-manager's
`klines-retention` CronJob
(`petrosa_k8s/k8s/data-extractor/klines-retention-cronjob.yaml`), which only
targets `MONGODB_URL`. It has no MySQL counterpart.

## Mechanism

`jobs/klines_retention.py` is the MySQL counterpart. It deletes klines rows
older than a configurable retention window, per interval/table, via the
existing `BaseAdapter.delete_range()` contract.

```bash
# Prune all supported periods, keep 180 days (default)
python -m jobs.klines_retention

# Prune a subset of periods with a shorter window
python -m jobs.klines_retention --periods 1m,5m,15m --retention-days 90

# Report what would be deleted without deleting anything
python -m jobs.klines_retention --retention-days 90 --dry-run
```

Configuration:

- `--retention-days` (env `KLINES_RETENTION_DAYS`, default `180`)
- `--periods` (default: all of `constants.SUPPORTED_INTERVALS`)
- `--db-adapter` / `--db-uri` (defaults to `constants.MYSQL_URI`)

A failure pruning one table (e.g. a table that doesn't exist yet for a
period that has never been backfilled) is logged and does not abort the
run for the remaining tables; the job exits non-zero if any table failed.

## Scope of this change

This repo owns the *mechanism* (the script + its tests). Wiring it into a
scheduled Kubernetes `CronJob` is a `petrosa_k8s` manifest change — a
separate, cross-repo follow-up, consistent with how the MongoDB retention
job is defined in `petrosa_k8s`, not in the service repo that writes the
data. Until that CronJob exists, run this script manually or via any
external scheduler pointed at the same image/entrypoint as the other
`jobs/extract_klines_*` scripts.

## Known limitation

`adapters/data_manager_adapter.py` (the production write path for the
Data Manager service) does not implement `delete_range`/`query_range`/
`get_record_count` yet, so this job only supports the direct
`mysql`/`mariadb` adapters today. That gap is tracked separately from
#282 and is not addressed by this change.
