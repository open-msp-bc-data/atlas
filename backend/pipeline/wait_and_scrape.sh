#!/bin/bash
# Poll CPSBC until rate limit lifts, then start scraping from scratch.

URL="https://www.cpsbc.ca/public/registrant-directory"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
INTERVAL=300  # check every 5 minutes

echo "Polling $URL every ${INTERVAL}s until rate limit lifts..."
while true; do
    STATUS=$(curl -sI -A "$UA" "$URL" -o /dev/null -w "%{http_code}")
    echo "$(date '+%Y-%m-%d %H:%M:%S') — HTTP $STATUS"
    if [ "$STATUS" = "200" ]; then
        echo "Site is back! Starting scraper..."
        cd "$(dirname "$0")/../.." && cd backend
        python -m pipeline.scrape_cpsbc
        break
    fi
    sleep $INTERVAL
done
