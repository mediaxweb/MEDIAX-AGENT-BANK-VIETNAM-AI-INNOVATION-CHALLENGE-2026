# QA Live Test Templates

Các file trong thư mục này là mẫu reusable cho live test hỏi đáp trên web:

```text
https://mediax-agent-bank.ai5phut.com/
```

## Files

```text
test_suite_50.md
```

Danh sách 50 testcase live Q&A đã chuẩn bị, gồm ID, nhóm kiểm thử, domain/agent kỳ vọng và kết quả mong đợi.

```text
testcase.template.json
```

Mẫu để tạo testcase mới trong `tests/qa_live_testing/cases/`.

```text
result.template.json
```

Mẫu để lưu kết quả sau khi chạy live test trong thư mục riêng của testcase.

```text
logbug.template.json
```

Mẫu để tạo artifact logbug khi testcase fail nghiêm trọng.

## Cách Dùng

1. Chọn testcase trong `test_suite_50.md` hoặc thư mục `cases/TC-XX/`.
2. Mở `cases/TC-XX/testcase.json` và copy nguyên văn `input_question`.
3. Chạy test theo `workflow.md` trên web QA.
4. Lưu screenshot/text evidence vào `cases/TC-XX/evidence/`.
5. Điền actual output, routing result, score và verdict vào `cases/TC-XX/result.json`.
6. Nếu cần log bug, tạo bug artifact trong `cases/TC-XX/logbug/`.
7. Khi tạo testcase mới ngoài bộ 50 case, copy `templates/testcase.template.json` và `templates/result.template.json` vào folder testcase mới.

## Cấu Trúc Chuẩn Cho Một Testcase

```text
tests/qa_live_testing/cases/TC-XX/
  testcase.json
  result.json
  evidence/
    result.txt
  logbug/
    bug.json
```
