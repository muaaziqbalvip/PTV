#!/bin/bash

set -euo pipefail

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/${STREAM_KEY}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

while true; do

  VIDEO_COUNT=$(jq '.videos | length' playlist.json)

  for i in $(seq 0 $((VIDEO_COUNT - 1))); do

    VIDEO=$(jq -r ".videos[$i].url" playlist.json)

    LOGO_ENABLED=$(jq -r '.logo.enabled' playlist.json)
    LOGO_PATH=$(jq -r '.logo.path' playlist.json)
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

    case "$LOGO_POSITION" in
      "top-right")    POSITION="main_w-overlay_w-10:10" ;;
      "top-left")     POSITION="10:10" ;;
      "bottom-right") POSITION="main_w-overlay_w-10:main_h-overlay_h-10" ;;
      "bottom-left")  POSITION="10:main_h-overlay_h-10" ;;
      *)              POSITION="10:10" ;;
    esac

    FILTER_COMPLEX=""

    if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
      FILTER_COMPLEX="[1:v]scale=${LOGO_WIDTH}:-1[logo];[0:v][logo]overlay=${POSITION}[ov];"
      FILTER_COMPLEX+="[ov]scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"
    else
      FILTER_COMPLEX="[0:v]scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM}"
    fi

    if [ "$TICKER_ENABLED" = "true" ]; then
      FILTER_COMPLEX+=",drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=${TICKER_BG}@0.9:t=fill"
      FILTER_COMPLEX+=",drawtext=text='${TICKER_TEXT}':fontcolor=${TICKER_TEXT_COLOR}:fontsize=${TICKER_FONT_SIZE}:x=w-mod(${TICKER_SPEED}*t\\,w+tw):y=h-${TICKER_HEIGHT}+12"
    fi

    FILTER_COMPLEX+="[vout]"

    log "Streaming: $VIDEO"

    if [ "$LOGO_ENABLED" = "true" ] && [ -f "$LOGO_PATH" ]; then
      ffmpeg -hide_banner -loglevel warning \
        -reconnect 1 \
        -reconnect_streamed 1 \
        -reconnect_delay_max 5 \
        -rtbufsize 512m \
        -i "$VIDEO" \
        -i "$LOGO_PATH" \
        -filter_complex "$FILTER_COMPLEX" \
        -map "[vout]" \
        -map "0:a?" \
        -af "asetrate=44100*${PITCH},aresample=44100" \
        -c:v libx264 \
        -preset ultrafast \
        -tune zerolatency \
        -maxrate 4500k \
        -bufsize 9000k \
        -pix_fmt yuv420p \
        -g 50 \
        -c:a aac \
        -b:a 192k \
        -ar 44100 \
        -f flv \
        "$YOUTUBE_URL" || log "FFmpeg exited — next video..."
    else
      ffmpeg -hide_banner -loglevel warning \
        -reconnect 1 \
        -reconnect_streamed 1 \
        -reconnect_delay_max 5 \
        -rtbufsize 512m \
        -i "$VIDEO" \
        -filter_complex "$FILTER_COMPLEX" \
        -map "[vout]" \
        -map "0:a?" \
        -af "asetrate=44100*${PITCH},aresample=44100" \
        -c:v libx264 \
        -preset ultrafast \
        -tune zerolatency \
        -maxrate 4500k \
        -bufsize 9000k \
        -pix_fmt yuv420p \
        -g 50 \
        -c:a aac \
        -b:a 192k \
        -ar 44100 \
        -f flv \
        "$YOUTUBE_URL" || log "FFmpeg exited — next video..."
    fi

    log "Next video..."
    sleep 2

  done

done