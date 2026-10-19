"""Find every prompt a blocking change can affect, so an edit does not leave stale positions behind (v68).

usage (from the project root):
  python .claude/skills/vde-episode/scripts/impact.py EP28 SC01 "terrace-side coping" "Irin" ...

Lists, in edit order, each clip of the scene whose image or video prompt contains any of the terms (case-insensitive),
with the matching lines and the clip's production status. Use it after changing the Blocking Table or a user
correction: fix the listed prompts too, or record in 00_สมมติฐาน.md why they stay (e.g. video already approved).
Editing a prompt resets that clip in production (collect.py), so prefer leaving approved clips whose picture is
unaffected, and say so.
"""
import json, os, sys

from vde_common import ROOT, prod_dir, load_json, read_prompt, clip_state_path


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    ep, scene, terms = sys.argv[1], sys.argv[2], [t.lower() for t in sys.argv[3:]]
    p = load_json(os.path.join(prod_dir(ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {ep} ก่อน')
    out = []
    for s in p['shots']:
        if s['scene'] != scene or s['reuse']:
            continue
        info = p['clips'][s['clip']]
        st = load_json(clip_state_path(ep, s['clip'])) or {}
        for kind in ('image', 'video'):
            path = info.get(f'{kind}_prompt')
            if not path:
                continue
            body = read_prompt(os.path.join(ROOT, path))[1]
            hits = [l.strip()[:220] for l in body.splitlines() if any(t in l.lower() for t in terms)]
            if hits:
                out.append({'shot': s['id'], 'clip': s['clip'], 'kind': kind, 'file': path,
                            'status': (st.get(kind) or {}).get('status'), 'lines': hits})
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'พบ {len(out)} ไฟล์ใน {scene}', file=sys.stderr)


if __name__ == '__main__':
    main()
