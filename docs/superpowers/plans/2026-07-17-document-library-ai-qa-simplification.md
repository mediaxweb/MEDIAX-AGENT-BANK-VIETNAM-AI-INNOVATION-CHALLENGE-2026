# Document Library and AI Q&A Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove manual taxonomy/agent controls and secondary Q&A actions so the prototype presents a flat RAG-managed document workspace and a focused AI conversation.

**Architecture:** Preserve the existing mock data and screen routing, but make the visible UI intentionally flat. `DocumentsScreen` keeps filename search, upload processing, and the document table; RAG metadata remains internal for Q&A citations. `AIQAScreen` keeps the deterministic multi-agent timeline and 3D stage while removing suggestions, stop, and reset controls.

**Tech Stack:** React 19, TypeScript, Vinext/Next.js App Router, Three.js, Lucide React, CSS, Node.js test runner.

## Global Constraints

- Keep `Tổng quan` as the initial screen and retain both new navigation items.
- Remove the topbar search for hồ sơ/chuyên gia.
- The document library has no visible folders, create-folder action, document-type filters, agent-permission controls, or document-details card.
- Upload modal only selects/drops files and shows processing progress; RAG mock data handles classification and agent routing implicitly.
- AI Q&A has no suggested questions, reset action, or stop action; disable new input while orchestration is running and re-enable it after completion.
- Keep mock-only behavior, existing model asset, package manager, lockfile, Vinext structure, and `.openai/hosting.json`.

---

## File Structure

- Modify `app/page.tsx`: remove global search markup and preserve route/page-title behavior.
- Modify `app/DocumentsScreen.tsx`: flatten the library, simplify upload controls, keep file filtering/progress, and expose a stage hook for the progress rail.
- Modify `app/AIQAScreen.tsx`: remove suggestions/stop/reset UI, preserve deterministic orchestration, and complete tab semantics.
- Modify `app/globals.css`: remove obsolete selectors only when safe and style the simplified flat library/upload/Q&A surface, including a stage-aware upload progress rail.
- Modify `tests/rendered-html.test.mjs`: add failing source contracts for removed UI and retained required UI.
- Modify `tests/prototype-data.test.mjs` only if a pure helper is needed for the stage-aware progress contract.

### Task 7: Simplify Topbar, Document Library, and Upload

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/DocumentsScreen.tsx`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Preserve `DocumentsScreen` filtering by filename query and the existing `UploadItem`/upload helper contracts.
- Add a stable document upload stage hook: `data-stage={item.stageIndex}` on each upload row or a `style={{ "--upload-progress": `${progress}%` }}` CSS variable.
- Keep `acceptedUploadFormats`, failure/retry, timer cleanup, and native file input behavior unchanged.

- [ ] **Step 1: Write failing source-contract tests**

Add assertions to `tests/rendered-html.test.mjs`:

```js
assert.doesNotMatch(pageSource, /global-search/);
assert.doesNotMatch(documentsSource, /Tạo thư mục|Loại tài liệu|Thư mục đích|Quyền sử dụng agent/);
assert.match(documentsSource, /Tải tài liệu lên/);
assert.match(documentsSource, /data-stage|--upload-progress/);
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL because the topbar search and manual document controls still exist.

- [ ] **Step 3: Implement the flat workspace**

In `app/page.tsx`, remove the `<label className="global-search">…</label>` block and leave the AI status, notification, and profile controls intact.

In `app/DocumentsScreen.tsx`:

- Remove folder state/tree, type state/chips, create-folder action, selected-document details state/panel, and agent-permission controls from upload.
- Keep one filename search input, the summary cards, the flat document table, empty state, and `Tải tài liệu lên`.
- Keep upload modal file list, accepted formats, retry/error behavior, and the processing stage text.
- Keep only the file drop zone and a concise note such as `RAG sẽ tự phân loại và điều phối agent phù hợp` before the start action.
- Add `data-stage={item.stageIndex}` to each upload row so CSS can render stage-aware progress.

