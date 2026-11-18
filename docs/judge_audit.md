# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok (`data/eval/judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | Có (`tp=24, fp=4, fn=6, tn=66`; observed fail rate `0.280` → Rogan-Gladen corrected `0.300`) | **dùng** (sau khi siết rubric theo bảng audit bên dưới) |
| helpful (`data/eval/judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | **Không** (`tp=9, fp=0, fn=21, tn=70`; `κ=0.375 < 0.6` và `Recall=0.300 < 0.7`; observed fail rate `0.090` → Rogan-Gladen corrected `0.300`) | **loại** (tuyệt đối không dùng làm gate) |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric / dữ liệu |
|---|---|---|---|---|---|
| 1 | `H-008`: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người đúng** (`fn`) | Xưng *"em"* và dùng khẩu ngữ *"nha"* quá suồng sã; judge nhầm là thân thiện. **Sửa rubric `tone_ok`:** Bắt buộc xưng *"LogiX"* và gọi khách là *"anh/chị"*; cấm xưng *"em"*, *"bạn"* hoặc dùng từ cảm thán suồng sã (*"nha"*, *"nhé"*). |
| 2 | `H-017`: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* | PASS | FAIL | **Người đúng** (`fn`) | Xưng *"bạn ơi"* + *"nha"* không chuẩn mực CSKH của LogiX. **Sửa rubric `tone_ok`:** Liệt kê rõ đại từ bị cấm (*"bạn"*, *"bạn ơi"*) trong danh sách điều kiện FAIL cứng. |
| 3 | `H-029`: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người đúng** (`fn`) | Câu cuối *"không cần nhắn thêm"* mang giọng ra lệnh/chặn lời khách, nhưng judge chỉ nhìn từ khóa mở đầu *"Dạ, vui lòng"*. **Sửa rubric `tone_ok`:** Đánh giá toàn bộ câu trả lời; cấm các mệnh đề xua đuổi hoặc cấm khách nhắn tiếp dù đầu câu có *"Dạ"*. |
| 4 | `H-042`: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | FAIL | PASS | **Người đúng** (`fp`) | Câu ngắn gọn, lịch sự (`Dạ ... ạ`), đủ số tiền và thời gian nhận tiền; judge phạt oan vì thiếu câu xin lỗi. **Sửa rubric `tone_ok`:** Không bắt buộc phải có câu xin lỗi trong thông báo đã hoàn tiền thành công. |
| 5 | `H-051`: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | FAIL | PASS | **Người đúng** (`fp`) | Từ *"refund"* nằm trong danh mục thuật ngữ CSKH LogiX cho phép; judge phạt vì lẫn tiếng Anh. **Sửa rubric `tone_ok`:** Cho phép từ *"refund"* tương đương *"hoàn tiền"*. |
| 6 | `H-063`: *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* | PASS | FAIL | **Người đúng** (`fn`) | Tự ý hứa hẹn *"sẽ hoàn thêm"* ngoài quyết định của hệ thống. **Sửa rubric `tone_ok`:** Đánh FAIL mọi câu hứa hẹn bồi thường/hoàn thêm ngoài kết quả đã chốt. |
| 7 | `H-070`: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* & `H-094` (mất dấu tiếng Việt) | PASS | FAIL | **Người đúng** (`fn`) | Dùng emoji `😂😂` phản cảm trong ngữ cảnh khiếu nại (`H-070`) và văn bản không dấu (`H-094`). **Sửa rubric `tone_ok`:** Cấm dùng emoji trong phản hồi khiếu nại và bắt buộc tiếng Việt có dấu chuẩn. |
| 8 | `H-081`: *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* | FAIL | PASS | **Judge đúng** (`fp` giả do nhãn người sai) | Câu từ chối cụt, thiếu hướng dẫn hỗ trợ tiếp theo (*"Anh/chị cần hỗ trợ thêm..."*); người gán nhãn đọc nhầm ticket. **Hành động:** Sửa lại nhãn chuẩn (human gold label) của `H-081` thành `FAIL`. |
| 9 | `HL-015`, `HL-016`, `HL-020`, `HL-028` (`helpful`) | PASS | FAIL | **Người đúng** (`fn`) | Reply nói sai số tiền hoàn so với ledger (`55.000đ` vs `40.000đ`/`35.000đ`, `90.000đ` vs `120.000đ`), kèm văn mẫu xin lỗi dài dòng làm judge bị đánh lừa (verbosity/politeness bias). **Hành động:** Loại judge `helpful`; dùng code grader `ReplyMatchesLedger` (`FM-08`) đối chiếu trực tiếp với `snapshot["refund_vnd"]`. |

## Kết luận
- **Tiêu chí bị loại và lý do (dẫn ma trận nhầm lẫn):**
  - Loại **`helpful`** vì ma trận nhầm lẫn trên 100 mẫu là `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`, dẫn đến **Recall = `0.300` (< sàn `0.70`)** và **Cohen's κ = `0.375` (< sàn `0.60`)**.
  - Nguyên nhân gốc rễ: trong 21 ca bỏ lọt lỗi (`fn`), có tới **18 ca báo sai số tiền hoàn so với ledger** (`HL-015`, `HL-016`, `HL-020`, `HL-028`, `HL-035`, `HL-041`, `HL-043`, `HL-053`, `HL-058`, `HL-062`, `HL-070`, `HL-072`, `HL-074`, `HL-087`, `HL-090`, `HL-096`, `HL-098`, `HL-100`) và **3 ca sai xưng hô** (`HL-047`, `HL-091`, `HL-097`). LLM judge chỉ đọc bề mặt câu chữ lịch sự/dài dòng mà không biết trạng thái thực trong `refund_ledger`, nên ước lượng tỉ lệ lỗi quan sát được bị lệch nặng (`observed_fail_rate = 0.090` so với thực tế `corrected_fail_rate = 0.300`). Theo nguyên tắc của bài: **tiền và phê duyệt luôn chấm bằng code (`RefundAmountCorrect`, `ReplyMatchesLedger`), không bao giờ giao cho LLM judge**.
- **Rủi ro còn lại:** Judge `tone_ok` tuy đạt sàn (`κ = 0.757`, `P = 0.857`, `R = 0.800`) nhưng mới chỉ được kiểm chuẩn trên tập dữ liệu replay công khai (`judge_tone_public.csv`); sau khi cập nhật rubric cần lấy mẫu và gán nhãn người mới trên một tập held-out độc lập để xác nhận lại trước khi đưa vào giám sát thực tế.

