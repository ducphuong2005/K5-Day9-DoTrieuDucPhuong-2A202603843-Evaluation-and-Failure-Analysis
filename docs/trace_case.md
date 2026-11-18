# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (`E-002@11`), run ID `E-seeded_regression-20261118-7d41` (trong `src/reports/eval_seeded_regression.json`; cũng xuất hiện trên `swarm C-002@55` trong `src/reports/baseline_v1.json` với run ID `E-swarm-20261118-7d41`) |
| Triệu chứng | `TrialPass` (`pass_rate`), `RefundAmountCorrect` (`refund_amount_correct`) và `DbFactKept` (`db_fact_kept`) cùng fail (`status resolved != denied`); `reply` báo `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` và `ledger` ghi `refund_vnd=20000`, `refund_count=1` trong khi nhãn chuẩn (`labels_v1.json`) là `status="denied"`, `refund_vnd=0`, `refund_count=0` |
| Bước sai đầu tiên | Step `3` · `model_override` · `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Step `1` (`handoff`: `{"claim_id": "C-002", "principal_scope": "owner_order_only", "allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"]}`) và Step `2` (`investigator`: `lookup_order` trả đúng dữ liệu DB của đơn `O-202` với `"delay_days": 2, "shipping_fee_vnd": 20000, "status": "delivered"`) đều hoàn toàn đúng; chỉ từ Step `3` (`model_override`) agent mới lấy số ngày trễ trong ticket (`5`) đè lên `delay_days=2` của DB, kéo theo Step `4` (`quote` tính sai `amount_vnd=20000` theo `SHIP-LATE-03`) và lệnh `issue_refund` hoàn nhầm `20.000đ` |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng `C-002@11` trên shape `fixed`: sau Step `2` (`investigator` trả `delay_days=2`), **không có** sự kiện `model_override`; Step `3` là `quote` giữ nguyên `delay_days=2` nên trả `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`, và Step `4` (`reply`) trả `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."` với `status="denied"`, `ledger.refund_vnd=0` |
| Regression test | `tests/test_lab9_graders.py::test_trace_case_c002_seed11_regression` (gọi `lab9.trace_case.investigate` kiểm tra `DbFactKept` và `RefundAmountCorrect` cộng với assert event thứ 3 `model_override`); đã xác nhận fail trên `seeded_regression` (`False`) và pass trên `fixed` (`True`), đồng thời item `E-002` trong `data/eval/eval_set_v1.jsonl` ghi nhận `provenance.from_trace = "traces/R-swarm-C-002-s55.json"` |
| Chưa chắc chắn | Trace chỉ cho thấy `parsed_delay=5` đã đè lên `order["delay_days"]=2` tại bước `model_override`; nếu một biến thể ẩn (`quiet_override`) sửa trực tiếp `order["delay_days"]` trong bộ nhớ mà không ghi event `model_override` ra trace thì `DbFactKept` không tự thấy được nguyên nhân ở bước trung gian mà phải nhờ `RefundAmountCorrect` / `TrialPass` bắt ở kết quả đầu ra trên ledger |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
