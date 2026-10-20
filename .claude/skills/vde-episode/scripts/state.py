"""Read and update per-clip production state.

usage (from the project root):
  python .claude/skills/vde-episode/scripts/state.py EP28 status
  python .claude/skills/vde-episode/scripts/state.py EP28 budget
  python .claude/skills/vde-episode/scripts/state.py EP28 todo image [--scene SC01]
  python .claude/skills/vde-episode/scripts/state.py EP28 todo video [--scene SC01]
  python .claude/skills/vde-episode/scripts/state.py EP28 prompt A001 image|video
  python .claude/skills/vde-episode/scripts/state.py EP28 refs-needed
  python .claude/skills/vde-episode/scripts/state.py EP28 ref-add "<input/... path>" '<visualReference json>'
  python .claude/skills/vde-episode/scripts/state.py EP28 take A001 image --file Image/EP28_A001_T01.png --job <id> --result ok|fail --qc "<note>" [--cost 42]
  python .claude/skills/vde-episode/scripts/state.py EP28 select A001 image --file Image/EP28_A001_T01.png [--flag "<note for human>"]
  python .claude/skills/vde-episode/scripts/state.py EP28 give-up A001 video --reason "<why>"
  python .claude/skills/vde-episode/scripts/state.py EP28 reset A001 image|video
  python .claude/skills/vde-episode/scripts/state.py EP28 facts A001 "<what the selected start image really shows>"
  python .claude/skills/vde-episode/scripts/state.py EP28 usable A001 2.4      -> edit.py uses the take only up to 2.4 s
"""
import argparse, json, mimetypes, os, re, sys
from vde_common import ROOT, ep_dir, prod_dir, load_json, save_json, read_prompt, clip_state_path, new_clip_state

CFG = load_json(os.path.join(os.path.dirname(__file__), '..', 'config.json'), {})
MAX_TAKES = {'image': CFG.get('max_image_takes', 3), 'video': CFG.get('max_video_takes', 3)}
DONE = ('done', 'flagged', 'gave_up')


