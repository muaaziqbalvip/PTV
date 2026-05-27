#!/bin/bash

# ╔══════════════════════════════════════════════════╗
# ║   MiTV Network — 24/7 YouTube Live Stream       ║
# ║   Upgraded: Logo Shine + Fast Encode + Stable   ║
# ╚══════════════════════════════════════════════════╝

set -euo pipefail

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/${STREAM_KEY}"
PLAYLIST="playlist.json"
LOGFILE="stream.log"
FONT_PATH="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

echo "======================================"
echo "  MiTV 24/7 Live Stream Starting..."
echo "  $(date)"
echo "======================================"

# ── Download / Prepare Logo ──────────────────────────
LOGO_PATH=$(jq -r '.logo.path' "$PLAYLIST")

if [[ "$LOGO_PATH" == http* ]]; then
  echo "[LOGO] Downloading from URL..."
  wget -q -O /tmp/logo_raw.png "$LOGO_PATH"
  LOGO_PATH="/tmp/logo_raw.png"
fi

# Pre-process logo: add white glow border for shining base
LOGO_PROCESSED="/tmp/logo_ready.png"
if command -v convert &>/dev/null; then
  # ImageMagick: add soft white halo glow around logo
  convert "$LOGO_PATH" \
    \( +clone -alpha extract \
       -morphology Dilate Disk:8 \
       -blur 0x4 \
       -level 0%,50% \
    \) \
    -compose Screen -composite \
    "$LOGO_PROCESSED" 2>/dev/null && echo "[LOGO] Glow pre-processed OK" \
  || cp "$LOGO_PATH" "$LOGO_PROCESSED"
else
  cp "$LOGO_PATH" "$LOGO_PROCESSED"
fi

LOGO_PATH="$LOGO_PROCESSED"

# ── Main Stream Loop ─────────────────────────────────
FAIL_COUNT=0
MAX_FAILS=5

