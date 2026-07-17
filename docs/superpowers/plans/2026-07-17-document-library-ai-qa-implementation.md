# Document Library and Multi-Agent AI Q&A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mock document library with upload simulation and a balanced two-column AI Q&A workspace that automatically orchestrates the existing 3D agent team.

**Architecture:** Keep `Home` as the screen router and move each new product surface into a focused client component. Put shared mock records and deterministic filtering/scenario helpers in a framework-independent TypeScript module so behavior can be tested without a browser. Extend the existing `AgentStage3D` API with a Q&A mode and drive all prototype progress with client-side timers.

**Tech Stack:** React 19, TypeScript 5.9, Vinext/Next.js App Router, Three.js, Lucide React, CSS, Node.js test runner.

## Global Constraints

- The prototype uses mock data only; do not add persistence, AI APIs, D1, R2, authentication, or environment variables.
- Keep **Tổng quan** as the initial screen.
- Add **Kho tài liệu** and **Hỏi đáp AI** to the existing left navigation.
- Reuse `public/models/character.glb` and the current Three.js stage.
- Desktop AI Q&A uses two near-equal columns; small screens use **Hội thoại** and **Agent 3D** tabs.
- Upload simulation supports PDF, DOCX, and XLSX and shows `Đang tải → Đang phân loại → Đang lập chỉ mục → Sẵn sàng`.
- Preserve the existing package manager, lockfile, Vinext structure, and `.openai/hosting.json`.

---

## File Structure

- Create `app/prototype-data.ts`: typed mock folders/documents, document filtering, upload stages, and deterministic Q&A scenario selection.
- Create `app/DocumentsScreen.tsx`: document library, folder tree, filters, details drawer, and upload modal/state machine.
- Create `app/AIQAScreen.tsx`: two-column conversation/orchestration UI, timers, source details, stop/reset, and mobile tabs.
- Create `app/ui.tsx`: shared `Badge`, `Button`, and `PageHeading` primitives used by the existing and new screens.
- Modify `app/page.tsx`: extend screen routing and navigation, render both new screens, and import shared primitives from `app/ui.tsx`.
- Modify `app/AgentStage3D.tsx`: add Q&A stage mode and deterministic per-agent state mapping.
- Modify `app/globals.css`: add document, upload, Q&A, source drawer, and responsive styles.
- Replace `tests/rendered-html.test.mjs`: verify final server-rendered shell instead of the removed starter skeleton.
- Create `tests/prototype-data.test.mjs`: verify filtering, upload stages, and Q&A scenario selection.

---

### Task 1: Deterministic Prototype Data and Behavior

**Files:**
- Create: `app/prototype-data.ts`
- Create: `tests/prototype-data.test.mjs`

**Interfaces:**
- Produces: `DocumentRecord`, `DocumentFolder`, `UploadStage`, `QaScenario` types.
- Produces: `documentFolders`, `documentRecords`, `uploadStages`, `qaScenarios` constants.
- Produces: `filterDocuments(records, folderId, type, query): DocumentRecord[]`.
- Produces: `selectQaScenario(question): QaScenario`.

- [ ] **Step 1: Write the failing behavior tests**

Create `tests/prototype-data.test.mjs` with tests that import `../app/prototype-data.ts` and assert:

```js
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
```

- [ ] **Step 2: Run the test and verify the module is missing**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `app/prototype-data.ts`.

- [ ] **Step 3: Implement the typed mock model**

Create `app/prototype-data.ts` with concrete folder/document records, the exact four upload states, and four scenarios (`assessment`, `risk`, `missing`, `sources`). Normalize Vietnamese search with `toLocaleLowerCase("vi")`; treat `folderId === "all"` and `type === "Tất cả"` as wildcards. `selectQaScenario` maps questions containing `rủi ro`, `thiếu`, or `chính sách|nguồn` to the matching scenario and otherwise returns `assessment`.

The main scenario must use:

