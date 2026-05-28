#!/bin/bash

# ─────────────────────────────────────────────
#  MiTV Network — YouTube 24/7 Live Stream
# ─────────────────────────────────────────────

set -e

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/${STREAM_KEY}"

if [ -z "$STREAM_KEY" ]; then
  echo "[ERROR] STREAM_KEY is not set. Exiting."
  exit 1
fi

# ── Font path for drawtext ──
FONT_PATH="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if [ ! -f "$FONT_PATH" ]; then
  FONT_PATH="/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
fi
if [ ! -f "$FONT_PATH" ]; then
  FONT_PATH=$(fc-match --format="%{file}" "sans-bold" 2>/dev/null || echo "")
fi

echo "[INFO] Using font: $FONT_PATH"
echo "[INFO] Stream starting → $YOUTUBE_URL"

stream_video() {
  local VIDEO="$1"

  echo "[INFO] Loading playlist settings..."

  LOGO_ENABLED=$(jq -r '.logo.enabled'          playlist.json)
  LOGO_PATH=$(jq -r    '.logo.path'             playlist.json)
  LOGO_POSITION=$(jq -r '.logo.position'        playlist.json)
  LOGO_WIDTH=$(jq -r   '.logo.width'            playlist.json)

  TICKER_ENABLED=$(jq -r   '.ticker.enabled'          playlist.json)
  TICKER_HEIGHT=$(jq -r    '.ticker.height'            playlist.json)
  TICKER_BG=$(jq -r        '.ticker.background_color'  playlist.json)
  TICKER_TEXT_COLOR=$(jq -r '.ticker.text_color'       playlist.json)
  TICKER_FONT_SIZE=$(jq -r  '.ticker.font_size'        playlist.json)
  TICKER_SPEED=$(jq -r      '.ticker.speed'            playlist.json)
  TICKER_TEXT=$(jq -r       '.ticker.text'             playlist.json)

  ZOOM=$(jq -r  '.effects.zoom'        playlist.json)
  PITCH=$(jq -r '.effects.audio_pitch' playlist.json)

  # ── Logo overlay position ──
  case "$LOGO_POSITION" in
    "top-right")    POSITION="main_w-overlay_w-10:10" ;;
    "top-left")     POSITION="10:10" ;;
    "bottom-right") POSITION="main_w-overlay_w-10:main_h-overlay_h-10" ;;
    "bottom-left")  POSITION="10:main_h-overlay_h-10" ;;
    *)              POSITION="10:10" ;;
  esac

  # ── Input args ──
  INPUT_ARGS="-re -stream_loop -1 -i \"$VIDEO\""
  LOGO_INPUT=""
  MAP_VIDEO="-map [vout]"
  MAP_AUDIO="-map 0:a"

  # ── Build filter_complex ──
  FILTER=""

  if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
    LOGO_INPUT="-i \"$LOGO_PATH\""
    FILTER="[1:v]scale=${LOGO_WIDTH}:-1,format=rgba[logo];"
    FILTER+="[0:v][logo]overlay=${POSITION}[base];"
    AFTER_BASE="[base]"
  else
    FILTER="[0:v]copy[base];"
    AFTER_BASE="[base]"
  fi

  # ── Zoom effect ──
  FILTER+="${AFTER_BASE}zoompan=z=${ZOOM}:d=1:s=1920x1080,crop=1920:1080[zoomed];"
  AFTER_ZOOM="[zoomed]"

  # ── Ticker / drawtext ──
  if [ "$TICKER_ENABLED" = "true" ]; then
    # Escape special chars in ticker text for ffmpeg
    SAFE_TEXT=$(echo "$TICKER_TEXT" | sed "s/'/'\\\\''/g" | sed 's/:/\\:/g')

    FILTER+="${AFTER_ZOOM}"
    FILTER+="drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=${TICKER_BG}@0.85:t=fill,"
    if [ -n "$FONT_PATH" ] && [ -f "$FONT_PATH" ]; then
      FILTER+="drawtext=fontfile='${FONT_PATH}':text='${SAFE_TEXT}':fontcolor=${TICKER_TEXT_COLOR}:fontsize=${TICKER_FONT_SIZE}:x=w-mod(t*${TICKER_SPEED}\\,w+tw):y=h-${TICKER_HEIGHT}+10[vout]"
    else
      FILTER+="drawtext=text='${SAFE_TEXT}':fontcolor=${TICKER_TEXT_COLOR}:fontsize=${TICKER_FONT_SIZE}:x=w-mod(t*${TICKER_SPEED}\\,w+tw):y=h-${TICKER_HEIGHT}+10[vout]"
    fi
  else
    FILTER+="${AFTER_ZOOM}null[vout]"
  fi

  echo "[INFO] Streaming: $VIDEO"
  echo "[DEBUG] Filter: $FILTER"

  # ── Run FFmpeg ──
  eval ffmpeg \
    $INPUT_ARGS \
    $LOGO_INPUT \
    -filter_complex "\"$FILTER\"" \
    $MAP_VIDEO \
    $MAP_AUDIO \
    -af "asetrate=44100*${PITCH},aresample=44100" \
    -c:v libx264 \
    -preset veryfast \
    -tune zerolatency \
    -maxrate 4500k \
    -bufsize 9000k \
    -pix_fmt yuv420p \
    -g 50 \
    -c:a aac \
    -b:a 192k \
    -ar 44100 \
    -f flv \
    "\"$YOUTUBE_URL\""

  local EXIT_CODE=$?
  if [ $EXIT_CODE -ne 0 ]; then
    echo "[WARN] FFmpeg exited with code $EXIT_CODE for video: $VIDEO"
  fi
}

# ── Main Loop ──
echo "[INFO] Starting 24/7 stream loop..."

while true; do
  VIDEO_COUNT=$(jq '.videos | length' playlist.json)

  if [ "$VIDEO_COUNT" -eq 0 ]; then
    echo "[ERROR] No videos in playlist.json! Waiting 30s..."
    sleep 30
    continue
  fi

  for i in $(seq 0 $((VIDEO_COUNT - 1))); do
    VIDEO=$(jq -r ".videos[$i].url" playlist.json)

    if [ -z "$VIDEO" ] || [ "$VIDEO" = "null" ]; then
      echo "[WARN] Skipping empty video entry at index $i"
      continue
    fi

    stream_video "$VIDEO" || true

    echo "[INFO] Next video in 5s..."
    sleep 5
  done

  echo "[INFO] Playlist ended. Restarting from beginning..."
done
