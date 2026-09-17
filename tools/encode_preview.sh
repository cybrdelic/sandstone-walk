#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p media
ffmpeg -y -framerate 24 -i build/frames/%04d.png -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart media/sandstone-walk.mp4
ffmpeg -y -framerate 24 -i build/frames/%04d.png -filter_complex '[0:v]fps=12,scale=720:480:flags=lanczos,split[x][y];[x]palettegen=max_colors=128:stats_mode=full[p];[y][p]paletteuse=dither=none:diff_mode=rectangle' -fps_mode passthrough -loop 0 media/sandstone-walk.gif
cp build/frames/0000.png media/hero.png
cp build/frames/0072.png media/interior.png