def plan(ep):
    p = load_json(os.path.join(prod_dir(ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {ep} ก่อน')
    return p


def state(ep, clip):
    return load_json(clip_state_path(ep, clip)) or new_clip_state(clip)


def cmd_status(ep, a):
    p = plan(ep)
    rows, count = [], {}
    for c in p['clips']:
        st = state(ep, c)
        for k in ('image', 'video'):
            count[(k, st[k]['status'])] = count.get((k, st[k]['status']), 0) + 1
        flags = [t.get('flag') for k in ('image', 'video') for t in [st[k]] if t.get('flag')]
        rows.append(f"{c:5s} {p['clips'][c]['scene']:5s} ภาพ:{st['image']['status']:8s}({len(st['image']['takes'])}) "
                    f"วิดีโอ:{st['video']['status']:8s}({len(st['video']['takes'])}) {' | '.join(flags)}")
    print('\n'.join(rows))
    print('รวม:', ', '.join(f'{k} {s}={n}' for (k, s), n in sorted(count.items())))


CLOSE = re.compile(r'close-up|closeup|\bE?CU\b|\bMCU\b', re.I)


def video_model(ep, clip, info):
    """Lite reframes/dissolves on long clips and on close shots whose partner is off-frame (EP27); route those to
    the standard model. Returns (model, usd_per_sec, reason)."""
    lite = CFG.get('video_model', 'grok-imagine-video-1.5-lite')
    std = CFG.get('video_model_standard', 'grok-imagine-video-1.5')
    lite_usd, std_usd = CFG.get('grok_usd_per_sec', 0.02), CFG.get('grok_usd_per_sec_standard', 0.08)
    if lite == std or not CFG.get('video_model_routing', True):
        return lite, lite_usd, 'config'
    sec = info.get('video_sec') or 0
    if sec > CFG.get('lite_max_sec', 6):
        return std, std_usd, f'ยาว {sec} วิ เกิน lite_max_sec'
    header, body = read_prompt(os.path.join(ROOT, info['video_prompt']))
    off = any(l.startswith('# - ') for l in header[next((i for i, l in enumerate(header) if 'ไม่อยู่ในเฟรม' in l), len(header)):])
    if off and CLOSE.search(body):
        return std, std_usd, 'ช็อตใกล้ที่มีคนเกี่ยวข้องอยู่นอกเฟรม'
    return lite, lite_usd, 'lite'


def cmd_budget(ep, a):
    p = plan(ep)
    img_unit = CFG.get('openart_image_credits', 42)
    need_img = [c for c in p['clips'] if state(ep, c)['image']['status'] not in DONE]
    need_vid = [c for c in p['clips'] if state(ep, c)['video']['status'] not in DONE]
    sec = sum(p['clips'][c]['video_sec'] or 0 for c in need_vid)
    usd = sum((p['clips'][c]['video_sec'] or 0) * video_model(ep, c, p['clips'][c])[1] for c in need_vid)
    r = CFG.get('expected_retake_rate', 0.5)
    spent = {'image': 0.0, 'video': 0.0}
    for c in p['clips']:
        for k in spent:
            spent[k] += sum(t.get('cost') or 0 for t in state(ep, c)[k]['takes'])
    print(json.dumps({
        'spent_openart_credits': round(spent['image']),
        'spent_grok_usd': round(spent['video'], 2),
        'images_todo': len(need_img),
        'openart_credits_first_pass': len(need_img) * img_unit,
        'openart_credits_with_retakes': round(len(need_img) * img_unit * (1 + r)),
        'videos_todo': len(need_vid),
        'video_seconds': sec,
        'grok_usd_first_pass': round(usd, 2),
        'grok_usd_with_retakes': round(usd * (1 + r), 2),
        'grok_usd_cap': CFG.get('grok_usd_cap_per_episode'),
    }, ensure_ascii=False, indent=2))


def takes_used(sk):
    # takes made since the last reset; earlier takes keep their numbers but no longer count against the limit
    return len(sk['takes']) - sk.get('reset_at', 0)


def cmd_todo(ep, a):
    p = plan(ep)
    cache = load_json(os.path.join(prod_dir(ep), 'ref_cache.json'), {})
    out = []
    for c, info in p['clips'].items():
        if a.scene and info['scene'] != a.scene:
            continue
        st = state(ep, c)
        k = a.kind
        if st[k]['status'] in DONE:
            continue
        if k == 'video' and not st['image']['selected']:
            continue
        item = {'clip': c, 'scene': info['scene'], 'status': st[k]['status'],
                'next_take': len(st[k]['takes']) + 1, 'takes_left': MAX_TAKES[k] - takes_used(st[k]),
                'last_qc': st[k]['takes'][-1].get('qc') if st[k]['takes'] else None}
        if k == 'image':
            item['prompt_file'] = info['image_prompt']
            item['refs'] = [{'path': r, 'visualReference': cache.get(r)} for r in info['refs']]
            item['out_file'] = f"{ep}/Image/{ep}_{c}_T{item['next_take']:02d}.png"
        else:
            item['prompt_file'] = info['video_prompt']
            item['seconds'] = info['video_sec']
            item['model'], item['usd_per_sec'], item['model_reason'] = video_model(ep, c, info)
            item['start_image'] = os.path.join(ROOT, st['image']['selected']).replace('/', os.sep)
            item['out_file'] = f"{ep}/Video/{ep}_{c}_T{item['next_take']:02d}.mp4"
        out.append(item)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_prompt(ep, a):
    info = plan(ep)['clips'][a.clip]
    f = info['image_prompt' if a.kind == 'image' else 'video_prompt']
    body = read_prompt(os.path.join(ROOT, f))[1]
    if a.kind == 'video':
        # lead with the take-file id: the Grok Automation extension names downloads after the prompt's first words
        # ("SHOT EP27-S001 / CLIP A001." -> "EP27_A001 SHOT EP27-S001."), so the import can map files back to clips
        m = re.match(r'SHOT (\S+) / CLIP (\S+?)\.\s*', body)
        if m:
            body = f'{ep}_{m.group(2)} SHOT {m.group(1)}. ' + body[m.end():]
        elif not body.startswith(f'{ep}_{a.clip}'):
            body = f'{ep}_{a.clip}. ' + body
    facts = state(ep, a.clip)['image'].get('facts')
    if a.kind == 'video' and facts:
        # the selected start image wins over the planned text; telling the model what it really shows stops it
        # from 'correcting' the picture with a morph or a cut
        body += '\nIMAGE FACTS (what the supplied starting image actually shows; keep it exactly): ' + facts
    print(body)


def cmd_refs_needed(ep, a):
    p = plan(ep)
    cache = load_json(os.path.join(prod_dir(ep), 'ref_cache.json'), {})
    need = sorted({r for c in p['clips'].values() for r in c['refs']} - set(cache))
    out = []
    for r in need:
        f = os.path.join(ROOT, r)
        if os.path.exists(f):
            out.append({'path': r, 'abs': f, 'size': os.path.getsize(f),
                        'contentType': mimetypes.guess_type(f)[0] or 'image/png'})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_ref_add(ep, a):
    path = os.path.join(prod_dir(ep), 'ref_cache.json')
    cache = load_json(path, {})
    vr = json.loads(a.json)
    vr.pop('metadata', None)
    cache[a.path] = vr
    save_json(path, cache)
    print(f'บันทึก {a.path}')


def cmd_take(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    t = {'take': len(st[a.kind]['takes']) + 1, 'file': a.file, 'job': a.job, 'result': a.result, 'qc': a.qc}
    if a.cost is not None:
        t['cost'] = a.cost
    st[a.kind]['takes'].append(t)
    st[a.kind]['status'] = 'retry' if a.result != 'ok' else 'review'
    save_json(sp, st)
    print(f"{a.clip} {a.kind} take {t['take']} = {a.result}; เหลือ {MAX_TAKES[a.kind] - takes_used(st[a.kind])} ครั้ง")


def cmd_select(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    st[a.kind]['selected'] = a.file
    st[a.kind]['status'] = 'flagged' if a.flag else 'done'
    st[a.kind]['flag'] = a.flag
    if a.kind == 'image' and st['video']['status'] in DONE:
        st['video'] = {**st['video'], 'status': 'todo', 'selected': None, 'reset_at': len(st['video']['takes'])}
        st['notes'].append('เปลี่ยนภาพตั้งต้น — วิดีโอต้องสร้างใหม่')
    save_json(sp, st)
    print(f'{a.clip} {a.kind} -> {st[a.kind]["status"]}: {a.file}')


def cmd_give_up(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    st[a.kind]['status'] = 'gave_up'
    st[a.kind]['flag'] = a.reason
    save_json(sp, st)
    print(f'{a.clip} {a.kind} -> gave_up: {a.reason}')


def cmd_reset(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    st[a.kind].update({'status': 'todo', 'selected': None, 'flag': None, 'reset_at': len(st[a.kind]['takes'])})
    save_json(sp, st)
    print(f'{a.clip} {a.kind} -> todo')


def cmd_facts(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    st['image']['facts'] = a.text.strip()
    save_json(sp, st)
    print(f'{a.clip} image facts saved ({len(a.text)} chars)')


def cmd_usable(ep, a):
    sp = clip_state_path(ep, a.clip)
    st = state(ep, a.clip)
    st['video']['usable_until'] = a.seconds
    save_json(sp, st)
    print(f'{a.clip} video usable until {a.seconds} s')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('budget')
    s = sub.add_parser('todo'); s.add_argument('kind', choices=['image', 'video']); s.add_argument('--scene')
    s = sub.add_parser('prompt'); s.add_argument('clip'); s.add_argument('kind', choices=['image', 'video'])
    sub.add_parser('refs-needed')
    s = sub.add_parser('ref-add'); s.add_argument('path'); s.add_argument('json')
    s = sub.add_parser('take'); s.add_argument('clip'); s.add_argument('kind', choices=['image', 'video'])
    s.add_argument('--file'); s.add_argument('--job'); s.add_argument('--result', choices=['ok', 'fail'], required=True)
    s.add_argument('--qc', default=''); s.add_argument('--cost', type=float)
    s = sub.add_parser('select'); s.add_argument('clip'); s.add_argument('kind', choices=['image', 'video'])
    s.add_argument('--file', required=True); s.add_argument('--flag')
    s = sub.add_parser('give-up'); s.add_argument('clip'); s.add_argument('kind', choices=['image', 'video'])
    s.add_argument('--reason', required=True)
    s = sub.add_parser('reset'); s.add_argument('clip'); s.add_argument('kind', choices=['image', 'video'])
    s = sub.add_parser('facts'); s.add_argument('clip'); s.add_argument('text')
    s = sub.add_parser('usable'); s.add_argument('clip'); s.add_argument('seconds', type=float)
    a = ap.parse_args()
    ep_dir(a.ep)
    globals()['cmd_' + a.cmd.replace('-', '_')](a.ep, a)


if __name__ == '__main__':
    main()
