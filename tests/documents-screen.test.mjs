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
