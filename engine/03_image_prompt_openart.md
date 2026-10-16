# 03 — Image Prompt สำหรับ OpenArt (GPT Image 2) (`prompt_writer`)

อ่านก่อนเริ่ม: ไฟล์ Shot ของ Scene ที่ได้รับ, `EPxx/03_setup_map.md`, `bible/ตัวละคร.md`, `bible/สถานที่.md`, `bible/พร็อพ.md`, `bible/look.md`, `EPxx/02_emotion_map.md`

## 1. กฎบังคับ: ทุกภาพและทุกวิดีโอเริ่มจากศูนย์

**ให้ถือว่า OpenArt และ Grok ไม่มีความจำจาก Shot ก่อนหน้า ทุกไฟล์ prompt ต้องมีรายละเอียดครบในตัวเอง** แม้อยู่ฉากเดียวกัน ใช้ตัวละครเดิม หรือแนบภาพแล้ว ใช้กับทุกคลิปที่ต้องผลิต: A-roll, B-roll, Reaction, Insert, Reverse, OTS และหน่วยย่อย ความสั้นหรือความเบลอของภาพไม่ใช่เหตุผลให้ละรายละเอียด

**ข้อมูลที่ต้องมีในทุก Image Prompt และเขียนซ้ำครบใน Video Prompt:**

1. **สถานที่และผัง:** ประเภทห้อง ผนัง พื้น ตำแหน่งประตู หน้าต่าง เฟอร์นิเจอร์หลัก ระบุทิศในห้องแยกจากซ้าย/ขวาของภาพ ไม่ใช้แค่ชื่อสถานที่หรือรหัส
2. **ตัวละครและตำแหน่ง:** ชื่อ จำนวนคนที่เห็นรวมคนติดขอบเฟรมหรือเห็นแค่ไหล่ ชุดและเครื่องประดับ ทรงผม ตำแหน่ง ท่า ทิศหน้า สายตา มองใคร ถ้ามีภาพตัวละคร ใช้ภาพเป็นหลักตามหัวข้อ 3
3. **กล้อง:** ตำแหน่งกล้องเทียบกับจุดคงที่ในห้อง ทิศที่หัน ฝั่งของแกนสนทนา ระดับ ขนาดภาพ เลนส์ สำหรับภาพนิ่งระบุเฟรมเริ่ม ไม่สั่งให้ภาพนิ่งแสดงการเคลื่อนหลายช่วง
4. **สิ่งที่เห็นและไม่เห็น:** Foreground, Subject, Visible Background, Off-frame ระบุว่าหลังตัวละครเป็นผนังใด มีอะไรจริง ห้ามใช้เพียง "ผนังเบลอ"
5. **แสงและสี:** แหล่งแสง ทิศในห้อง ความนุ่ม สีแสง โทนภาพ แหล่งแสงไม่ย้ายฝั่งเพราะเปลี่ยนมุมกล้อง
6. **พร็อพ:** ชนิด ตำแหน่ง ผู้ถือ มือไหน สถานะก่อนเริ่มช็อต ห้าม reset พร็อพ
7. **สำหรับวิดีโอ:** Start State → การกระทำตามลำดับ → End State พร้อมผู้พูด เสียง และผู้ฟังที่เงียบ (engine/04)

**คำที่ห้ามใช้แทนรายละเอียด:** "ห้องเดิม", "ชุดเดิม", "ตำแหน่งเดิม", "ต่อจากช็อตก่อน", "ตามภาพก่อน", "same as previous shot", "exact same room", "match the approved master" หรือรหัสเพียงอย่างเดียว

**วิธีทำงาน:** คัดลอกข้อเท็จจริงคงที่จาก Bible และ Setup Map → คำนวณสิ่งที่กล้องเห็นตามตำแหน่งและทิศกล้อง → ใส่สถานะตัวละครและพร็อพ ณ จังหวะนั้น → ตรวจ Image และ Video Prompt แยกเดี่ยว มุมย้อนกลับต้องเห็นส่วนที่ถูกต้องของห้อง ไม่คัดลอกพื้นหลังเดียวกันทุกมุม

**ทดสอบก่อนบันทึกไฟล์:** เปิดไฟล์ image เพียงไฟล์เดียว ต้องจัดภาพได้โดยไม่อ่านไฟล์อื่น เปิดไฟล์ video เพียงไฟล์เดียวพร้อมภาพ ต้องรู้ผัง กล้อง ชุด ตำแหน่ง แสง พร็อพ การแสดง และเสียงครบ และทั้งสองไฟล์ต้องบรรยายพื้นที่และสถานะเดียวกัน

