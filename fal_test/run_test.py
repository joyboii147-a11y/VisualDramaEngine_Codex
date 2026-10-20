"""Quality test matrix for fal openai/gpt-image-2/edit: 4 shot sizes x 4 cast setups x 2 gaze = 32 images per quality.
usage: python run_test.py <low|medium|high> [submit|collect|sheet]
"""
import json, os, subprocess, sys, time

PROJ = r'C:\Users\snoyk\OneDrive\Documents\VisualDramaEngine_Codex'
sys.path.insert(0, os.path.join(PROJ, '.claude', 'skills', 'vde-episode', 'scripts'))
import fal_image as F  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = 'openai/gpt-image-2/edit'
SIZE = {'width': 1152, 'height': 2048}

CHAR = {
    'Irin': ('input/characters/ไอริน/ไอริน W07 ชุดเดรสคลุมท้องลูกไม้สีไอวอรี่แบบเกาะอก.png',
             'Irin, a young pregnant Thai woman with a visible baby bump'),
    'Wit': ('input/characters/วิทย์/วิทย์ W05 ชุดลำลอง.png', 'Wit, a young Thai man'),
    'Mother': ('input/characters/แม่วิทย์/แม่วิทย์ W01 ชุดออกงาน.png', "Wit's mother, an elegant middle-aged Thai woman"),
    'Rita': ('input/characters/ริต้า/ริต้า W04 เดรสแดง.jpeg', 'Rita, a glamorous young Thai woman'),
}
CASTS = {
    '1p': (['Irin'], 0),
    '2p': (['Irin', 'Wit'], 0),
    '4p': (['Rita', 'Irin', 'Wit', 'Mother'], 0),
    'grp': (['Irin', 'Wit'], 7),
}
SIZES = {
    'CU': 'close-up: head and top of the shoulders fill the frame, 85mm, eye level',
    'MS': 'medium shot: framed from the waist up, 50mm, eye level',
    'LS': 'long shot: full bodies head to toe with some terrace around them, 35mm, eye level',
    'ELS': 'extreme long shot: the people are small within the wide terrace, pool and skyline, 24mm, slightly high angle',
}
GAZE = {
    'cam': 'every named main character looks straight into the camera lens',
    'away': 'no one looks at the camera; the named main characters look at each other or off to the side',
}
SETTING = ('a luxury rooftop event terrace beside a long rectangular swimming pool with white stone coping, white stone '
           'paving, a tall glass building with a lit doorway behind, black pyramid patio heaters and tall round cocktail '
           'tables, city towers beyond a white-framed glass wall, soft overcast daylight under a glass canopy. '
           'Everyone is completely dry.')


def jobs():
    for s in SIZES:
        for c in CASTS:
            for g in GAZE:
                yield f'{s}_{c}_{g}', s, c, g


def build(size, cast, gaze):
    names, extras = CASTS[cast]
    refs = [CHAR[n][0] for n in names]
    ref_lines = [f'Image {i + 1}: {n} — use for face, skin tone, hairstyle, body shape and this exact outfit. '
                 'Do not copy the background, lighting, pose or camera angle.' for i, n in enumerate(names)]
    people = '; '.join(CHAR[n][1] + f' (Image {i + 1})' for i, n in enumerate(names))
    total = len(names) + extras
    order = ' , '.join(names)
    extra_txt = (f' Behind and around them stand {extras} other well-dressed Thai party guests in small groups, '
                 'softer in focus, each in distinct formal clothing; the guests do not look at the camera.') if extras else ''
    return refs, '\n'.join([
        'Create one cinematic live-action still, photorealistic, natural skin and fabric texture. Vertical 9:16.',
        'REFERENCE IMAGES:', *ref_lines,
        f'CHARACTERS: {people}.{extra_txt}',
        f'CAST COUNT: exactly {total} people visible in the frame.',
        f'SETTING: {SETTING}',
        f'FRAMING: {SIZES[size]}.',
        f'FRAME ORDER: from screen-left to screen-right: {order}.' if len(names) > 1 else 'FRAME ORDER: Irin at center.',
        f'GAZE: {GAZE[gaze]}.',
        'No captions, subtitles, labels, watermarks, panels or collage.'])


