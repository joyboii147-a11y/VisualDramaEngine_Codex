"""Build EPxx/production/plan.json from shots/SCxx.md and prompts/, and create per-clip state files.

usage: python .claude/skills/vde-episode/scripts/collect.py EP28
Re-running is safe: existing clip state is kept; a clip whose prompt file changed is reset to 'todo'.
"""
import glob, os, re, sys
from vde_common import (ROOT, ep_dir, prod_dir, rel, load_json, save_json, sha1, read_prompt,
                        parse_refs, parse_video_seconds, clip_state_path, new_clip_state)

QUOTE = re.compile(r'[“"]([^”"]+)[”"]')
CFG = load_json(os.path.join(os.path.dirname(__file__), '..', 'config.json'), {})
# fal takes up to fal_max_refs; OpenArt accepts 4
MAX_REFS = CFG.get('fal_max_refs', 8) if CFG.get('image_provider') == 'fal' else 4


def field(block, key):
    for line in block:
        if line.startswith(f'- {key}:'):
            return line.split(':', 1)[1].strip()
    return ''


def first_num(text, pattern=r'([0-9]+(?:\.[0-9]+)?)\s*วิ'):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def parse_shot_file(path, ep):
    with open(path, encoding='utf-8-sig') as fh:
        lines = fh.read().splitlines()
    scene = os.path.splitext(os.path.basename(path))[0]
    shots, cur = [], None
    for line in lines:
        if line.startswith('## Optional Coverage'):
            break
        m = re.match(r'^##\s+(' + re.escape(ep) + r'-S\d+[A-Z]?)\s*$', line)
        if m:
            cur = {'id': m.group(1), 'scene': scene, 'lines': []}
            shots.append(cur)
        elif cur is not None:
            cur['lines'].append(line)
    out = []
    for s in shots:
        b = s['lines']
        clip_txt = field(b, 'Clip')
        cm = re.match(r'^(REUSE\s+)?([AB]\d{3}[A-Z]?)', clip_txt)
        if not cm:
            print(f'! {s["id"]}: อ่านช่อง Clip ไม่ได้ ({clip_txt!r}) — ข้าม', file=sys.stderr)
            continue
        use_txt = field(b, 'เวลาใช้จริง / จุดตัด / Continuity')
        use_sec = first_num(use_txt, r'(?:ประมาณ|~)\s*([0-9]+(?:\.[0-9]+)?)\s*วิ') or first_num(use_txt)
        dlg_txt = field(b, 'บทพูด / เสียง')
        text = '\n'.join(b)
        mode = re.search(r'โหมด\s*([ABC])', dlg_txt)
        out.append({
            'id': s['id'],
            'scene': s['scene'],
            'clip': cm.group(2),
            'reuse': bool(cm.group(1)),
            'gen_sec': first_num(field(b, 'เวลาสั่งสร้าง')),
            'use_sec': use_sec,
            'dialogue_ids': re.findall(r'D\d{3}', dlg_txt),
            'dialogue': QUOTE.findall(dlg_txt),
            'audio_mode': mode.group(1) if mode else None,
            'mute': 'ปิดเสียง' in text and cm.group(2).startswith('B'),
            'overlay': 'ทับช่วง' in text,
            'cut_note': use_txt,
        })
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: collect.py EPxx')
    ep = sys.argv[1]
    d = ep_dir(ep)
    shot_files = sorted(glob.glob(os.path.join(d, 'shots', 'SC*.md')),
                        key=lambda p: int(re.sub(r'\D', '', os.path.basename(p)) or 0))
    if not shot_files:
        sys.exit(f'ไม่พบไฟล์ Shot ใน {ep}/shots — ต้องรันขั้นเขียน prompt ก่อน')
    shots = []
    for f in shot_files:
        shots += parse_shot_file(f, ep)

    clips, problems = {}, []
    for s in shots:
        if s['reuse'] or s['clip'] in clips:
            continue
        c = s['clip']
        ip = os.path.join(d, 'prompts', f'{ep}_{c}_image.txt')
        vp = os.path.join(d, 'prompts', f'{ep}_{c}_video.txt')
        info = {'clip': c, 'kind': c[0], 'scene': s['scene'], 'shots': [], 'refs': [],
                'image_prompt': None, 'video_prompt': None, 'video_sec': None}
        if os.path.exists(ip):
            hdr, _ = read_prompt(ip)
            info['image_prompt'] = rel(ip)
            info['image_sha'] = sha1(ip)
            info['refs'] = parse_refs(hdr)
            for r in info['refs']:
                if not os.path.exists(os.path.join(ROOT, r)):
                    problems.append(f'{c}: ไม่พบภาพอ้างอิง {r}')
            if len(info['refs']) > MAX_REFS:
                problems.append(f'{c}: แนบ {len(info["refs"])} ภาพ เกิน {MAX_REFS} — ใช้ {MAX_REFS} ภาพแรก')
                info['refs'] = info['refs'][:MAX_REFS]
        else:
            problems.append(f'{c}: ไม่พบ {rel(ip)}')
        if os.path.exists(vp):
            hdr, _ = read_prompt(vp)
            info['video_prompt'] = rel(vp)
            info['video_sha'] = sha1(vp)
            info['video_sec'] = parse_video_seconds(hdr) or (
                max(1, min(15, int(-(-s['gen_sec'] // 1)))) if s['gen_sec'] else None)
            if not info['video_sec']:
                problems.append(f'{c}: หาความยาววิดีโอไม่ได้')
        else:
            problems.append(f'{c}: ไม่พบ {rel(vp)}')
        clips[c] = info
    for s in shots:
        if s['clip'] in clips:
            clips[s['clip']]['shots'].append(s['id'])
        elif s['reuse']:
            problems.append(f'{s["id"]}: REUSE {s["clip"]} แต่ไม่มีคลิปต้นทาง')

    pdir = prod_dir(ep)
    save_json(os.path.join(pdir, 'plan.json'), {'episode': ep, 'shots': shots, 'clips': clips, 'problems': problems})

    reset = []
    for c, info in clips.items():
        sp = clip_state_path(ep, c)
        st = load_json(sp) or new_clip_state(c)
        for kind in ('image', 'video'):
            sha = info.get(f'{kind}_sha')
            if st[kind]['prompt_sha'] and sha and st[kind]['prompt_sha'] != sha and st[kind]['status'] != 'todo':
                st[kind]['status'] = 'todo'
                st[kind]['selected'] = None
                st[kind]['reset_at'] = len(st[kind]['takes'])
                st['notes'].append(f'{kind} prompt เปลี่ยน — รีเซ็ตเป็น todo')
                reset.append(f'{c} {kind}')
                if kind == 'image':  # new start frame means the video must be redone too
                    st['video']['status'] = 'todo'
                    st['video']['selected'] = None
                    st['video']['reset_at'] = len(st['video']['takes'])
            st[kind]['prompt_sha'] = sha
        save_json(sp, st)

    gen = sum(c['video_sec'] or 0 for c in clips.values())
    print(f'{ep}: Shot {len(shots)} / Clip ใหม่ {len(clips)} '
          f'(A {sum(1 for c in clips if c[0]=="A")}, B {sum(1 for c in clips if c[0]=="B")}) / '
          f'REUSE {sum(1 for s in shots if s["reuse"])} / วิดีโอที่ต้องสั่งรวม {gen} วิ')
    print(f'ภาพอ้างอิงไม่ซ้ำ: {len({r for c in clips.values() for r in c["refs"]})}')
    if reset:
        print('รีเซ็ตเพราะ prompt เปลี่ยน:', ', '.join(reset))
    for p in problems:
        print('!', p)


if __name__ == '__main__':
    main()
