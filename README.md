# Final Shorts

A simple, free-tier YouTube Shorts factory built one independently testable function at a time.

## Current
Function 01 — Topic Fetching

The Streamlit dashboard has two modes:
- **Test**: independent function testing. Currently Topic Fetcher only.
- **Live**: present but disabled during development.

Run locally:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```
