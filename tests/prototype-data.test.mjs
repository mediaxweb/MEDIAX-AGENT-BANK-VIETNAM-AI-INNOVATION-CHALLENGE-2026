import assert from "node:assert/strict";
import test from "node:test";
import {
  advanceUploadStage,
  acceptedUploadFormats,
  documentRecords,
  filterDocuments,
  qaScenarios,
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

test("accepts every upload format supported by the prototype", () => {
  assert.deepEqual(acceptedUploadFormats, ["PDF", "DOCX", "XLSX"]);
});

test("selects a risk scenario and falls back to the main assessment", () => {
  assert.equal(selectQaScenario("Điểm rủi ro chính là gì?").id, "risk");
  assert.equal(selectQaScenario("Đánh giá hồ sơ này").id, "assessment");
  assert.equal(qaScenarios.assessment.activeAgents.length, 4);
});