## 2. ฝั่งผู้ใช้ใน OpenArt (ไม่เขียนลงไฟล์ prompt)

ข้อมูลนี้ให้ shot_planner ใส่ในช่อง "แนบใน OpenArt" ของ Shot และให้ผู้ใช้ทำในหน้าเว็บ:
- เลือกโมเดล **GPT Image 2** และตั้ง **Aspect ratio 9:16 ที่ปุ่มในหน้าเว็บ** ข้อความใน prompt ไม่ได้บังคับขนาดภาพ
- อัปโหลดภาพตัวละคร **ตามลำดับที่ระบุ** เพราะ prompt อ้างถึง "Image 1", "Image 2" ตามลำดับการอัปโหลด
- สร้างหลายภาพต่อครั้ง แล้วเลือกภาพที่ตรงภาพตัวละครและผังที่สุด ไม่ยึดภาพแรก ถ้าไม่มีภาพใดผ่าน ให้สร้างใหม่ก่อนส่งเข้า Grok

ไฟล์ `.txt` ขึ้นต้นด้วยส่วนหมายเหตุตัวละครตาม engine/07 หัวข้อ 4 แล้วตามด้วย prompt ใต้เส้นคั่น ตัวอย่างในไฟล์นี้แสดงเฉพาะส่วน prompt

## 3. ภาพตัวละครที่ผู้ใช้เตรียม (Reference-Image Mode)

ภาพอยู่ใน `input/characters/<ชื่อ>/` ตามกฎ engine/07 หัวข้อ 0 ใช้เสมอเมื่อตัวละครที่เห็นในภาพมีไฟล์ภาพ

**สาเหตุที่หน้าและชุดมักเพี้ยน:** คำบรรยายใน prompt แข่งกับภาพจริง โมเดลจึงผสมสองแหล่ง ภาพต้องเป็นแหล่งหลัก ข้อความเป็นตัวเสริมที่ต้องไม่ขัดกับภาพ

**เลือกภาพที่แนบ — คนละ 1 ภาพต่อตัวละครที่เห็น**

| สถานการณ์ใน Shot | แนบภาพ | ภาพนั้นคุมอะไร |
|---|---|---|
| ภาพกว้างกว่า MCU และมีภาพชุดนั้น | `W0x_<ชื่อชุด>` ตรงกับ Wardrobe State | หน้า ผม รูปร่าง และชุด |
| MCU, CU, ECU (หน้าเป็นจุดหลัก) และมี `face.png` | `face.png` | หน้าและผมเท่านั้น ชุดใช้ข้อความ |
| MCU หรือแคบกว่า แต่ไม่มี `face.png` | `W0x_<ชื่อชุด>` | หน้า ผม และชุด |
| เจ้าของไหล่ใน OTS และมีภาพ `_หลัง` | `W0x_<ชื่อชุด>_หลัง` | ผม เสื้อด้านหลัง |
| ชุดนี้ไม่มีภาพ | `face.png` หรือภาพชุดอื่นของตัวละครนั้น | หน้าและผมเท่านั้น ห้ามคัดลอกชุดจากภาพ |
| ตัวละครไม่มีโฟลเดอร์ภาพ | ไม่แนบ | ใช้ Identity Block เต็มจาก Bible |

- แนบเฉพาะตัวละครที่**เห็นในภาพนี้** ไม่แนบหลายภาพของคนเดียวกันพร้อมกัน
- จำนวนภาพแนบรวมไม่เกินค่าที่ AGENTS.md กฎข้อ 10 กำหนด
- ไม่แนบภาพสถานที่หรือพร็อพถ้าไม่จำเป็น

**บล็อก REFERENCE IMAGES** อยู่ต้น prompt บอกหน้าที่ของแต่ละภาพตามลำดับการอัปโหลด ใช้ประโยคตามชนิดภาพ:

```text
REFERENCE IMAGES:
Image 1: [name] — use for face, skin tone, hairstyle, body shape and this exact outfit.
Do not copy the background, lighting, pose or camera angle from this image.
Image 2: [name] — use only for face, skin tone and hairstyle. The outfit comes from
the text below. Do not copy the outfit, background, lighting or camera angle.
Image 3: [name] — rear view; use for hair seen from behind and the back of this outfit.
```

