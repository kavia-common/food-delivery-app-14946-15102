```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

WORKSPACE="/home/kavia/workspace/code-generation/food-delivery-app-14946-15102/Review&RatingService"
cd "$WORKSPACE"

# === COMMAND: INSTALL ===
echo 'export NODE_ENV=development' | $SUDO tee /etc/profile.d/react_env.sh > /dev/null
$SUDO chmod 644 /etc/profile.d/react_env.sh

# === COMMAND: SCAFFOLD ===
# Use default template unless custom needed; comment below if changed.
if [ ! -f "$WORKSPACE/package.json" ]; then
    npx create-react-app "$WORKSPACE" --use-npm --no-install > /dev/null 2>&1
fi

# === COMMAND: DEPS ===
[ -f "$WORKSPACE/package.json" ] && npm i --no-audit --no-fund --loglevel=error --yes

# === COMMAND: BUILD ===
npm run build --if-present --silent

# === COMMAND: TEST ===
CI=true npm test -- --ci --coverage --watchAll=false --silent

# === COMMAND: START ===
# Canonical foreground launch, clean start, no PID management
BROWSER=none npm start -- --host 0.0.0.0 --port 3000

# === COMMAND: VALIDATE ===
# Start server in background, perform validation, ensure clean stop
if pgrep -f "react-scripts start" > /dev/null; then
    echo "ERROR: Dev server already running. Stop it before validation." >&2
    exit 1
fi
BROWSER=none npm start -- --host 0.0.0.0 --port 3000 > /dev/null 2>&1 &
srv_pid=$!
timeout=30
while ! resp=$(curl -sf http://localhost:3000/ 2>/dev/null); do
    sleep 1; timeout=$((timeout-1))
    if [ "$timeout" -le 0 ]; then
        echo "ERROR: React dev server not responding on port 3000 after 30s" >&2
        kill "$srv_pid" 2>/dev/null || true
        exit 1
    fi
done
# (Optional) Check for expected React content for better diagnostics
if [[ ! "$resp" =~ "<div" ]]; then
    echo "ERROR: Dev server responded but output did not match expected HTML." >&2
    kill "$srv_pid" 2>/dev/null || true
    exit 2
fi
kill "$srv_pid" 2>/dev/null || true
wait "$srv_pid" 2>/dev/null || true

# === COMMAND: STOP ===
if [ -f "$WORKSPACE/react_dev_server.pid" ]; then
    kill "$(cat "$WORKSPACE/react_dev_server.pid")" 2>/dev/null && rm -f "$WORKSPACE/react_dev_server.pid"
else
    pkill -f "react-scripts start" 2>/dev/null || true
fi
```