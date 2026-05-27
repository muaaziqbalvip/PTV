#!/bin/bash

set -e

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/${STREAM_KEY}"

# Download logo if URL is given (optional)
LOGO_PATH=$(jq -r '.logo.path' playlist.json)

if [[ "$LOGO_PATH" == http* ]]; then
  echo "Downloading logo from URL..."
  wget -q -O logo.png "$LOGO_PATH"
  LOGO_PATH="logo.png"
fi

while true; do

  # Read all video URLs into array
  mapfile -t VIDEOS < <(jq -r '.videos[].url' playlist.json)

  for VIDEO in "${VIDEOS[@]}"; do

    # --- Read config ---
    LOGO_ENABLED=$(jq -r '.logo.enabled' playlist.json)
    LOGO_WIDTH=$(jq -r '.logo.width' playlist.json)
    LOGO_POSITION=$(jq -r '.logo.position' playlist.json)

    TICKER_ENABLED=$(jq -r '.ticker.enabled' playlist.json)
    TICKER_HEIGHT=$(jq -r '.ticker.height' playlist.json)
    TICKER_BG=$(jq -r '.ticker.background_color' playlist.json)
    TICKER_TEXT_COLOR=$(jq -r '.ticker.text_color' playlist.json)
    TICKER_FONT_SIZE=$(jq -r '.ticker.font_size' playlist.json)
    TICKER_SPEED=$(jq -r '.ticker.speed' playlist.json)
    TICKER_TEXT=$(jq -r '.ticker.text' playlist.json)

    ZOOM=$(jq -r '.effects.zoom' playlist.json)
    PITCH=$(jq -r '.effects.audio_pitch' playlist.json)

    # --- Logo overlay position ---
    case "$LOGO_POSITION" in
      "top-right")    OVERLAY_POS="main_w-overlay_w-10:10" ;;
      "top-left")     OVERLAY_POS="10:10" ;;
      "bottom-right") OVERLAY_POS="main_w-overlay_w-10:main_h-overlay_h-10" ;;
      "bottom-left")  OVERLAY_POS="10:main_h-overlay_h-10" ;;
      *)              OVERLAY_POS="main_w-overlay_w-10:10" ;;
    esac

    # --- Build filter_complex ---
    FILTER=""
    INPUT_FLAGS="-re -stream_loop -1 -i \"$VIDEO\""
    LOGO_INPUT=""
    MAP_VIDEO="-map [vout]"
    MAP_AUDIO="-map 0:a"

    if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
      LOGO_INPUT="-i \"$LOGO_PATH\""
      FILTER="[1:v]scale=${LOGO_WIDTH}:-1[logo];"
      FILTER+="[0:v][logo]overlay=${OVERLAY_POS}[overlaid];"
      FILTER+="[overlaid]scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"
    else
      FILTER="[0:v]scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"
    fi

    if [ "$TICKER_ENABLED" = "true" ]; then
      # Escape special chars in ticker text for ffmpeg drawtext
      SAFE_TEXT=$(echo "$TICKER_TEXT" | sed "s/'/\\\\'/g")
      FILTER+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=${TICKER_BG}@0.9:t=fill"
      FILTER+=",drawtext=text='${SAFE_TEXT}':fontcolor=${TICKER_TEXT_COLOR}:fontsize=${TICKER_FONT_SIZE}:x=w-mod(${TICKER_SPEED}*t\\,w+tw):y=h-${TICKER_HEIGHT}+12"
    fi

    FILTER+="[vout]"

    echo "==============================="
    echo "Now Streaming: $VIDEO"
    echo "==============================="

    # Run ffmpeg — eval used to properly expand quoted variables
    eval ffmpeg -hide_banner -loglevel warning \
      $INPUT_FLAGS \
      $LOGO_INPUT \
      -filter_complex \"$FILTER\" \
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
      \"$YOUTUBE_URL\" || echo "FFmpeg exited for $VIDEO, moving to next..."

    echo "Waiting 3s before next video..."
    sleep 3

  done

  echo "Playlist finished. Restarting from beginning..."
  sleep 2

done
