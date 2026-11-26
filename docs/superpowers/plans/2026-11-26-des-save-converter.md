# DeS Save Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a safe one-click Windows GUI that wraps decrypted Demon's Souls `USR-DATA` files in the complete KytyPS5 save structure.

**Architecture:** A dependency-free Python conversion library validates and copies the game data, reads character metadata and stages a complete output directory before atomically publishing it. A small Tkinter GUI calls that library; unittest covers conversion and failure paths and PyInstaller produces the standalone release executable.

**Tech Stack:** Python 3.12 standard library, Tkinter, unittest, PyInstaller 6, GitHub CLI.

**Spec:** `DES_SAVE_CONVERTER_AGENT_BRIEF.md` (copied from the analysis at the workspace root).

## Global Constraints

- Never modify `USR-DATA`; output copies must be byte-identical.
- Never modify the input or reference save and never overwrite a non-empty output.
- Reject invalid headers, FNV-1a checksums, unknown character data and unsupported reference metadata.
- Runtime code uses only the Python standard library.
- Do not claim PS5 decryption, encryption, account re-signing or in-game verification.
- Tests use generated temporary fixtures; real user saves are not committed.

## Review Focus

- Existing output or a failed conversion: no data loss and no partial destination; covered by Tasks 2 and 3.
- Corrupt or truncated player/options data: reject before creating output; covered by Task 1.
- Unexpected save field types or string bounds: fail with a useful error rather than misread; covered by Task 1.
- Unsupported reference `param.bin`: reject instead of generating malformed metadata; covered by Task 2.
- GUI startup and release artifact: test actual Tkinter startup and inspect the packaged executable; covered by Tasks 3 and 4.

---

### Task 1: Validated save parser

**Files:**
- Create: `des_save_converter.py`
- Create: `tests/test_converter.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: `validate_usr_data(data: bytes) -> None`, `read_character(data: bytes) -> Character`, `fnv1a32(data: bytes) -> int` and `ConversionError`.
- `Character` fields: `name: str`, `class_id: int`, `class_name: str`, `soul_level: int`.

- [ ] **Step 1: Write failing tests and fixture helpers**
  - Generate valid player data containing the known character fields and minimal valid options data.
  - Test Knight `mobus`, level 18; Soldier `Jirka`, level 6.
  - Test bad version, marker, payload size, checksum, truncated string, unknown class and unknown field type.
- [ ] **Step 2: Run tests and verify failure**
  - Run: `python -m unittest discover -s tests -v`.
  - Expected: import failure because the converter does not exist.
- [ ] **Step 3: Implement bounded field walking and header validation**
  - Use little-endian binary parsing and the exact FNV-1a constants from the spec.
  - Do not scan for character keys in arbitrary bytes.
- [ ] **Step 4: Run focused tests and commit**
  - Run the full unittest command and require all parser tests to pass.
  - Commit `feat: parse and validate Demon's Souls saves`.

### Task 2: Safe complete-save conversion

**Files:**
- Modify: `des_save_converter.py`
- Modify: `tests/test_converter.py`

**Interfaces:**
- Consumes: Task 1 parser interfaces.
- Produces: `convert_save(input_dir: Path, reference_dir: Path, output_dir: Path) -> Character`.
- Produces a root containing exactly the eight files in the spec.

- [ ] **Step 1: Write failing conversion tests**
  - Verify output layout, metadata text, options metadata, icon/blocks copying and identical `USR-DATA` hashes.
  - Test missing input/reference files, unsupported `param.bin`, existing non-empty output and rollback after injected copy failure.
- [ ] **Step 2: Run tests and verify the conversion test fails**
  - Expected: `convert_save` is not defined.
- [ ] **Step 3: Implement staged conversion**
  - Validate both input files and reference before writing.
  - Create a temporary sibling directory, copy data, synthesize player `param.bin`, validate and publish it with rename.
  - Add an argparse CLI with `--input`, `--reference`, `--output` and a concise success/error message.
- [ ] **Step 4: Verify and commit**
  - Run all unit tests, then perform an integration conversion on a temporary copy of the supplied real saves without changing originals.
  - Commit `feat: convert incomplete saves safely`.

### Task 3: Simple GUI and user documentation

**Files:**
- Create: `des_save_gui.py`
- Create: `README.md`
- Create: `LICENSE`

**Interfaces:**
- Consumes: `convert_save` and `ConversionError` from Task 2.
- GUI entry point: `main() -> None`.

- [ ] **Step 1: Implement Tkinter GUI**
  - Three path fields and Browse buttons, a Convert button and a status area.
  - Disable conversion while busy, run it in a worker thread and return results/errors to the Tk event loop.
  - Default the output to a new sibling path; never launch conversion on the UI thread.
- [ ] **Step 2: Write README and license**
  - Czech quick start for the executable, input/reference/output explanation, safety, limitations, source usage, tests and build instructions.
- [ ] **Step 3: Verify GUI startup and tests**
  - Launch and close the GUI without conversion; check no startup exception and all tests still pass.
  - Commit `feat: add user-friendly converter GUI` and `docs: add user and build guide` together.

### Task 4: Reproducible build and release checks

**Files:**
- Create: `build.ps1`
- Create: `requirements-build.txt`

- [ ] **Step 1: Add isolated build script**
  - Create a local build venv, install PyInstaller 6, build one windowed executable named `DeSSaveConverter.exe` and generate SHA-256.
- [ ] **Step 2: Build and inspect the executable**
  - Run the build, confirm a non-zero PE executable exists and starts without an immediate crash.
  - Run the source unit tests again and record the real-save integration result.
- [ ] **Step 3: Commit release build files**
  - Commit `build: add standalone Windows executable build`.

### Task 5: Repository and GitHub release

- [ ] **Step 1: Review the repository state**
  - Require clean tests, no build artifacts or save data staged and a final source diff review.
- [ ] **Step 2: Publish the repository**
  - Create public GitHub repository `Hammanek/des-save-converter`, push `main` and tag `v1.0.0`.
- [ ] **Step 3: Publish and verify the release**
  - Create release `v1.0.0` with usage notes, `DeSSaveConverter.exe` and `DeSSaveConverter.exe.sha256`.
  - Download assets to a temporary directory and compare their hashes with the local artifacts.
