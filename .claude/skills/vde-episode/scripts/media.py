"""File transfer and inspection helpers.

usage (from the project root):
  python .claude/skills/vde-episode/scripts/media.py upload "<signURL>" "<file>" <contentType>
  python .claude/skills/vde-episode/scripts/media.py fetch "<url>" EP28/Video/EP28_A001_T01.mp4
  python .claude/skills/vde-episode/scripts/media.py frames EP28/Video/EP28_A001_T01.mp4   -> 3 QC frames (jpg)
  python .claude/skills/vde-episode/scripts/media.py probe EP28/Video/EP28_A001_T01.mp4
  python .claude/skills/vde-episode/scripts/media.py wait 30
"""
import json, os, subprocess, sys, time, urllib.request
from vde_common import ROOT


def absp(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration',
                          '-of', 'json', path], capture_output=True, text=True)
    if out.returncode:
        return {'ok': False, 'error': out.stderr.strip()}
    j = json.loads(out.stdout)
    v = next((s for s in j.get('streams', []) if s['codec_type'] == 'video'), {})
    return {'ok': True, 'width': v.get('width'), 'height': v.get('height'),
            'duration': round(float(j.get('format', {}).get('duration', 0) or 0), 2),
            'has_audio': any(s['codec_type'] == 'audio' for s in j.get('streams', []))}


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'upload':
        url, f, ctype = args
        data = open(absp(f), 'rb').read()
        req = urllib.request.Request(url, data=data, method='PUT',
                                     headers={'Content-Type': ctype, 'Content-Length': str(len(data))})
        with urllib.request.urlopen(req, timeout=300) as r:
            print(f'upload HTTP {r.status} {len(data)} bytes')
    elif cmd == 'fetch':
        url, dest = args
        dest = absp(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=300) as r, open(dest, 'wb') as fh:
                    fh.write(r.read())
                break
            except Exception as e:  # transient CDN errors
                if attempt == 2:
                    sys.exit(f'ดาวน์โหลดไม่สำเร็จ: {e}')
                time.sleep(5)
        info = {'file': dest, 'bytes': os.path.getsize(dest)}
        if dest.lower().endswith(('.mp4', '.mov', '.webm')):
            info.update(probe(dest))
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == 'frames':
        src = absp(args[0])
        d = probe(src)['duration'] or 1
        outdir = os.path.join(os.path.dirname(src), '_qc')
        os.makedirs(outdir, exist_ok=True)
        base = os.path.splitext(os.path.basename(src))[0]
        outs = []
        for name, t in (('start', 0.3), ('mid', d / 2), ('end', max(0, d - 0.3))):
            o = os.path.join(outdir, f'{base}_{name}.jpg')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t:.2f}', '-i', src, '-frames:v', '1',
                            '-vf', 'scale=360:-2', o], check=True)
            outs.append(o)
        print('\n'.join(outs))
    elif cmd == 'probe':
        print(json.dumps(probe(absp(args[0])), ensure_ascii=False))
    elif cmd == 'wait':
        time.sleep(float(args[0]))
        print('ok')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