def main():
    q, cmd = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'submit')
    out = os.path.join(HERE, q)
    os.makedirs(out, exist_ok=True)
    jf = os.path.join(out, 'jobs.json')
    state = json.load(open(jf, encoding='utf-8')) if os.path.exists(jf) else {}
    key = F.api_key()
    if cmd == 'submit':
        uri = {}
        for jid, s, c, g in jobs():
            if jid in state and state[jid]['status'] in ('pending', 'done'):
                continue
            refs, prompt = build(s, c, g)
            for r in refs:
                uri.setdefault(r, F.ref_data_uri(os.path.join(PROJ, r)))
            body = {'prompt': prompt, 'image_urls': [uri[r] for r in refs], 'image_size': SIZE, 'quality': q,
                    'num_images': 1, 'output_format': 'png'}
            try:
                r = F.http('POST', f'https://queue.fal.run/{ENDPOINT}', key, body)
            except RuntimeError as e:
                print(jid, 'SUBMIT ERROR', e)
                if any(x in str(e) for x in ('401', '403', 'balance', 'credit')):
                    break
                continue
            state[jid] = {'status': 'pending', 'status_url': r['status_url'], 'response_url': r['response_url'],
                          'request_id': r['request_id'], 'refs': len(refs), 't0': time.time()}
            json.dump(state, open(jf, 'w', encoding='utf-8'), indent=1)
        print('submitted', sum(1 for v in state.values() if v['status'] == 'pending'))
    elif cmd == 'collect':
        deadline = time.time() + 900
        while True:
            pend = 0
            for jid, v in state.items():
                if v['status'] != 'pending':
                    continue
                try:
                    s = F.http('GET', v['status_url'], key)
                    if s.get('status') != 'COMPLETED':
                        pend += 1
                        continue
                    if s.get('error'):
                        raise RuntimeError(s['error'])
                    res = F.http('GET', v['response_url'], key)
                    F.download(res['images'][0]['url'], os.path.join(out, jid + '.png'))
                    v.update(status='done', secs=round(time.time() - v['t0']))
                except Exception as e:  # report and keep going
                    v.update(status='failed', error=str(e)[:300])
                    print(jid, 'FAILED', v['error'])
            json.dump(state, open(jf, 'w', encoding='utf-8'), indent=1)
            if not pend or time.time() > deadline:
                break
            time.sleep(10)
        c = {}
        for v in state.values():
            c[v['status']] = c.get(v['status'], 0) + 1
        print(c)
    elif cmd == 'sheet':
        font = 'C\\:/Windows/Fonts/tahoma.ttf'
        for size in SIZES:
            items = [(jid, os.path.join(out, jid + '.png')) for jid, s, c, g in jobs() if s == size]
            items = [(j, p) for j, p in items if os.path.exists(p)]
            args, fil = [], []
            for i, (j, p) in enumerate(items):
                args += ['-i', p]
                fil.append(f"[{i}:v]scale=300:534,drawtext=fontfile='{font}':text='{j}':x=6:y=6:fontsize=26:"
                           f"fontcolor=yellow:box=1:boxcolor=black@0.7[v{i}]")
            k = len(items)
            lay = '|'.join(f'{(i % 4) * 300}_{(i // 4) * 534}' for i in range(k))
            fil.append(''.join(f'[v{i}]' for i in range(k)) + f'xstack=inputs={k}:layout={lay}:fill=black[o]')
            dst = os.path.join(out, f'sheet_{q}_{size}.jpg')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', *args, '-filter_complex', ';'.join(fil), '-map', '[o]',
                            '-q:v', '4', dst], check=True)
            print(dst)


if __name__ == '__main__':
    main()
