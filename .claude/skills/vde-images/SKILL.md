---
name: vde-images
description: สร้างภาพตั้งต้นของทุกคลิปด้วย GPT Image 2 (fal.ai หรือ OpenArt ตาม image_provider ใน config) จากไฟล์ EPxx/prompts/*_image.txt แนบภาพตัวละครตามหัวไฟล์ ตรวจภาพเองและเลือกภาพที่ผ่าน ใช้เมื่อสั่ง "สร้างรูป EPxx" หรือ "สร้างรูป EPxx SC01"
---

# สร้างภาพตั้งต้น (OpenArt · GPT Image 2)

อาร์กิวเมนต์: `EPxx` และถ้ามี `SCxx` (ทำเฉพาะ Scene นั้น) ทุกคำสั่งรันจากโฟลเดอร์โปรเจกต์
`S=.claude/skills/vde-episode/scripts` · ค่าตั้งอยู่ใน `.claude/skills/vde-episode/config.json`

## ช่องทางสร้างภาพ: ดู `image_provider` ใน config.json
- `"openart"` (ค่าเริ่มต้น) → ทำข้อ 0–2 ตามปกติผ่าน OpenArt MCP (ใช้ภาพอ้างอิงได้จริงแค่ 2 รูปแรก)
- `"fal"` → **ข้ามข้อ 0–2 ทั้งหมด** ไม่ต้องอัปโหลด ref ไม่ใช้ OpenArt MCP แล้วทำแทนด้วย:
  1. `python $S/fal_image.py check` — ถ้าไม่พบ key ให้หยุดและรายงาน: "ตั้ง fal key ด้วย `! pwsh -File ~/.claude/secrets/set-fal-key.ps1`"
  2. `python $S/fal_image.py EPxx submit [--scene SCxx]` — ส่งทุกคลิป todo พร้อมกัน (prompt ตรงตัว + ภาพอ้างอิงสูงสุด `fal_max_refs` รูปจากหัวไฟล์) ถ้าผลมี `error` เรื่อง 401/403/เครดิต → หยุดและรายงาน
  3. `python $S/fal_image.py EPxx collect --wait 600` — รอและดาวน์โหลดลง out_file; บรรทัด `failed` → `state.py take ... --result fail --qc "<error>"`
  4. ไปข้อ 3 (ตรวจภาพ) ตามปกติ บันทึก `--job <request_id> --cost <fal_usd_per_image>` (หน่วย USD ไม่ใช่เครดิต)
  5. ถ่ายซ้ำ: `fal_image.py EPxx submit --clips <clip>` (ส่งซ้ำได้หลังบันทึก take ก่อนหน้าแล้วเท่านั้น สคริปต์กันส่งซ้ำซ้อนให้)
  - ถูก safety checker ปฏิเสธ (error มีคำว่า safety/content) → บันทึก fail; ซ้ำ 2 ครั้ง → `give-up` พร้อมเหตุผล

## 0. เตรียม (ข้ามได้ถ้า agent หลักทำให้แล้ว)
1. ถ้ายังไม่มี `EPxx/production/plan.json` ให้รัน `python $S/collect.py EPxx`
2. **อัปโหลดภาพตัวละคร** — `python $S/state.py EPxx refs-needed` แล้วทีละไฟล์:
   - `openart_upload_sign` (mediaType image, size, contentType ตามที่สคริปต์ให้, purpose create-image, label = ชื่อไฟล์)
   - `python $S/media.py upload "<signURL>" "<abs>" <contentType>`
   - `openart_upload_metadata_get` (mediaUrl = accessURL, uploadId, label) → ได้ visualReference
   - `python $S/state.py EPxx ref-add "<path>" '<visualReference json>'`
   - ถ้าเป็น worker ที่ถูก spawn มาทำ Scene เดียว **ห้ามเขียน ref_cache.json** ถ้ายังมี ref ขาด ให้รายงานกลับ agent หลัก

## 1. สั่งสร้าง (ส่งทั้งชุดก่อน แล้วค่อยรอผล)
`python $S/state.py EPxx todo image [--scene SCxx]` → ทุกรายการ:
- `python $S/state.py EPxx prompt <clip> image` → ข้อความ prompt (ใช้ตรงตัว ห้ามแก้ ห้ามย่อ)
- ถ้า `refs` มีรายการ → `openart_generate_image` model `gpt-image-2` mode `image2image`, params:
  `{prompt, visualReferences:[visualReference ตามลำดับใน refs], aspectRatio:"9:16", resolutionTier:"2k", quality:"medium", imageCount:1, autoEnhancePrompt:false}`
- ถ้า refs ว่าง → mode `text2image` params เดียวกันแต่ไม่มี visualReferences
- ถ้า ref ตัวไหน visualReference เป็น null → ข้าม ref นั้น และจดใน qc ว่า "ขาดภาพอ้างอิง <path>"
- จด historyId ของแต่ละคลิปไว้

## 2. รอผลและดาวน์โหลด
- `python $S/media.py wait 20` แล้ว `openart_creation_get` ทีละ historyId จนเป็น COMPLETED / FAILED
- COMPLETED → `python $S/media.py fetch "<resources[0].url>" <out_file จาก todo>`
- FAILED → `python $S/state.py EPxx take <clip> image --job <id> --result fail --qc "<เหตุผล>"`

## 3. ตรวจภาพเอง (ผู้ใช้เลือกแบบ ข: Claude ตรวจและเลือกให้)
เปิดภาพด้วย Read และเทียบกับหัวไฟล์ prompt (`# ตัวละครในเฟรม`) และเนื้อ prompt ถ้ามีภาพอ้างอิงให้เปิดเทียบหน้าด้วย
**ไม่ผ่าน ถ้ามีข้อใดข้อหนึ่ง:**
1. จำนวนคนในภาพไม่ตรง CAST COUNT (นับคนเบลอ/เห็นบางส่วนด้วย)
2. ภาพไม่ใช่แนวตั้ง 9:16
3. ชุด สีผม ทรงผม ผิดจาก WARDROBE LOCKED ชัดเจน
4. หน้าไม่เหมือนภาพอ้างอิง (เมื่อมีภาพอ้างอิง)
5. ตำแหน่ง/ทิศหน้า/สายตาผิดจาก START STATE หรือหมายเหตุ "ตัวละครในเฟรม" ชัดเจน
6. มีตัวหนังสือ ซับ ลายน้ำ โลโก้ ที่ prompt ไม่ได้สั่ง
7. ร่างกายผิดรูป (มือ นิ้ว แขนขา หน้าบิด) ที่เห็นชัด
8. ฉาก/แสงขัดกับ SCENE GEOGRAPHY / LIGHTING ชัดเจน
9. (v68) ลำดับซ้าย→ขวาไม่ตรง FRAME ORDER / หัวไฟล์ "ตัวละครในเฟรม" หรือเฟรมเห็นที่ว่างตรงที่ควรมีคนตาม Blocking Table หรือภาพผังกลับด้าน (สิ่งที่ขวางระหว่างกล้องกับตัวละคร)

ความต่อเนื่องข้าม Shot ตรวจอีกรอบทั้ง Scene ในขั้นตรวจความต่อเนื่องของ vde-episode

บันทึกทุก take: `python $S/state.py EPxx take <clip> image --file <out_file> --job <historyId> --result ok|fail --qc "<สรุปสั้น ข้อที่ไม่ผ่าน>" --cost 42`
- ผ่าน → `python $S/state.py EPxx select <clip> image --file <out_file>`
  แล้วบันทึกสิ่งที่ภาพจริงแสดง (ภาษาอังกฤษ 1–3 ประโยค: ใครอยู่ซ้าย→ขวา ท่า ขนาดภาพ สิ่งที่เห็น/ไม่เห็น เช่น มือหรือพร็อพที่โผล่) ด้วย `python $S/state.py EPxx facts <clip> "<text>"` — ขั้นวิดีโอจะส่งข้อความนี้ต่อท้าย prompt เพื่อไม่ให้ Grok 'แก้' ภาพด้วยการ morph หรือตัดภาพ (v68)
- ไม่ผ่านและยังมี takes_left → กลับไปข้อ 1 กับคลิปนั้น (prompt เดิม)
- ไม่ผ่านครบจำนวนครั้ง → เลือก take ที่ดีที่สุด `select ... --flag "<ปัญหาที่เหลือ>"` (ยังไปสร้างวิดีโอได้ แต่ขึ้นในรายงานให้คนตรวจ)
- ห้ามบอกว่า "หน้าเหมือนแน่นอน" — การตรวจของ Claude เป็นการคัดกรองเบื้องต้น

## 4. รายงานกลับ
สั้นๆ: คลิปที่ผ่าน / flagged (พร้อมเหตุผล) / ล้มเหลว / เครดิตที่ใช้ (จำนวน take × 42 โดยประมาณ) ไม่ต้องส่งเนื้อหา prompt กลับ

## กฎ
- หยุดทันทีถ้า OpenArt แจ้งเครดิตไม่พอ แล้วรายงานพร้อม upgradeUrl
- ไม่แก้ไฟล์ prompt/Shot ถ้าเห็นว่า prompt ผิด ให้รายงานกลับ
- เขียนเฉพาะไฟล์สถานะของคลิปตัวเอง (`production/clips/<clip>.json` ผ่าน state.py) และไฟล์ใน `EPxx/Image/`
