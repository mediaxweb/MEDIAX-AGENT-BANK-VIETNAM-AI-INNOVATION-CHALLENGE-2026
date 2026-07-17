# Thiết kế Kho tài liệu và Hỏi đáp AI đa-agent 3D

Ngày: 17/07/2026  
Trạng thái: Đã cập nhật theo hướng A — trải nghiệm phẳng, RAG tự điều phối

## 1. Mục tiêu

Mở rộng prototype MediaX Agent Bank bằng hai khu vực mới:

1. Kho tài liệu cấp hệ thống, hỗ trợ mô phỏng upload và theo dõi trạng thái xử lý trong một danh sách phẳng.
2. Hỏi đáp AI đa-agent, hiển thị đồng thời hội thoại và quá trình nhiều agent 3D tự động phối hợp xử lý câu hỏi.

Phiên bản này chỉ dùng dữ liệu và trạng thái giả lập. Không lưu file, không gọi API AI và không triển khai backend.

## 2. Nguyên tắc trải nghiệm

- Giữ **Tổng quan** là màn hình mặc định.
- Thêm **Kho tài liệu** và **Hỏi đáp AI** vào thanh điều hướng bên trái.
- Giữ ngôn ngữ hình ảnh hiện tại: nền xanh đậm, điểm nhấn xanh dương, trạng thái xanh lá/vàng và mật độ thông tin phù hợp hệ thống nghiệp vụ ngân hàng.
- Sử dụng nội dung demo nhất quán với câu chuyện thẩm định hồ sơ vay doanh nghiệp 2,5 tỷ đồng.
- Tái sử dụng model và sân khấu 3D hiện có; không thay đổi tài sản 3D.
- Bỏ thanh tìm kiếm hồ sơ/chuyên gia trên topbar để giảm nhiễu và dành không gian cho trạng thái hệ thống.
- RAG tự phân loại tài liệu và điều phối agent; người dùng không cấu hình thư mục, loại tài liệu hoặc quyền agent.

## 3. Kho tài liệu

### 3.1. Bố cục

Màn hình gồm:

- Phần tiêu đề, thống kê nhanh và hành động **Tải tài liệu lên**.
- Thanh tìm kiếm riêng cho tên tài liệu.
- Bảng danh sách tài liệu phẳng, hiển thị tên, dung lượng, ngày cập nhật và trạng thái xử lý.
- Empty state khi từ khóa không có kết quả.

Màn hình không hiển thị cây thư mục, tạo thư mục, chip loại tài liệu hoặc card/panel chi tiết tài liệu.

### 3.2. RAG tự tổ chức tri thức

Các thuộc tính loại, thư mục và agent được phép sử dụng không xuất hiện trong UI. Prototype mô phỏng việc RAG tự nhận diện nội dung, lập chỉ mục và cung cấp tài liệu cho agent phù hợp. Metadata nội bộ có thể tiếp tục tồn tại trong mock data để phục vụ nguồn trích dẫn, nhưng không phải cấu hình của người dùng.

### 3.3. Upload giả lập

Nút **Tải tài liệu lên** mở modal hỗ trợ kéo-thả hoặc chọn nhiều file. Các định dạng hiển thị trong prototype là PDF, DOCX và XLSX.

Người dùng chỉ chọn hoặc kéo-thả file rồi bắt đầu xử lý. Modal không có trường loại tài liệu, thư mục đích hoặc quyền sử dụng của agent.

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
- Tin nhắn của người dùng.
- Cập nhật ngắn về tiến độ điều phối.
- Câu trả lời cuối có mức tin cậy, danh sách agent tham gia và tài liệu nguồn.
- Ô nhập câu hỏi và nút gửi.

Không hiển thị câu hỏi gợi ý, nút dừng hoặc nút đặt lại. Trong khi đang điều phối, ô nhập và nút gửi bị vô hiệu hóa cho đến khi câu trả lời hoàn tất.

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

## 5. Thành phần và ranh giới

Các khối giao diện được tách theo trách nhiệm:

- `Home`: quản lý điều hướng cấp màn hình và các overlay chung.
- `DocumentsScreen`: quản lý tìm kiếm theo tên, bảng tài liệu phẳng và modal upload.
- `UploadDocumentModal`: quản lý danh sách file và tiến trình upload giả lập.
- `AIQAScreen`: quản lý lịch sử hội thoại và trạng thái phiên hỏi đáp.
- `AgentStage3D`: tiếp tục chịu trách nhiệm render model 3D; nhận trạng thái agent/giai đoạn để thể hiện lựa chọn và hoạt động.
- Panel nguồn trích dẫn: chỉ hiển thị metadata khi người dùng mở một nguồn trong Hỏi đáp AI.

State chỉ tồn tại phía client và được reset khi tải lại trang. Không thêm cơ sở dữ liệu, R2 hoặc biến môi trường.

## 6. Trạng thái lỗi và trường hợp biên

- Upload không có file: vô hiệu hóa nút xác nhận.
- File lỗi: hiển thị lý do và nút thử lại.
- Không có tài liệu phù hợp từ khóa: hiển thị empty state có hành động xóa tìm kiếm.
- Câu hỏi trống: vô hiệu hóa nút gửi.
- Đang chạy điều phối: vô hiệu hóa ô nhập và gửi câu hỏi mới cho đến khi hoàn tất.
- Model 3D chưa tải: tiếp tục dùng fallback hiện có để giao diện vẫn sử dụng được.

## 7. Responsive và khả năng sử dụng

- Desktop: Hỏi đáp AI dùng hai cột gần bằng nhau; Kho tài liệu dùng một bảng phẳng toàn chiều rộng.
- Tablet/mobile: thanh điều hướng theo cơ chế hiện có; bảng tài liệu cuộn ngang khi cần; Hỏi đáp AI dùng hai tab.
- Nút và trường nhập có nhãn truy cập phù hợp.
- Các trạng thái không chỉ phân biệt bằng màu mà còn có biểu tượng hoặc nhãn chữ.
- Tương tác chính hỗ trợ chuột, bàn phím và cảm ứng.

## 8. Tiêu chí nghiệm thu

- Tổng quan vẫn là màn hình mặc định.
- Hai mục điều hướng mới hoạt động và không làm hỏng các màn hình hiện có.
- Topbar không còn thanh tìm kiếm hồ sơ/chuyên gia.
- Kho tài liệu chỉ có tìm kiếm theo tên và danh sách phẳng; không còn thư mục, loại tài liệu hoặc card chi tiết.
- Modal upload mô phỏng đủ chuỗi trạng thái, có trường hợp lỗi và thử lại.
- Modal upload không yêu cầu loại tài liệu, thư mục đích hoặc quyền agent.
- Câu hỏi của người dùng kích hoạt đúng chuỗi điều phối và làm nổi bật agent tương ứng.
- Hỏi đáp AI không có câu hỏi gợi ý, đặt lại hoặc dừng.
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
