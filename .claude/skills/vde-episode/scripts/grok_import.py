"""Manual video route (secondary): bring videos downloaded by the Grok Automation extension back into production.

usage (from the project root):
  python .claude/skills/vde-episode/scripts/grok_import.py EP28 "<download folder>" [--move]

Matches each .mp4 by the take id at the start of its name (001_EP28A001-SHOT-EP28-S001-..._grok-video-<uuid>.mp4
-> A001; the extension drops the "_", and the id may also come back with "-" or in lower case), copies it to the next free take name
EPxx/Video/EPxx_A001_Tnn.mp4 and prints one row per file. It does NOT record takes: run the vde-videos QC step
(frames, drift, take/select with --job manual-extension --cost 0) on every imported file. Files that match no clip of
the episode are listed under "unmatched" and left untouched.
"""
import argparse, glob, json, os, re, shutil, sys

from vde_common import ROOT, ep_dir, prod_dir, load_json, clip_state_path


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument('ep')
    ap.add_argument('src')
    ap.add_argument('--move', action='store_true', help='move instead of copy')
    a = ap.parse_args()
    p = load_json(os.path.join(prod_dir(a.ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {a.ep} ก่อน')
    if not os.path.isdir(a.src):
        sys.exit(f'ไม่พบโฟลเดอร์ {a.src}')
    ep_pat = re.escape(a.ep).replace('\\-', '[-_]')
    # the extension drops the underscore: 001_EP27A016-SHOT-EP27-S016-..._grok-video-<uuid>.mp4
    pat = re.compile(rf'{ep_pat}[-_]?([AB]\d{{3}}[A-Z]?)(?![0-9])', re.I)
    vdir = os.path.join(ep_dir(a.ep), 'Video')
    os.makedirs(vdir, exist_ok=True)
    rows, unmatched = [], []
    for f in sorted(glob.glob(os.path.join(a.src, '*.mp4')), key=os.path.getmtime):
        m = pat.search(os.path.basename(f))
        clip = m.group(1).upper() if m else None
        if clip not in p['clips']:
            unmatched.append(os.path.basename(f))
            continue
        st = load_json(clip_state_path(a.ep, clip)) or {}
        n = len((st.get('video') or {}).get('takes', [])) + 1
        while os.path.exists(os.path.join(vdir, f'{a.ep}_{clip}_T{n:02d}.mp4')):
            n += 1                                     # several downloads of one clip before any take is recorded
        dest = os.path.join(vdir, f'{a.ep}_{clip}_T{n:02d}.mp4')
        (shutil.move if a.move else shutil.copy2)(f, dest)
        rows.append({'clip': clip, 'source': os.path.basename(f),
                     'out_file': os.path.relpath(dest, ROOT).replace(os.sep, '/')})
    print(json.dumps({'imported': rows, 'unmatched': unmatched}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
