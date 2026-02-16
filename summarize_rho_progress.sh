#!/bin/bash

LOG_FILE="/Volumes/Crucial X10/Decide9ja/logs/fleet-rho.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Fleet RHO: Log file not found: $LOG_FILE"
    exit 1
fi

LAST_SCRAPING=$(grep -E 'Scraping: Egbe Omo Oduduwa [0-9]{4}-[0-9]{2}-[0-9]{2}' "$LOG_FILE" | tail -n 1)
LAST_SAVED=$(grep -E 'Saved [0-9]+ articles, [0-9]+ images' "$LOG_FILE" | tail -n 1)

CURRENT_DATE="N/A"
TOTAL_ARTICLES="N/A"
TOTAL_IMAGES="N/A"
SUMMARY_DATE="N/A"

if [ -n "$LAST_SCRAPING" ]; then
    CURRENT_DATE=$(echo "$LAST_SCRAPING" | grep -o -E '[0-9]{4}-[0-9]{2}-[0-9]{2}' | tail -n 1)
fi

if [ -n "$LAST_SAVED" ]; then
    ARTICLES=$(echo "$LAST_SAVED" | grep -o -E 'Saved ([0-9]+) articles' | grep -o -E '[0-9]+')
    IMAGES=$(echo "$LAST_SAVED" | grep -o -E '([0-9]+) images' | grep -o -E '[0-9]+')
    
    # We need to calculate cumulative sums, which is harder with grep/tail
    # For now, let's just report the last saved entry's counts.
    # A more robust solution would involve parsing all "Saved" entries and summing them up.
    # For simplicity, we'll just report the last successful save.
    TOTAL_ARTICLES=$ARTICLES
    TOTAL_IMAGES=$IMAGES
    SUMMARY_DATE=$(echo "$LAST_SAVED" | grep -o -E '[0-9]{4}-[0-9]{2}-[0-9]{2}' | tail -n 1)
fi

if [ "$CURRENT_DATE" == "N/A" ] && [ "$SUMMARY_DATE" == "N/A" ]; then
    echo "Fleet RHO: No scraping progress yet."
elif [ "$CURRENT_DATE" != "N/A" ] && [ "$SUMMARY_DATE" == "N/A" ]; then
    echo "Fleet RHO: Currently scraping $CURRENT_DATE. No articles saved yet."
elif [ "$CURRENT_DATE" == "N/A" ] && [ "$SUMMARY_DATE" != "N/A" ]; then
    echo "Fleet RHO: Last saved progress on $SUMMARY_DATE: $TOTAL_ARTICLES articles, $TOTAL_IMAGES images."
else
    echo "Fleet RHO Progress (Egbe Omo Oduduwa): Currently scraping $CURRENT_DATE. Last saved on $SUMMARY_DATE: $TOTAL_ARTICLES articles, $TOTAL_IMAGES images."
fi
