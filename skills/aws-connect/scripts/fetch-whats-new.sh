#!/usr/bin/env bash
# Fetch Amazon Connect announcements from the AWS "What's New" directory API, newest first.
#
# Usage: fetch-whats-new.sh [SINCE_YYYY-MM-DD] [MAX_ITEMS]
#   SINCE_YYYY-MM-DD  only print announcements posted on/after this date (default: all)
#   MAX_ITEMS         cap on printed announcements (default: 100)
#
# Output: markdown bullets:  - **YYYY-MM-DD** — headline\n  <url>
# Requires: curl, jq
set -euo pipefail

SINCE="${1:-2000-01-01}"
MAX="${2:-100}"
API='https://aws.amazon.com/api/dirs/items/search'
TAG='whats-new%23general-products%23amazon-connect'

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

for page in 0 1 2 3 4; do
  url="${API}?item.directoryId=whats-new&sort_by=item.additionalFields.postDateTime&sort_order=desc&size=100&page=${page}&item.locale=en_US&tags.id=${TAG}"
  if ! resp="$(curl -sf "$url")"; then
    echo "WARN: What's New API request failed on page ${page}" >&2
    break
  fi
  n="$(jq '.items | length' <<<"$resp")"
  if [ "$n" -eq 0 ]; then break; fi

  jq -r --arg since "$SINCE" '
    .items[].item.additionalFields
    | select((.postDateTime // "1970-01-01")[0:10] >= $since)
    | "- **\(.postDateTime[0:10])** — \(.headline)\n  <https://aws.amazon.com\(.headlineUrl)>"
  ' <<<"$resp" >>"$tmp"

  oldest="$(jq -r '.items[-1].item.additionalFields.postDateTime[0:10]' <<<"$resp")"
  if [ "$oldest" \< "$SINCE" ]; then break; fi
done

if [ ! -s "$tmp" ]; then
  echo "No Amazon Connect announcements found since ${SINCE}." >&2
  exit 0
fi

# each entry is 2 lines
head -n "$((MAX * 2))" "$tmp"
