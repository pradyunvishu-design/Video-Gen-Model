# Using the integrated idea research

This extends the existing pipeline. No new app, paid model call, video download, upload or account is required for reference collection.

## Run locally

From the repository root:

```powershell
py -3.12 -m scripts.research_video_ideas --refresh-news
```

Without `--refresh-news`, it uses the existing source cache. Sources older than eight hours are excluded and reported as `refresh_required`. YouTube metadata is reused for six hours. `--force-youtube` bypasses that cache and consumes API quota; it is not needed for every board refresh.

Credentials remain in the existing environment `YOUTUBE_API_KEY`, or `secrets/youtube_agent_keys.env` (`YOUTUBE_API_KEY` or `YOUTUBE_DATA_API_KEY`). Do not attach secrets to a research report or commit them.

Review local files:

- `data/research/latest_ideas.md`: readable research board.
- `data/research/latest_ideas.json`: structured commissioning packet.
- `data/research/latest_sources.json`: dated source evidence.
- `data/research/youtube_ideas/current.json`: public metadata snapshot.
- `data/research/youtube_ideas/history.json`: bounded observation history, pruned on refresh.

These runtime files are local and are not included in the source-code push. If you stop using the collector, remove its cached API metadata and reports within the applicable retention period; pruning is run-driven, not a background deletion service.

## Existing n8n / worker integration

`refresh_sources` now builds the board automatically. Both existing weekly planners receive fresh, evidence-ready ideas. Restart a running worker to load the new code. This task has not edited the remote n8n instance or enabled a new schedule.

For a research-only refresh, use the existing authenticated `POST /jobs`:

```json
{
  "stage": "research_video_ideas",
  "payload": {"force_youtube": false},
  "idempotency_key": "idea-research-YYYY-MM-DD-HH"
}
```

Set the existing worker bearer credential in n8n. Use a new idempotency key per scheduled window; retry the same window with its original key. Poll the existing job-status endpoint. The job returns local board paths, public-data availability, source freshness and analytics-permission status. It does not render or publish.

## Analytics-permission gate

`configs/youtube_idea_radar.json` defaults to:

```json
"derived_metrics_permission": {"status": "unconfirmed", "approval_reference": ""}
```

Keep this default until the API project has the applicable [YouTube analytics amendment/permission](https://developers.google.com/youtube/terms/derived-metrics-policy). Record a non-secret reference to that real approval, not an invented consent record, before setting `status` to `approved`. This configuration is an operator attestation, not an automatic verification with Google.

Without confirmed permission: raw reference counts and links are shown for human review; no API-derived momentum, outlier, topic or composite score enters production. Non-YouTube news scoring still works. With permission: fixture-tested channel-relative ranking and matched-source enrichment become eligible. Neither mode guarantees views.

## Verification

```powershell
py -3.12 -m pytest tests/test_idea_radar.py tests/test_youtube_radar.py tests/test_idea_radar_integration.py tests/test_weekly_news.py tests/test_editorial.py tests/test_worker_api.py -q -p no:cacheprovider --basetemp="$env:TEMP\idea-radar-tests"
```

Use a fresh temporary directory if Windows denies reuse. Mocked tests make no network or paid-provider requests. Live collection and board generation were also exercised, but new real weekly scripts, audio, video renders and owner Analytics were not run in this task.