while true; do

  mapfile -t VIDEOS < <(jq -r '.videos[].url' "$PLAYLIST")

  for VIDEO in "${VIDEOS[@]}"; do

    # Read config fresh each iteration (hot-reload support)
    LOGO_ENABLED=$(jq -r '.logo.enabled'            "$PLAYLIST")
    LOGO_WIDTH=$(jq -r '.logo.width'                "$PLAYLIST")
    LOGO_POSITION=$(jq -r '.logo.position'          "$PLAYLIST")

    TICKER_ENABLED=$(jq -r '.ticker.enabled'        "$PLAYLIST")
    TICKER_HEIGHT=$(jq -r '.ticker.height'          "$PLAYLIST")
    TICKER_BG=$(jq -r '.ticker.background_color'    "$PLAYLIST")
    TICKER_FG=$(jq -r '.ticker.text_color'          "$PLAYLIST")
    TICKER_SIZE=$(jq -r '.ticker.font_size'         "$PLAYLIST")
    TICKER_SPEED=$(jq -r '.ticker.speed'            "$PLAYLIST")
    TICKER_TEXT=$(jq -r '.ticker.text'              "$PLAYLIST")

    ZOOM=$(jq -r '.effects.zoom'                    "$PLAYLIST")
    PITCH=$(jq -r '.effects.audio_pitch'            "$PLAYLIST")

    # ── Logo Position ──
    case "$LOGO_POSITION" in
      "top-right")    OVR="main_w-overlay_w-18:18" ;;
      "top-left")     OVR="18:18" ;;
      "bottom-right") OVR="main_w-overlay_w-18:main_h-overlay_h-18" ;;
      "bottom-left")  OVR="18:main_h-overlay_h-18" ;;
      *)              OVR="main_w-overlay_w-18:18" ;;
    esac

    # ── Build filter_complex ──────────────────────────
    # Logo shining animation using lut + sine wave brightness pulse
    # sin(2*PI*t * speed) oscillates between 0 and 1 → creates glow pulse
    SHINE_SPEED="1.2"   # pulses per second
    SHINE_MIN="0.75"    # minimum brightness (0.0–1.0)
    SHINE_MAX="1.0"     # max brightness at peak shine

    FC=""
    INPUTS=(-re -stream_loop -1 -i "$VIDEO")

    if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
      INPUTS+=(-i "$LOGO_PATH")

      # Scale logo → apply shine pulse via lut (eq brightness) using geq
      # geq applies per-pixel expression; sine oscillation on luma channel
      FC="[1:v]scale=${LOGO_WIDTH}:-1,"
      FC+="geq="
      FC+="r='r(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="g='g(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="b='b(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="a='alpha(X,Y)'"
      FC+="[logo_shine];"

      # White flash ring effect (optional shimmer overlay)
      # Composite shining logo onto video
      FC+="[0:v][logo_shine]overlay=${OVR}:format=auto[with_logo];"
      BASE="[with_logo]"
    else
      BASE="[0:v]"
    fi

    # Zoom + crop (subtle cinematic zoom)
    FC+="${BASE}scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"

    # Ticker bar
    if [ "$TICKER_ENABLED" = "true" ]; then
      SAFE_TEXT=$(echo "$TICKER_TEXT" | sed "s/[:\\\\':]/\\\\&/g; s/%/%%/g")
      # Gradient-style ticker using two drawbox layers
      FC+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=black@0.6:t=fill"
      FC+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=3:color=00ff99@1.0:t=fill"
      FC+=",drawtext="
      FC+="fontfile='${FONT_PATH}':"
      FC+="text='${SAFE_TEXT} ★ ${SAFE_TEXT} ★ ${SAFE_TEXT}':"
      FC+="fontcolor=${TICKER_FG}:"
      FC+="fontsize=${TICKER_SIZE}:"
      FC+="x=w-mod(${TICKER_SPEED}*t\\,w+tw):"
      FC+="y=h-${TICKER_HEIGHT}+10:"
      FC+="shadowcolor=black@0.8:shadowx=1:shadowy=1"
    fi

    FC+="[vout]"

    # ── Map flags ──
    MAP_V="-map [vout]"
    MAP_A="-map 0:a?"   # '?' = don't fail if no audio track

    echo ""
    echo "▶ Streaming: $VIDEO"
    echo "  $(date)"

    # ── FFmpeg Command ─────────────────────────────────
    # Speed optimizations:
    #  -preset ultrafast   → lowest CPU, fastest encode
    #  -tune zerolatency   → minimizes buffering for live
    #  -threads 0          → auto-detect all CPU cores
    #  -fflags +genpts+discardcorrupt → handle corrupt frames
    #  -err_detect ignore_err → skip bad packets
    #  -probesize 5M / -analyzeduration 5M → fast source probe

    ffmpeg \
      -hide_banner \
      -loglevel warning \
      -stats \
      -fflags +genpts+discardcorrupt \
      -err_detect ignore_err \
      -probesize 5M \
      -analyzeduration 5M \
      "${INPUTS[@]}" \
      -filter_complex "$FC" \
      $MAP_V \
      $MAP_A \
      -af "asetrate=44100*${PITCH},aresample=44100,volume=1.2,loudnorm" \
      -c:v libx264 \
      -preset ultrafast \
      -tune zerolatency \
      -profile:v baseline \
      -level 4.1 \
      -b:v 4000k \
      -maxrate 4500k \
      -bufsize 8000k \
      -pix_fmt yuv420p \
      -g 50 \
      -keyint_min 25 \
      -sc_threshold 0 \
      -threads 0 \
      -c:a aac \
      -b:a 192k \
      -ar 44100 \
      -ac 2 \
      -f flv \
      -flvflags no_duration_filesize \
      "$YOUTUBE_URL" \
      2>>"$LOGFILE" \
    && FAIL_COUNT=0 \
    || {
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "⚠️  FFmpeg failed (attempt $FAIL_COUNT/$MAX_FAILS)"
        if [ "$FAIL_COUNT" -ge "$MAX_FAILS" ]; then
          echo "❌ Too many failures. Waiting 60s before retry..."
          sleep 60
          FAIL_COUNT=0
        fi
      }

    echo "⏭ Next video in 3s..."
    sleep 3

  done

  echo ""
  echo "🔁 Playlist complete — restarting loop"
  sleep 2

done
