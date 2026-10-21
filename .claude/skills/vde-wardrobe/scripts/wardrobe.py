"""Make missing wardrobe turnaround sheets (front / side / back) for input/characters/<name>/.

usage (from the project root):
  python .claude/skills/vde-wardrobe/scripts/wardrobe.py EP30 plan
  python .claude/skills/vde-wardrobe/scripts/wardrobe.py EP30 gen jobs.json [--quality high]

plan: lists every (character, Wxx) used in the story file that has no image yet, with the face file found
      and the shots where that outfit appears (frames to use as clothing references).
gen:  jobs.json = [{"character": "วิทย์", "wardrobe": "W08", "label": "แจ็กเก็ตหนังกลับน้ำตาล",
                    "outfit": "<English outfit description>", "person": "<English age/build, only when there is no face>",
                    "frames": ["S012", "S087"]}]
      Writes input/characters/<character>/<character> <Wxx> <label>.png and never overwrites.
"""
import argparse, glob, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, '.claude', 'skills', 'vde-episode', 'scripts'))
from fal_image import api_key, http, download, ref_data_uri  # noqa: E402

CHARS = os.path.join(ROOT, 'input', 'characters')
SHOT = re.compile(r'^#### (S\d{3}[A-Z]?) · ')
USE = re.compile(r'^-? ?([^\s(:"][^(:"]*?) \((W\d+)\)')
FACE_ONLY = ("The first reference image is the identity reference: copy this person's face, age, skin and facial features exactly. "
             "The other reference images are film stills used ONLY for the clothing: copy the outfit design, colors, fabrics and accessories, "
             "but NEVER copy the faces of the people in the film stills. ")
NO_FACE = ("The reference images are film stills used ONLY for the clothing: copy the outfit design, colors, fabrics and accessories, "
           "but invent a NEW original face matching the person description; NEVER copy the face of anyone in the film stills. ")
COMMON = ("Character wardrobe turnaround sheet, photorealistic studio photo, pure white seamless background, soft even lighting. "
          "The SAME person shown three times side by side, full body head to shoes: front view, left side profile view, back view. ")
TAIL = "No text, no watermark, no logos, no captions."


def story(ep):
    for p in (os.path.join(ROOT, 'Source', f'{ep}_แกะคลิป', f'{ep}.txt'), os.path.join(ROOT, 'input', 'story', f'{ep}.txt')):
        if os.path.exists(p):
            return p
    sys.exit(f'ไม่พบไฟล์เรื่องของ {ep}')


def frames_dir(ep):
    return os.path.join(ROOT, 'Source', f'{ep}_แกะคลิป', 'frames')


def face_file(name):
    d = os.path.join(CHARS, name)
    hits = [f for f in (os.listdir(d) if os.path.isdir(d) else []) if re.search(r'face', f, re.I)]
    return os.path.join(d, sorted(hits)[0]) if hits else None


def has_image(name, w):
    d = os.path.join(CHARS, name)
    return os.path.isdir(d) and any(re.search(rf'(^|\s){w}(\D|$)', f) for f in os.listdir(d))


def cmd_plan(a):
    lines = open(story(a.ep), encoding='utf-8-sig').read().splitlines()
    cast = set()
    for ln in lines:
        m = re.match(r'^- ([^—]+?) — ', ln)
        if m:
            cast.update(n.strip() for n in m.group(1).split(','))
    seen, shot = {}, None
    for ln in lines:
        m = SHOT.match(ln)
        if m:
            shot = m.group(1)
            continue
        m = USE.match(ln.strip())
        if m and m.group(1).strip() in cast:
            k = (m.group(1).strip(), m.group(2))
            seen.setdefault(k, [])
            if shot and shot not in seen[k]:
                seen[k].append(shot)
    out = []
    for (name, w), shots in sorted(seen.items()):
        if has_image(name, w):
            continue
        f = face_file(name)
        out.append({'character': name, 'wardrobe': w, 'face': os.path.relpath(f, ROOT) if f else None,
                    'shots': shots, 'frames_dir': os.path.relpath(frames_dir(a.ep), ROOT)})
    print(json.dumps({'missing': out}, ensure_ascii=False, indent=1))


def cmd_gen(a):
    jobs = json.load(open(a.jobs, encoding='utf-8'))
    key = api_key()
    pending = {}
    for j in jobs:
        name, w = j['character'], j['wardrobe']
        out = os.path.join(CHARS, name, f"{name} {w} {j['label']}.png")
        if os.path.exists(out) or has_image(name, w):
            print(json.dumps({'skip': f'{name} {w}', 'reason': 'มีภาพชุดนี้แล้ว'}, ensure_ascii=False))
            continue
        face = face_file(name)
        refs = ([face] if face else []) + [os.path.join(frames_dir(a.ep), f'{a.ep}_{s}.jpg') for s in j.get('frames', [])]
        refs = [r for r in refs if os.path.exists(r)][:8]
        if not refs:
            print(json.dumps({'skip': f'{name} {w}', 'reason': 'ไม่มีภาพอ้างอิง'}, ensure_ascii=False))
            continue
        if face:
            prompt = COMMON + FACE_ONLY + TAIL + ' Outfit: ' + j['outfit']
        else:
            prompt = COMMON + NO_FACE + TAIL + ' Person: ' + j.get('person', '') + ' Outfit: ' + j['outfit']
        body = {'prompt': prompt, 'image_size': {'width': 2048, 'height': 1152}, 'quality': a.quality, 'num_images': 1,
                'output_format': 'png', 'image_urls': [ref_data_uri(p) for p in refs]}
        try:
            r = http('POST', 'https://queue.fal.run/openai/gpt-image-2/edit', key, body)
        except Exception as e:  # balance / auth errors stop here so nothing half-runs silently
            print(json.dumps({'error': f'{name} {w}', 'detail': str(e)[:300]}, ensure_ascii=False))
            break
        pending[r['request_id']] = (out, name, w, bool(face))
        print(json.dumps({'submitted': f'{name} {w}', 'refs': [os.path.relpath(p, ROOT) for p in refs]}, ensure_ascii=False), flush=True)
    t0 = time.time()
    while pending and time.time() - t0 < a.wait:
        time.sleep(8)
        for rid, (out, name, w, face) in list(pending.items()):
            base = f'https://queue.fal.run/openai/gpt-image-2/requests/{rid}'
            try:
                if http('GET', base + '/status', key).get('status') != 'COMPLETED':
                    continue
                res = http('GET', base, key)
            except Exception as e:
                print(json.dumps({'failed': f'{name} {w}', 'detail': str(e)[:300]}, ensure_ascii=False))
                del pending[rid]
                continue
            del pending[rid]
            os.makedirs(os.path.dirname(out), exist_ok=True)
            download(res['images'][0]['url'], out)
            print(json.dumps({'saved': os.path.relpath(out, ROOT), 'new_face': not face}, ensure_ascii=False), flush=True)
    for rid, (out, name, w, _) in pending.items():
        print(json.dumps({'still_pending': f'{name} {w}', 'request_id': rid}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ep')
    ap.add_argument('cmd', choices=['plan', 'gen'])
    ap.add_argument('jobs', nargs='?')
    ap.add_argument('--quality', default='high', choices=['low', 'medium', 'high'])
    ap.add_argument('--wait', type=int, default=900)
    a = ap.parse_args()
    a.ep = a.ep.upper()
    if a.cmd == 'gen' and not a.jobs:
        sys.exit('ต้องระบุไฟล์ jobs.json')
    {'plan': cmd_plan, 'gen': cmd_gen}[a.cmd](a)


if __name__ == '__main__':
    main()