```ts
assessment: {
  id: "assessment",
  question: "Đánh giá khả năng vay 2,5 tỷ đồng của khách hàng doanh nghiệp này.",
  answer: "Đội chuyên gia đề xuất phê duyệt có điều kiện. Điểm CIC 742 và DTI 38,5% nằm trong ngưỡng cho phép, nhưng hồ sơ cần bổ sung tờ khai thuế gần nhất trước khi ra quyết định.",
  confidence: 87,
  activeAgents: ["orchestrator", "credit", "compliance", "operations"],
  sources: ["Quy trình cấp tín dụng 2026.pdf", "Chính sách chấm điểm tín dụng.pdf", "Báo cáo CIC khách hàng.pdf"],
}
```

- [ ] **Step 4: Run the behavior tests**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit the behavior layer**

```bash
git add app/prototype-data.ts tests/prototype-data.test.mjs
git commit -m "feat: add prototype document and QA data"
```

### Task 2: Navigation and Document Library

**Files:**
- Create: `app/DocumentsScreen.tsx`
- Create: `app/ui.tsx`
- Modify: `app/page.tsx`
- Replace: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `documentFolders`, `documentRecords`, and `filterDocuments` from `app/prototype-data.ts`.
- Consumes: `Badge`, `Button`, and `PageHeading` from `app/ui.tsx`.
- Produces: `DocumentsScreen(): JSX.Element` and the `documents` screen route.

- [ ] **Step 1: Replace the stale starter render test**

Rewrite `tests/rendered-html.test.mjs` to build/import `dist/server/index.js`, request `/`, and assert status 200 plus the initial HTML labels:

```js
assert.match(html, /MediaX Agent Bank/);
assert.match(html, /Tổng quan/);
assert.match(html, /Kho tài liệu/);
assert.match(html, /Hỏi đáp AI/);
assert.match(html, /Đội chuyên gia AI/);
assert.doesNotMatch(html, /Your site is taking shape/);
```

- [ ] **Step 2: Run the production render test and verify the new routes are absent**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL because `Kho tài liệu` and `Hỏi đáp AI` are not rendered.

- [ ] **Step 3: Add navigation routes and shared UI exports**

In `app/page.tsx`:

```ts
type Screen = "agents" | "documents" | "qa" | "team" | "run" | "comparison";
```

Move `Badge`, `Button`, and `PageHeading` without behavior changes into `app/ui.tsx`; import them into `app/page.tsx`. Add navigation entries with `LibraryBig` and `MessagesSquare`; map page titles explicitly; render `<DocumentsScreen />` and `<AIQAScreen />` while keeping `useState<Screen>("agents")` unchanged.

- [ ] **Step 4: Implement the document library surface**

Create `DocumentsScreen.tsx` as a client component with state for `folderId`, `type`, `query`, and `selectedDocumentId`. Render:

- Four summary cards: `1.284 Tổng tài liệu`, `1.247 Sẵn sàng`, `24 Đang xử lý`, `13 Cần kiểm tra`.
- Folder buttons with counts from `documentFolders`.
- Type chips for `Tất cả`, `Quy trình`, `Chính sách`, `Biểu mẫu`, `Báo cáo`, `Dữ liệu tham chiếu`.
- Search input labeled `Tìm trong kho tài liệu`.
- A semantic document table with status badges.
- An empty state with a `Xóa bộ lọc` button.
- A selected-document details panel with type, folder, updated date, file size, status, and allowed agent names.
- Primary actions `Tạo thư mục` and `Tải tài liệu lên`.

- [ ] **Step 5: Build and run both tests**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs`

Expected: build succeeds and all tests PASS.

- [ ] **Step 6: Commit document navigation and library**

```bash
git add app/page.tsx app/ui.tsx app/DocumentsScreen.tsx tests/rendered-html.test.mjs
git commit -m "feat: add document library workspace"
```

### Task 3: Mock Upload Modal and State Machine

**Files:**
- Modify: `app/DocumentsScreen.tsx`
- Modify: `app/prototype-data.ts`
- Modify: `tests/prototype-data.test.mjs`

**Interfaces:**
- Consumes: `uploadStages` from `app/prototype-data.ts`.
- Produces: local `UploadItem` shape `{ id, name, size, stageIndex, failed, error? }` and modal open/close behavior.

- [ ] **Step 1: Add failing upload transition assertions**

Add `advanceUploadStage(stageIndex, failed): { stageIndex: number; failed: boolean }` to the test imports and assert:

```js
assert.deepEqual(advanceUploadStage(0, false), { stageIndex: 1, failed: false });
assert.deepEqual(advanceUploadStage(2, false), { stageIndex: 3, failed: false });
assert.deepEqual(advanceUploadStage(3, false), { stageIndex: 3, failed: false });
assert.deepEqual(advanceUploadStage(1, true), { stageIndex: 1, failed: true });
```

- [ ] **Step 2: Run the behavior test and verify the export is missing**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs`