**กฎข้อความคู่กับภาพ**
- ช่อง CHARACTERS ของคนที่มีภาพ: ตัดคำบรรยายรูปหน้า สีผิว ทรงตา จมูก ออก เหลือชื่อ อายุโดยประมาณ ท่าทาง และ**คำบรรยายชุด LOCKED จาก Bible** ซึ่งเขียนจากภาพชุดนั้น จึงไม่ขัดกับภาพ
- ห้ามเขียนสิ่งที่ขัดกับภาพ เช่น สีเสื้อ ทรงผม หรือเครื่องประดับที่ต่างจากภาพ
- สภาพที่เปลี่ยนตามเรื่อง (ผมเปียก เสื้อเปื้อน รอยน้ำตา แขนเสื้อพับ) เขียนเพิ่มเป็นการเปลี่ยนแปลงจากภาพ เช่น "same outfit as Image 1, now with the cardigan sleeves pushed up and a wine stain on the skirt"
- ภาพตัวละครมักเป็นพื้นหลังเรียบและยืนตรง ต้องเขียนท่า ฉาก แสง และกล้องของ Shot ให้ครบเสมอ ไม่ปล่อยให้โมเดลคัดลอกท่าหรือพื้นหลังจากภาพ

**ความเสี่ยงที่ต้องรายงาน**
- **Shot แรกของตัวละครในซีรีส์:** ถ้ามุมหน้า ทิศสายตา แสง และฉากหลัง ต่างจากภาพอ้างอิงทุกด้านพร้อมกัน ให้รายงานกลับและแนะนำให้ผู้ใช้ทำภาพยึด (anchor) หน้าเกือบตรง แสงเรียบ ก่อน
- มุมและแสงรุนแรง (extreme close-up, มุมเงย/ก้มชัน, ย้อนแสงจัด, เงาปิดครึ่งหน้า) ลดความแม่นของใบหน้าเสมอ ใช้เมื่อจำเป็นต่อเรื่องและระบุในช่อง Clip ว่าเสี่ยง
- ตัวละครที่ถูกตัดออกเพราะเกินจำนวนภาพแนบ ระบุในช่อง Clip
- กฎนี้ลดอัตราเพี้ยน ไม่รับประกันผล ผู้ใช้ยังต้องเทียบภาพกับภาพอ้างอิงก่อนใช้

## 4. แม่แบบ Image Prompt

```text
Create one standalone starting-frame image for SHOT [Shot ID].
Vertical 9:16. Cinematic live-action still, photorealistic.
REFERENCE IMAGES: [ตามหัวข้อ 3 เฉพาะคนที่มีภาพแนบ หรือลบบล็อกนี้]
CHARACTERS: [each visible person: name, approximate age, reference binding or full
Identity Block, this shot's exact wardrobe text, hair; include partial, blurred,
reflected and foreground people].
CAST COUNT: exactly [n] people visible, including partial figures.
[For OTS only: FOREGROUND OWNER / VISIBLE FOREGROUND IDENTITY / CAMERA RELATION /
FOCUS SUBJECT / OCCLUSION block from section 5.]
SCENE GEOGRAPHY: [room type, walls, floor, fixed door/window/furniture positions;
character positions relative to named walls or landmarks].
CAMERA POSITION: [physical location in the room, side of the conversation axis].
VIEW DIRECTION: [toward named subject, then the named wall or landmark beyond].
VISIBLE BACKGROUND: [only architecture and objects inside this view and crop].
OFF-FRAME: [relevant walls, objects or people outside the frame, with spatial reason].
START STATE: [pose, body facing, eyeline, expression, relative depth, hands, prop state].
CAMERA: [shot size], [full-frame-equivalent focal length], [height], [angle].
FOCUS: [subject and depth of field].
LIGHTING: [source, direction in the room, quality, color temperature for this setup].
GRADE: [project grade text from bible/look.md].
Show only the starting moment, before any planned movement begins.
No captions, subtitles, labels, watermarks, panels or collage.
```

- แทนที่ทุกช่องด้วยข้อมูลจริง ห้ามเหลือวงเล็บหรือ placeholder
- ภาพ CU ที่ไม่เห็นพร็อพ ไม่ต้องบังคับให้พร็อพเข้าเฟรม แต่ระบุว่าอยู่นอกเฟรม
- สีหน้าใน START STATE คือสีหน้าตอน**เริ่ม**คลิป (เช่น ยังยิ้มอยู่ ก่อนเปลี่ยนเป็นช็อก)
- ไม่ใส่ negative prompt ยาว เขียนสิ่งที่ต้องการในเชิงบวกก่อน

