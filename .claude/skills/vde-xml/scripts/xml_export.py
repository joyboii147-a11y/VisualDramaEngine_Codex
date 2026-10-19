"""Write an editable timeline (Final Cut Pro 7 XML / xmeml v4) from the cut that edit.py made.

usage (from the project root):
  python .claude/skills/vde-xml/scripts/xml_export.py EP28

Reads EPxx/Edit/EPxx_edl.csv (order, in/out of every shot) and plan.json (mute flags), and links the original
takes in EPxx/Video/ so every cut can still be trimmed in the editor.
  - V1: one clipitem per shot, named "<shot> <clip>"; A1/A2: the stereo audio of the same take, linked to V1
  - B-roll marked "ปิดเสียง" keeps its audio clip but disabled, so it can be switched back on
  - MISSING shots (no selected take) leave a gap of the planned length
  - every shot with dialogue gets a sequence marker carrying the verbatim line
Opens in Premiere Pro (File > Import) and DaVinci Resolve (File > Import > Timeline). Subtitles stay in EPxx.srt;
loudness and music from edit.py are not in the XML.
Output: EPxx/Edit/EPxx_timeline.xml
"""
import csv, json, os, subprocess, sys
from urllib.parse import quote
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'vde-episode', 'scripts'))
from vde_common import ROOT, ep_dir, prod_dir, load_json  # noqa: E402

W, H, FPS = 720, 1280, 24


def frames(sec):
    return int(round(float(sec) * FPS))


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height',
                        '-of', 'json', p], capture_output=True, text=True, encoding='utf-8', errors='replace')
    j = json.loads(r.stdout or '{}')
    v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), {})
    return {'dur': frames(j.get('format', {}).get('duration', 0)), 'w': v.get('width', W), 'h': v.get('height', H),
            'audio': any(s.get('codec_type') == 'audio' for s in j.get('streams', []))}


def pathurl(p):
    return 'file://localhost/' + quote(os.path.abspath(p).replace('\\', '/'), safe='/:')


def rate():
    return f'<rate><timebase>{FPS}</timebase><ntsc>FALSE</ntsc></rate>'


def file_xml(fid, src, info, first):
    if not first:
        return f'<file id="{fid}"/>'
    audio = ('<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics>'
             '<channelcount>2</channelcount></audio>') if info['audio'] else ''
    return (f'<file id="{fid}"><name>{escape(os.path.basename(src))}</name><pathurl>{pathurl(src)}</pathurl>{rate()}'
            f'<duration>{info["dur"]}</duration><media><video><samplecharacteristics>{rate()}'
            f'<width>{info["w"]}</width><height>{info["h"]}</height><pixelaspectratio>square</pixelaspectratio>'
            f'</samplecharacteristics></video>{audio}</media></file>')


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ep = sys.argv[1]
    out_dir = os.path.join(ep_dir(ep), 'Edit')
    edl = os.path.join(out_dir, f'{ep}_edl.csv')
    if not os.path.exists(edl):
        sys.exit(f'ยังไม่มี {edl} — รัน vde-edit ก่อน')
    with open(edl, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    shots = {s['id']: s for s in (load_json(os.path.join(prod_dir(ep), 'plan.json')) or {}).get('shots', [])}

    files, v_items, a_items, markers, warnings = {}, [], [[], []], [], []
    # place every shot where edit.py put it (timeline_start), so EPxx.srt lines up with this timeline too
    bounds = [frames(r['timeline_start']) for r in rows] + [frames(float(rows[-1]['timeline_start']) + float(rows[-1]['length']))]
    t = bounds[-1]
    for n, r in enumerate(rows, 1):
        start, end = bounds[n - 1], bounds[n]
        length = max(1, end - start)
        if r['dialogue']:
            markers.append(f'<marker><name>{escape(r["shot"])}</name><comment>{escape(r["dialogue"])}</comment>'
                           f'<in>{start}</in><out>-1</out></marker>')
        if r['type'] == 'MISSING':
            warnings.append(f'{r["shot"]} ({r["clip"]}): ไม่มีวิดีโอ — เว้นช่องว่าง {length} เฟรม')
            continue
        src = os.path.join(ROOT, r['source'])
        if not os.path.exists(src):
            warnings.append(f'{r["shot"]}: ไม่พบไฟล์ {r["source"]} — เว้นช่องว่าง')
            continue
        first = src not in files
        if first:
            files[src] = {'id': f'file-{len(files) + 1}', **probe(src)}
        info = files[src]
        name = escape(f'{r["shot"]} {r["clip"]}')
        src_in = max(0, min(frames(r['in']), info['dur'] - length))
        common = (f'<name>{name}</name><duration>{info["dur"]}</duration>{rate()}<start>{start}</start><end>{end}</end>'
                  f'<in>{src_in}</in><out>{src_in + length}</out>')
        links = ''.join(f'<link><linkclipref>{k}-{n}</linkclipref></link>' for k in ('v', 'a1', 'a2')) if info['audio'] else ''
        v_items.append(f'<clipitem id="v-{n}">{common}{file_xml(info["id"], src, info, first)}{links}</clipitem>')
        if info['audio']:
            muted = bool(shots.get(r['shot'], {}).get('mute'))
            for ch in (0, 1):
                a_items[ch].append(
                    f'<clipitem id="a{ch + 1}-{n}">{common}<enabled>{"FALSE" if muted else "TRUE"}</enabled>'
                    f'<file id="{info["id"]}"/><sourcetrack><mediatype>audio</mediatype><trackindex>{ch + 1}</trackindex>'
                    f'</sourcetrack>{links}</clipitem>')

    fmt = (f'<format><samplecharacteristics>{rate()}<width>{W}</width><height>{H}</height>'
           f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>')
    a_tracks = ''.join(f'<track>{"".join(items)}<outputchannelindex>{ch + 1}</outputchannelindex></track>'
                       for ch, items in enumerate(a_items))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
           f'<sequence id="sequence-1"><name>{escape(ep)}_ตัดต่อ</name><duration>{t}</duration>{rate()}'
           f'<timecode>{rate()}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>'
           f'<media><video>{fmt}<track>{"".join(v_items)}</track></video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{a_tracks}</audio></media>{"".join(markers)}'
           '</sequence></xmeml>\n')
    out = os.path.join(out_dir, f'{ep}_timeline.xml')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(xml)
    print(json.dumps({'xml': out, 'frames': t, 'seconds': round(t / FPS, 2), 'clips': len(v_items),
                      'source_files': len(files), 'markers': len(markers), 'warnings': warnings},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
