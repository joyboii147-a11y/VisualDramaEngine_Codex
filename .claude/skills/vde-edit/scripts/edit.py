"""Assemble an episode from the selected video takes, following shots/SCxx.md order and timing.

usage (from the project root):
  python .claude/skills/vde-edit/scripts/edit.py EP28 [--music "file.wav"] [--music-db -22] [--burn] [--head 0.5]

Per shot:
  - new clip : start after the 0.5 s head, keep "เวลาใช้จริง" seconds; for dialogue shots the cut is widened so
               no detected speech is clipped (speech start - 0.15 s, last speech + 0.3 s)
  - REUSE    : continue the source clip from where its previous use ended, for "เวลาใช้จริง" seconds
  - B-roll marked "ปิดเสียง" is muted
  - missing take: black placeholder of the planned length, listed in the report
Outputs to EPxx/Edit/: EPxx_ตัดต่อ.mp4, EPxx.srt (from the shot dialogue, verbatim), EPxx_edl.csv,
optionally EPxx_ตัดต่อ_ซับ.mp4 (burned subtitles).
"""
import argparse, csv, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'vde-episode', 'scripts'))
from vde_common import ROOT, ep_dir, prod_dir, load_json, clip_state_path  # noqa: E402

CFG = load_json(os.path.join(os.path.dirname(__file__), '..', '..', 'vde-episode', 'config.json'), {})
W, H, FPS = 720, 1280, 24


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)
    if r.returncode:
        sys.exit(f'ffmpeg ล้มเหลว: {" ".join(cmd[:6])} ...\n{r.stderr[-1500:]}')
    return r


def duration(p):
    r = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p])
    return float(r.stdout.strip())


def has_audio(p):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', p])
    return bool(r.stdout.strip())


_speech = {}


def speech(p, d):
    if p in _speech:
        return _speech[p]
    if not has_audio(p):
        _speech[p] = []
        return []
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', p, '-map', '0:a:0', '-af',
                          f"silencedetect=noise={CFG.get('silence_db', -35)}dB:d=0.3", '-f', 'null', '-'],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    sil, s = [], None
    for k, v in re.findall(r'silence_(start|end): ([0-9.]+)', err):
        if k == 'start':
            s = float(v)
        else:
            sil.append((s, float(v))); s = None
    if s is not None:
        sil.append((s, d))
    out, t = [], 0.0
    for a, b in sil:
        if a - t > 0.08:
            out.append((t, a))
        t = b
    if d - t > 0.08:
        out.append((t, d))
    _speech[p] = out
    return out


