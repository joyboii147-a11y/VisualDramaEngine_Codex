"""Manual video route (secondary): build a batch pack for the Grok Automation Chrome extension (grok.com/imagine,
SuperGrok subscription, no API credits).

usage (from the project root):
  python .claude/skills/vde-episode/scripts/grok_pack.py EP28 [--scene SC01] [--clips A001,A002]

Writes EPxx/production/grok_pack/<6s|10s>/
  prompts.txt  one prompt per line, a blank line between prompts (the extension's batch format); every prompt starts
               with the take id "EPxx_A001 SHOT EPxx-S001." so downloads are named 001_EPxx_A001-SHOT-...
  images/      the selected start image of each clip, named EPxx_A001.<ext> (same id as the prompt, for Auto-add)
  manifest.json  order of clips in the batch
Prompts are sorted by clip id, the same order File Explorer shows the images in, so dragging all images in at once
lines up with the prompt list.
The extension only offers 6 s or 10 s clips, so clips are split into two batches by length; edit.py trims to the
planned length later. Run each folder as its own batch: Frame to Video, 9:16, 1 output per prompt, 720p download.
"""
import argparse, json, os, shutil, subprocess, sys

from vde_common import ROOT, prod_dir, load_json, clip_state_path

S = os.path.dirname(os.path.abspath(__file__))
DONE = ('done', 'flagged', 'gave_up')


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument('ep')
    ap.add_argument('--scene')
    ap.add_argument('--clips')
    a = ap.parse_args()
    p = load_json(os.path.join(prod_dir(a.ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {a.ep} ก่อน')
    want = set(a.clips.split(',')) if a.clips else None
    root = os.path.join(prod_dir(a.ep), 'grok_pack')
    # clear only what this script writes; the user keeps downloads (e.g. 6s/vdo/) inside these folders
    for bucket in ('6s', '10s'):
        d = os.path.join(root, bucket)
        shutil.rmtree(os.path.join(d, 'images'), ignore_errors=True)
        for f in ('prompts.txt', 'manifest.json'):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
    batches, skipped = {}, []
    for c, info in p['clips'].items():
        if (a.scene and info['scene'] != a.scene) or (want and c not in want):
            continue
        st = load_json(clip_state_path(a.ep, c)) or {}
        if (st.get('video') or {}).get('status') in DONE and not want:
            continue
        sel = (st.get('image') or {}).get('selected')
        if not sel or not os.path.exists(os.path.join(ROOT, sel)):
            skipped.append(f'{c}: ยังไม่มีภาพตั้งต้นที่เลือก')
            continue
        r = subprocess.run([sys.executable, os.path.join(S, 'state.py'), a.ep, 'prompt', c, 'video'],
                           capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        if r.returncode:
            skipped.append(f'{c}: อ่าน prompt ไม่ได้ ({r.stderr.strip()[-120:]})')
            continue
        prompt = ' '.join(r.stdout.split())          # the extension needs one line per prompt
        bucket = '6s' if (info.get('video_sec') or 6) <= 6 else '10s'
        b = batches.setdefault(bucket, [])
        b.append({'n': len(b) + 1, 'clip': c, 'shot_sec': info.get('video_sec'), 'prompt': prompt, 'image': sel})
    for bucket, items in batches.items():
        # same order as the image files sorted by name, so dragging the whole images/ folder lines up with the prompts
        items.sort(key=lambda i: f"{a.ep}_{i['clip']}")
        for n, i in enumerate(items, 1):
            i['n'] = n
        d = os.path.join(root, bucket)
        os.makedirs(os.path.join(d, 'images'), exist_ok=True)
        with open(os.path.join(d, 'prompts.txt'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n\n'.join(i['prompt'] for i in items) + '\n')
        for i in items:
            ext = os.path.splitext(i['image'])[1]
            shutil.copy(os.path.join(ROOT, i['image']), os.path.join(d, 'images', f"{a.ep}_{i['clip']}{ext}"))
        with open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8') as fh:
            json.dump([{k: v for k, v in i.items() if k != 'prompt'} for i in items], fh, ensure_ascii=False, indent=1)
    print(json.dumps({'pack': root, 'batches': {k: [i['clip'] for i in v] for k, v in batches.items()},
                      'skipped': skipped}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
