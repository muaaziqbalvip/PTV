#!/bin/bash

# ╔══════════════════════════════════════════════════╗
# ║   MiTV Network — 24/7 YouTube Live Stream       ║
# ║   UPGRADED: YouTube Live + MP4 Cast + Fast HD   ║
# ╚══════════════════════════════════════════════════╝

set -euo pipefail

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/${STREAM_KEY}"
PLAYLIST="playlist.json"
LOGFILE="stream.log"
FONT_PATH="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TEMP_DIR="/tmp/mitv_stream"
CACHE_DIR="$TEMP_DIR/cache"

mkdir -p "$TEMP_DIR" "$CACHE_DIR"

echo "======================================"
echo "  MiTV 24/7 Live Stream Starting..."
echo "  $(date)"
echo "======================================"

# ── Download / Prepare Logo ──────────────────────────
LOGO_PATH=$(jq -r '.logo.path' "$PLAYLIST")

if [[ "$LOGO_PATH" == http* ]]; then
  echo "[LOGO] Downloading from URL..."
  wget -q -O "$TEMP_DIR/logo_raw.png" "$LOGO_PATH" 2>/dev/null || {
    echo "[LOGO] Download failed, using placeholder"
  }
  LOGO_PATH="$TEMP_DIR/logo_raw.png"
fi

# Pre-process logo: add white glow using ImageMagick
LOGO_PROCESSED="$TEMP_DIR/logo_ready.png"
if command -v convert &>/dev/null && [ -f "$LOGO_PATH" ]; then
  convert "$LOGO_PATH" \
    \( +clone -alpha extract \
       -morphology Dilate Disk:8 \
       -blur 0x4 \
       -level 0%,50% \
    \) \
    -compose Screen -composite \
    "$LOGO_PROCESSED" 2>/dev/null \
  && echo "[LOGO] Glow pre-processed OK" \
  || cp "$LOGO_PATH" "$LOGO_PROCESSED" 2>/dev/null || true
else
  [ -f "$LOGO_PATH" ] && cp "$LOGO_PATH" "$LOGO_PROCESSED" || true
fi

LOGO_PATH="$LOGO_PROCESSED"

# ── Function: Get Stream URL from YouTube Live Link ──
get_youtube_stream() {
  local yt_link="$1"
  local video_id=$(echo "$yt_link" | grep -oP '(?<=v=|/)[\w-]{11}|(?<=youtu.be/)[\w-]{11}' | head -1)
  
  if [ -z "$video_id" ]; then
    return 1
  fi
  
  # Use youtube-dl / yt-dlp to get direct stream URL
  if command -v yt-dlp &>/dev/null; then
    yt-dlp -f "best[ext=mp4]" -g "$yt_link" 2>/dev/null || return 1
  elif command -v youtube-dl &>/dev/null; then
    youtube-dl -f "best[ext=mp4]" -g "$yt_link" 2>/dev/null || return 1
  else
    return 1
  fi
}

# ── Function: Convert YouTube Live to MP4 (Fast Mode) ──
youtube_to_mp4_fast() {
  local yt_link="$1"
  local output_file="$2"
  
  echo "[YOUTUBE] Converting live stream to MP4 (fast mode)..."
  
  # Use yt-dlp to capture live stream
  if command -v yt-dlp &>/dev/null; then
    yt-dlp -f "best[ext=mp4]" \
      --no-warnings \
      -o "$output_file" \
      --quiet \
      "$yt_link" 2>/dev/null && return 0
  fi
  
  return 1
}

# ── Function: Fast MP4 Re-encode (Preserve Quality) ──
optimize_mp4_for_stream() {
  local input_file="$1"
  local output_file="$2"
  
  echo "[MP4] Optimizing for streaming (fast encode)..."
  
  ffmpeg -hide_banner -loglevel warning \
    -i "$input_file" \
    -c:v libx264 \
    -preset veryfast \
    -tune zerolatency \
    -crf 23 \
    -b:v 3500k \
    -maxrate 4500k \
    -bufsize 8000k \
    -c:a aac \
    -b:a 192k \
    -ar 44100 \
    -ac 2 \
    -movflags +faststart \
    "$output_file" 2>>"$LOGFILE"
}

# ── Function: Process Video URL ──
get_video_url() {
  local input_url="$1"
  
  # Check if it's a YouTube live link
  if [[ "$input_url" == *"youtube.com/live"* ]] || [[ "$input_url" == *"youtu.be"* ]]; then
    echo "[VIDEO] YouTube Live detected, converting to MP4..."
    
    local cache_file="$CACHE_DIR/$(echo "$input_url" | md5sum | cut -d' ' -f1).mp4"
    
    if [ -f "$cache_file" ]; then
      echo "[CACHE] Using cached MP4"
      echo "$cache_file"
    else
      local temp_mp4="$TEMP_DIR/youtube_$(date +%s).mp4"
      
      if youtube_to_mp4_fast "$input_url" "$temp_mp4"; then
        optimize_mp4_for_stream "$temp_mp4" "$cache_file"
        rm -f "$temp_mp4"
        echo "$cache_file"
      else
        echo "[ERROR] Failed to convert YouTube live to MP4" >&2
        return 1
      fi
    fi
  else
    # Regular MP4/M3U link
    echo "$input_url"
  fi
}

