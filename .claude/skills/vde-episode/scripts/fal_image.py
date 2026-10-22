"""Generate start images through fal.ai (OpenAI GPT Image 2) instead of OpenArt.

usage (from the project root):
  python .claude/skills/vde-episode/scripts/fal_image.py check
  python .claude/skills/vde-episode/scripts/fal_image.py EP28 submit [--scene SC01] [--clips A001,B002] [--dry-run]
  python .claude/skills/vde-episode/scripts/fal_image.py EP28 collect [--scene SC01] [--wait 600]

submit  : every todo image clip (or the ones named) is sent to the fal queue with its prompt verbatim and its
          reference images (from the prompt header) attached as data URIs — no upload step. Clips that already
          have a pending fal job are skipped, so running it twice never double-sends. --dry-run prints what would be
          sent without calling fal.
collect : polls the pending jobs, downloads finished images to the out_file that `state.py todo` gave, and prints
          one line per clip. It does NOT record takes: review each image, then use `state.py take/select` as usual.

API key : env FAL_KEY, else ~/.claude/secrets/fal_key.dpapi (Windows DPAPI, made with set-fal-key). Never printed.
Settings: config.json fal_* keys (endpoint, size, quality, max refs, price estimate).
Jobs    : EPxx/production/fal_jobs/<clip>.json (one file per clip, safe for parallel scene workers)
"""
import argparse, base64, json, os, subprocess, sys, time, urllib.error, urllib.request

from vde_common import ROOT, prod_dir, load_json, save_json, read_prompt, clip_state_path, new_clip_state

CFG = load_json(os.path.join(os.path.dirname(__file__), '..', 'config.json'), {})
EDIT = CFG.get('fal_image_endpoint', 'openai/gpt-image-2/edit')      # with reference images
TEXT = CFG.get('fal_text_endpoint', 'openai/gpt-image-2')            # no reference images
SIZE = CFG.get('fal_image_size', {'width': 1152, 'height': 2048})
QUALITY = CFG.get('fal_quality', 'medium')
MAX_REFS = CFG.get('fal_max_refs', 8)
REF_EDGE = CFG.get('fal_ref_max_edge', 1536)
USD = CFG.get('fal_usd_per_image', 0.06)
USD_HIGH = CFG.get('fal_usd_per_image_high', 0.25)
MAX_TAKES = CFG.get('max_image_takes', 3)
DONE = ('done', 'flagged', 'gave_up')
KEY_FILE = os.path.join(os.path.expanduser('~'), '.claude', 'secrets', 'fal_key.dpapi')


