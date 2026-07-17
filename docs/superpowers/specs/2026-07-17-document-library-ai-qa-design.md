# Thiết kế Kho tài liệu và Hỏi đáp AI đa-agent 3D

Ngày: 17/07/2026  
Trạng thái: Đã thống nhất thiết kế trong phiên brainstorming

## 1. Mục tiêu

Mở rộng prototype MediaX Agent Bank bằng hai khu vực mới:

1. Kho tài liệu cấp hệ thống, hỗ trợ mô phỏng upload, phân loại, tổ chức thư mục và theo dõi trạng thái xử lý.
2. Hỏi đáp AI đa-agent, hiển thị đồng thời hội thoại và quá trình nhiều agent 3D tự động phối hợp xử lý câu hỏi.

Phiên bản này chỉ dùng dữ liệu và trạng thái giả lập. Không lưu file, không gọi API AI và không triển khai backend.

## 2. Nguyên tắc trải nghiệm

- Giữ **Tổng quan** là màn hình mặc định.
- Thêm **Kho tài liệu** và **Hỏi đáp AI** vào thanh điều hướng bên trái.
- Giữ ngôn ngữ hình ảnh hiện tại: nền xanh đậm, điểm nhấn xanh dương, trạng thái xanh lá/vàng và mật độ thông tin phù hợp hệ thống nghiệp vụ ngân hàng.
- Sử dụng nội dung demo nhất quán với câu chuyện thẩm định hồ sơ vay doanh nghiệp 2,5 tỷ đồng.
- Tái sử dụng model và sân khấu 3D hiện có; không thay đổi tài sản 3D.

## 3. Kho tài liệu

### 3.1. Bố cục

Màn hình gồm:

- Phần tiêu đề, thống kê nhanh và hành động **Tải tài liệu lên**.
- Cây thư mục ở cột trái, gồm thư mục hệ thống và thư mục nghiệp vụ mẫu.
- Khu vực chính chứa tìm kiếm, chip lọc loại tài liệu, điều khiển sắp xếp/chế độ xem và bảng tài liệu.
- Panel chi tiết xuất hiện khi chọn một tài liệu, hiển thị metadata, trạng thái xử lý và agent được phép sử dụng.

### 3.2. Loại tài liệu

Prototype hỗ trợ các loại:

- Quy trình
- Chính sách
- Biểu mẫu
- Báo cáo
- Dữ liệu tham chiếu

Người dùng có thể lọc theo một loại hoặc xem tất cả.

### 3.3. Thư mục

Cây thư mục mock gồm:

- Tất cả tài liệu
- Tín dụng doanh nghiệp
- Tuân thủ và pháp lý
- Vận hành hồ sơ
- Biểu mẫu nghiệp vụ
- Tài liệu lưu trữ

Chọn thư mục cập nhật danh sách tài liệu ở khu vực chính. Có hành động tạo thư mục mới và hiển thị số tài liệu trong từng thư mục. Việc tạo thư mục chỉ tồn tại trong state của phiên trình duyệt.

### 3.4. Upload giả lập

Nút **Tải tài liệu lên** mở modal hỗ trợ kéo-thả hoặc chọn nhiều file. Các định dạng hiển thị trong prototype là PDF, DOCX và XLSX.

Trước khi xác nhận, người dùng chọn:

- Loại tài liệu
- Thư mục đích
- Các agent được phép sử dụng

Sau khi xác nhận, mỗi file đi qua chuỗi trạng thái:

1. Đang tải
2. Đang phân loại
3. Đang lập chỉ mục
4. Sẵn sàng

Một file mẫu có thể chuyển sang trạng thái lỗi để minh họa thông báo nguyên nhân và hành động **Thử lại**. Toàn bộ tiến trình dùng timer phía client.

## 4. Hỏi đáp AI đa-agent

### 4.1. Bố cục đã chọn

Sử dụng phương án A — bố cục hai cột cân bằng:

- Cột trái: hội thoại và nguồn trích dẫn.
- Cột phải: sân khấu agent 3D và trạng thái điều phối.

Trên màn hình nhỏ, hai khu vực chuyển thành tab **Hội thoại** và **Agent 3D**.

### 4.2. Cột hội thoại

Bao gồm:

- Tiêu đề phiên hỏi đáp và trạng thái hệ thống.
- Các câu hỏi gợi ý dùng cho demo nhanh.
- Tin nhắn của người dùng.
- Cập nhật ngắn về tiến độ điều phối.
- Câu trả lời cuối có mức tin cậy, danh sách agent tham gia và tài liệu nguồn.
- Ô nhập câu hỏi, nút gửi, nút dừng tác vụ và nút đặt lại hội thoại.

Các nguồn trích dẫn có thể nhấp để mở panel xem thông tin tài liệu mock.

### 4.3. Điều phối tự động

Người dùng không chọn agent trước khi hỏi. Điều phối viên tự phân tích câu hỏi và kích hoạt 2–3 agent phù hợp trong số:

- Điều phối viên AI
- Chuyên gia tín dụng
- Chuyên gia tuân thủ
- Chuyên gia vận hành

Quy trình hiển thị theo bốn giai đoạn:

1. Phân rã yêu cầu
2. Phân tích song song
3. Kiểm tra chéo
4. Tổng hợp câu trả lời

Agent đang xử lý được làm nổi bật trên sân khấu 3D. Dòng trạng thái dưới sân khấu hiển thị giai đoạn hiện tại và kết quả ngắn của từng agent. Chuỗi này được điều khiển bằng timer và dữ liệu mẫu cố định.

### 4.4. Kịch bản demo chính

Câu hỏi mặc định:

> Đánh giá khả năng vay 2,5 tỷ đồng của khách hàng doanh nghiệp này.

Điều phối viên kích hoạt ba chuyên gia tín dụng, tuân thủ và vận hành. Kết quả cuối là **Phê duyệt có điều kiện**, kèm lưu ý DTI gần ngưỡng và cần bổ sung tờ khai thuế gần nhất.

Các câu hỏi gợi ý bổ sung:

- Điểm rủi ro chính của hồ sơ là gì?
- Hồ sơ đang thiếu tài liệu nào?
- Chính sách nào được dùng để đưa ra kết luận?

## 5. Thành phần và ranh giới

Các khối giao diện được tách theo trách nhiệm:

- `Home`: quản lý điều hướng cấp màn hình và các overlay chung.
- `DocumentsScreen`: quản lý thư mục, bộ lọc, bảng tài liệu và tài liệu đang chọn.
- `UploadDocumentModal`: quản lý danh sách file và tiến trình upload giả lập.
- `AIQAScreen`: quản lý lịch sử hội thoại, câu hỏi gợi ý và trạng thái phiên hỏi đáp.
- `AgentStage3D`: tiếp tục chịu trách nhiệm render model 3D; nhận trạng thái agent/giai đoạn để thể hiện lựa chọn và hoạt động.
- Panel tài liệu dùng chung: hiển thị metadata cho cả Kho tài liệu và nguồn trích dẫn trong Hỏi đáp AI.

State chỉ tồn tại phía client và được reset khi tải lại trang. Không thêm cơ sở dữ liệu, R2 hoặc biến môi trường.

## 6. Trạng thái lỗi và trường hợp biên

- Upload không có file: vô hiệu hóa nút xác nhận.
- File lỗi: hiển thị lý do và nút thử lại.
- Không có tài liệu phù hợp bộ lọc: hiển thị empty state có hành động xóa bộ lọc.
- Câu hỏi trống: vô hiệu hóa nút gửi.
- Đang chạy điều phối: vô hiệu hóa gửi câu hỏi mới và cho phép dừng.
- Dừng tác vụ: giữ lại tiến độ hiện tại và hiển thị trạng thái đã dừng.
- Model 3D chưa tải: tiếp tục dùng fallback hiện có để giao diện vẫn sử dụng được.

## 7. Responsive và khả năng sử dụng

- Desktop: Hỏi đáp AI dùng hai cột gần bằng nhau; Kho tài liệu dùng cây thư mục và bảng song song.
- Tablet/mobile: thanh điều hướng theo cơ chế hiện có; Kho tài liệu xếp dọc; Hỏi đáp AI dùng hai tab.
- Nút và trường nhập có nhãn truy cập phù hợp.
- Các trạng thái không chỉ phân biệt bằng màu mà còn có biểu tượng hoặc nhãn chữ.
- Tương tác chính hỗ trợ chuột, bàn phím và cảm ứng.

## 8. Tiêu chí nghiệm thu

- Tổng quan vẫn là màn hình mặc định.
- Hai mục điều hướng mới hoạt động và không làm hỏng các màn hình hiện có.
- Kho tài liệu lọc đúng theo thư mục, loại và từ khóa.
- Modal upload mô phỏng đủ chuỗi trạng thái, có trường hợp lỗi và thử lại.
- Câu hỏi mẫu kích hoạt đúng chuỗi điều phối và làm nổi bật agent tương ứng.
- Câu trả lời cuối hiển thị mức tin cậy, agent tham gia và nguồn trích dẫn.
- Hỏi đáp AI hiển thị hai cột trên desktop và hai tab trên màn hình nhỏ.
- Build production thành công.
- Các bài kiểm tra hiện có tiếp tục vượt qua; bổ sung kiểm tra phù hợp cho nội dung và tương tác mới.

## 9. Ngoài phạm vi

- Upload hoặc lưu file thật
- Cơ sở dữ liệu và phân quyền thật
- Gọi mô hình AI hoặc orchestration backend
- Trích xuất nội dung và embedding tài liệu
- Đồng bộ trạng thái giữa các thiết bị hoặc phiên trình duyệt
- Thay thế model nhân vật 3D hiện có
