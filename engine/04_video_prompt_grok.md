# 04 — Video Prompt สำหรับ Grok Imagine (`prompt_writer`)

ใช้คู่กับ engine/03 หัวข้อ 1 (กฎความจำศูนย์) ทุกข้อ

## 1. หลักการ

- เส้นทางหลักคือ **image-to-video**: ผู้ใช้แนบภาพที่เลือกจาก OpenArt **ของคลิปเดียวกัน** พร้อมข้อความจากไฟล์ video ในคำขอเดียวกัน ทุกคลิปเป็นอิสระต่อกัน ไม่ต้องรอคลิปอื่นเสร็จ ชื่อไฟล์ที่พิมพ์ใน prompt ไม่ได้ทำให้ Grok ได้รับภาพ
- ภาพตั้งต้นไม่ยกเว้นการเขียนรายละเอียด ต้องขยายผัง ตัวละคร ชุด ตำแหน่ง กล้อง พื้นหลัง สิ่งนอกเฟรม แสง พร็อพ ครบ และ**ต้องตรงกับภาพ** ห้ามเขียนขัดกับภาพ เพราะภาพมีน้ำหนักเหนือข้อความ ถ้าขัดกัน ผลจะเพี้ยน
- Codex ไม่เห็นภาพจริง Start State ใน video prompt จึงต้องตรงกับ START STATE ใน image prompt ของคลิปเดียวกันเสมอ
- ไม่ต้องใส่ negative prompt ยาว เขียนสิ่งที่ต้องการให้เกิด
- ไม่ส่งบทก่อนหน้าหรือบทถัดไปเข้า prompt ใส่เฉพาะเจตนาที่จำเป็น ไม่งั้น Grok อาจพูดซ้ำ
- ไม่ใช้ "same as previous shot", "continue the scene", "use the earlier voice" หรือรหัสเสียงเปล่า
- ความยาว อัตราส่วน และโมเดลถูกตั้งโดย skill `vde-videos` (Claude Code) หรือผู้ใช้ในหน้าเว็บ ข้อความใน prompt ไม่เปลี่ยน setting
- End State เป็นเป้าหมาย ไม่ใช่การรับประกันว่า Grok จะจบตรงทุกครั้ง

**สาเหตุหลักของ transition และฉากหลังหลอน (v68 จากผล EP27):** โมเดลวิดีโอพยายาม "เปิดให้เห็น" ทุกอย่างที่ prompt เอ่ยถึง ช็อตใกล้ที่บรรยายคนนอกเฟรม ห้องทั้งห้อง หรือพร็อพนอกกรอบ จะถูกถอยกล้อง ตัดภาพ หรือ dissolve ไปหาสิ่งนั้น ส่วนภาพกว้างที่ทุกคนอยู่ในเฟรมแล้วออกมาสะอาด กฎที่ตามมา:
- SCENE GEOGRAPHY ใน video prompt บรรยายเฉพาะสิ่งที่อยู่ในเฟรมและฉากหลังที่เห็น ไม่บรรยายผังทั้งห้อง
- OFF-FRAME มีได้แค่เป้าสายตาแบบไม่ระบุรายละเอียด และต้องจบด้วย "No one else enters the frame at any time."
- **ชุดใน VISIBLE CAST บรรยายเฉพาะส่วนที่อยู่ในเฟรม:** ช็อตที่ไม่เห็นเท้า ห้ามมีรองเท้า (EP27: "stiletto pumps"/"pointed heels" ทำให้ Grok ถอยกล้องให้เห็นเท้า และในฉากสระทำให้ตัวละครยืนน้ำตื้น) ช็อตที่ไม่เห็นมือ ห้ามมีแหวน/ของในมือ — คำ LOCKED ใน image prompt ยังใช้ครบได้ แต่ video prompt ตัดส่วนที่อยู่นอก crop
- สายตาที่มองหาคนนอกเฟรม ให้เขียนว่า "only her eyes turn; the camera does not follow her gaze" ไม่บรรยายว่ามองหาใครที่อยู่ตรงไหน
- คลิปที่ผลิตยาวกว่าบท (extension ให้แค่ 6/10 วิ) ต้องสั่งช่วงท้ายให้ชัด: "stays still … until the very end of the clip; the framing does not change" ช่วงว่างที่ไม่มีคำสั่งคือจุดที่โมเดลใส่ transition
- CAMERA ค่าเริ่มต้นคือ "locked-off, the framing never changes" ใช้กล้องเคลื่อนเฉพาะเมื่อ Shot สั่ง และระบุจุดจบของการเคลื่อน
- ทุกไฟล์ต้องมีบรรทัด "One continuous take: no cuts, no transitions, no dissolves, no fades, no zoom-out or reframing."
- คลิปเกิน `lite_max_sec` จะถูกส่งไปโมเดลปกติอัตโนมัติ ให้ shot_planner แบ่งคลิปตาม engine/02 หัวข้อ 6
- หลังเลือกภาพตั้งต้นแล้ว Claude Code จะเติมบล็อก `IMAGE FACTS` (สิ่งที่ภาพจริงแสดง) ต่อท้าย prompt ตอนส่ง ไม่ต้องเขียนในไฟล์