def api_key():
    k = os.environ.get('FAL_KEY', '').strip()
    if k:
        return k
    if os.path.exists(KEY_FILE):
        r = subprocess.run(['pwsh', '-NoProfile', '-Command',
                            f"ConvertTo-SecureString (Get-Content '{KEY_FILE}' -Raw) | ConvertFrom-SecureString -AsPlainText"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        sys.exit('ถอดรหัส fal_key.dpapi ไม่ได้ — ตั้ง key ใหม่ด้วย set-fal-key.ps1')
    sys.exit(f'ไม่พบ fal API key — ตั้ง env FAL_KEY หรือรัน set-fal-key.ps1 (จะเก็บที่ {KEY_FILE})')


def http(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': f'Key {key}', 'Content-Type': 'application/json', 'User-Agent': 'vde-fal/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        msg = e.read().decode('utf-8', 'replace')[:500]
        raise RuntimeError(f'HTTP {e.code}: {msg}') from None


def download(url, dest):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as fh:
            fh.write(r.read())
    except urllib.error.URLError:
        # Python on this PC lacks the CA chain of fal's media CDN; Windows curl uses the system store
        r = subprocess.run(['curl', '-sSfL', '--retry', '2', '-o', dest, url], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f'ดาวน์โหลดไม่สำเร็จ: {r.stderr.strip()[:300]}')


def ref_data_uri(path):
    """Downscale a reference to REF_EDGE px JPEG so requests stay small (refs are often 5 MB phone photos)."""
    vf = f"scale='min({REF_EDGE},iw)':'min({REF_EDGE},ih)':force_original_aspect_ratio=decrease"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf, '-frames:v', '1', '-q:v', '3',
                        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'], capture_output=True)
    if r.returncode or not r.stdout:
        sys.exit(f'แปลงภาพอ้างอิงไม่ได้: {path}\n{r.stderr.decode("utf-8", "replace")[-300:]}')
    return 'data:image/jpeg;base64,' + base64.b64encode(r.stdout).decode()


def jobs_dir(ep):
    d = os.path.join(prod_dir(ep), 'fal_jobs')
    os.makedirs(d, exist_ok=True)
    return d


def todo(ep, scene, clips):
    p = load_json(os.path.join(prod_dir(ep), 'plan.json'))
    if not p:
        sys.exit(f'ยังไม่มี plan.json — รัน collect.py {ep} ก่อน')
    out = []
    for c, info in p['clips'].items():
        if (scene and info['scene'] != scene) or (clips and c not in clips):
            continue
        st = load_json(clip_state_path(ep, c)) or new_clip_state(c)
        im = st['image']
        if im['status'] in DONE and not clips:
            continue
        used = len(im['takes']) - im.get('reset_at', 0)
        if used >= MAX_TAKES:
            print(f'! {c}: ครบ {MAX_TAKES} take แล้ว — ข้าม (ใช้ state.py reset ถ้าจะทำต่อ)', file=sys.stderr)
            continue
        out.append({'clip': c, 'scene': info['scene'], 'prompt_file': info['image_prompt'], 'refs': info['refs'],
                    'quality': info.get('image_quality') or QUALITY,
                    'out_file': f"{ep}/Image/{ep}_{c}_T{len(im['takes']) + 1:02d}.png"})
    return out


def cmd_check(_):
    key = api_key()
    print(json.dumps({'key': 'ok', 'source': 'env FAL_KEY' if os.environ.get('FAL_KEY') else KEY_FILE,
                      'edit_endpoint': EDIT, 'text_endpoint': TEXT, 'size': SIZE, 'quality': QUALITY,
                      'max_refs': MAX_REFS, 'usd_per_image_estimate': USD}, ensure_ascii=False, indent=1))
    del key


def cmd_submit(ep, a):
    clips = set(a.clips.split(',')) if a.clips else None
    items = todo(ep, a.scene, clips)
    jd = jobs_dir(ep)
    key = None if a.dry_run else api_key()
    sent, skipped = [], []
    for it in items:
        jf = os.path.join(jd, f"{it['clip']}.json")
        old = load_json(jf)
        if old and old.get('status') == 'pending':
            skipped.append(f"{it['clip']} (มีงานค้าง {old['request_id']})")
            continue
        if old and old.get('status') == 'done' and old.get('out_file') == it['out_file']:
            skipped.append(f"{it['clip']} ({it['out_file']} ยังไม่ได้บันทึก take — ตรวจแล้วรัน state.py take ก่อน)")
            continue
        prompt = read_prompt(os.path.join(ROOT, it['prompt_file']))[1]
        refs = [r for r in it['refs'] if os.path.exists(os.path.join(ROOT, r))][:MAX_REFS]
        missing = [r for r in it['refs'] if not os.path.exists(os.path.join(ROOT, r))]
        body = {'prompt': prompt, 'image_size': SIZE, 'quality': it['quality'], 'num_images': 1, 'output_format': 'png'}
        endpoint = TEXT
        if refs:
            endpoint = EDIT
            body['image_urls'] = [ref_data_uri(os.path.join(ROOT, r)) for r in refs]
        row = {'clip': it['clip'], 'endpoint': endpoint, 'quality': it['quality'], 'refs': refs,
               'out_file': it['out_file'], 'prompt_chars': len(prompt)}
        if missing:
            row['missing_refs'] = missing
        if len(it['refs']) > MAX_REFS:
            row['refs_dropped'] = it['refs'][MAX_REFS:]
        if a.dry_run:
            row['payload_kb'] = round(len(json.dumps(body)) / 1024)
            sent.append(row)
            continue
        try:
            r = http('POST', f'https://queue.fal.run/{endpoint}', key, body)
        except RuntimeError as e:
            row['error'] = str(e)
            sent.append(row)
            if '401' in str(e) or '403' in str(e) or 'balance' in str(e).lower():
                break  # bad key or no credit: stop instead of failing every clip
            continue
        save_json(jf, {**row, 'status': 'pending', 'request_id': r['request_id'], 'status_url': r['status_url'],
                       'response_url': r['response_url'], 'submitted': time.strftime('%Y-%m-%d %H:%M:%S')})
        sent.append({**row, 'request_id': r['request_id']})
    usd = sum(USD_HIGH if r.get('quality') == 'high' else USD for r in sent)
    print(json.dumps({'dry_run': a.dry_run, 'count': len(sent), 'usd_estimate': round(usd, 2),
                      'jobs': sent, 'skipped': skipped}, ensure_ascii=False, indent=1))


def cmd_collect(ep, a):
    jd = jobs_dir(ep)
    key = api_key()
    # --scene: only this scene's jobs, so parallel scene workers do not wait on or download each other's
    mine = None
    if a.scene:
        p = load_json(os.path.join(prod_dir(ep), 'plan.json')) or {'clips': {}}
        mine = {c for c, info in p['clips'].items() if info['scene'] == a.scene}
    deadline = time.time() + a.wait
    while True:
        pending = []
        for f in sorted(os.listdir(jd)):
            j = load_json(os.path.join(jd, f))
            if not j or j.get('status') != 'pending' or (mine is not None and j['clip'] not in mine):
                continue
            try:
                s = http('GET', j['status_url'], key)
                if s.get('status') != 'COMPLETED':
                    pending.append(j['clip'])
                    continue
                if s.get('error'):
                    raise RuntimeError(f"{s.get('error_type', '')}: {s['error']}")
                res = http('GET', j['response_url'], key)
                url = res['images'][0]['url']
                dest = os.path.join(ROOT, j['out_file'])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                download(url, dest)
                im = res['images'][0]
                j.update({'status': 'done', 'width': im.get('width'), 'height': im.get('height')})
            except (RuntimeError, KeyError, IndexError, urllib.error.URLError) as e:
                j.update({'status': 'failed', 'error': str(e)[:500]})
            j['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
            save_json(os.path.join(jd, f), j)
            print(json.dumps({k: j.get(k) for k in ('clip', 'status', 'out_file', 'request_id', 'width', 'height', 'error')
                              if j.get(k) is not None}, ensure_ascii=False))
        if not pending or time.time() >= deadline:
            break
        time.sleep(10)
    print(json.dumps({'still_pending': pending}, ensure_ascii=False))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        return cmd_check(None)
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument('ep')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('submit'); s.add_argument('--scene'); s.add_argument('--clips'); s.add_argument('--dry-run', action='store_true')
    s = sub.add_parser('collect'); s.add_argument('--scene'); s.add_argument('--wait', type=int, default=600)
    a = ap.parse_args()
    {'submit': cmd_submit, 'collect': cmd_collect}[a.cmd](a.ep, a)


if __name__ == '__main__':
    main()
