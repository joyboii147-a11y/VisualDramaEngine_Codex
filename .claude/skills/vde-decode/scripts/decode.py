"""Break down a source drama clip (story, events, dialogue) with Gemini via fal openrouter/router/video.

usage (from the project root):
  python .claude/skills/vde-decode/scripts/decode.py EP30 prep [--video "Source/SRC EP30.mp4"] [--mode full|dialogue]
  python .claude/skills/vde-decode/scripts/decode.py EP30 run  [--mode full|dialogue] [--model google/gemini-3.1-pro-preview]
  python .claude/skills/vde-decode/scripts/decode.py EP30 frames
  python .claude/skills/vde-decode/scripts/decode.py EP30 check
  python .claude/skills/vde-decode/scripts/decode.py EP30 promote [--force]

Work folder: Source/EPxx_แกะคลิป/ (prompt, compressed video, output, frames). input/ is written only by `promote`.
"""
import argparse, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '.claude', 'skills', 'vde-episode', 'scripts'))
from fal_image import api_key, http  # noqa: E402

GUIDE = os.path.join(ROOT, 'Claude_prompt_แกะคลิป.md')
HEADERS = {'full': os.path.join(HERE, '..', 'task_full.md'), 'dialogue': os.path.join(HERE, '..', 'task_dialogue.md')}
OUT_NAME = {'full': '{ep}.txt', 'dialogue': '{ep}_บทพูด.txt'}
DEFAULT_MODEL = 'google/gemini-3.1-pro-preview'
SHOT = re.compile(r'^#### (S\d{3}[A-Z]?) · (\d+):(\d+(?:\.\d+)?)–(\d+):(\d+(?:\.\d+)?)')
SCENE = re.compile(r'^### ฉากที่ (\d+) .*?(\d+):(\d+(?:\.\d+)?)–(\d+):(\d+(?:\.\d+)?)\s*$')
LINE = re.compile(r'^([^\s"(][^"(]*?) \((W\d+|W\?\?)\)(?: [^:]*)?: "')
FLAGS = ('[ตรวจเสียง', '[ภาพไม่ชัด', '[ฟังไม่ชัด', '[ตัวละครใหม่]', 'W??')


def work(ep):
    return os.path.join(ROOT, 'Source', f'{ep}_แกะคลิป')


def find_video(ep, given=None):
    if given:
        return os.path.join(ROOT, given) if not os.path.isabs(given) else given
    hits = [p for p in glob.glob(os.path.join(ROOT, 'Source', '*.mp4')) if re.search(rf'\b{ep}\b', os.path.basename(p), re.I)]
    if len(hits) != 1:
        sys.exit(f'หาไฟล์วิดีโอของ {ep} ใน Source/ ไม่ได้ (พบ {len(hits)}) ใช้ --video ระบุเอง')
    return hits[0]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')


def duration(video):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video]).stdout.strip())


def cuts(video):
    err = run(['ffmpeg', '-i', video, '-vf', "select='gt(scene,0.25)',showinfo", '-f', 'null', '-']).stderr
    return [round(float(t), 3) for t in re.findall(r'pts_time:([0-9.]+)', err)]


def mmss(sec):
    return f'{int(sec // 60):02d}:{sec % 60:04.1f}'


def roster(ep):
    """Character roster block from the latest earlier story file, so names and wardrobe codes stay consistent."""
    n = int(re.sub(r'\D', '', ep) or 0)
    best = None
    for p in glob.glob(os.path.join(ROOT, 'input', 'story', 'EP*.txt')):
        m = re.match(r'EP(\d+)', os.path.basename(p))
        if m and int(m.group(1)) < n and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), p)
    if not best:
        return '', '(ไม่มีไฟล์เรื่องตอนก่อน)'
    lines = open(best[1], encoding='utf-8-sig').read().splitlines()
    out, on = [], False
    for ln in lines:
        if ln.startswith('รายชื่อตัวละคร'):
            on = True
        elif on and not ln.strip():
            break
        if on:
            out.append(ln)
    return '\n'.join(out), os.path.basename(best[1]).replace('.txt', '')


def cmd_prep(a):
    video = find_video(a.ep, a.video)
    wd = work(a.ep)
    os.makedirs(wd, exist_ok=True)
    small = os.path.join(wd, f'{a.ep}_small.mp4')
    if not os.path.exists(small):
        r = run(['ffmpeg', '-y', '-i', video, '-vf', 'scale=540:-2', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
                 '-c:a', 'aac', '-b:a', '96k', small])
        if r.returncode:
            sys.exit('บีบวิดีโอไม่สำเร็จ: ' + r.stderr[-400:])
    dur = duration(video)
    cut = cuts(video) if a.mode == 'full' else []
    names, prev = roster(a.ep)
    head = open(HEADERS[a.mode], encoding='utf-8').read().format(
        ep=a.ep, dur=mmss(dur), ncut=len(cut), cuts=' '.join(f'{c:g}' for c in cut), prev=prev, roster=names or '(ไม่มี)',
        video=os.path.relpath(video, ROOT).replace('\\', '/'))
    prompt = head + ('\n\n---\n\n' + open(GUIDE, encoding='utf-8').read() if a.mode == 'full' else '')
    pf = os.path.join(wd, f'prompt_{a.mode}.txt')
    open(pf, 'w', encoding='utf-8', newline='\n').write(prompt)
    meta = {'ep': a.ep, 'video': os.path.relpath(video, ROOT), 'small': os.path.relpath(small, ROOT), 'duration': dur,
            'cuts': cut, 'prev_episode': prev}
    json.dump(meta, open(os.path.join(wd, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'prompt': os.path.relpath(pf, ROOT), 'chars': len(prompt), 'duration': mmss(dur), 'cuts': len(cut),
                      'roster_from': prev, 'small_mb': round(os.path.getsize(small) / 1e6, 1)}, ensure_ascii=False, indent=1))