## 2. แม่แบบ Video Prompt

**บรรทัดแรกต้องขึ้นต้นด้วยรหัสไฟล์ take (v68):** `[EPxx]_[Clip ID] SHOT [Shot ID].` เช่น `EP28_A001 SHOT EP28-S001.` เพราะ extension Grok Automation ตั้งชื่อไฟล์ดาวน์โหลดจากคำแรกของ prompt (ได้ `001_EP28_A001-SHOT-EP28-S001-…`) ทำให้ระบบนำวิดีโอกลับเข้าคลิปและตัดต่อได้ถูก Shot (prompt เก่าที่ขึ้นต้น `SHOT … / CLIP ….` ถูกแปลงให้อัตโนมัติตอนดึงด้วย `state.py prompt`)

```text
[EPxx]_[Clip ID] SHOT [Shot ID]. One continuous cinematic live-action shot, vertical 9:16.
TARGET DURATION: [n] seconds including handles.
Animate the supplied starting image. Use only this request's image and instructions.
One continuous take: no cuts, no transitions, no dissolves, no fades, no zoom-out or reframing.
SCENE GEOGRAPHY: [only the part of the set inside the frame and the background seen behind
the cast; positions of visible characters relative to landmarks].
VISIBLE CAST: [each name, hair, complete wardrobe and accessories, world position, pose,
facing and eyeline; exact count including partial foreground people; FRAME ORDER from
screen-left to screen-right copied from the Setup Map].
CAMERA POSITION / VIEW DIRECTION / AXIS SIDE: [position relative to fixed landmarks,
viewing direction, axis side, camera height, framing and lens].
FOREGROUND / VISIBLE BACKGROUND: [named foreground owner if any; wall and details behind
the subject derived from the viewing direction].
OFF-FRAME: [eyeline target only, e.g. "the person she answers is beyond the right frame
edge"]. No one else enters the frame at any time.
LIGHTING / COLOR: [source, direction in the room, softness, color and grade].
PROP STATE: [visible objects only, positions, holders and hands at clip start].
[For OTS: foreground owner, visible hair and outer garment, focused subject;
preserve both identities throughout the clip.]
START STATE: [pose, facing, eyeline, expression, hands and prop state matching the image].
PERFORMANCE CONTEXT: [current intention and emotion, without quoting other dialogue].
ACTION: [named actor or object + ordered physical actions; timing only where useful].
END STATE: [intended final pose, gaze, expression, hands and prop position].
CAMERA: [default "locked-off, the framing never changes"; or one planned continuous
movement with direction and endpoint].
VISUAL CONTINUITY: Preserve the starting image's faces, hair, wardrobe, set geometry,
lighting character and color treatment. Allow only the specified actions and camera
movement. No unplanned cuts, added people, identity swaps or prop teleportation.
[ONE AUDIO MODE FROM SECTION 3, fully resolved.]
```

