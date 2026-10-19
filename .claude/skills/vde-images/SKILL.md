---
name: vde-images
description: สร้างภาพตั้งต้นของทุกคลิปด้วย OpenArt GPT Image 2 จากไฟล์ EPxx/prompts/*_image.txt แนบภาพตัวละครตามหัวไฟล์ ตรวจภาพเองและเลือกภาพที่ผ่าน ใช้เมื่อสั่ง "สร้างรูป EPxx" หรือ "สร้างรูป EPxx SC01"
---

# สร้างภาพตั้งต้น (OpenArt · GPT Image 2)

อาร์กิวเมนต์: `EPxx` และถ้ามี `SCxx` (ทำเฉพาะ Scene นั้น) ทุกคำสั่งรันจากโฟลเดอร์โปรเจกต์
`S=.claude/skills/vde-episode/scripts` · ค่าตั้งอยู่ใน `.claude/skills/vde-episode/config.json`

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

บันทึกทุก take: `python $S/state.py EPxx take <clip> image --file <out_file> --job <historyId> --result ok|fail --qc "<สรุปสั้น ข้อที่ไม่ผ่าน>" --cost 42`
- ผ่าน → `python $S/state.py EPxx select <clip> image --file <out_file>`
- ไม่ผ่านและยังมี takes_left → กลับไปข้อ 1 กับคลิปนั้น (prompt เดิม)
- ไม่ผ่านครบจำนวนครั้ง → เลือก take ที่ดีที่สุด `select ... --flag "<ปัญหาที่เหลือ>"` (ยังไปสร้างวิดีโอได้ แต่ขึ้นในรายงานให้คนตรวจ)
- ห้ามบอกว่า "หน้าเหมือนแน่นอน" — การตรวจของ Claude เป็นการคัดกรองเบื้องต้น

## 4. รายงานกลับ
สั้นๆ: คลิปที่ผ่าน / flagged (พร้อมเหตุผล) / ล้มเหลว / เครดิตที่ใช้ (จำนวน take × 42 โดยประมาณ) ไม่ต้องส่งเนื้อหา prompt กลับ

## กฎ
- หยุดทันทีถ้า OpenArt แจ้งเครดิตไม่พอ แล้วรายงานพร้อม upgradeUrl
- ไม่แก้ไฟล์ prompt/Shot ถ้าเห็นว่า prompt ผิด ให้รายงานกลับ
- เขียนเฉพาะไฟล์สถานะของคลิปตัวเอง (`production/clips/<clip>.json` ผ่าน state.py) และไฟล์ใน `EPxx/Image/`
