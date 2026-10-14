#!/bin/bash
# felsig control script.
#   ./felsig.sh setup        install Python deps, create config.toml and .env
#   ./felsig.sh voice        install whisper.cpp + download the transcription model (~550MB)
#   ./felsig.sh run          run the bot in this terminal (for testing)
#   ./felsig.sh start|stop|restart|status|logs   manage the always-on launchd service
#   ./felsig.sh permissions  open Full Disk Access settings with the Python path on your clipboard
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"

LABEL="com.vviggyy.felsig"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/felsig.log"
MODEL="ggml-large-v3-turbo-q5_0.bin"
MODEL_DIR="$HOME/.felsig/models"
# venv lives outside ~/Desktop: launchd can't reliably exec from TCC-protected folders
export UV_PROJECT_ENVIRONMENT="$HOME/.felsig/venv"
PY="$UV_PROJECT_ENVIRONMENT/bin/python"

real_python() { "$PY" -c 'import os, sys; print(os.path.realpath(sys.executable))'; }

case "${1:-}" in
setup)
    uv sync
    [ -f config.toml ] || cp config.example.toml config.toml
    [ -f .env ] || cp .env.example .env
    echo "Next: put your bot token in .env, check config.toml, then ./felsig.sh run"
    ;;
voice)
    command -v whisper-cli >/dev/null || brew install whisper.cpp
    mkdir -p "$MODEL_DIR"
    if [ ! -f "$MODEL_DIR/$MODEL" ]; then
        curl -L --fail -C - -o "$MODEL_DIR/$MODEL.part" \
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL"
        mv "$MODEL_DIR/$MODEL.part" "$MODEL_DIR/$MODEL"
    fi
    echo "Voice ready: $MODEL_DIR/$MODEL"
    ;;
run)
    exec "$PY" "$DIR/bot.py"
    ;;
start)
    mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
    cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$DIR/bot.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONUNBUFFERED</key><string>1</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$LOG</string>
    <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$UID" "$PLIST"
    echo "Started. It restarts on crash and at login. Logs: ./felsig.sh logs"
    echo "If the log shows 'Operation not permitted', run ./felsig.sh permissions"
    ;;
stop)
    launchctl bootout "gui/$UID/$LABEL" && echo "Stopped."
    ;;
restart)
    launchctl kickstart -k "gui/$UID/$LABEL" && echo "Restarted."
    ;;
status)
    launchctl print "gui/$UID/$LABEL" | grep -E '^\s*(state|pid|last exit code) =' || echo "Not running."
    ;;
logs)
    tail -n 50 -f "$LOG"
    ;;
permissions)
    real_python | tr -d '\n' | pbcopy
    echo "Python path copied to clipboard: $(real_python)"
    echo "In Full Disk Access: click +, press Cmd+Shift+G, paste, Open. Then ./felsig.sh restart"
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
    ;;
*)
    sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
