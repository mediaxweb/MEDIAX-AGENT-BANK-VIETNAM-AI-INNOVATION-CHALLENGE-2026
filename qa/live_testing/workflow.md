# QA Live Test Workflow

Quy trình này dùng cho các testcase hỏi đáp chạy trực tiếp trên web mặc định:

```text
https://mediax-agent-bank.ai5phut.com/
```

Nếu trang không tự mở đúng khu vực hỏi đáp, chọn mục:

```text
Hỏi đáp AI
```

## 1. Chọn Testcase

Mỗi testcase phải có một thư mục riêng trong:

```text
tests/qa_live_testing/cases/<test_case_id>/
```

Ví dụ:

```text
tests/qa_live_testing/cases/TC-05/testcase.json
```

Danh sách bộ 50 testcase chuẩn nằm tại:

```text
tests/qa_live_testing/test_suite_50.md
```

Mọi file liên quan đến testcase đó phải nằm trong cùng thư mục testcase:

```text
tests/qa_live_testing/cases/TC-05/
  testcase.json
  result.json
  evidence/
  logbug/
```

Đọc tối thiểu các trường:

```text
test_case_id
title
target_web_url
base_web_url
target_section
test_category
preconditions
test_data
test_steps
input_question
expected_answer
routing_expectation
pass_criteria
fail_criteria
scoring_rubric
logbug_condition
```

## 2. Gửi Câu Hỏi

Mở `base_web_url` hoặc `target_web_url` nếu testcase có khai báo riêng. Vào mục `target_section`, tạo phiên mới nếu cần.

Trước khi gửi câu hỏi, tối ưu layout để lưu evidence:

```text
Mở rộng vùng chat/hội thoại tối đa trong khả năng của web.
Thu gọn hoặc ẩn sidebar/menu không cần thiết nếu web có nút hỗ trợ.
Giữ panel TRAO ĐỔI GIỮA CÁC CHUYÊN GIA vẫn quan sát được nếu cần chụp cùng routing.
Không che khuất câu hỏi, câu trả lời, nguồn trích dẫn hoặc trace ID.
```

Sau đó copy nguyên văn `input_question` vào ô:

```text
Nhập câu hỏi nghiệp vụ...
```

Gửi câu hỏi và chờ Agent trả lời xong.

## 3. Verify Điều Phối Agent

Kiểm tra panel bên phải:

```text
TRAO ĐỔI GIỮA CÁC CHUYÊN GIA
```

Đối chiếu với `routing_expectation` trong testcase.

Các điểm cần xác nhận:

```text
expected_router
expected_agent_or_domain
expected_message_contains
source/domain được truy xuất
trace_id nếu có
```

Ví dụ đạt:

```text
Bộ điều phối -> Chuyên gia Chính sách
Đã chọn miền Chính sách để xử lý câu hỏi.
```

Nếu routing sai, ghi nhận lỗi ở nhóm `agent_routing`.

## 4. Lưu Evidence

Lưu evidence vào thư mục của chính testcase:

```text
tests/qa_live_testing/cases/<test_case_id>/evidence/
```

Cần lưu:

```text
Ảnh chụp câu hỏi và câu trả lời sau khi đã mở rộng vùng chat tối đa
Ảnh chụp hoặc text panel TRAO ĐỔI GIỮA CÁC CHUYÊN GIA sau khi đã tối ưu layout
Toàn bộ text response của Agent
Nguồn trích dẫn
Trace ID nếu có
Thời gian chạy test
```

Nếu screenshot bị thiếu nội dung, bị trắng, hoặc không đọc được, bắt buộc lưu thêm text evidence:

```text
tests/qa_live_testing/cases/<test_case_id>/evidence/result.txt
```

Text evidence phải có input question, actual answer, routing panel, source và trace ID.

## 5. Trích Xuất Actual Output

Từ response của Agent, bóc tách các thông tin cần chấm.

Ví dụ:

