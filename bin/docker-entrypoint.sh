#!/bin/bash
set -e

server() {
  # Recycle gunicorn workers every n-th request. See http://docs.gunicorn.org/en/stable/settings.html#max-requests for more details.
  MAX_REQUESTS=${MAX_REQUESTS:-1000}
  MAX_REQUESTS_JITTER=${MAX_REQUESTS_JITTER:-100}
  exec /usr/local/bin/gunicorn  --timeout 120 -b 0.0.0.0:5000 --name wx_bot -w${WXBOT_WORKERS:-4} wx_bot.wsgi:app --max-requests $MAX_REQUESTS --max-requests-jitter $MAX_REQUESTS_JITTER
}

case "$1" in
  server)
    shift
    server
    ;;
  *)
    exec "$@"
    ;;
esac