def ts(t):
    ms = int(round(t * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep')
    ap.add_argument('--music')
    ap.add_argument('--music-db', type=float, default=CFG.get('music_db', -22))
    ap.add_argument('--burn', action='store_true')
    ap.add_argument('--head', type=float, default=CFG.get('clip_head_sec', 0.5))
    a = ap.parse_args()
    ep = a.ep
    d = ep_dir(ep)
    plan = load_json(os.path.join(prod_dir(ep), 'plan.json'))
    if not plan:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {ep} ก่อน')
    out_dir = os.path.join(d, 'Edit')
    seg_dir = os.path.join(out_dir, '_segments')
    shutil.rmtree(seg_dir, ignore_errors=True)
    os.makedirs(seg_dir)

    consumed, rows, cues, warnings = {}, [], [], []
    t_line = 0.0
    for i, s in enumerate(plan['shots']):
        st = load_json(clip_state_path(ep, s['clip'])) or {}
        sel = (st.get('video') or {}).get('selected')
        src = os.path.join(ROOT, sel) if sel else None
        seg = os.path.join(seg_dir, f'{i:03d}.mp4')
        vf = f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p'
        if not src or not os.path.exists(src):
            length = s['use_sec'] or s['gen_sec'] or 2.0
            run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=black:s={W}x{H}:r={FPS}:d={length}',
                 '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f'{length}', '-c:v', 'libx264',
                 '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', seg])
            warnings.append(f'{s["id"]} ({s["clip"]}): ไม่มีวิดีโอที่เลือก — ใส่จอดำ {length:.1f} วิ')
            start, end, kind = 0.0, length, 'MISSING'
        else:
            dur = duration(src)
            sp = speech(src, dur)
            use = s['use_sec']
            if s['reuse']:
                start = consumed.get(s['clip'], a.head)
                end = min(dur - 0.02, start + (use or 2.0))
                if end - start < 0.4:
                    warnings.append(f'{s["id"]}: REUSE {s["clip"]} เหลือเนื้อคลิปไม่พอ — ใช้ช่วงท้ายคลิปแทน')
                    start, end = max(0, dur - (use or 2.0) - 0.02), dur - 0.02
                kind = 'REUSE'
            else:
                start = min(a.head, dur * 0.2)
                end = min(dur - 0.02, start + use) if use else dur - a.head
                if s['dialogue'] and sp:
                    start = max(0.0, min(start, sp[0][0] - 0.15))
                    end = min(dur - 0.02, max(end, sp[-1][1] + 0.3))
                elif s['dialogue'] and not sp:
                    warnings.append(f'{s["id"]}: มีบทพูดแต่ตรวจไม่พบเสียงพูดใน {sel}')
                kind = 'NEW'
            consumed[s['clip']] = end
            audio = ['-af', 'volume=0'] if s['mute'] else []
            inputs = ['-ss', f'{start:.3f}', '-to', f'{end:.3f}', '-i', src]
            if not has_audio(src):
                inputs += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                maps = ['-map', '0:v:0', '-map', '1:a:0', '-shortest']
            else:
                maps = ['-map', '0:v:0', '-map', '0:a:0']
            run(['ffmpeg', '-y', '-v', 'error', *inputs, *maps, '-vf', vf, *audio, '-c:v', 'libx264', '-preset', 'medium',
                 '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', seg])
            if s['overlay']:
                warnings.append(f'{s["id"]} ({s["clip"]}): ไฟล์ Shot ระบุให้ภาพทับเสียงคลิปอื่น ("ทับช่วง") — ต้องจัดเสียงเองในโปรแกรมตัดต่อ')
        seg_len = duration(seg)
        if s['dialogue']:
            lead = 0.0
            if kind == 'NEW' and src and _speech.get(src):
                lead = max(0.0, _speech[src][0][0] - start)
            cues.append((t_line + lead, t_line + seg_len, '\n'.join(s['dialogue'])))
        rows.append([s['id'], s['scene'], s['clip'], kind, sel or '', f'{start:.2f}', f'{end:.2f}',
                     f'{seg_len:.2f}', f'{t_line:.2f}', ' / '.join(s['dialogue'])])
        t_line += seg_len

    lst = os.path.join(seg_dir, 'list.txt')
    with open(lst, 'w', encoding='utf-8') as fh:
        for i in range(len(plan['shots'])):
            fh.write(f"file '{i:03d}.mp4'\n")
    joined = os.path.join(seg_dir, 'joined.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy', 'joined.mp4'],
        cwd=seg_dir)

    final = os.path.join(out_dir, f'{ep}_ตัดต่อ.mp4')
    loud = f"loudnorm=I={CFG.get('loudness_lufs', -14)}:TP=-1.5:LRA=11"
    if a.music:
        music = a.music if os.path.isabs(a.music) else os.path.join(ROOT, a.music)
        fc = (f'[0:a]{loud}[v];[1:a]volume={a.music_db}dB,afade=t=out:st={max(0, t_line - 2):.2f}:d=2[m];'
              f'[v][m]amix=inputs=2:duration=first:normalize=0[a]')
        run(['ffmpeg', '-y', '-v', 'error', '-i', joined, '-stream_loop', '-1', '-i', music, '-filter_complex', fc,
             '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{t_line:.3f}', final])
    else:
        run(['ffmpeg', '-y', '-v', 'error', '-i', joined, '-af', loud, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
             '-ar', '48000', final])

    srt = os.path.join(out_dir, f'{ep}.srt')
    with open(srt, 'w', encoding='utf-8') as fh:
        for n, (s0, s1, text) in enumerate(cues, 1):
            fh.write(f'{n}\n{ts(s0)} --> {ts(s1)}\n{text}\n\n')
    with open(os.path.join(out_dir, f'{ep}_edl.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['shot', 'scene', 'clip', 'type', 'source', 'in', 'out', 'length', 'timeline_start', 'dialogue'])
        w.writerows(rows)

    if a.burn:
        font = CFG.get('subtitle_font', 'Tahoma')
        style = f'FontName={font},FontSize=13,Outline=2,Shadow=0,MarginV=70,Alignment=2'
        run(['ffmpeg', '-y', '-v', 'error', '-i', os.path.basename(final), '-vf',
             f"subtitles={ep}.srt:charenc=UTF-8:force_style='{style}'", '-c:v', 'libx264', '-crf', '18',
             '-c:a', 'copy', f'{ep}_ตัดต่อ_ซับ.mp4'], cwd=out_dir)

    shutil.rmtree(seg_dir, ignore_errors=True)
    print(json.dumps({'final': final, 'seconds': round(t_line, 1), 'shots': len(rows), 'subtitles': len(cues),
                      'missing': sum(1 for r in rows if r[3] == 'MISSING'), 'warnings': warnings},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
