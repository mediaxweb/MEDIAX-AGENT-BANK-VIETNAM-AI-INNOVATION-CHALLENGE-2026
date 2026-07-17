"use client";

import { FileText, FolderPlus, Search, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { documentFolders, documentRecords, filterDocuments } from "./prototype-data";
import { Badge, Button, PageHeading } from "./ui";

const documentTypes = ["Tất cả", "Quy trình", "Chính sách", "Biểu mẫu", "Báo cáo", "Dữ liệu tham chiếu"];
const agentNames: Record<string, string> = {
  orchestrator: "Điều phối viên AI",
  credit: "Chuyên gia tín dụng",
  compliance: "Chuyên gia tuân thủ",
  operations: "Chuyên gia vận hành",
};

function statusTone(status: string) {
  if (status === "Sẵn sàng") return "success";
  if (status === "Đang xử lý") return "info";
  return "warning";
}

export default function DocumentsScreen() {
  const [folderId, setFolderId] = useState("all");
  const [type, setType] = useState("Tất cả");
  const [query, setQuery] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState(documentRecords[0].id);

  const filteredDocuments = useMemo(
    () => filterDocuments(documentRecords, folderId, type, query),
    [folderId, type, query],
  );
  const selectedDocument = documentRecords.find((document) => document.id === selectedDocumentId);
  const selectedFolder = documentFolders.find((folder) => folder.id === selectedDocument?.folderId);

  function resetFilters() {
    setFolderId("all");
    setType("Tất cả");
    setQuery("");
  }

  return <>
    <PageHeading title="Kho tài liệu" subtitle="Quản lý nguồn tri thức nghiệp vụ cho đội chuyên gia AI">
      <Button variant="secondary"><FolderPlus size={16} /> Tạo thư mục</Button>
      <Button><Upload size={16} /> Tải tài liệu lên</Button>
    </PageHeading>

    <section className="document-summary" aria-label="Tổng quan kho tài liệu">
      {[
        ["1.284", "Tổng tài liệu"],
        ["1.247", "Sẵn sàng"],
        ["24", "Đang xử lý"],
        ["13", "Cần kiểm tra"],
      ].map(([value, label]) => <article className="card" key={label}><strong>{value}</strong><span>{label}</span></article>)}
    </section>

    <div className="documents-layout">
      <aside className="document-folders card" aria-label="Thư mục tài liệu">
        <div><h2>Thư mục</h2><span>6 khu vực lưu trữ</span></div>
        {documentFolders.map((folder) => <button key={folder.id} className={folderId === folder.id ? "active" : ""} onClick={() => setFolderId(folder.id)}>
          <span>{folder.name}</span><b>{folder.count}</b>
        </button>)}
      </aside>

      <section className="document-workspace">
        <div className="document-controls card">
          <label className="search-box"><Search size={17} /><span className="sr-only">Tìm trong kho tài liệu</span><input aria-label="Tìm trong kho tài liệu" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm trong kho tài liệu" /></label>
          <div className="document-type-chips" aria-label="Lọc theo loại tài liệu">
            {documentTypes.map((item) => <button key={item} className={type === item ? "selected" : ""} onClick={() => setType(item)}>{item}</button>)}
          </div>
        </div>

        <div className="document-table-card card">
          {filteredDocuments.length ? <table className="document-table">
            <caption className="sr-only">Danh sách tài liệu nghiệp vụ</caption>
            <thead><tr><th>Tên tài liệu</th><th>Loại</th><th>Cập nhật</th><th>Dung lượng</th><th>Trạng thái</th></tr></thead>
            <tbody>{filteredDocuments.map((document) => <tr key={document.id} className={selectedDocumentId === document.id ? "selected" : ""} onClick={() => setSelectedDocumentId(document.id)}>
              <td><span className="document-name"><FileText size={17} />{document.name}</span></td><td>{document.type}</td><td>{document.updatedAt}</td><td>{document.size}</td><td><Badge tone={statusTone(document.status)}>{document.status}</Badge></td>
            </tr>)}</tbody>
          </table> : <div className="document-empty"><FileText size={28} /><strong>Không tìm thấy tài liệu phù hợp</strong><p>Thử thay đổi từ khóa hoặc bộ lọc đang dùng.</p><Button variant="secondary" onClick={resetFilters}>Xóa bộ lọc</Button></div>}
        </div>
      </section>

      {selectedDocument && <aside className="document-details card" aria-label="Chi tiết tài liệu đã chọn">
        <div><span>CHI TIẾT TÀI LIỆU</span><h2>{selectedDocument.name}</h2></div>
        <dl>
          <div><dt>Loại tài liệu</dt><dd>{selectedDocument.type}</dd></div>
          <div><dt>Thư mục</dt><dd>{selectedFolder?.name}</dd></div>
          <div><dt>Cập nhật</dt><dd>{selectedDocument.updatedAt}</dd></div>
          <div><dt>Dung lượng</dt><dd>{selectedDocument.size}</dd></div>
          <div><dt>Trạng thái</dt><dd><Badge tone={statusTone(selectedDocument.status)}>{selectedDocument.status}</Badge></dd></div>
        </dl>
        <div className="allowed-agents"><span>AGENT ĐƯỢC PHÉP SỬ DỤNG</span>{selectedDocument.allowedAgents.map((agent) => <p key={agent}>{agentNames[agent]}</p>)}</div>
      </aside>}
    </div>
  </>;
}