```json
{
  "result": "CONDITIONAL",
  "issue": "Số tiền vay vượt 80% tổng nhu cầu vốn",
  "loan_to_capital_need_ratio": "90%",
  "max_amount_by_capital_need": "8 tỷ VND",
  "recommendation": "Giảm khoản vay xuống tối đa 8 tỷ hoặc chứng minh thêm vốn tự có"
}
```

Nếu Agent không trả field có cấu trúc, trích xuất từ text và ghi rõ field nào không xuất hiện trực tiếp.

## 6. So Sánh Với Expected

Đối chiếu actual output với:

```text
expected_answer
pass_criteria
fail_criteria
routing_expectation
```

Kết luận từng tiêu chí theo một trong các trạng thái:

```text
PASS
FAIL
REVIEW
NOT_OBSERVED
```

## 7. Chấm Điểm

Chấm theo `scoring_rubric`.

Rubric chuẩn cho testcase Q&A multi-agent:

```text
accuracy: 35
groundedness: 20
agent_routing: 10
completeness: 20
explainability: 15
total: 100
```

Ý nghĩa:

```text
accuracy: Agent tính/kết luận đúng nghiệp vụ.
groundedness: Agent bám đúng rule/tài liệu nguồn.
agent_routing: Bộ điều phối chọn đúng chuyên gia/domain.
completeness: Câu trả lời đủ result, issue, số liệu, recommendation.
explainability: Agent giải thích rõ phép tính/lý do.
```

## 8. Ghi Result File

Tạo result file ngay trong thư mục testcase:

```text
tests/qa_live_testing/cases/<test_case_id>/result.json
```

Ví dụ:

```text
tests/qa_live_testing/cases/TC-05/result.json
```

Result file cần có:

```text
test_case_id
test_case_file
executed_at
target_web_url
verdict
log_bug
input_question
actual_answer
expected_answer
routing_result
criteria_results
score
source_and_trace
evidence_files
recommendation
```

## 9. Quy Tắc Verdict

Dùng các verdict sau:

```text
NOT_RUN
PASS
PARTIAL_PASS_NEEDS_REVIEW
FAIL
LOG_BUG
BLOCKED
```

Gợi ý quyết định:

```text
NOT_RUN: Chỉ dùng trước khi chạy live test, không dùng làm kết luận sau khi đã submit câu hỏi.
PASS: Đúng routing, đúng nghiệp vụ, đủ expected chính.
PARTIAL_PASS_NEEDS_REVIEW: Đúng phần lõi nhưng thiếu format, thiếu nhãn result hoặc thiếu recommendation.
FAIL: Sai nghiệp vụ nhưng chưa đủ điều kiện log bug nghiêm trọng.
LOG_BUG: Sai rule quan trọng, routing sai gây kết quả sai, hoặc Agent duyệt hồ sơ đáng lẽ phải cảnh báo/chặn.
BLOCKED: Không chạy được test do web lỗi, thiếu quyền, không có response hoặc không lưu được evidence.
```

## 10. Điều Kiện Log Bug

Log bug nếu một trong các điều kiện trong `logbug_condition.log_when` xảy ra.

Bug report tối thiểu cần có:

```text
title
severity
test_case_id
input_question
expected_answer
actual_answer
routing_result
source_and_trace
evidence_files
business_impact
steps_to_reproduce
```

## 11. Checklist Cho Codex Khi Chạy Live

Trước khi kết thúc live test, Codex phải kiểm tra:

```text
[ ] Đã gửi đúng input_question.
[ ] Đã chờ Agent trả lời xong.
[ ] Đã verify routing trong panel TRAO ĐỔI GIỮA CÁC CHUYÊN GIA.
[ ] Đã lưu screenshot evidence.
[ ] Evidence nằm trong thư mục testcase hiện tại.
[ ] Đã lưu full text actual answer.
[ ] Đã lưu source/trace nếu có.
[ ] Đã chấm từng criteria.
[ ] Đã chấm scoring_rubric đủ 100 điểm.
[ ] Đã tạo result JSON hợp lệ trong cùng thư mục testcase.
[ ] Đã kết luận verdict và log_bug.
```
