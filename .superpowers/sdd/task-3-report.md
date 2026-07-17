# Task 3 Report: Mock Upload Modal and State Machine

## Delivered

- Added `advanceUploadStage(stageIndex, failed)`, which advances one stage, caps at `Sẵn sàng`, and preserves failed items.
- Added an accessible upload modal with native controls for opening, closing, selecting/dropping files, document type, destination folder, and four agent permissions.
- Added three preloaded demo files. Processing advances every 650 ms; `Sao kê giao dịch lỗi.xlsx` fails at indexing with the requested error and can be retried.
- Closing the modal clears its processing interval. Styling changes were intentionally deferred.

## TDD evidence

- RED: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs` failed because `advanceUploadStage` was not exported.
- GREEN: the same focused test command passed all 5 tests after implementation.

## Verification and review

- `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build` passed.
- `git diff --check` passed.
- Self-review confirmed every Task 3 brief requirement is represented; the drop zone was refined to a native button for keyboard accessibility.

## Known non-blocking output

- The existing production build emits Vite's chunk-size advisory and Vinext's route-classification advisory. Neither reports a build failure.

## Reviewer follow-up fixes

- The upload dialog now focuses its first interactive control on open, traps Tab and Shift+Tab within the dialog, closes on Escape, and restores focus to the upload trigger when closed.
- `isAcceptedUploadFileName` accepts only PDF, DOCX, and XLSX filenames. `addFiles` uses it for both chooser and drag-and-drop inputs, ignoring unsupported files.
- Extracted deterministic upload-item helpers for advancing stages (including the indexing failure), retry/reset, and start eligibility. The component uses these helpers directly.

## Reviewer follow-up TDD evidence

- RED, pure helpers: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs` failed because `advanceUploadItems` was not exported.
- GREEN, pure helpers: the same command passed 9/9 tests after implementation.
- RED, focus contract: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/documents-screen.test.mjs` failed because the upload trigger/dialog focus refs and keyboard behavior were absent.
- GREEN, focused suite: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs tests/documents-screen.test.mjs` passed 12/12 tests.
- Production verification: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build` passed; `git diff --check` passed.

## Hidden file-input follow-up

- Replaced the unavailable `sr-only` utility on the native file input with `hidden` and `tabIndex={-1}`. The visible drop-zone button remains the sole activator through `fileInputRef.current?.click()`.
- RED: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/documents-screen.test.mjs` failed the new hidden-input contract because the input used `className="sr-only"`.
- GREEN: the same command passed 4/4 tests after the structural hiding change.
- Focused verification: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" node --test tests/prototype-data.test.mjs tests/documents-screen.test.mjs` passed 13/13 tests.
- Production verification: `PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" npm run build` passed; `git diff --check` passed.
