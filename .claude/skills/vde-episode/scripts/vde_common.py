"""Shared helpers for the VDE production skills (collect / images / videos / edit).

Layout produced under each episode folder:
  EPxx/production/plan.json        static plan parsed from shots/ + prompts/ (written by collect.py only)
  EPxx/production/clips/A001.json  per-clip production state (each clip written by one worker only)
  EPxx/production/ref_cache.json   OpenArt visualReference per character image (written by the orchestrator only)
  EPxx/Image/EPxx_A001_T01.png     image takes
  EPxx/Video/EPxx_A001_T01.mp4     video takes
  EPxx/Edit/                       edited episode, subtitles, EDL
"""
import hashlib, json, math, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
SEP_COPY = '# ==================== ก๊อปตั้งแต่บรรทัดถัดไป ===================='

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def ep_dir(ep):
    d = os.path.join(ROOT, ep)
    if not os.path.isdir(d):
        sys.exit(f'ไม่พบโฟลเดอร์ตอน {d}')
    return d


def prod_dir(ep):
    d = os.path.join(ep_dir(ep), 'production')
    os.makedirs(os.path.join(d, 'clips'), exist_ok=True)
    return d


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, '/')


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def save_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def sha1(path):
    with open(path, 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:12]


def read_prompt(path):
    """Return (header_lines, body_text) of a prompt .txt file."""
    with open(path, encoding='utf-8-sig') as fh:
        lines = fh.read().splitlines()
    for i, line in enumerate(lines):
        if line.strip() == SEP_COPY:
            return lines[:i], '\n'.join(lines[i + 1:]).strip()
    # no separator: everything not starting with '#' is the prompt
    return [l for l in lines if l.startswith('#')], '\n'.join(l for l in lines if not l.startswith('#')).strip()


def parse_refs(header):
    """Attachment paths from '# แนบใน OpenArt: 1) path ; 2) path'. May continue on following '#' lines."""
    refs, grab = [], False
    for line in header:
        s = line.lstrip('#').strip()
        if s.startswith('แนบใน OpenArt:'):
            grab = True
            s = s[len('แนบใน OpenArt:'):]
        elif grab and re.match(r'^\d\)', s):
            pass
        else:
            grab = False
            continue
        if 'ไม่มี' in s and 'input/' not in s:
            return []
        for part in re.split(r'\s*;\s*|\s+(?=\d\)\s)', s):
            part = re.sub(r'^\d\)\s*', '', part.strip())
            if part.startswith('input/'):
                refs.append(part)
    return refs


def parse_video_seconds(header):
    for line in header:
        m = re.search(r'ยาว\s*([0-9.]+)\s*วิ', line)
        if m:
            return max(1, min(15, math.ceil(float(m.group(1)) - 1e-9)))
    return None


def clip_state_path(ep, clip):
    return os.path.join(prod_dir(ep), 'clips', f'{clip}.json')


def new_clip_state(clip):
    return {
        'clip': clip,
        'image': {'status': 'todo', 'takes': [], 'selected': None, 'prompt_sha': None},
        'video': {'status': 'todo', 'takes': [], 'selected': None, 'prompt_sha': None},
        'notes': [],
    }