Expected: FAIL because `advanceUploadStage` is not exported.

- [ ] **Step 3: Implement the transition helper and modal**

Implement `advanceUploadStage` as a capped deterministic transition. Add an accessible modal in `DocumentsScreen.tsx` with:

- Drop zone and hidden `input type="file"` accepting `.pdf,.docx,.xlsx`.
- Three preloaded demo files so the flow works without a native file chooser.
- Selects for type and destination folder.
- Agent permission checkboxes for all four agents.
- Disabled start button when the file list is empty.
- A timer that advances items every 650 ms.
- One demo failure for `Sao kê giao dịch lỗi.xlsx` at indexing, with error text `Tệp bị gián đoạn khi lập chỉ mục` and a `Thử lại` action that clears failure and resumes.
- Close behavior that clears timers.

- [ ] **Step 4: Run behavior tests and build**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build`

Expected: all tests PASS and build succeeds.

- [ ] **Step 5: Commit upload simulation**

```bash
git add app/DocumentsScreen.tsx app/prototype-data.ts tests/prototype-data.test.mjs
git commit -m "feat: simulate document upload processing"
```

### Task 4: Multi-Agent AI Q&A Workspace

**Files:**
- Create: `app/AIQAScreen.tsx`
- Modify: `app/page.tsx`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `selectQaScenario`, `qaScenarios`, and `QaScenario` from `app/prototype-data.ts`.
- Consumes: `AgentStage3D` with `mode="qa"`, `selected`, and `runStep`.
- Produces: `AIQAScreen(): JSX.Element`, Q&A progress values `0..4`, and source details overlay.

- [ ] **Step 1: Add failing final-shell assertions**

Add source-level assertions to `tests/rendered-html.test.mjs` that read `app/AIQAScreen.tsx` and match:

```js
assert.match(qaSource, /Cuộc hội thoại/);
assert.match(qaSource, /Đội agent đang phối hợp/);
assert.match(qaSource, /Phân rã yêu cầu/);
assert.match(qaSource, /Kiểm tra chéo/);
assert.match(qaSource, /Độ tin cậy/);
```

- [ ] **Step 2: Run the render test and verify the component is missing**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL because `app/AIQAScreen.tsx` does not exist.

- [ ] **Step 3: Implement the balanced two-column Q&A screen**

Create a client component with state for `question`, `messages`, `runStep`, `scenario`, `stopped`, `activeMobileTab`, and `selectedSource`. The `sendQuestion` function must:

1. Reject trimmed empty input.
2. Select a deterministic scenario.
3. Add the user message.
4. Schedule run steps at 0, 700, 1500, 2300, and 3100 ms.
5. Add progress messages for delegation, parallel analysis, and cross-checking.
6. Add the final answer with confidence and sources at step 4.

Render the selected layout:

- Left card: suggested questions, messages, cited sources, textarea, send/stop/reset actions.
- Right card: live status, `AgentStage3D`, four progress stages, and agent result tiles.
- Source overlay: document name, category, folder, updated date, excerpt, and `Được sử dụng bởi`.
- Mobile tab buttons `Hội thoại` and `Agent 3D`.

Clean up every scheduled timeout in `useEffect` cleanup and when stop/reset is clicked.

- [ ] **Step 4: Wire the route and verify**

Import `AIQAScreen` into `app/page.tsx`, render it for `screen === "qa"`, then run:

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs`

Expected: build succeeds and all tests PASS.

- [ ] **Step 5: Commit Q&A workspace**

