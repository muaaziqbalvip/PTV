#!/bin/bash

YOUTUBE_URL="rtmp://a.rtmp.youtube.com/live2/$STREAM_KEY"

while true
do

VIDEOS=$(jq -r '.videos[].url' playlist.json)

for VIDEO in $VIDEOS
do

LOGO_ENABLED=$(jq -r '.logo.enabled' playlist.json)
LOGO_PATH=$(jq -r '.logo.path' playlist.json)
LOGO_POSITION=$(jq -r '.logo.position' playlist.json)
LOGO_WIDTH=$(jq -r '.logo.width' playlist.json)

TICKER_ENABLED=$(jq -r '.ticker.enabled' playlist.json)
TICKER_HEIGHT=$(jq -r '.ticker.height' playlist.json)
TICKER_BG=$(jq -r '.ticker.background_color' playlist.json)
TICKER_TEXT_COLOR=$(jq -r '.ticker.text_color' playlist.json)
TICKER_FONT_SIZE=$(jq -r '.ticker.font_size' playlist.json)
TICKER_SPEED=$(jq -r '.ticker.speed' playlist.json)
TICKER_TEXT=$(jq -r '.ticker.text' playlist.json)

ZOOM=$(jq -r '.effects.zoom' playlist.json)
PITCH=$(jq -r '.effects.audio_pitch' playlist.json)

POSITION="10:10"

if [ "$LOGO_POSITION" = "top-right" ]; then
POSITION="main_w-overlay_w-10:10"
fi

if [ "$LOGO_POSITION" = "top-left" ]; then
POSITION="10:10"
fi

if [ "$LOGO_POSITION" = "bottom-right" ]; then
POSITION="main_w-overlay_w-10:main_h-overlay_h-10"
fi

if [ "$LOGO_POSITION" = "bottom-left" ]; then
POSITION="10:main_h-overlay_h-10"
fi

FILTER_COMPLEX=""

if [ "$LOGO_ENABLED" = "true" ]; then
FILTER_COMPLEX="[1:v]scale=${LOGO_WIDTH}:-1[logo];"
FILTER_COMPLEX+="[0:v][logo]overlay=${POSITION},"
else
FILTER_COMPLEX="[0:v]"
fi

FILTER_COMPLEX+="scale=iw*${ZOOM}:ih*${ZOOM},crop=iw/${ZOOM}:ih/${ZOOM},"

if [ "$TICKER_ENABLED" = "true" ]; then

FILTER_COMPLEX+="drawbox=x=0:y=ih-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=${TICKER_BG}@0.9:t=fill,"

FILTER_COMPLEX+="drawtext=text='${TICKER_TEXT}':fontcolor=${TICKER_TEXT_COLOR}:fontsize=${TICKER_FONT_SIZE}:x=w-mod(${TICKER_SPEED}*t\\,w+tw):y=h-${TICKER_HEIGHT}+12"
fi

echo "Streaming: $VIDEO"

ffmpeg -re \
-stream_loop -1 \
-i "$VIDEO" \
-i "$LOGO_PATH" \
-filter_complex "$FILTER_COMPLEX" \
-map 0:v \
-map 0:a \
-af "asetrate=44100*${PITCH},aresample=44100" \
-c:v libx264 \
-preset veryfast \
-maxrate 4500k \
-bufsize 9000k \
-pix_fmt yuv420p \
-g 50 \
-c:a aac \
-b:a 192k \
-ar 44100 \
-f flv \
"$YOUTUBE_URL"

echo "Restarting stream..."

sleep 5

done

done