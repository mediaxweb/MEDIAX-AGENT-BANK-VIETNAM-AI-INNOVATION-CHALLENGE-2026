import assert from "node:assert/strict";
import test from "node:test";
import {
  advanceUploadItems,
  advanceUploadStage,
  acceptedUploadFormats,
  canStartUpload,
  documentRecords,
  filterDocuments,
  isAcceptedUploadFileName,
  qaScenarios,
  retryUploadItem,
  selectQaScenario,
  uploadStages,
} from "../app/prototype-data.ts";

test("filters documents by folder, type, and Vietnamese query", () => {
  const result = filterDocuments(documentRecords, "credit", "Chính sách", "chấm điểm");
  assert.deepEqual(result.map((item) => item.name), ["Chính sách chấm điểm tín dụng.pdf"]);
});

test("defines the complete upload simulation", () => {
  assert.deepEqual(uploadStages, ["Đang tải", "Đang phân loại", "Đang lập chỉ mục", "Sẵn sàng"]);
});

test("advances upload stages without moving failed or completed items", () => {
  assert.deepEqual(advanceUploadStage(0, false), { stageIndex: 1, failed: false });
  assert.deepEqual(advanceUploadStage(2, false), { stageIndex: 3, failed: false });
  assert.deepEqual(advanceUploadStage(3, false), { stageIndex: 3, failed: false });
  assert.deepEqual(advanceUploadStage(1, true), { stageIndex: 1, failed: true });
});

test("accepts only supported upload file extensions", () => {
  assert.equal(isAcceptedUploadFileName("statement.PDF"), true);
  assert.equal(isAcceptedUploadFileName("report.docx"), true);
  assert.equal(isAcceptedUploadFileName("ledger.xlsx"), true);
  assert.equal(isAcceptedUploadFileName("statement.pdf.exe"), false);
  assert.equal(isAcceptedUploadFileName("notes.txt"), false);
});

test("marks the demo statement as failed when it reaches indexing", () => {
  const items = [{
    id: "statement-error",
    name: "Sao kê giao dịch lỗi.xlsx",
    size: "1,1 MB",
    stageIndex: 1,
    failed: false,
  }];

  assert.deepEqual(advanceUploadItems(items), [{
    ...items[0],
    stageIndex: 2,
    failed: true,
    error: "Tệp bị gián đoạn khi lập chỉ mục",
  }]);
});

test("caps completed uploads and retry clears a failed upload for resumption", () => {
  const completed = { id: "complete", name: "complete.pdf", size: "1 KB", stageIndex: 3, failed: false };
  const failed = {
    id: "statement-error",
    name: "Sao kê giao dịch lỗi.xlsx",
    size: "1,1 MB",
    stageIndex: 2,
    failed: true,
    error: "Tệp bị gián đoạn khi lập chỉ mục",
  };

  assert.deepEqual(advanceUploadItems([completed]), [completed]);
  assert.deepEqual(retryUploadItem([failed], failed.id), [{
    id: "statement-error",
    name: "Sao kê giao dịch lỗi.xlsx",
    size: "1,1 MB",
    stageIndex: 2,
    failed: false,
  }]);
});

test("only starts upload processing when files are present", () => {
  assert.equal(canStartUpload([]), false);
  assert.equal(canStartUpload([{ id: "one", name: "one.pdf", size: "1 KB", stageIndex: 0, failed: false }]), true);
});

test("accepts every upload format supported by the prototype", () => {
  assert.deepEqual(acceptedUploadFormats, ["PDF", "DOCX", "XLSX"]);
});

test("selects a risk scenario and falls back to the main assessment", () => {
  assert.equal(selectQaScenario("Điểm rủi ro chính là gì?").id, "risk");
  assert.equal(selectQaScenario("Đánh giá hồ sơ này").id, "assessment");
  assert.equal(qaScenarios.assessment.activeAgents.length, 4);
});
