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
- `python $S/state.py EPxx prompt <clip> video` → prompt (ใช้ตรงตัว ห้ามแก้ ห้ามย่อ ห้ามแปลบทพูด)
- `grok_imagine_video` ด้วย:
  `{prompt, image:"<start_image จาก todo (พาธเต็มในเครื่อง)>", duration:<seconds>, aspect_ratio:"9:16", resolution:"720p", model:"grok-imagine-video-1.5", wait:false}`
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
   **ไม่ผ่าน ถ้า:** หน้าหรือชุดเปลี่ยนไปจากภาพตั้งต้นชัดเจน · มีคนเพิ่ม/หาย · ตัดภาพหรือเปลี่ยนมุมกล้องกลางคลิป · ร่างกายบิดเบี้ยว · มีตัวหนังสือ/ลายน้ำ · ภาพค้างนิ่งทั้งคลิปทั้งที่ ACTION สั่งให้เคลื่อน
3. บันทึก: `python $S/state.py EPxx take <clip> video --file <out_file> --job <request_id> --result ok|fail --qc "<สรุป>" --cost <seconds × grok_usd_per_sec>`
   - ผ่าน → `select <clip> video --file <out_file>`; ถ้ามีบทพูด ใส่ `--flag "ต้องฟังลิปซิงก์"` เสมอ (Claude ตรวจเสียง/ลิปซิงก์ไม่ได้)
   - ไม่ผ่านและยังมี takes_left → ส่งใหม่ (prompt และภาพเดิม)
   - ครบจำนวนครั้ง → เลือก take ที่ดีที่สุด `--flag "<ปัญหา>"` หรือ `give-up` ถ้าไม่มี take ใช้ได้

## 4. รายงานกลับ
คลิปที่ผ่าน / flagged / gave_up / เงินที่ใช้ (USD) ห้ามบอกว่าลิปซิงก์หรือเสียงพูด "ผ่าน"

## กฎ
- ใช้ภาพตั้งต้นของคลิปตัวเองเสมอ ห้ามใช้เฟรมสุดท้ายของคลิปอื่น (AGENTS.md ข้อ 7.5)
- ไม่แก้ไฟล์ prompt/Shot เขียนเฉพาะสถานะคลิปตัวเองและไฟล์ใน `EPxx/Video/`
