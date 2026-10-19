---
name: vde-xml
description: ทำไฟล์ XML ไทม์ไลน์ (Final Cut Pro 7 XML) ของตอนที่ตัดต่อแล้ว สำหรับเปิดแก้ต่อใน Premiere Pro หรือ DaVinci Resolve โดยลิงก์คลิปต้นฉบับใน EPxx/Video/ ใช้เมื่อสั่ง "ทำ XML EPxx" หรือ "ขอไฟล์ XML" (vde-edit เรียกให้อัตโนมัติหลังตัดต่อเสร็จ)
---

# ไฟล์ XML สำหรับโปรแกรมตัดต่อ

อาร์กิวเมนต์: `EPxx` รันจากโฟลเดอร์โปรเจกต์

## ขั้นตอน
1. ต้องมี `EPxx/Edit/EPxx_edl.csv` ก่อน ถ้ายังไม่มีให้ใช้ skill `vde-edit` (ซึ่งจะทำ XML ให้เองตอนจบ)
2. รัน `python .claude/skills/vde-xml/scripts/xml_export.py EPxx`
3. รายงาน: ไฟล์ผลลัพธ์ ความยาว จำนวนคลิป จำนวน marker และ warnings ทุกข้อ

## สิ่งที่อยู่ใน `EPxx/Edit/EPxx_timeline.xml`
- Sequence 720×1280 24fps ชื่อ `EPxx_ตัดต่อ` ตำแหน่งทุก Shot ตรงกับ `EPxx_ตัดต่อ.mp4` และ `EPxx.srt`
- V1: คลิปละ Shot ชื่อ `<Shot> <Clip>` ลิงก์ไฟล์ take ที่เลือกใน `EPxx/Video/` (ยังลากขอบคลิปยืด/หดได้)
- A1/A2: เสียงสเตอริโอของ take เดียวกัน ลิงก์กับภาพ; B-roll ที่ไฟล์ Shot สั่ง "ปิดเสียง" ถูกปิด (disabled) ไว้ เปิดคืนได้
- Marker ทุก Shot ที่มีบทพูด ใส่บทคำต่อคำ
- Shot ที่ไม่มีวิดีโอ → เว้นช่องว่างตามความยาวที่วางแผน

## ไม่อยู่ใน XML
- ซับ: นำเข้า `EPxx.srt` แยก (Premiere: File > Import / Resolve: ลากเข้า Media Pool แล้วลงแทร็กซับ)
- เพลงประกอบและการปรับความดัง -14 LUFS ที่ edit.py ทำในไฟล์ mp4
- CapCut นำเข้า XML ไม่ได้ ให้ใช้ไฟล์ mp4 + srt แทน

## วิธีเปิด
- Premiere Pro: File > Import > เลือก `EPxx_timeline.xml`
- DaVinci Resolve: File > Import > Timeline > เลือก `EPxx_timeline.xml` (ถ้าหาไฟล์ไม่เจอ ให้ชี้ไปที่ `EPxx/Video/`)
- XML ลิงก์ไฟล์ด้วยพาธเต็มในเครื่องนี้ ถ้าย้ายโฟลเดอร์โปรเจกต์หรือเปิดเครื่องอื่น ต้อง relink ไปที่ `EPxx/Video/`