- ACTION และ expression ต้องเป็นสิ่งที่มองเห็นได้ ใช้ข้อมูลจากช่อง Expression/Action ใน Emotion Map
- **การเดิน** ใน ACTION ต้องระบุจุดเริ่ม ทิศ ปลายทาง และคนที่เดินเข้าหา เช่น "Irin and Wit walk side by side from the back of the room toward Wit's mother at the left end of the drinks table and stop beside her, facing the two guests" และระบุปฏิกิริยาของคนที่ถูกเข้าหา ห้ามเขียนแค่ "walk in" หรือ "walk forward"
- คนที่อยู่ในเฟรมแต่ไม่ใช่จุดสนใจ (เช่น ริต้าที่แท่นข้างๆ) ต้องมี ACTION ของตัวเองสั้นๆ เช่น "Rita, at the adjacent display, keeps examining a ring with her black-gloved hand" ไม่ปล่อยให้ยืนนิ่งหรือหายไป
- คนที่จะเข้าเฟรมภายหลังต้องบรรยายเต็มจาก Bible ถ้าต้องเห็นหน้าชัดและไม่มีในภาพตั้งต้น ผลจะไม่นิ่ง ให้รายงานกลับและเสนอ coverage แบบอื่น
- มอนทาจ: prompt สั้นได้ในส่วน ACTION แต่ส่วนฉาก ตัวละคร กล้อง แสง ยังต้องครบ

## 3. เสียง — เลือกหนึ่งโหมดต่อคลิป

ใช้โหมดตามที่ shot_planner ระบุในช่องบทพูด/เสียงของ Shot

**โหมด A: Grok สร้างบทพูดในคลิป** (ค่าเริ่มต้นเมื่อมีบทพูด)

```text
AUDIO MODE: generated dialogue.
SPEECH EVENT 1:
SPEAKER: [name + visible identifier, ON / OS / VO].
EXACT THAI DIALOGUE: "[verbatim line for this clip]"
VOICE IDENTITY: [copied verbatim from bible/ตัวละคร.md].
DELIVERY: [this clip's emotion, pace and energy from the Emotion Map].
[ON: Lip-sync only the assigned visible speaker.]
[OS/VO: The speaker is not visible; no visible person lip-syncs to this voice.]
NON-SPEAKERS: [visible names]; no speech-like lip movements.
Speak only the assigned dialogue exactly once, without paraphrasing or added words.
Do not stretch speech to fill the clip. No unassigned voices.
AFTER SPEECH: [planned silent action or brief hold until the cut].
AMBIENCE/SFX: [allowed sounds].
```

- **เสียงที่ไม่ใช่คำพูด** (กรี๊ด หัวเราะ สะอื้น อุทาน "อ๊ะ" ที่บทเขียนเป็นคำเลียนเสียง) ห้ามใส่ใน `EXACT THAI DIALOGUE` เพราะ Grok จะพูดออกมาเป็นคำ (EP27 A027: ตะโกนคำว่า "กรี๊ด" แทนการกรีดร้อง) ให้เขียนเป็น `SOUND EVENT n (NOT SPEECH):` บรรยายเสียง ความยาว และย้ำ "no words, no syllables, no consonants" — Ledger และซับยังใช้ข้อความต้นฉบับตรงตัว
- ลบตัวเลือก ON/OS/VO ที่ไม่ใช้ออก
- ผู้พูดสองคนให้เพิ่ม SPEECH EVENT ตามลำดับ พร้อมข้อมูลเสียงครบทุกคน ไม่สั่งให้คนที่จะพูดทีหลังเงียบตลอดคลิป
- **Voice Identity คัดลอกจาก Bible ตรงตัวทุกคลิป** ส่วน Delivery เปลี่ยนตามอารมณ์
- เสียงในใจ (`[เสียงในใจ]` ใน Dialogue Ledger) ใช้ VO ของตัวละครนั้น ปากไม่ขยับ
- ไม่เพิ่มผู้บรรยายเอง

**โหมด B: พากย์ทีหลัง**

```text
AUDIO MODE: picture for separately edited dialogue.
Do not generate intelligible speech or background chatter.
PERFORMANCE: [listening, reaction or action matching the intended dialogue timing].
AMBIENCE/SFX: [specified sounds or intentional silence].
```

บทเต็มและ Voice Identity อยู่ในช่องบทพูดของ Shot ไม่อยู่ในคำสั่งให้ Grok พูด Shot ที่เห็นปากต้องลิปซิงก์ภายหลัง หรือเลือก coverage ที่ไม่เห็นปาก