## 5. OTS และคนที่เห็นบางส่วน

ปัญหาที่ป้องกัน: prompt บรรยายเฉพาะคนที่คมชัด แล้วใช้คำว่า "ไหล่คู่สนทนา" กับอีกคน ทำให้คนหน้าเฟรมกลายเป็นคนแปลกหน้า

- ระบุ **เจ้าของไหล่** (ชื่อ ตำแหน่งในฉาก มองจากด้านหลังหรือเฉียงหลัง), **ลักษณะที่เห็น** (ความยาวและสีผม เสื้อชั้นนอก สี เนื้อผ้า สายกระเป๋าที่อยู่ใน crop), **คนที่โฟกัส** (ชื่อ ตำแหน่ง สายตา การแสดง)
- ไหล่ซ้าย/ขวาเป็นด้านร่างกาย ขอบซ้าย/ขวาเป็นตำแหน่งในภาพ ระบุแยกกัน
- ห้ามใช้ `someone`, `a shoulder`, `the listener`, `the other person` แทนชื่อและรูปลักษณ์
- แยกเสื้อชั้นในกับชั้นนอก ไหล่ที่เห็นต้องเป็นเสื้อชั้นนอก
- ความเบลอลดรายละเอียดได้ แต่ไม่เปลี่ยนความยาวผม สีเสื้อ หรือชนิดเสื้อผ้า
- ไม่บังคับให้เห็นหน้าคนหน้าเฟรม ใช้ผม เสื้อ เครื่องประดับแทน
- OTS ยังต้องผ่าน Scene Geography: เจ้าของไหล่ถูกแต่พื้นหลังผิดก็ไม่ผ่าน

```text
FOREGROUND OWNER: [name], [world position], seen from [rear/three-quarter rear].
VISIBLE FOREGROUND IDENTITY: [hair length/style/color; outer garment; visible accessories].
CAMERA RELATION: camera behind [name]'s anatomical [left/right] shoulder,
with that shoulder occupying [screen edge and approximate amount].
FOCUS SUBJECT: [other name + relevant appearance], [position and eyeline].
OCCLUSION: [foreground parts visible and outside crop]. Keep [subject]'s face readable.
FOCUS: [subject] sharp; [foreground name] softly defocused, while hair silhouette and
outer-garment color remain recognizable.
The foreground person is [name], not an additional person or a generic stand-in.
```

## 6. Insert และตัวหนังสือในภาพ

GPT Image 2 วาดตัวหนังสือได้ดี จึงต้องสั่งให้ชัด:
- ภาพทั่วไปต้องมีบรรทัด "No captions, subtitles, labels..." เสมอ
- Insert ที่ต้องเห็นข้อความ (จอมือถือ เอกสาร ป้าย) ให้เขียนข้อความที่ต้องปรากฏในเครื่องหมายคำพูดตรงตัว ระบุภาษา ตำแหน่ง ขนาด และสี และเขียนว่า "Render only this text; no other readable text"
- ข้อความภาษาไทยในภาพให้สั้นที่สุด และระบุในช่อง Clip ว่าต้องตรวจตัวสะกด ถ้าข้อความยาวหรือสำคัญ แนะนำให้ใส่เป็นกราฟิกตอนตัดต่อแทน และให้ภาพแสดงจอหรือกระดาษแบบไม่มีข้อความ

## 7. ตรวจผังก่อนบันทึกไฟล์

- กล้องอยู่ตรงไหน มองไปทางไหน
- มองผ่านตัวละครแล้ว พื้นที่ข้างหลังตรงกับ Scene Geography หรือไม่
- พื้นหลังเป็นของมุมนี้จริง หรือเผลอคัดลอกจากภาพเปิดฉาก
- สิ่งนอกกรอบมีเหตุผลจากผังหรือ crop และไม่ถูกสั่งให้โผล่ในส่วนอื่นของ prompt
- ท่า สายตา แกน และทิศแสงสอดคล้องกับจุดตั้งกล้อง

## 8. คลิปที่ไม่ต้องมี Image Prompt — มีแค่ REUSE

- **REUSE** ไม่สร้างไฟล์ prompt ใดๆ
- คลิปอื่นทุกคลิปต้องมีไฟล์ image ของตัวเอง รวมถึงคลิปที่ `ต่อการกระทำจาก` คลิปก่อน ในกรณีนั้น START STATE ให้วาดท่า สีหน้า มือ และพร็อพตาม End State ที่วางแผนไว้ของคลิปก่อน ไม่อ้างถึงคลิปก่อนในข้อความ prompt

