"use client";

import { FileText, Search, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { advanceUploadItems, canStartUpload, documentRecords, failedDemoUploadFileName, filterDocumentsByName, isAcceptedUploadFileName, retryUploadItem, uploadStages } from "./prototype-data";
import { Badge, Button } from "./ui";

interface UploadItem {
  id: string;
  name: string;
  size: string;
  stageIndex: number;
  failed: boolean;
  error?: string;
}

const demoUploadItems: UploadItem[] = [
  { id: "credit-application", name: "Hồ sơ đề nghị cấp tín dụng.pdf", size: "2,4 MB", stageIndex: 0, failed: false },
  { id: "collateral-list", name: "Danh mục tài sản bảo đảm.docx", size: "840 KB", stageIndex: 0, failed: false },
  { id: "statement-error", name: failedDemoUploadFileName, size: "1,1 MB", stageIndex: 0, failed: false },
];

function statusTone(status: string) {
  if (status === "Sẵn sàng") return "success";
  if (status === "Đang xử lý") return "info";
  return "warning";
}

export default function DocumentsScreen() {
  const [query, setQuery] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadItems, setUploadItems] = useState<UploadItem[]>(demoUploadItems);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadTriggerRef = useRef<HTMLButtonElement>(null);
  const uploadDialogRef = useRef<HTMLElement>(null);
  const uploadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  useEffect(() => {
    setCurrentPage(1);
  }, [query]);

  const filteredDocuments = useMemo(
    () => filterDocumentsByName(documentRecords, query),
    [query],
  );

  const paginatedDocuments = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredDocuments.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredDocuments, currentPage]);

  const totalPages = Math.ceil(filteredDocuments.length / itemsPerPage);

  function resetFilters() {
    setQuery("");
  }

  function clearUploadTimer() {
    if (uploadTimerRef.current) {
      clearInterval(uploadTimerRef.current);
      uploadTimerRef.current = null;
    }
  }

  function closeUploadModal() {
    clearUploadTimer();
    setUploadOpen(false);
    uploadTriggerRef.current?.focus();
  }

  function startUploadProcessing() {
    if (!canStartUpload(uploadItems)) return;
    clearUploadTimer();
    uploadTimerRef.current = setInterval(() => {
      setUploadItems((currentItems) => {
        const nextItems = advanceUploadItems(currentItems);

        if (nextItems.every((item) => item.failed || item.stageIndex === uploadStages.length - 1)) clearUploadTimer();
        return nextItems;
      });
    }, 650);
  }

  function retryUpload(id: string) {
    setUploadItems((currentItems) => retryUploadItem(currentItems, id));
    startUploadProcessing();
  }

  function addFiles(files: FileList | File[]) {
    const uploadedFiles = Array.from(files).filter((file) => isAcceptedUploadFileName(file.name));
    if (!uploadedFiles.length) return;

    setUploadItems((currentItems) => [...currentItems, ...uploadedFiles.map((file) => ({
      id: `${file.name}-${file.lastModified}`,
      name: file.name,
      size: `${Math.max(1, Math.round(file.size / 1024))} KB`,
      stageIndex: 0,
      failed: false,
    }))]);
  }

  useEffect(() => clearUploadTimer, []);

  useEffect(() => {
    if (!uploadOpen) return;

    const dialog = uploadDialogRef.current;
    if (!dialog) return;

    const getFocusableElements = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex=\"-1\"])",
    ));
    const focusableElements = getFocusableElements();
    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements.at(-1);
    (firstFocusable ?? dialog).focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeUploadModal();
        return;
      }

      if (event.key !== "Tab" || !firstFocusable || !lastFocusable) return;

      if (event.shiftKey && document.activeElement === firstFocusable) {
        event.preventDefault();
        lastFocusable.focus();
      } else if (!event.shiftKey && document.activeElement === lastFocusable) {
        event.preventDefault();
        firstFocusable.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [uploadOpen]);

  return <>
    <section className="document-summary" aria-label="Tổng quan kho tài liệu">
      {[
        ["1.284", "Tổng tài liệu"],
        ["1.247", "Sẵn sàng"],
        ["24", "Đang xử lý"],
        ["13", "Cần kiểm tra"],
      ].map(([value, label]) => <article className="card" key={label}><strong>{value}</strong><span>{label}</span></article>)}
    </section>

    <section className="document-workspace">
        <div className="document-controls card">
          <label className="search-box"><Search size={17} /><span className="sr-only">Tìm trong kho tài liệu</span><input aria-label="Tìm trong kho tài liệu" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm trong kho tài liệu" /></label>
          <button ref={uploadTriggerRef} type="button" className="button primary" style={{ marginLeft: "auto" }} onClick={() => setUploadOpen(true)}><Upload size={16} /> Tải tài liệu lên</button>
        </div>

        <div className="document-table-card card" style={{ display: "flex", flexDirection: "column" }}>
          {filteredDocuments.length ? (
            <>
              <div style={{ overflowX: "auto", flex: 1 }}>
                <table className="document-table">
                  <caption className="sr-only">Danh sách tài liệu nghiệp vụ</caption>
                  <thead><tr><th>Tên tệp</th><th>Cập nhật</th><th>Dung lượng</th><th>Trạng thái</th></tr></thead>
                  <tbody>{paginatedDocuments.map((document) => <tr key={document.id}>
                    <td><span className="document-name"><FileText size={17} />{document.name}</span></td><td>{document.updatedAt}</td><td>{document.size}</td><td><Badge tone={statusTone(document.status)}>{document.status}</Badge></td>
                  </tr>)}</tbody>
                </table>
              </div>
              
              <div className="table-footer" style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 20px",
                borderTop: "1px solid var(--border)",
                background: "var(--elev)",
                fontSize: "12px",
                color: "var(--muted)",
                flexWrap: "wrap",
                gap: "12px"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
                  <div>
                    Hiển thị <strong>{Math.min(filteredDocuments.length, (currentPage - 1) * itemsPerPage + 1)}-{Math.min(filteredDocuments.length, currentPage * itemsPerPage)}</strong> trong tổng số <strong>{filteredDocuments.length}</strong> tài liệu
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "11px", color: "var(--muted)" }}>Số dòng:</span>
                    <select
                      value={itemsPerPage}
                      onChange={(e) => {
                        setItemsPerPage(Number(e.target.value));
                        setCurrentPage(1);
                      }}
                      style={{
                        background: "var(--side)",
                        border: "1px solid var(--border)",
                        color: "var(--text)",
                        borderRadius: "5px",
                        padding: "3px 6px",
                        fontSize: "11px",
                        cursor: "pointer",
                        outline: "none",
                        width: "auto",
                        marginTop: 0
                      }}
                    >
                      {[10, 20, 30, 40, 50, 100].map((num) => (
                        <option key={num} value={num} style={{ background: "var(--side)", color: "var(--text)" }}>
                          {num}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {totalPages > 1 && (
                  <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      style={{ height: "28px", padding: "0 10px", fontSize: "11px" }}
                    >
                      Trang trước
                    </button>
                    
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <button
                        key={page}
                        type="button"
                        className={`button ${currentPage === page ? "primary" : "secondary"}`}
                        onClick={() => setCurrentPage(page)}
                        style={{
                          height: "28px",
                          width: "28px",
                          padding: 0,
                          fontSize: "11px",
                          display: "grid",
                          placeItems: "center"
                        }}
                      >
                        {page}
                      </button>
                    ))}

                    <button
                      type="button"
                      className="button secondary"
                      disabled={currentPage === totalPages}
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      style={{ height: "28px", padding: "0 10px", fontSize: "11px" }}
                    >
                      Trang sau
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="document-empty"><FileText size={28} /><strong>Không tìm thấy tài liệu phù hợp</strong><p>Thử thay đổi từ khóa tìm kiếm.</p><Button variant="secondary" onClick={resetFilters}>Xóa tìm kiếm</Button></div>
          )}
        </div>
    </section>

    {uploadOpen && <div className="modal-layer">
      <button type="button" className="overlay" aria-label="Đóng cửa sổ tải tài liệu" onClick={closeUploadModal} />
      <section ref={uploadDialogRef} className="modal" tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="upload-modal-title">
        <div className="modal-head">
          <div><span className="modal-icon"><Upload size={20} /></span><div><h2 id="upload-modal-title">Tải tài liệu lên</h2><p>Thêm tài liệu vào kho tri thức nghiệp vụ.</p></div></div>
          <button type="button" aria-label="Đóng cửa sổ tải tài liệu" onClick={closeUploadModal}><X /></button>
        </div>
        <div className="modal-body">
          <input ref={fileInputRef} hidden tabIndex={-1} type="file" accept=".pdf,.docx,.xlsx" multiple onChange={(event) => {
            if (event.target.files) addFiles(event.target.files);
            event.target.value = "";
          }} />
          <button
            type="button"
            className="upload-dropzone"
            aria-label="Chọn tệp PDF, DOCX hoặc XLSX để tải lên"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              addFiles(event.dataTransfer.files);
            }}
          >
            <Upload size={22} /><strong>Kéo thả tệp vào đây hoặc chọn tệp</strong><span>Hỗ trợ PDF, DOCX, XLSX</span>
          </button>

          <section aria-label="Tiến trình tải tài liệu">
            <h3>Tệp chờ xử lý</h3>
            {uploadItems.map((item) => <article className="upload-file" data-stage={item.stageIndex} key={item.id}>
              <div><FileText size={16} /><span><strong>{item.name}</strong><small>{item.size} · {item.failed ? "Cần xử lý lại" : uploadStages[item.stageIndex]}</small></span></div>
              {item.failed ? <div><p role="alert">{item.error}</p><button type="button" onClick={() => retryUpload(item.id)}>Thử lại</button></div> : <span>{uploadStages[item.stageIndex]}</span>}
            </article>)}
          </section>
        </div>
        <div className="modal-actions"><p>RAG sẽ tự phân loại và điều phối agent phù hợp.</p><Button variant="secondary" onClick={closeUploadModal}>Hủy</Button><Button onClick={startUploadProcessing} disabled={!canStartUpload(uploadItems)}>Bắt đầu xử lý</Button></div>
      </section>
    </div>}
  </>;
}
