# Gap Filler — MongoDB `candles_*` Dual-Write (Operator Guide)

**Issue:** [PetroSa2/petrosa-binance-data-extractor#300](https://github.com/PetroSa2/petrosa-binance-data-extractor/issues/300)
**Status:** shipped, **disabled by default**
**Applies to:** `jobs/extract_klines_gap_filler.py`

---

## 1. Why this exists

`extract_klines_gap_filler` historically repaired gaps in the **MySQL `klines_*`
tables only**. The execution read path no longer reads from there: since
[petrosa-data-manager#275](https://github.com/PetroSa2/petrosa-data-manager/issues/275)
strategy consumers (`petrosa-bot-ta-analysis`) are served candles from the
MongoDB `candles_{SYMBOL}_{timeframe}` collections.

Net effect before this change: a gap-filler run could report success, MySQL
would be complete, and the analytics calculators would still fail with
"insufficient data" because the Mongo candle window was still short.

This feature lets the gap filler **mirror** every gap chunk it repairs into the
corresponding `candles_*` collection.

---

## 2. Safety model (read before enabling)

The Mongo `candles_*` namespace has caused four Atlas M0 quota incidents. The
standing rule from
[petrosa-data-manager#274](https://github.com/PetroSa2/petrosa-data-manager/issues/274)
/ [#287](https://github.com/PetroSa2/petrosa-data-manager/issues/287) is:

> Never write to Mongo without a **bound** and an **off-flag**.

This implementation honours both:

| Guarantee | How |
|---|---|
| **Off by default** | `CANDLES_DUAL_WRITE_ENABLED=false`. Nothing changes unless you opt in. |
| **Hard bound** | `CANDLES_DUAL_WRITE_MAX_RECORDS_PER_RUN` caps candle documents **per process**, shared across all worker threads. When the budget is exhausted the job keeps filling MySQL and skips the mirror. |
| **Idempotent** | `petrosa-data-manager` derives `_id = "{symbol}_{timestamp_ms}"` and inserts with `ordered=False`. Re-running is a no-op, not a duplicate. |
| **Non-destructive** | The mirror runs **after** the primary write and outside its retry envelope. A Mongo failure is logged and counted; it never fails or re-drives a successful MySQL repair. |
| **Self-limiting downstream** | `data_manager/maintenance/candles_retention.py` trims each collection to the newest 400 candles. |

---

## 3. Configuration

| Env var | Default | Meaning |
|---|---|---|
| `CANDLES_DUAL_WRITE_ENABLED` | `false` | Master off-switch. |
| `CANDLES_DUAL_WRITE_MAX_RECORDS_PER_RUN` | `200000` | Hard ceiling on candle documents mirrored per process. |
| `CANDLES_DUAL_WRITE_DATABASE` | `mongodb` | Data Manager `database` routing value. |
| `CANDLES_COLLECTION_PREFIX` | `candles` | Collection prefix. Must match `data_manager.db.repositories.candle_repository.mongo_collection_name`. |

CLI flags override the environment:

```bash
# Enable for a single run
python -m jobs.extract_klines_gap_filler \
    --period 5m --db-adapter data_manager \
    --candles-dual-write --candles-max-records 50000

# Force-disable even if the env var is on (kill-switch for one run)
python -m jobs.extract_klines_gap_filler --period 5m --no-candles-dual-write
```

`--candles-dual-write` and `--no-candles-dual-write` are mutually exclusive.
When neither is passed, `CANDLES_DUAL_WRITE_ENABLED` decides.

Collection naming is `candles_{SYMBOL}_{period}`, e.g. `--period 5m` for
`BTCUSDT` writes `candles_BTCUSDT_5m`.

---

## 4. Observability

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `binance_extractor_gaps_filled_mongodb_total` | counter | `symbol`, `interval` | Gap chunks successfully mirrored into `candles_*`. |
| `binance_extractor_candles_written_mongodb_total` | counter | `symbol`, `interval` | Candle documents actually written (duplicates are excluded by the data-manager insert). |

These two are intentionally **flat Prometheus-style names**, unlike the dotted
`extractor.*` OTel names used elsewhere in this service — operator dashboards
reference them verbatim. The exception is documented in
`tests/test_metrics.py::TestMetricsNaming`.

The run summary also logs, when dual-write is on:

```
🍃 MongoDB candle gaps filled: <n>
🍃 MongoDB candles written: <n> (budget remaining: <n>)
⚠️  Candles dropped over budget: <n>     # only when the bound was hit
```

The job's result dict gains `candles_dual_write_enabled`,
`total_mongodb_gaps_filled`, `total_candles_written` and
`candles_dropped_over_budget`.

### What to alert on

- `binance_extractor_gaps_filled_mongodb_total` flat at 0 while
  `extractor.data_gaps.total` is rising → the mirror is off or failing.
- `Candles dropped over budget` non-zero on a steady-state run → the budget is
  too small for the backlog; raise it deliberately rather than removing it.

---

## 5. Rollout runbook

Roll out **one timeframe at a time**, smallest backlog first.

1. **Dry check the blast radius.** Estimate candles per run:
   `symbols × gap_minutes ÷ period_minutes`. Set
   `--candles-max-records` to roughly 2× that, never "unlimited".
2. **Manual run, one period.** Run the job by hand with
   `--candles-dual-write` and a small `--candles-max-records` (e.g. `5000`).
   Confirm `binance_extractor_gaps_filled_mongodb_total` increments and the
   target collection grows.
3. **Verify the read path.** Query
   `GET /data/candles/readiness` on `petrosa-data-manager` for the pair and
   timeframe you just filled — it must report ready (depth ≥ 400 and fresh).
4. **Enable on one CronJob** by adding `--candles-dual-write` to its `args` and
   `CANDLES_DUAL_WRITE_MAX_RECORDS_PER_RUN` to its `env`.
5. **Watch one full cycle** before enabling the remaining timeframes.
6. **Rollback** is a single manifest edit: remove `--candles-dual-write` (or
   add `--no-candles-dual-write`). No data migration is needed — the mirror
   only ever adds documents, and retention trims them.

---

## 6. Deployment: CronJob changes required in `petrosa_k8s`

> **Scope note.** The CronJob manifests live in the GitOps repo
> `PetroSa2/petrosa_k8s` (`k8s/data-extractor/klines-gap-filler-cronjob.yaml`),
> **not** in this repository. Enabling dual-write and changing the schedule is
> therefore a separate, separately-reviewed GitOps PR, deliberately gated on
> steps 1–3 of the runbook above. Shipping the schedule change together with a
> feature that is still flagged off would have enabled nothing and only
> increased CronJob frequency.

The five gap-filler CronJobs currently run **once nightly** each
(`0 2`, `15 2`, `30 2`, `45 2`, `0 3`). Nightly is too coarse for the execution
read path: a gap opened at 03:00 starves the calculators for ~23 hours.

Target schedule — every 6 hours, keeping the existing 15-minute stagger so the
five jobs never overlap (`concurrencyPolicy: Forbid` is per-CronJob, not
global):

| CronJob | Current | Target |
|---|---|---|
| `binance-klines-gap-filler-m5` | `0 2 * * *` | `0 */6 * * *` |
| `binance-klines-gap-filler-m15` | `15 2 * * *` | `15 */6 * * *` |
| `binance-klines-gap-filler-m30` | `30 2 * * *` | `30 */6 * * *` |
| `binance-klines-gap-filler-h1` | `45 2 * * *` | `45 */6 * * *` |
| `binance-klines-gap-filler-d1` | `0 3 * * *` | `0 3 * * *` (daily candles — nightly is correct) |

Per-container delta for each of the four intraday CronJobs:

```yaml
            args:
            - --period=5m               # unchanged per job
            - --max-workers=3
            - --db-adapter=data_manager # required: the mirror rides the Data Manager gateway
            - --weekly-chunk-days=7
            - --max-gap-size-days=3000
            - --candles-dual-write      # NEW (#300)
            env:
            - name: CANDLES_DUAL_WRITE_MAX_RECORDS_PER_RUN
              value: "50000"            # NEW (#300) — bound, tune per runbook step 1
```

Note `--db-adapter=data_manager`: the manifests still pass
`--db-adapter=mysql`, which
[#294](https://github.com/PetroSa2/petrosa-binance-data-extractor/issues/294)
already deprecated with a runtime warning. The mirror needs the Data Manager
gateway, so that migration is a prerequisite for enabling dual-write.

Run duration is currently 47s–3m2s against `activeDeadlineSeconds: 3600`
(petrosa_k8s#1012), so a 6-hourly schedule has ample margin and needs no
resource change.

---

## 7. Related

- [#294](https://github.com/PetroSa2/petrosa-binance-data-extractor/issues/294) — gap filler migrated off the direct MySQL adapter onto `DataManagerAdapter` (the seam this builds on).
- [#317](https://github.com/PetroSa2/petrosa-binance-data-extractor/issues/317) — parent: unified candle gap filling pipeline.
- [petrosa-data-manager#275](https://github.com/PetroSa2/petrosa-data-manager/issues/275) — candle warm-up backfill, `candles_*` namespace, dual-write mirror.
- [petrosa-data-manager#274](https://github.com/PetroSa2/petrosa-data-manager/issues/274) / [#287](https://github.com/PetroSa2/petrosa-data-manager/issues/287) — capped-count retention, the bound-and-off-flag rule.