## 9. ตัวอย่าง Image Prompt — มินเดี่ยว CU (แนบ face.png)

```text
Create one standalone starting-frame image for SHOT EP01-S005.
Vertical 9:16. Cinematic live-action still, photorealistic.
REFERENCE IMAGES:
Image 1: Min — use only for face, skin tone and hairstyle. The outfit comes from
the text below. Do not copy the outfit, background, lighting or camera angle.
CHARACTERS: Min, a Thai woman in her early thirties, wearing an ivory cotton collared
blouse with plain buttons, no visible jewelry; straight black chin-length bob tucked
behind both ears.
CAST COUNT: exactly one person visible.
SCENE GEOGRAPHY: a small office with an oak desk. Min sits at the west side of the
desk; her conversation partner sits opposite at the east side, outside this frame.
The west wall is pale gray plaster. Daylight enters from a window in the east wall.
CAMERA POSITION: southeast of Min, on the south side of the dialogue axis.
VIEW DIRECTION: diagonally northwest toward Min, with the west wall beyond her.
VISIBLE BACKGROUND: softly defocused pale gray west wall only.
OFF-FRAME: the east-wall window is behind the camera; the desk top and a manila
envelope on it are below the crop.
START STATE: Min sits upright, framed from upper chest to head, looking slightly
screen-right toward her unseen partner. Lips closed, brows slightly drawn,
restrained hurt in the eyes. Both hands rest in her lap below the crop.
CAMERA: close-up, 85mm full-frame equivalent, seated eye level, three-quarter view.
FOCUS: sharp eyes, softly defocused background.
LIGHTING: soft daylight from the east-wall window, reaching the front and
camera-right side of her face; neutral daylight color.
GRADE: neutral skin tones, muted warm wood, restrained saturation, moderate contrast.
Show only the starting moment, before any planned movement begins.
No captions, subtitles, labels, watermarks, panels or collage.
```

## 10. ตัวอย่าง OTS — หลังไหล่มุก มองไปที่ส้ม

```text
Create one standalone starting-frame image for SHOT EP02-S014.
Vertical 9:16. Cinematic live-action still, photorealistic.
CHARACTERS: Som, a young adult woman with long loosely wavy dark-brown hair, wearing
a white ribbed cropped top under an open light-gray zip hoodie with dark collegiate
lettering, blue jeans and a black backpack. Mook, a young adult woman with long
dark-brown hair, wearing a blue knit cardigan over a white collared shirt, with a
black shoulder bag on her right shoulder.
CAST COUNT: exactly two women, Som and Mook, including the partial foreground figure.
FOREGROUND OWNER: Mook, standing beside the window wall, seen from behind in the
right foreground.
VISIBLE FOREGROUND IDENTITY: long dark-brown hair falling down her upper back and a
blue knit cardigan covering her shoulders and back. The visible shoulder is blue
knit, not a white shirt.
CAMERA RELATION: camera behind Mook's anatomical left shoulder, with that shoulder,
part of her hair and the back of her head occupying about the right fifth of the frame.
FOCUS SUBJECT: Som, standing across the corridor beside the classroom-door wall,
holding the backpack strap with her right hand near her chest, lips closed,
looking slightly screen-right toward Mook.
SCENE GEOGRAPHY: a school corridor with classroom doors along one wall and tall
windows along the opposite wall. Som is beside the classroom-door wall; Mook is
beside the window wall. Neither changes position.
CAMERA POSITION: near the window side behind Mook, offset toward the open corridor,
on the established side of the dialogue axis.
VIEW DIRECTION: diagonally across the corridor past Mook toward Som and the
classroom-door wall beyond her.
VISIBLE BACKGROUND: cream classroom wall and classroom door frames in natural perspective.
OFF-FRAME: the window wall is on the camera side, outside the background.
OCCLUSION: Mook's face is not visible. Keep Som's face and gripping hand unobstructed.
CAMERA: over-the-shoulder medium close-up, 65mm full-frame equivalent, standing eye level.
FOCUS: Som sharp; Mook softly defocused, with long hair and blue knit still identifiable.
LIGHTING: soft window daylight from the camera side, gently illuminating Som.
GRADE: natural skin tones, restrained saturation, moderate contrast.
The foreground person is Mook, not an additional person or a generic stand-in.
No captions, subtitles, labels, watermarks, panels or collage.
```
