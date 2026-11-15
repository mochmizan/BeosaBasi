#!/bin/bash
for i in $(seq 1 24); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18082/healthz)
  if [ "$CODE" = 200 ]; then break; fi
  sleep 5
done
echo "CODE=$CODE"
curl -s http://127.0.0.1:18082/healthz; echo
curl -s -o /dev/null -w 'metrics:%{http_code}\n' \
  http://127.0.0.1:18082/api/admin/metrics || true
