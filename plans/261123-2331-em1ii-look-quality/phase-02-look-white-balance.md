---
phase: 2
title: "WB shift theo look"
status: pending
priority: P1
effort: "3-4d emulator + 1 camera build"
dependencies: [1]
---

# Phase 02: WB shift theo look

## Overview
Mỗi look mang độ lệch cân bằng trắng riêng (A-B, G-M, ±7), như các mô phỏng phim của Fujifilm. Look ghi gì thì áp
nấy khi đang ở Color Creator. WB của người dùng không bị đổi. Không cần phase 00: field đã có trong format chung.

## Requirements
- Functional:
  - dùng các byte đã có trong record: cờ WB +25, a_b +26, g_m +27 (`make_looks_bin.py:91-95`);
  - encoder chung **đã xuất** ba byte này (`format.ts:152`, `targets/em1mk2.ts:17-20`), nên webapp không phải sửa
    encoder;
  - áp lệch WB của look khi picture mode là Color Creator, `P_ACTIVE = 1` và cờ +25 bật;
  - ngoài các trường hợp trên thì WB như stock.
- Non-functional: không ghi đè sid WB toàn cục của người dùng; ra khỏi Color Creator là WB quay về như cũ.

## Architecture
- E-P7 (`docs/WB_PATCH.md`): 16 chỗ gọi getter WB `0x6005e971` được trỏ sang stub `wb_get`; stub trả fine-tune của
  slot (A-B ở capture+24098, G-M ở +24100).
- E-M1 II: chưa biết sid/key WB và các chỗ gọi. Dùng `tools/omdem1mk2_ep7_match.py` (tìm theo chữ ký có mask) để tìm
  các chỗ tương ứng với 16 chỗ của E-P7. Getter thuộc tính là `0x6005e6cf`.
- Stub `wb_get` của E-M1:
  - nếu đủ điều kiện (Color Creator, `P_ACTIVE`, cờ +25) thì trả giá trị của look;
  - nếu không, nhảy về getter stock.
  - Đặt trong khoảng trống 100 KB (`0x612e7000..0x61300000`), **trước trang Halo `0x612f0000`**, hoặc phần đuôi
    section 3.
- **Live view:** trên E-P7, live view không hiện lệch WB, chỉ JPEG có (`WB_PATCH.md:136,166`). E-M1 II nhiều khả năng
  giống vậy. Ghi rõ trong hướng dẫn thử để người dùng không tưởng là lỗi.
- **Look cũ đã có wb_shift:** khi tính năng lên máy, các look này sẽ đổi màu JPEG so với trước. Phải ghi trong release
  notes, và bỏ mục WB khỏi danh sách `em1Dropped` của target em1mk2 (hiện panel báo WB bị bỏ qua trên E-M1 II).

## Related Code Files
- Create:
  - `patches/omdem1mk2/look_wb/` (`wb.s`, `build.py`);
  - `tools/omdem1mk2_emu_look_wb.py`.
- Modify:
  - `webapp/src/targets/em1mk2.ts` (`em1Dropped`, `toEm1`, chú thích; encoder giữ nguyên) và test của nó;
  - `docs/OMD-EM1-II/ARCHITECTURE_AND_MEMORY_MAP.md` (các chỗ gọi WB);
  - `tools/omdem1mk2_catalog_release.py`.

## Implementation Steps
1. Tìm getter WB và các chỗ gọi trên E-M1 bằng `ep7_match`. Chạy getter trên emulator với key thật. Ghi lại các chỗ đó
   trong ARCHITECTURE_AND_MEMORY_MAP.
2. Viết stub. Emulator: với mọi chỗ gọi, mọi tổ hợp (mode, `P_ACTIVE`, cờ) thì giá trị trả về đúng thiết kế, các
   thanh ghi được giữ.
3. Chạy thử đường tạo request màu (`tools/omdem1mk2_emu_work_list.py`): với look có WB, các field WB trong request thay
   đổi; không có look thì request giống stock từng byte.
4. Target em1mk2: bỏ `'WB shift'` khỏi `em1Dropped` (`em1mk2.ts:26`), giữ `wb` trong `toEm1` cho look màu
   (`em1mk2.ts:42`, hiện đặt `wb: null`), sửa chú thích đầu file; vitest đạt.
5. Dựng bản thử riêng.

## Success Criteria
- [ ] Emulator: các chỗ gọi đều được chuyển hướng; ngoài Color Creator thì stock.
- [ ] Máy: chụp thẻ xám cùng ánh sáng:
  - look có A-B +3 cho tỉ lệ R/B trung bình cao hơn rõ so với cùng look A-B 0;
  - đổi sang Natural thì R/B như stock;
  - EXIF vẫn ghi WB của người dùng.

## Risk Assessment
- **WB được áp ở bước chụp chứ không ở request ảnh:** khi đó stub phải nằm ở chỗ đọc của bước chụp. Bước 3 sẽ phát hiện.
- **WB ảnh hưởng tới AWB hoặc live view theo cách khác E-P7:** cần kiểm trên máy.
