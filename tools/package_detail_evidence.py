"""Build current media from verified browser output, not from generated imagery."""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageSequence
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--after',type=Path,required=True);ap.add_argument('--before',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'evidence/detail');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    after=json.loads((a.after/'report.json').read_text());before=json.loads((a.before/'report.json').read_text())
    assert after['result']==before['result']=='PASS' and not after['errors'] and not before['errors']
    assert after['source_mesh_sha256']==before['source_mesh_sha256']
    for source,report in [(a.after,after),(a.before,before)]:
        for name,data in report['captures'].items():assert sha(source/(name+'.png'))==data['sha256'],name
    for name in ['hero','right_close','left_close','ground','talus','forward']:
        old=before['captures'][name];new=after['captures'][name]
        assert old['pose']['eye']==new['pose']['eye'] and old['pose']['quaternion']==new['pose']['quaternion'],name
        assert old['size']==new['size']==[1200,800],name
    assert after['export4k']['report']['samples']==8 and not after['export4k']['report']['upscaled']
    assert sha(a.after/'hero_4k.png')==after['export4k']['sha256']
    for name,data in after['captures'].items():shutil.copyfile(a.after/(name+'.png'),a.out/(name+'.png'))
    shutil.copyfile(a.after/'hero_4k.png',a.out/'hero_4k.png')
    shutil.copyfile(a.after/'report.json',a.out/'report.json')
    olddir=a.out/'before';olddir.mkdir(exist_ok=True)
    for p in a.before.glob('*.png'):shutil.copyfile(p,olddir/p.name)
    shutil.copyfile(a.before/'report.json',olddir/'report.json')
    font=ImageFont.load_default(size=22)
    for name,out in [('hero','comparison.jpg'),('right_close','close_comparison.jpg'),('ground','ground_comparison.jpg')]:
        left=Image.open(a.before/(name+'.png')).convert('RGB');right=Image.open(a.after/(name+'.png')).convert('RGB')
        image=Image.new('RGB',(2400,850),(19,17,15));image.paste(left,(0,50));image.paste(right,(1200,50));d=ImageDraw.Draw(image)
        d.text((20,14),'BEFORE / v0.4 / same camera and 1200 x 800 raster',font=font,fill=(237,226,210))
        d.text((1220,14),'AFTER / v0.5 / 4K photographic materials + HDR AA',font=font,fill=(237,226,210))
        image.save(a.out/out,quality=96,subsampling=0)
    film=after['film'];assert film['fps']==12 and film['size']==[720,480] and len(film['frames'])==48
    assert len({f['sha256'] for f in film['frames']})==48 and film['interpolation'] is False
    for f in film['frames']:
        assert f['actual_source_draw']==5029800 and sha(a.after/'film'/f"{f['frame']:04d}.png")==f['sha256']
    media=ROOT/'media';media.mkdir(exist_ok=True)
    pattern=str(a.after/'film/%04d.png');gif=media/'sandstone-detail.gif';mp4=media/'sandstone-detail.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','12','-i',pattern,'-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(mp4)],check=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','12','-i',pattern,'-filter_complex','[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',str(gif)],check=True)
    with Image.open(gif) as image:
        hashes=[hashlib.sha256(im.convert('RGB').tobytes()).hexdigest() for im in ImageSequence.Iterator(image)]
        assert len(hashes)==len(set(hashes))==48
    movie=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames,width,height,r_frame_rate','-of','json',str(mp4)]))['streams'][0]
    assert int(movie['nb_read_frames'])==48 and movie['width']==720 and movie['height']==480 and movie['r_frame_rate']=='12/1'
    receipt={'result':'PASS','source':'actual Three.js browser draws','source_mesh_sha256':after['source_mesh_sha256'],
      'matched_before_after_camera_poses':True,'comparison_raster':[1200,800],'export_raster':[3840,2560],
      'comparison_edits':'Two unretouched browser images assembled with text labels; JPEG compression only',
      'film':film,'gif_frames':48,'gif_distinct_frames':48,'video':movie,'image_generation':False,
      'files':{p.relative_to(ROOT).as_posix():sha(p) for p in [gif,mp4,a.out/'hero_4k.png',a.out/'comparison.jpg',a.out/'close_comparison.jpg',a.out/'ground_comparison.jpg']}}
    (a.out/'media.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS: media hashes, 48 genuine frames and matched-camera comparisons')
if __name__=='__main__':main()
