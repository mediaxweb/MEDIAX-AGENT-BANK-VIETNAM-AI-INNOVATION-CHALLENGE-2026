import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const qaSource = readFileSync(new URL("../app/AIQAScreen.tsx", import.meta.url), "utf8");
const stageSource = readFileSync(new URL("../app/AgentStage3D.tsx", import.meta.url), "utf8");
const pageSource = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
const documentsSource = readFileSync(new URL("../app/DocumentsScreen.tsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

assert.doesNotMatch(qaSource, /Câu hỏi gợi ý|Đặt lại hội thoại|Dừng tác vụ|Dừng xử lý/);
assert.match(qaSource, /Hội thoại/);
assert.match(qaSource, /Agent 3D/);
assert.match(qaSource, /aria-selected/);
assert.match(qaSource, /Cuộc hội thoại/);
assert.match(qaSource, /Đội agent đang phối hợp/);
assert.match(qaSource, /Phân rã yêu cầu/);
assert.match(qaSource, /Kiểm tra chéo/);
assert.match(qaSource, /Độ tin cậy/);
assert.match(stageSource, /type StageMode = "builder" \| "run" \| "qa"/);
assert.match(stageSource, /mode === "qa"/);
assert.doesNotMatch(pageSource, /global-search/);
assert.doesNotMatch(documentsSource, /Tạo thư mục|Loại tài liệu|Thư mục đích|Quyền sử dụng agent/);
assert.doesNotMatch(documentsSource, /Thư mục lưu trữ|Agent được phép sử dụng/);
assert.match(documentsSource, /Tải tài liệu lên/);
assert.match(documentsSource, /data-stage|--upload-progress/);
assert.match(css, /\.document-workspace/);
assert.match(css, /\.upload-dropzone/);
assert.match(css, /\.qa-workspace/);
assert.match(css, /grid-template-columns:\s*minmax\(0,1fr\)\s+minmax\(0,1fr\)/);
assert.match(css, /\.qa-mobile-tabs/);
assert.match(css, /\.qa-stage-visual\s+\.agent-stage-3d\s*{[^}]*margin:\s*0;/s);
assert.doesNotMatch(css, /#1677ff 0 58%/);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the MediaX workspace shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /MediaX Agent Bank/);
  assert.match(html, /Tổng quan/);
  assert.match(html, /Kho tài liệu/);
  assert.match(html, /Hỏi đáp AI/);
  assert.match(html, /Đội chuyên gia AI/);
  assert.doesNotMatch(html, /Your site is taking shape/);
});
