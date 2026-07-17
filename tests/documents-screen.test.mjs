import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const screenUrl = new URL("../app/DocumentsScreen.tsx", import.meta.url);

async function readScreen() {
  return readFile(screenUrl, "utf8");
}

test("renders a flat filename table without document selection controls", async () => {
  const screen = await readScreen();

  assert.match(screen, /filterDocumentsByName\(documentRecords, query\)/);
  assert.match(screen, /<td><span className="document-name"><FileText size=\{17\} \/>\{document\.name\}<\/span><\/td>/);
  assert.doesNotMatch(screen, /selectedDocumentId|document-details/);
  assert.doesNotMatch(screen, /<tr[^>]*onClick=/);
});

test("leaves manual document organization and agent permissions out of the workspace", async () => {
  const screen = await readScreen();

  assert.doesNotMatch(screen, /Tạo thư mục|Loại tài liệu|Thư mục đích|Quyền sử dụng agent/);
  assert.match(screen, /RAG sẽ tự phân loại và điều phối agent phù hợp\./);
  assert.match(screen, /<article className="upload-file" data-stage=\{item\.stageIndex\}/);
});

test("keeps keyboard focus in the upload dialog and restores the trigger on close", async () => {
  const screen = await readScreen();

  assert.match(screen, /const uploadTriggerRef = useRef<HTMLButtonElement>\(null\);/);
  assert.match(screen, /const uploadDialogRef = useRef<HTMLElement>\(null\);/);
  assert.match(screen, /if \(event\.key === "Escape"\) \{\s*event\.preventDefault\(\);\s*closeUploadModal\(\);/);
  assert.match(screen, /event\.shiftKey && document\.activeElement === firstFocusable/);
  assert.match(screen, /!event\.shiftKey && document\.activeElement === lastFocusable/);
  assert.match(screen, /uploadTriggerRef\.current\?\.focus\(\);/);
  assert.match(screen, /<section ref=\{uploadDialogRef\} className="modal" tabIndex=\{-1\} role="dialog"/);
});

test("keeps the native file input hidden and out of the tab order", async () => {
  const screen = await readScreen();

  assert.match(screen, /<input ref=\{fileInputRef\} hidden tabIndex=\{-1\} type="file"/);
  assert.doesNotMatch(screen, /<input ref=\{fileInputRef\} className="sr-only"/);
});