- [ ] **Step 4: Run focused tests and build**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs tests/documents-screen.test.mjs`

Expected: all focused tests PASS and the existing upload helper behavior remains covered.

- [ ] **Step 5: Commit Task 7**

```bash
git add app/page.tsx app/DocumentsScreen.tsx tests/rendered-html.test.mjs
git commit -m "feat: simplify document workspace and topbar"
```

### Task 8: Focus AI Q&A and Preserve Orchestration

**Files:**
- Modify: `app/AIQAScreen.tsx`
- Modify: `app/page.tsx`
- Modify: `tests/rendered-html.test.mjs`

**Interfaces:**
- Preserve `selectQaScenario`, `qaScenarios`, `runStep`, timeout cleanup, source overlay, and `AgentStage3D mode="qa"`.
- Keep `Hội thoại` and `Agent 3D` mobile tabs, but expose correct `role="tab"`, `aria-selected`, `aria-controls`, and one active `role="tabpanel"`.

- [ ] **Step 1: Write failing Q&A-removal tests**

Add source-contract assertions:

```js
assert.doesNotMatch(qaSource, /Câu hỏi gợi ý|Đặt lại hội thoại|Dừng tác vụ|Dừng xử lý/);
assert.match(qaSource, /Hội thoại/);
assert.match(qaSource, /Agent 3D/);
assert.match(qaSource, /aria-selected/);
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs`

Expected: FAIL because the current Q&A source still contains suggestions and stop/reset controls.

- [ ] **Step 3: Implement the focused Q&A UI**

In `app/AIQAScreen.tsx`:

- Remove suggestion buttons and all `stopped`, reset, stop, and clear-run controls.
- Keep the textarea and send button; disable both while `runStep > 0 && runStep < 4`.
- Keep the deterministic scenario selected from the typed question, progress messages, final confidence, agent results, and source dialog.
- Add `id="qa-conversation-panel"`, `id="qa-agent-panel"`, tab IDs, `aria-controls`, and `aria-selected` to the mobile tab controls.
- Render only the active panel with `hidden={!isActive}` or an equivalent semantic approach.

In `app/page.tsx`, lazy-load `AIQAScreen` alongside the existing lazy 3D stage so the initial Tổng quan bundle does not eagerly load the Q&A surface.

- [ ] **Step 4: Run tests and production build**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs tests/documents-screen.test.mjs`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build`

Expected: all focused tests PASS and build succeeds.

- [ ] **Step 5: Commit Task 8**

```bash
git add app/AIQAScreen.tsx app/page.tsx tests/rendered-html.test.mjs
git commit -m "feat: focus AI Q&A on conversation and orchestration"
```

### Task 9: Final Simplified-Prototype Verification

**Files:**
- Modify: `app/globals.css`
- Modify: `tests/rendered-html.test.mjs`

- [ ] **Step 1: Add stage-aware progress CSS contract**

Assert the stylesheet includes a stage-aware upload rail and the exact simplified responsive contracts:

```js
assert.match(css, /upload-file\[data-stage=/);
assert.match(css, /\.qa-workspace/);
assert.match(css, /\.qa-mobile-tabs/);
```

- [ ] **Step 2: Implement the progress rail and remove obsolete visual selectors**

Use `data-stage` to map stage 0–3 to visible rail widths, keep failed rows visibly distinct, and remove only selectors that no longer have consumers. Keep desktop equal columns and the existing max-width 820px responsive behavior.

- [ ] **Step 3: Run the final verification set**

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run lint` (record the known repository baseline if unchanged)

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm test`

Run: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/rendered-html.test.mjs tests/prototype-data.test.mjs tests/documents-screen.test.mjs`

Run: `git diff --check`

Expected: production build and tests PASS; only documented pre-existing lint findings remain; no whitespace errors.

- [ ] **Step 4: Commit Task 9**

```bash
git add app/globals.css tests/rendered-html.test.mjs
git commit -m "test: verify simplified prototype contracts"
```
