"""Rename characters (or any name) consistently across an episode's documents.

usage (from the project root):
  python .claude/skills/vde-rename/scripts/rename.py EP30 "เลขาชเว=เลขาเจต" "ประธานคิม=ประธานวรเทพ" [--scope story|episode|all] [--apply]

scope  story   (default) the breakdown file only: Source/EPxx_แกะคลิป/EPxx.txt or input/story/EPxx.txt
       episode story + EPxx/**/*.md (documents of that episode)
       all     episode + bible/*.md + state/*.md (series-wide; use when the name is already in the Bible)
Without --apply it only reports counts per file (dry run). Longer names are replaced first so
"ประธานคิมจุนโฮ" is not half-replaced by "ประธานคิม". Prompt files (English) and input/characters are never touched.
"""
import argparse, glob, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))


def targets(ep, scope):
    files = [p for p in (os.path.join(ROOT, 'Source', f'{ep}_แกะคลิป', f'{ep}.txt'),
                         os.path.join(ROOT, 'Source', f'{ep}_แกะคลิป', f'{ep}_บทพูด.txt'),
                         os.path.join(ROOT, 'input', 'story', f'{ep}.txt')) if os.path.exists(p)]
    if scope in ('episode', 'all'):
        files += glob.glob(os.path.join(ROOT, ep, '**', '*.md'), recursive=True)
    if scope == 'all':
        files += glob.glob(os.path.join(ROOT, 'bible', '*.md')) + glob.glob(os.path.join(ROOT, 'state', '*.md'))
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep')
    ap.add_argument('pairs', nargs='+', help='"old=new"')
    ap.add_argument('--scope', choices=['story', 'episode', 'all'], default='story')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    ep = a.ep.upper()
    pairs = []
    for p in a.pairs:
        if '=' not in p:
            sys.exit(f'รูปแบบต้องเป็น "ชื่อเดิม=ชื่อใหม่": {p}')
        old, new = (s.strip() for s in p.split('=', 1))
        if not old or old == new:
            sys.exit(f'คู่ชื่อไม่ถูกต้อง: {p}')
        pairs.append((old, new))
    pairs.sort(key=lambda x: -len(x[0]))
    files = targets(ep, a.scope)
    if not files:
        sys.exit(f'ไม่พบไฟล์ของ {ep} ในขอบเขต {a.scope}')
    report, total = [], 0
    for f in files:
        text = open(f, encoding='utf-8-sig', newline='').read()
        counts = {}
        for old, new in pairs:
            n = text.count(old)
            if n:
                counts[f'{old}→{new}'] = n
                text = text.replace(old, new)
        if counts:
            total += sum(counts.values())
            report.append({'file': os.path.relpath(f, ROOT), 'replaced': counts})
            if a.apply:
                open(f, 'w', encoding='utf-8', newline='').write(text)
    print(json.dumps({'applied': a.apply, 'scope': a.scope, 'total': total, 'files': report}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
