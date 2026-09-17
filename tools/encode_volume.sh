#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p media build
ffmpeg -y -v error -framerate 24 -i build/formation_frames/%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart media/sandstone-walk.mp4
ffmpeg -y -v error -i media/sandstone-walk.mp4 -filter_complex '[0:v]fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a' -loop 0 media/sandstone-walk.gif
cp evidence/formation/hero_beauty.png media/hero.png
cp evidence/formation/orbit_beauty.png media/orbit.png
python - <<'PY'
from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageSequence
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frames=sorted(Path('build/formation_frames').glob('[0-9][0-9][0-9][0-9].png'))
assert len(frames)==144 and len(set(map(sha,frames)))==144
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames','-of','json','media/sandstone-walk.mp4']))['streams'][0]
assert probe['nb_read_frames']=='144' and probe['width']==960 and probe['height']==640 and probe['r_frame_rate']=='24/1'
with Image.open('media/sandstone-walk.gif') as im:
 assert im.n_frames==72
 g={'frames':im.n_frames,'width':im.width,'height':im.height,'unique_decoded_frames':len({hashlib.sha256(f.convert('RGB').tobytes()).hexdigest() for f in ImageSequence.Iterator(im)})}
assert g['unique_decoded_frames']==72
record={'source':'144 actual GLES draws using the new geometry, new native bake and unchanged Three.js surface shaders','interpolation':False,'reference_image_used':False,'shots':['walking camera','orbit camera'],'native_unique_frames':len(frames),'mp4':probe,'gif':g,'sha256':{p.name:sha(p) for p in map(Path,['media/sandstone-walk.gif','media/sandstone-walk.mp4','media/hero.png','media/orbit.png'])}}
Path('evidence/formation/media.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
PY
