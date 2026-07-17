import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const qaSource = readFileSync(new URL("../app/AIQAScreen.tsx", import.meta.url), "utf8");
const stageSource = readFileSync(new URL("../app/AgentStage3D.tsx", import.meta.url), "utf8");

assert.match(qaSource, /Cuộc hội thoại/);
assert.match(qaSource, /Đội agent đang phối hợp/);
assert.match(qaSource, /Phân rã yêu cầu/);
assert.match(qaSource, /Kiểm tra chéo/);
assert.match(qaSource, /Độ tin cậy/);
assert.match(stageSource, /type StageMode = "builder" \| "run" \| "qa"/);
assert.match(stageSource, /mode === "qa"/);

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
