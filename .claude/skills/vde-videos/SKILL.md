---
name: vde-videos
description: ส่งภาพตั้งต้นที่เลือกแล้วของแต่ละคลิปเข้า Grok Imagine ผ่าน grok MCP พร้อม prompt จาก EPxx/prompts/*_video.txt ตามความยาวในไฟล์ ดาวน์โหลดและตรวจเฟรม ใช้เมื่อสั่ง "สร้างวิดีโอ EPxx" หรือ "สร้างวิดีโอ EPxx SC01"
---

# สร้างวิดีโอ (grok MCP · Grok Imagine image-to-video)

อาร์กิวเมนต์: `EPxx` และถ้ามี `SCxx` ทุกคำสั่งรันจากโฟลเดอร์โปรเจกต์
`S=.claude/skills/vde-episode/scripts` · ค่าตั้งอยู่ใน `.claude/skills/vde-episode/config.json`

## 0. ตรวจก่อนเริ่ม
1. เรียก `grok_list_models` — ถ้า error (เช่น `Incorrect API key`) **หยุด** แล้วรายงาน: "grok MCP ใช้ไม่ได้: <ข้อความ> — แก้ XAI_API_KEY แล้วเปิด Claude ใหม่"
2. `python $S/state.py EPxx budget` — ถ้า `spent_grok_usd + grok_usd_first_pass` เกิน `grok_usd_cap` ให้ทำเฉพาะเท่าที่ไม่เกินเพดาน แล้วรายงานส่วนที่ค้าง

## 1. ส่งงานเป็นชุด
`python $S/state.py EPxx todo video [--scene SCxx]` (จะมีเฉพาะคลิปที่เลือกภาพแล้ว) ส่งครั้งละไม่เกิน `video_parallel` คลิป:
- `python $S/state.py EPxx prompt <clip> video` → prompt (ใช้ตรงตัว ห้ามแก้ ห้ามย่อ ห้ามแปลบทพูด) — สคริปต์ต่อท้ายบล็อก `IMAGE FACTS` ให้เองถ้าขั้นภาพบันทึกไว้
- `grok_imagine_video` ด้วย:
  `{prompt, image:"<start_image จาก todo (พาธเต็มในเครื่อง)>", duration:<seconds>, aspect_ratio:"9:16", resolution:"<video_resolution จาก config>", model:"<model จาก todo>", wait:false}`
  - v68: todo ให้ `model` ต่อคลิป (Lite สำหรับคลิปสั้นและภาพกว้าง, รุ่นปกติสำหรับคลิปเกิน `lite_max_sec` หรือช็อตใกล้ที่มีคนนอกเฟรม) ใช้ตามนั้นเสมอ และคิดเงินด้วย `usd_per_sec` ของคลิปนั้น
- จด request_id ของแต่ละคลิป

## 2. รอผล
- `python $S/media.py wait 20` แล้ว `grok_imagine_video_status` ทีละ request_id จนเสร็จหรือ error
- ผลสำเร็จ: หา URL ของวิดีโอในผลลัพธ์ (ลิงก์ http ที่เป็นไฟล์วิดีโอ) → `python $S/media.py fetch "<url>" <out_file จาก todo>`
  ถ้าผลลัพธ์ให้พาธไฟล์ในเครื่องแทน URL ให้คัดลอกไฟล์นั้นไปที่ out_file
- `failed` / `expired` / ถูกปฏิเสธด้านเนื้อหา → `take ... --result fail --qc "<เหตุผลจาก xAI>"` ถ้าถูกปฏิเสธด้านเนื้อหา 2 ครั้ง → `give-up` พร้อมเหตุผล
- error เรื่องเครดิต/ยอดเงิน/คีย์ → หยุดทั้งหมดและรายงาน

## 3. ตรวจเอง
1. `fetch` คืนค่า duration / has_audio: ความยาวต้องใกล้ seconds ที่สั่ง (±1 วิ); คลิปที่หัวไฟล์ระบุ `เสียงโหมด A` ต้องมีเสียง
2. `python $S/media.py frames <out_file>` → เปิด 3 เฟรม (start/mid/end) ด้วย Read เทียบกับภาพตั้งต้น
   **v68 ตรวจ transition:** `python $S/media.py drift <out_file>` ถ้า `suspect: true` ให้เปิด 3 เฟรม drift (start/turn/peak) ดูว่าเป็นการเคลื่อนไหวจริงตาม ACTION (ว่ายน้ำ กระโดด) หรือกล้องถอย/ตัด/dissolve/ฉากหลังเปลี่ยน ถ้าเป็นอย่างหลัง = ไม่ผ่าน และถ้าต้องเลือก take นี้ในที่สุด ให้บันทึก `python $S/state.py EPxx usable <clip> <stable_until>` เพื่อให้ตัดต่อใช้เฉพาะช่วงก่อนเปลี่ยน
   **ไม่ผ่าน ถ้า:** หน้าหรือชุดเปลี่ยนไปจากภาพตั้งต้นชัดเจน · มีคนเพิ่ม/หาย · ตัดภาพ dissolve ถอยกล้อง หรือเปลี่ยนมุมกล้องกลางคลิป · ฉากหลังเปลี่ยน/บิด · คนในเฟรมสลับข้าง · ร่างกายบิดเบี้ยว · มีตัวหนังสือ/ลายน้ำ · ภาพค้างนิ่งทั้งคลิปทั้งที่ ACTION สั่งให้เคลื่อน
3. บันทึก: `python $S/state.py EPxx take <clip> video --file <out_file> --job <request_id> --result ok|fail --qc "<สรุป>" --cost <seconds × usd_per_sec ของคลิป>`
   - ผ่าน → `select <clip> video --file <out_file>`; ถ้ามีบทพูด ใส่ `--flag "ต้องฟังลิปซิงก์"` เสมอ (Claude ตรวจเสียง/ลิปซิงก์ไม่ได้)
   - ไม่ผ่านและยังมี takes_left → ส่งใหม่ (prompt และภาพเดิม)
   - ครบจำนวนครั้ง → เลือก take ที่ดีที่สุด `--flag "<ปัญหา>"` หรือ `give-up` ถ้าไม่มี take ใช้ได้

## ช่องทางรอง: ทำมือผ่าน Grok Automation extension (v68)
ใช้เมื่อผู้ใช้สั่ง "ทำวิดีโอแบบทำมือ" / "ใช้ extension" หรือเมื่อ grok API ใช้ไม่ได้ (เครดิต xAI หมด) และผู้ใช้เลือกทำเอง — ใช้ subscription SuperGrok บน grok.com/imagine ไม่เสียเครดิต API ช่องทางหลักยังเป็นข้อ 0–3 ข้างบน
1. `python $S/grok_pack.py EPxx [--scene SCxx] [--clips A001,...]` → `EPxx/production/grok_pack/6s/` และ `10s/` แต่ละโฟลเดอร์มี `prompts.txt` (หนึ่ง prompt ต่อบรรทัด คั่นด้วยบรรทัดว่าง ขึ้นต้นด้วย `EPxx_A001 SHOT EPxx-S001.` และรวม IMAGE FACTS แล้ว) กับ `images/EPxx_A001.png`
2. บอกผู้ใช้ให้รันทีละโฟลเดอร์ใน extension: Frame to Video · Duration ตามชื่อโฟลเดอร์ (6 หรือ 10 วิ) · 9:16 · Outputs per prompt 1 · Auto download 720p · Auto-add character images เปิด · Concurrent 1 + Random Delay · ตรวจจำนวนคิวก่อนเริ่ม (ต้องเท่าจำนวน prompt ไม่ใช่ภาพ×prompt)
3. ผู้ใช้บอกโฟลเดอร์ที่ดาวน์โหลด → `python $S/grok_import.py EPxx "<โฟลเดอร์>"` คัดลอกเป็น `EPxx/Video/EPxx_A001_Tnn.mp4` ตามรหัสในชื่อไฟล์ (ไฟล์ที่จับคู่ไม่ได้อยู่ใน `unmatched` ให้ถามผู้ใช้)
4. ทำข้อ 3 (ตรวจเอง: frames, drift, take/select) กับทุกไฟล์ที่ import โดยใช้ `--job manual-extension --cost 0`
- วิดีโอจาก extension ยาว 6/10 วิ เสมอ ยาวกว่าที่วางแผน — ไม่ถือเป็นข้อผิด `edit.py` ตัดตามเวลาใช้จริง แต่ถ้าบทพูดถูกยืดหรือเฟรมเปลี่ยนช่วงท้าย ให้ใช้ `usable` บันทึกจุดที่ใช้ได้
- เลือกรุ่น Lite/ปกติไม่ได้ (ขึ้นกับ grok.com) และอาจขัดข้อตกลงการใช้งานของ xAI เพราะเป็นการกดเว็บอัตโนมัติ — ความเสี่ยงบัญชีเป็นการตัดสินใจของผู้ใช้

## 4. รายงานกลับ
คลิปที่ผ่าน / flagged / gave_up / เงินที่ใช้ (USD) ห้ามบอกว่าลิปซิงก์หรือเสียงพูด "ผ่าน"

## กฎ
- ใช้ภาพตั้งต้นของคลิปตัวเองเสมอ ห้ามใช้เฟรมสุดท้ายของคลิปอื่น (AGENTS.md ข้อ 7.5)
- ไม่แก้ไฟล์ prompt/Shot เขียนเฉพาะสถานะคลิปตัวเองและไฟล์ใน `EPxx/Video/`
