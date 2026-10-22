"""Contact sheets of the selected takes in edit order, for the cross-shot continuity check (v68).

usage (from the project root):
  python .claude/skills/vde-episode/scripts/continuity_sheet.py EP28 [--scene SC01] [--kind image|video]

Writes EPxx/production/continuity/<scene>_<kind>_<n>.jpg (8 shots per sheet, labelled with the clip id) and
<scene>_<kind>.txt with, for every shot in order, what the prompt header says should be in frame. Open both and
compare neighbouring shots: left-to-right order, who is missing, standing/sitting, wet/dry, who holds the prop.
--kind video takes one frame at 70% of each selected video (shows drift that the start image hides).
"""
import argparse, json, os, subprocess, sys

from vde_common import ROOT, prod_dir, load_json, read_prompt, clip_state_path

W, H, PER = 300, 534, 8
FONT = '/System/Library/Fonts/Supplemental/Tahoma.ttf' if sys.platform == 'darwin' else 'C\\:/Windows/Fonts/tahoma.ttf'


def video_frame(src, out):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
                       capture_output=True, text=True)
    t = float(r.stdout.strip() or 1) * 0.7
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', src, '-map', '0:v:0', '-frames:v', '1', out],
                   check=True)
    return out


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument('ep')
    ap.add_argument('--scene')
    ap.add_argument('--kind', choices=['image', 'video'], default='image')
    a = ap.parse_args()
    p = load_json(os.path.join(prod_dir(a.ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {a.ep} ก่อน')
    out_dir = os.path.join(prod_dir(a.ep), 'continuity')
    tmp = os.path.join(out_dir, '_frames')
    os.makedirs(tmp, exist_ok=True)

    by_scene = {}
    for s in p['shots']:
        if a.scene and s['scene'] != a.scene:
            continue
        by_scene.setdefault(s['scene'], []).append(s)

    result = []
    for scene, shots in by_scene.items():
        items, notes = [], []
        for s in shots:
            st = load_json(clip_state_path(a.ep, s['clip'])) or {}
            sel = (st.get(a.kind) or {}).get('selected')
            src = os.path.join(ROOT, sel) if sel else None
            header = read_prompt(os.path.join(ROOT, p['clips'][s['clip']]['image_prompt']))[0]
            in_frame = [l[4:].strip() for l in header if l.startswith('# - ')]
            notes.append(f"{s['id']} {s['clip']}{' REUSE' if s['reuse'] else ''}: "
                         + (' / '.join(in_frame) if in_frame else '(ไม่มีบันทึกตัวละครในหัวไฟล์)')
                         + ('' if src and os.path.exists(src) else '  [ไม่มีไฟล์ที่เลือก]'))
            if not src or not os.path.exists(src) or s['reuse']:
                continue
            if a.kind == 'video':
                src = video_frame(src, os.path.join(tmp, f"{s['clip']}.jpg"))
            items.append((s['clip'], src))
        with open(os.path.join(out_dir, f'{scene}_{a.kind}.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(notes) + '\n')
        for n in range(0, len(items), PER):
            chunk = items[n:n + PER]
            args, fil = [], []
            for i, (clip, f) in enumerate(chunk):
                args += ['-i', f]
                fil.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                           f"drawtext=fontfile='{FONT}':text='{clip}':x=8:y=8:fontsize=34:fontcolor=yellow:"
                           f"box=1:boxcolor=black@0.7[v{i}]")
            k = len(chunk)
            layout = '|'.join(f'{(i % 4) * W}_{(i // 4) * H}' for i in range(k))
            fil.append(''.join(f'[v{i}]' for i in range(k)) + f'xstack=inputs={k}:layout={layout}:fill=black[o]'
                       if k > 1 else '[v0]null[o]')
            out = os.path.join(out_dir, f'{scene}_{a.kind}_{n // PER + 1}.jpg')
            r = subprocess.run(['ffmpeg', '-v', 'error', '-y', *args, '-filter_complex', ';'.join(fil), '-map', '[o]',
                                '-q:v', '4', out], capture_output=True, text=True)
            if r.returncode:
                sys.exit(f'ทำ contact sheet ไม่สำเร็จ: {r.stderr[-400:]}')
            result.append({'sheet': out, 'clips': [c for c, _ in chunk]})
        result.append({'notes': os.path.join(out_dir, f'{scene}_{a.kind}.txt')})
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
