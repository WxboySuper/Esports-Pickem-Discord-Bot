# PandaScore Rate Limit Audit

This document provides an audit of the application's PandaScore API usage as of the current version.

## Key Information
- **Rate Limit**: 1,000 requests per hour (resets hourly).
- **Tracking**: Implemented via `PandaScoreClient` using response headers (`X-Rate-Limit-Remaining`).
- **Warning Threshold**: configured to trigger when remaining requests drop below 200 (20%).

## Scheduled Jobs Analysis

The application uses two main scheduled jobs that consume API requests:

### 1. `perform_pandascore_sync` (Hourly Sync)
- **Schedule**: Runs every 1 hour (at the top of the hour).
- **Function**: `src.pandascore_sync.perform_pandascore_sync`
- **Actions**:
  - Fetches upcoming matches (Page 1).
  - Fetches running matches.
  - Fetches recent past matches.
- **Request Count**: ~3 requests per execution.
- **Hourly Impact**: 3 requests.

### 2. `poll_running_matches_job` (Live Polling)
- **Schedule**: Runs every 1 minute.
- **Function**: `src.pandascore_polling.poll_running_matches_job`
- **Actions**:
  - Fetches current list of running matches to detect starts/finishes and score updates.
- **Request Count**: 1 request per execution.
- **Hourly Impact**: 60 requests.

## Total Estimated Usage

| Job | Frequency | Requests/Run | Requests/Hour |
| :--- | :--- | :--- | :--- |
| Hourly Sync | 1/hour | ~3 | 3 |
| Live Polling | 1/minute | 1 | 60 |
| **Total** | | | **~63** |

**Utilization**: ~6.3% of the 1,000 requests/hour limit.

## Conclusion
The current usage is well within the rate limits. The system has significant headroom (over 900 requests/hour) to accommodate additional features or increased polling frequency if needed.

## Monitoring
Automated monitoring is now in place. Developers (admins) will receive a direct message if the remaining rate limit drops below 200 requests.
