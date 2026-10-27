# Free YouTube Channel Analytics

Final-Shorts uses Google's official YouTube Analytics API and YouTube Data API for this feature. It adds no analytics subscription or paid API provider. Google API quotas and project setup requirements still apply.

## One-time setup

1. Confirm the factory's existing YouTube authorization works and token.json exists locally.
2. Open a terminal in the Final-Shorts project folder.
3. Run the following command:

       python authorize_youtube_analytics.py

4. Sign in as the Google account that owns the target channel and approve the read-only permissions.
5. Refresh the Streamlit dashboard and choose Channel Analytics from the navigation.

This creates a separate analytics_token.json. The existing token.json used for uploads is not changed. The new token uses only yt-analytics.readonly and youtube.readonly scopes; it does not have upload/comment permission. Never share or commit either token.

## What's included

- Channel identity and lifetime totals for views, subscribers, and published videos.
- 7, 28, 90, and 365-day reporting windows.
- Views, engaged views, watch time, average view duration, subscribers gained/lost, likes, comments, and shares.
- Daily trends, top videos and traffic sources.
- CSV export for summary, daily trends and top videos.

The report ends two days before today to reduce partial-day reporting. Revenue is not requested by default because it needs a separate monetary-analytics permission.

## Troubleshooting

Ensure YouTube Analytics API and YouTube Data API v3 are enabled in the Google Cloud project used by the factory. Re-run python authorize_youtube_analytics.py if the analytics token is missing, revoked, or lacks the expected scopes. The page is read-only and does not upload, publish, or modify content.