# ── Main Stream Loop ─────────────────────────────────
FAIL_COUNT=0
MAX_FAILS=5

while true; do

  mapfile -t VIDEOS < <(jq -r '.videos[].url' "$PLAYLIST")

  for VIDEO in "${VIDEOS[@]}"; do

    # Read config fresh each iteration
    LOGO_ENABLED=$(jq -r '.logo.enabled'           "$PLAYLIST")
    LOGO_WIDTH=$(jq -r '.logo.width'               "$PLAYLIST")
    LOGO_POSITION=$(jq -r '.logo.position'         "$PLAYLIST")

    TICKER_ENABLED=$(jq -r '.ticker.enabled'       "$PLAYLIST")
    TICKER_HEIGHT=$(jq -r '.ticker.height'         "$PLAYLIST")
    TICKER_BG=$(jq -r '.ticker.background_color'   "$PLAYLIST")
    TICKER_FG=$(jq -r '.ticker.text_color'         "$PLAYLIST")
    TICKER_SIZE=$(jq -r '.ticker.font_size'        "$PLAYLIST")
    TICKER_SPEED=$(jq -r '.ticker.speed'           "$PLAYLIST")
    TICKER_TEXT=$(jq -r '.ticker.text'             "$PLAYLIST")

    ZOOM=$(jq -r '.effects.zoom'                   "$PLAYLIST")
    PITCH=$(jq -r '.effects.audio_pitch'           "$PLAYLIST")

    # ── Get actual video URL (handle YouTube Live) ──
    ACTUAL_VIDEO=$(get_video_url "$VIDEO") || {
      echo "⚠️  Could not process video URL: $VIDEO"
      sleep 5
      continue
    }

    # ── Logo Position ──
    case "$LOGO_POSITION" in
      "top-right")    OVR="main_w-overlay_w-18:18" ;;
      "top-left")     OVR="18:18" ;;
      "bottom-right") OVR="main_w-overlay_w-18:main_h-overlay_h-18" ;;
      "bottom-left")  OVR="18:main_h-overlay_h-18" ;;
      *)              OVR="main_w-overlay_w-18:18" ;;
    esac

    # ── Shine animation settings ──
    SHINE_SPEED="1.2"
    SHINE_MIN="0.72"
    SHINE_MAX="1.0"

    # ── Build filter_complex ──
    FC=""
    LOGO_INPUT_FLAG=""

    if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
      LOGO_INPUT_FLAG="-i $LOGO_PATH"

      # Scale + sine-wave brightness pulse (shine effect)
      FC="[1:v]scale=${LOGO_WIDTH}:-1,"
      FC+="geq="
      FC+="r='r(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="g='g(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="b='b(X,Y)*clip(${SHINE_MIN}+(${SHINE_MAX}-${SHINE_MIN})*0.5*(1+sin(2*3.14159*${SHINE_SPEED}*T)),0,1)':"
      FC+="a='alpha(X,Y)'"
      FC+="[logo_shine];"
      FC+="[0:v][logo_shine]overlay=${OVR}:format=auto[with_logo];"
      BASE="[with_logo]"
    else
      BASE="[0:v]"
    fi

    # Zoom + crop
    FC+="${BASE}scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"

    # Ticker
    if [ "$TICKER_ENABLED" = "true" ]; then
      SAFE_TEXT=$(printf '%s' "$TICKER_TEXT" | sed "s/[:\\\\':]/\\\\&/g; s/%/%%/g")
      FC+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=black@0.65:t=fill"
      FC+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=3:color=00ff99@1.0:t=fill"
      FC+=",drawtext=fontfile='${FONT_PATH}':text='${SAFE_TEXT}  ✦  ${SAFE_TEXT}':fontcolor=${TICKER_FG}:fontsize=${TICKER_SIZE}:x=w-mod(${TICKER_SPEED}*t\\,w+tw):y=h-${TICKER_HEIGHT}+10:shadowcolor=black@0.8:shadowx=1:shadowy=1"
    fi

    FC+="[vout]"

    echo ""
    echo "▶  Streaming: $ACTUAL_VIDEO"
    echo "   $(date)"

    # ── FFmpeg — Optimized for Speed + HD Quality ──
    ffmpeg \
      -hide_banner \
      -loglevel warning \
      -stats \
      -fflags +genpts+discardcorrupt \
      -err_detect ignore_err \
      -probesize 5M \
      -analyzeduration 5M \
      -re \
      -stream_loop -1 \
      -i "$ACTUAL_VIDEO" \
      $LOGO_INPUT_FLAG \
      -filter_complex "$FC" \
      -map "[vout]" \
      -map "0:a?" \
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
        echo "⚠️  FFmpeg error (attempt $FAIL_COUNT / $MAX_FAILS)"
        if [ "$FAIL_COUNT" -ge "$MAX_FAILS" ]; then
          echo "❌ Max failures hit. Cooling down 60s..."
          sleep 60
          FAIL_COUNT=0
        fi
      }

    echo "⏭  Next video in 3s..."
    sleep 3

  done

  echo "🔁 Playlist looped — restarting..."
  sleep 2

done