```bash
git add app/AIQAScreen.tsx app/page.tsx tests/rendered-html.test.mjs
git commit -m "feat: add multi-agent AI question workspace"
```

### Task 5: Q&A-Aware 3D Agent Stage

**Files:**
- Modify: `app/AgentStage3D.tsx`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Extends: `StageMode` to `"builder" | "run" | "qa"`.
- Consumes: Q&A `runStep` values where 1 activates orchestrator, 2 activates three specialists, 3 activates all agents for cross-checking, and 4 marks all agents done.

- [ ] **Step 1: Add a failing source assertion for Q&A stage support**

Read `app/AgentStage3D.tsx` in the render test and assert:

```js
assert.match(stageSource, /type StageMode = "builder" \| "run" \| "qa"/);
assert.match(stageSource, /mode === "qa"/);
```

- [ ] **Step 2: Run the test and verify the Q&A mode is absent**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL on the StageMode assertion.

- [ ] **Step 3: Implement Q&A agent states**

Extend `getState` with this deterministic map:

```ts
if (mode === "qa") {
  if (!runStep) return "ready";
  if (runStep >= 4) return "done";
  if (runStep === 1) return index === 0 ? "running" : "waiting";
  if (runStep === 2) return index === 0 ? "done" : "running";
  return "running";
}
```

Update the approval-gate copy in Q&A mode to `Điều phối tự động` and `Agent được chọn theo nội dung câu hỏi`. Keep builder/run behavior unchanged.

- [ ] **Step 4: Run tests and build**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build`

Expected: tests PASS and build succeeds.

- [ ] **Step 5: Commit 3D orchestration states**

```bash
git add app/AgentStage3D.tsx tests/rendered-html.test.mjs
git commit -m "feat: animate 3D agents for QA orchestration"
```

### Task 6: Product Styling, Responsive Layout, and Final Verification

**Files:**
- Modify: `app/globals.css`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: class names from `DocumentsScreen.tsx` and `AIQAScreen.tsx`.
- Produces: desktop document split, balanced Q&A columns, upload modal states, source overlay, and mobile tab behavior.

- [ ] **Step 1: Add failing CSS contract assertions**

Read `app/globals.css` in `tests/rendered-html.test.mjs` and assert the final stylesheet contains:

```js
assert.match(css, /\.document-workspace/);
assert.match(css, /\.upload-dropzone/);
assert.match(css, /\.qa-workspace/);
assert.match(css, /grid-template-columns:\s*minmax\(0,1fr\)\s+minmax\(0,1fr\)/);
assert.match(css, /\.qa-mobile-tabs/);
```

- [ ] **Step 2: Run the test and verify new style contracts are absent**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL on `.document-workspace`.

- [ ] **Step 3: Add complete desktop and responsive styling**

Append focused styles to `app/globals.css` for:

- `document-stats`, `document-workspace`, `folder-tree`, `document-toolbar`, `document-table`, `document-detail`.
- `upload-modal`, `upload-dropzone`, `upload-file`, progress bar, failure state, and agent permission chips.
- `qa-shell`, `qa-workspace`, `qa-conversation`, `qa-stage-panel`, `qa-message`, `qa-composer`, `qa-progress`, `qa-agent-results`, `qa-source-link`, and source overlay.
- Minimum desktop Q&A height of `calc(100vh - 150px)` and exact equal columns `minmax(0,1fr) minmax(0,1fr)`.
- At `max-width: 820px`, stack the document workspace, show `.qa-mobile-tabs`, and display only the selected Q&A panel.
- Visible focus states and reduced-motion handling for new animated elements.

- [ ] **Step 4: Run complete automated verification**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run lint`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm test`

Expected: lint succeeds; production build succeeds; all Node tests PASS.

- [ ] **Step 5: Inspect the final diff and confirm scope**

Run: `git status --short`

Run: `git diff --check`

Run: `git diff --stat HEAD`

Expected: only the planned app, test, and plan files are changed; no whitespace errors; `.openai/hosting.json` remains unchanged.

- [ ] **Step 6: Commit final styling and verification contracts**

```bash
git add app/globals.css tests/rendered-html.test.mjs
git commit -m "feat: finish document and AI workspace styling"
```