def upload(key, path):
    up = http('POST', 'https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3', key,
              {'content_type': 'video/mp4', 'file_name': os.path.basename(path).encode('ascii', 'ignore').decode() or 'clip.mp4'})
    r = run(['curl', '-sSf', '-X', 'PUT', '-H', 'Content-Type: video/mp4', '--data-binary', f'@{path}', up['upload_url']])
    if r.returncode:
        sys.exit('อัปโหลดไม่สำเร็จ: ' + r.stderr[-400:])
    return up['file_url']


def cmd_run(a):
    wd = work(a.ep)
    pf = os.path.join(wd, f'prompt_{a.mode}.txt')
    if not os.path.exists(pf):
        sys.exit('ยังไม่มี prompt — รัน prep ก่อน')
    meta = json.load(open(os.path.join(wd, 'meta.json'), encoding='utf-8'))
    out = os.path.join(wd, OUT_NAME[a.mode].format(ep=a.ep))
    if os.path.exists(out) and not a.force:
        sys.exit(f'มี {os.path.relpath(out, ROOT)} แล้ว — ใช้ --force ถ้าจะแกะใหม่ทับ')
    key = api_key()
    url = upload(key, os.path.join(ROOT, meta['small']))
    print('uploaded', flush=True)
    body = {'video_urls': [url], 'prompt': open(pf, encoding='utf-8').read(), 'model': a.model,
            'temperature': 0.3, 'reasoning': True, 'max_tokens': 60000}
    job = http('POST', 'https://queue.fal.run/openrouter/router/video', key, body)
    print('request', job['request_id'], flush=True)
    base = 'https://queue.fal.run/openrouter/router/requests/' + job['request_id']
    t0 = time.time()
    while http('GET', base + '/status', key).get('status') != 'COMPLETED':
        if time.time() - t0 > a.wait:
            sys.exit(f'ยังไม่เสร็จใน {a.wait} วิ — request {job["request_id"]}')
        time.sleep(10)
    res = http('GET', base, key)
    text = re.sub(r'^```[a-z]*\n|\n```\s*$', '', (res.get('output') or '').strip())
    if not text:
        sys.exit('ผลลัพธ์ว่าง: ' + json.dumps(res, ensure_ascii=False)[:600])
    open(out, 'w', encoding='utf-8', newline='\n').write(text + '\n')
    json.dump({'request_id': job['request_id'], 'model': a.model, 'usage': res.get('usage')},
              open(os.path.join(wd, f'usage_{a.mode}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'out': os.path.relpath(out, ROOT), 'chars': len(text), 'usage': res.get('usage')}, ensure_ascii=False))


def story_path(ep):
    for p in (os.path.join(work(ep), f'{ep}.txt'), os.path.join(ROOT, 'input', 'story', f'{ep}.txt')):
        if os.path.exists(p):
            return p
    sys.exit(f'ไม่พบไฟล์แกะคลิปของ {ep}')


def shots(text):
    out = []
    for ln in text.splitlines():
        m = SHOT.match(ln)
        if m:
            s = int(m.group(2)) * 60 + float(m.group(3))
            e = int(m.group(4)) * 60 + float(m.group(5))
            out.append((m.group(1), s, e))
    return out


def cmd_frames(a):
    meta = json.load(open(os.path.join(work(a.ep), 'meta.json'), encoding='utf-8'))
    video = os.path.join(ROOT, meta['video'])
    fd = os.path.join(work(a.ep), 'frames')
    os.makedirs(fd, exist_ok=True)
    n = 0
    for sid, s, e in shots(open(story_path(a.ep), encoding='utf-8-sig').read()):
        out = os.path.join(fd, f'{a.ep}_{sid}.jpg')
        if os.path.exists(out):
            continue
        r = run(['ffmpeg', '-y', '-ss', f'{(s + e) / 2:.2f}', '-i', video, '-frames:v', '1', '-vf', 'scale=540:-2', '-q:v', '3', out])
        n += 0 if r.returncode else 1
    print(json.dumps({'frames_dir': os.path.relpath(fd, ROOT), 'new': n}, ensure_ascii=False))


def cmd_check(a):
    p = story_path(a.ep)
    text = open(p, encoding='utf-8-sig').read()
    lines = text.splitlines()
    meta_p = os.path.join(work(a.ep), 'meta.json')
    dur = json.load(open(meta_p, encoding='utf-8'))['duration'] if os.path.exists(meta_p) else None
    sh = shots(text)
    probs = []
    m = re.search(r'จำนวนช็อตต้นฉบับ:\s*(\d+)', text)
    if m and int(m.group(1)) != len(sh):
        probs.append(f'หัวไฟล์บอก {m.group(1)} ช็อต แต่พบ {len(sh)}')
    for (p1, s1, e1), (p2, s2, e2) in zip(sh, sh[1:]):
        if s2 < e1 - 0.05:
            probs.append(f'{p1}–{p2} เวลาทับกัน ({e1:.1f} > {s2:.1f})')
        elif s2 > e1 + 0.3:
            probs.append(f'{p1}–{p2} มีช่องว่าง {s2 - e1:.1f} วิ')
    for sid, s, e in sh:
        if e <= s:
            probs.append(f'{sid} เวลาจบไม่มากกว่าเวลาเริ่ม')
    if sh and dur and abs(sh[-1][2] - dur) > 1.0:
        probs.append(f'ช็อตสุดท้ายจบ {sh[-1][2]:.1f} แต่คลิปยาว {dur:.1f}')
    scenes = [(int(m.group(1)), int(m.group(2)) * 60 + float(m.group(3)), int(m.group(4)) * 60 + float(m.group(5)))
              for m in (SCENE.match(l) for l in lines) if m]
    for (n1, _, e1), (n2, s2, _) in zip(scenes, scenes[1:]):
        if s2 < e1 - 0.05:
            probs.append(f'ฉากที่ {n1}–{n2} เวลาทับกัน')
    # names + wardrobe codes used in dialogue/composition lines vs character folders
    chars_dir = os.path.join(ROOT, 'input', 'characters')
    folders = set(os.listdir(chars_dir)) if os.path.isdir(chars_dir) else set()
    used = {}
    for ln in lines:
        mm = LINE.match(ln.lstrip('- ').strip()) or re.match(r'^- ([^\s(:][^(:]*?) \((W\d+|W\?\?)\):', ln)
        if mm:
            used.setdefault(mm.group(1).strip(), set()).add(mm.group(2))
    cast = set()
    for ln in lines:
        mr = re.match(r'^- ([^—]+?) — ', ln)
        if mr:
            cast.update(n.strip() for n in mr.group(1).split(','))
    unknown = sorted(n for n in used if n not in cast)
    wardrobe = []
    for name, ws in sorted(used.items()):
        if name not in cast:
            continue
        files = os.listdir(os.path.join(chars_dir, name)) if name in folders else []
        for w in sorted(ws):
            has = any(re.search(rf'(^|\s){w}(\D|$)', f) for f in files)
            wardrobe.append({'character': name, 'wardrobe': w, 'folder': name in folders, 'image': has})
    flags = {f: text.count(f) for f in FLAGS}
    print(json.dumps({'file': os.path.relpath(p, ROOT), 'shots': len(sh), 'scenes': len(scenes),
                      'problems': probs, 'flags': flags, 'names_not_in_roster': unknown,
                      'wardrobe_missing': [w for w in wardrobe if not w['image']]}, ensure_ascii=False, indent=1))


def cmd_promote(a):
    src = os.path.join(work(a.ep), f'{a.ep}.txt')
    dst = os.path.join(ROOT, 'input', 'story', f'{a.ep}.txt')
    if not os.path.exists(src):
        sys.exit('ไม่พบ ' + os.path.relpath(src, ROOT))
    if os.path.exists(dst) and not a.force:
        sys.exit(f'มี {os.path.relpath(dst, ROOT)} อยู่แล้ว — ใช้ --force ถ้าจะแทนที่')
    text = open(src, encoding='utf-8-sig').read()
    note = f'หมายเหตุ: ภาพอ้างอิงช็อต frames/ อยู่ที่ Source/{a.ep}_แกะคลิป/frames/'
    if note not in text:
        text = re.sub(r'^(ที่มา:.*)$', lambda m: m.group(1) + '\n' + note, text, count=1, flags=re.M)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8', newline='\n').write(text)
    os.remove(src)
    print(json.dumps({'moved_to': os.path.relpath(dst, ROOT)}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep')
    ap.add_argument('cmd', choices=['prep', 'run', 'frames', 'check', 'promote'])
    ap.add_argument('--video')
    ap.add_argument('--mode', choices=['full', 'dialogue'], default='full')
    ap.add_argument('--model', default=DEFAULT_MODEL)
    ap.add_argument('--wait', type=int, default=1800)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    a.ep = a.ep.upper()
    {'prep': cmd_prep, 'run': cmd_run, 'frames': cmd_frames, 'check': cmd_check, 'promote': cmd_promote}[a.cmd](a)


if __name__ == '__main__':
    main()
