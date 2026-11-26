# DeS Save Converter

A simple Windows tool that converts an incomplete **Demon’s Souls Remake (PPSA01341)** save **from KytyPS5 to the native PC port**. It adds the missing `sce_sys` metadata without changing game progress.

> The tool only works with already-decrypted `USR-DATA` files. It does not encrypt, decrypt, or re-sign PS5 saves.

## Quick start — prebuilt application

1. Download `DeSSaveConverter.exe` from the [latest release](https://github.com/Hammanek/des-save-converter/releases/latest).
2. Run the application. Python is not required.
3. Select:
   - **Incomplete save** — the folder containing `SAVEDATA0PlayerProfile0` and `SAVEDATA0OptionsProfile0` with only `USR-DATA` files.
   - **Working reference** — another working save from the same game that has complete `sce_sys` folders.
   - **Output folder** — a new or empty folder for the converted save.
4. Click **Convert save**.
5. Use the completed output folder as `PPSA01341` in your native PC port save data.

The reference supplies only the icon, block sizes, and metadata templates. The output `param.bin` is generated from the actual character name, class, and Soul Level in the input save.

## Example

Input:

```text
PPSA01341_before_repair/
├── SAVEDATA0PlayerProfile0/USR-DATA
└── SAVEDATA0OptionsProfile0/USR-DATA
```

Output:

```text
PPSA01341_converted/
├── SAVEDATA0PlayerProfile0/
│   ├── USR-DATA
│   └── sce_sys/
│       ├── blocks
│       ├── icon0.png
│       └── param.bin
└── SAVEDATA0OptionsProfile0/
    ├── USR-DATA
    └── sce_sys/
        ├── blocks
        ├── icon0.png
        └── param.bin
```

## Safety

- The input and reference saves are never modified.
- Both output `USR-DATA` files are byte-for-byte identical to the input.
- The header version, payload size, and FNV-1a checksum are validated.
- Corrupt or unsupported data is rejected.
- Conversion is staged in a temporary folder and published only after verification.
- A non-empty output folder is never overwritten.
- Keeping your own save backup is still recommended.

## Limitations

- Supports the observed `USR-DATA` version 7 and the `param.bin` layout used by the native PC port.
- Unknown location and playtime are not invented for generated metadata.
- The tool does not handle save encryption, PSN account ownership, or transfers between accounts.
- File validation is not a substitute for loading the save in the game. Game and emulator compatibility is outside the tool’s scope.

## Verify the download

The release also includes `DeSSaveConverter.exe.sha256`. Get the local file hash in PowerShell:

```powershell
(Get-FileHash .\DeSSaveConverter.exe -Algorithm SHA256).Hash
```

Compare it with the hash in the `.sha256` file.

## Run from source

Python 3.10 or newer is required. There are no runtime dependencies.

GUI:

```powershell
python des_save_gui.py
```

Command line:

```powershell
python des_save_converter.py `
  --input "PPSA01341_before_repair" `
  --reference "1\PPSA01341" `
  --output "PPSA01341_converted"
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary synthetic saves. No user game data is included in the repository.

## Build the Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The script creates an isolated `.venv-build`, installs PyInstaller, and produces:

```text
dist/DeSSaveConverter.exe
dist/DeSSaveConverter.exe.sha256
```

## License

MIT — see [LICENSE](LICENSE).