**โหมด C: ไม่มีบทพูด** (B-roll, Reaction, Insert, มอนทาจ)

```text
AUDIO MODE: no dialogue.
No intelligible speech or speech-like lip-sync.
AMBIENCE/SFX: [allowed sounds, including scripted nonverbal breathing or gasps].
```

ไม่บังคับปิดปากถ้าการแสดงต้องหอบหรือตกใจ

## 4. ทางเลือก Text-to-video

ใช้เมื่อผู้ใช้สั่งว่าไม่ส่งภาพเข้า Grok เท่านั้น ขยาย Identity, Wardrobe, Location, Lighting, Grade, Camera ลง prompt เต็ม แล้วใช้ Action/End State/Audio ตามแม่แบบเดิม และระบุว่าใบหน้าและฉากข้ามคลิปไม่นิ่งเท่า image-to-video ห้ามสลับมาใช้เส้นทางนี้เอง

## 5. ตัวอย่าง Video Prompt — มินพูด CU (โหมด A)

```text
EP01_A005 SHOT EP01-S005. One continuous cinematic live-action close-up, vertical 9:16.
TARGET DURATION: 7 seconds including handles.
Animate the supplied starting image. Use only this request's image and instructions.
SCENE GEOGRAPHY: a small office with an oak desk. Min sits at the west side of the desk;
her unseen partner sits opposite at the east side. Pale gray plaster west wall; daylight
from a window in the east wall.
VISIBLE CAST: exactly one person: Min, a Thai woman in her early thirties with a straight
black chin-length bob tucked behind both ears, wearing an ivory cotton collared blouse with
plain buttons and no visible jewelry. She is seated upright at the west side of the desk,
three-quarter facing the camera, eyes directed slightly screen-right toward her unseen
partner.
CAMERA POSITION / VIEW DIRECTION / AXIS SIDE: southeast of Min, looking diagonally northwest
toward her, on the south side of the dialogue axis; seated eye level; close-up from upper
chest to head; 85mm full-frame equivalent.
FOREGROUND / VISIBLE BACKGROUND: no foreground person; softly defocused pale gray west wall
behind Min.
OFF-FRAME: the east-wall window is behind the camera; the desk top and a manila envelope
lie below the crop; the partner is outside the frame to screen-right.
LIGHTING / COLOR: soft daylight from the east window, reaching the front and camera-right
side of her face; neutral skin tones, muted warm wood, restrained saturation.
PROP STATE: both of Min's hands rest in her lap below the frame; the envelope stays on the
desk out of frame.
START STATE: Min is seated upright, lips closed, brows slightly drawn, gaze slightly
screen-right.
PERFORMANCE CONTEXT: Min feels hurt at being excluded from an important decision and states
that hurt firmly, without shouting or crying.
ACTION: Min takes a small breath, delivers the assigned line while keeping her gaze
screen-right, then gently closes her lips. Her hands remain in her lap.
END STATE: Min stays seated, lips closed, gaze on the unseen partner, shoulders still.
CAMERA: static close-up throughout; no zoom, pan or cut.
VISUAL CONTINUITY: Preserve the starting image's face, bob haircut, ivory blouse, background
geometry, soft front-right daylight and muted color treatment. Allow only the specified
actions. No unplanned cuts, added people, identity swaps or prop teleportation.
AUDIO MODE: generated dialogue.
SPEECH EVENT 1:
SPEAKER: Min, visible on screen (ON), the only speaker.
EXACT THAI DIALOGUE: "มีสิ แต่เธอไม่เคยถามฉัน"
VOICE IDENTITY: adult Thai woman, medium register, clear slightly breathy timbre, standard
Central Thai accent, precise consonants and soft vocal onset.
DELIVERY: restrained hurt, firm and conversational, a brief natural pause after "มีสิ".
Lip-sync only Min to the assigned line.
NON-SPEAKERS: none visible.
Speak only the assigned dialogue exactly once, without paraphrasing or added words.
Do not stretch speech to fill the clip. No unassigned voices.
AFTER SPEECH: lips closed, gaze held on the partner, a brief quiet hold for the cut.
AMBIENCE/SFX: faint steady indoor room tone; no music or chatter.
```
