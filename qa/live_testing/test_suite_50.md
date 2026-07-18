# QA Live Test Suite - 50 Testcases

Bộ testcase dùng cho live test trực tiếp trên web QA, không dùng API.

| ID | Category | Domain/Agent | Title | Expected |
| --- | --- | --- | --- | --- |
| TC-01 | Negative | Chuyên gia Pháp lý | Doanh nghiệp thiếu Giấy ĐKKD | FAILED |
| TC-02 | Negative | Chuyên gia Pháp lý | Cá nhân thiếu giấy tờ định danh | FAILED |
| TC-03 | Positive | Chuyên gia Pháp lý | Hồ sơ pháp lý doanh nghiệp đầy đủ | PASSED |
| TC-04 | Negative | Chuyên gia Pháp lý | Giấy tờ định danh hết hạn | FAILED |
| TC-05 | Negative | Chuyên gia Chính sách | Vay vượt 80% nhu cầu vốn | CONDITIONAL |
| TC-06 | Boundary | Chuyên gia Chính sách | Vay đúng ngưỡng 80% nhu cầu vốn | PASSED |
| TC-07 | Boundary | Chuyên gia Chính sách | Tổng nhu cầu vốn bằng 0 | FAILED |
| TC-08 | Negative | Chuyên gia Chính sách | Mục đích vay đầu cơ chứng khoán | FAILED |
| TC-09 | Negative | Chuyên gia Chính sách | Mục đích vay mô tả mơ hồ | NEEDS_REVIEW |
| TC-10 | Boundary | Chuyên gia Chính sách | Thời hạn vay vượt 360 tháng | FAILED |
| TC-11 | Negative | Chuyên gia Chính sách | Khách hàng chưa đủ 18 tuổi | FAILED |
| TC-12 | Boundary | Chuyên gia Chính sách | Khách hàng đúng 18 tuổi | PASSED |
| TC-13 | Negative | Chuyên gia Tài chính | DTI vượt 40% | CONDITIONAL |
| TC-14 | Boundary | Chuyên gia Tài chính | DTI đúng 40% | PASSED |
| TC-15 | Negative | Chuyên gia Tài chính | Thiếu báo cáo tài chính | FAILED |
| TC-16 | Negative | Chuyên gia Tài chính | Báo cáo tài chính thiếu thu nhập | NEEDS_REVIEW |
| TC-17 | Calculation | Chuyên gia Tài chính | Tính hạn mức theo thu nhập | CONDITIONAL |
| TC-18 | Calculation | Chuyên gia Tài chính | Không còn năng lực trả nợ tháng | FAILED |
| TC-19 | Negative | Chuyên gia Tài sản bảo đảm | LTV tài sản vượt 70% | CONDITIONAL |
| TC-20 | Boundary | Chuyên gia Tài sản bảo đảm | LTV đúng 70% | PASSED |
| TC-21 | Negative | Chuyên gia Tài sản bảo đảm | Không có tài sản bảo đảm | FAILED |
| TC-22 | Negative | Chuyên gia Tài sản bảo đảm | Tài sản thiếu giấy sở hữu | CONDITIONAL |
| TC-23 | Negative | Chuyên gia Tài sản bảo đảm | Chứng thư định giá hết hiệu lực | NEEDS_REVIEW |
| TC-24 | Negative | Chuyên gia Tài sản bảo đảm | Tài sản tranh chấp pháp lý | FAILED |
| TC-25 | Negative | Chuyên gia Tài chính | Dòng tiền âm sau trả nợ | CONDITIONAL |
| TC-26 | Calculation | Chuyên gia Tài chính | Biên lợi nhuận ròng thấp | NEEDS_REVIEW |
| TC-27 | Calculation | Chuyên gia Tài chính | DSCR dưới 1.2 lần | CONDITIONAL |
| TC-28 | Boundary | Chuyên gia Tài chính | DSCR đúng 1.2 lần | PASSED |
| TC-29 | Positive | Chuyên gia Chính sách | Vốn tự có đạt 20% | PASSED |
| TC-30 | Negative | Chuyên gia Chính sách | Vốn tự có chỉ 10% | CONDITIONAL |
| TC-31 | Negative | Chuyên gia Chính sách | Nguồn trả nợ từ khoản vay mới | FAILED |
| TC-32 | Negative | Chuyên gia Chính sách | Thiếu lịch trả nợ | NEEDS_REVIEW |
| TC-33 | Negative | Chuyên gia Tuân thủ | Khách hàng nằm trong danh sách cấm vận | FAILED |
| TC-34 | Negative | Chuyên gia Tuân thủ | Khách hàng PEP | NEEDS_REVIEW |
| TC-35 | Negative | Chuyên gia Tuân thủ | Địa chỉ KYC không khớp hồ sơ | CONDITIONAL |
| TC-36 | Security | Chuyên gia Tuân thủ | Dấu hiệu giao dịch đáng ngờ | NEEDS_REVIEW |
| TC-37 | Security | Chuyên gia Tuân thủ | Prompt injection trong câu hỏi | NEEDS_REVIEW |
| TC-38 | Negative | Chuyên gia Tuân thủ | Thiếu xác minh chủ sở hữu hưởng lợi | CONDITIONAL |
| TC-39 | Routing | Chuyên gia Pháp lý | Routing ưu tiên hard stop pháp lý | FAILED |
| TC-40 | Routing | Chuyên gia Tài sản bảo đảm | Routing câu hỏi LTV sang tài sản | CONDITIONAL |
| TC-41 | Negative | Chuyên gia Vận hành | Giải ngân khi chưa hoàn tất pháp lý | FAILED |
| TC-42 | Negative | Chuyên gia Vận hành | Giải ngân sai người thụ hưởng | CONDITIONAL |
| TC-43 | Negative | Chuyên gia Vận hành | Thiếu checklist trước giải ngân | CONDITIONAL |
| TC-44 | Positive | Chuyên gia Vận hành | Đủ điều kiện tạo báo cáo hồ sơ | PASSED |
| TC-45 | Negative | Chuyên gia Vận hành | Quá hạn bổ sung chứng từ | CONDITIONAL |
| TC-46 | Regression | Chuyên gia Pháp lý | Không trả lời ngoài tài liệu nguồn | NEEDS_REVIEW |
| TC-47 | Negative | Chuyên gia Chính sách | Câu hỏi thiếu dữ liệu tính toán | NEEDS_REVIEW |
| TC-48 | Regression | Chuyên gia Tài chính | Câu hỏi tiếng Anh giữ đúng ngôn ngữ | CONDITIONAL |
| TC-49 | Routing | Chuyên gia Tuân thủ | Routing câu hỏi AML sang tuân thủ | NEEDS_REVIEW |
| TC-50 | End-to-End | Chuyên gia Pháp lý | Case tổng hợp nhiều điều kiện | FAILED |
