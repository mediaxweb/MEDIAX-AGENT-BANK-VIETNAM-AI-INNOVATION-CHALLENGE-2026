import assert from "node:assert/strict";
import test from "node:test";
import {
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

test("selects a risk scenario and falls back to the main assessment", () => {
  assert.equal(selectQaScenario("Điểm rủi ro chính là gì?").id, "risk");
  assert.equal(selectQaScenario("Đánh giá hồ sơ này").id, "assessment");
  assert.equal(qaScenarios.assessment.activeAgents.length, 4);
});
