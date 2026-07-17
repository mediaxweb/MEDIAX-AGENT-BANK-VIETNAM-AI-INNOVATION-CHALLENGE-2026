import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const screenUrl = new URL("../app/DocumentsScreen.tsx", import.meta.url);

async function readScreen() {
  return readFile(screenUrl, "utf8");
}

test("selects a document through a keyboard-operable button", async () => {
  const screen = await readScreen();

  assert.match(
    screen,
    /<button type="button" className="document-name" onClick=\{\(\) => setSelectedDocumentId\(document\.id\)\}>/,
  );
  assert.doesNotMatch(screen, /<tr[^>]*onClick=/);
});

test("only shows details for a document in the filtered list", async () => {
  const screen = await readScreen();

  assert.match(
    screen,
    /const selectedDocument = filteredDocuments\.find\(\(document\) => document\.id === selectedDocumentId\);/,
  );
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
