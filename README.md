# DeS Save Converter

Jednoduchý nástroj pro Windows, který z neúplného saveu **Demon’s Souls Remake (PPSA01341)** vytvoří kompletní strukturu pro **KytyPS5**. Doplní chybějící `sce_sys` metadata, ale samotný herní postup nezmění.

> Nástroj pracuje pouze s už dešifrovanými `USR-DATA`. Nešifruje, nedešifruje a nepřepodpisovává PS5 savey.

## Rychlý start — hotový program

1. Stáhněte `DeSSaveConverter.exe` z [nejnovějšího release](https://github.com/Hammanek/des-save-converter/releases/latest).
2. Spusťte program. Python není potřeba.
3. Vyberte:
   - **Neúplný save** — složku obsahující `SAVEDATA0PlayerProfile0` a `SAVEDATA0OptionsProfile0` s pouhými `USR-DATA`.
   - **Funkční reference** — jiný funkční save téže hry, který má kompletní složky `sce_sys`.
   - **Výstupní složka** — novou nebo prázdnou složku pro výsledek.
4. Stiskněte **Převést save**.
5. Hotovou výstupní složku použijte jako `PPSA01341` v uložených datech KytyPS5.

Reference se používá pouze jako zdroj ikony, velikosti bloků a šablony metadat. Výsledný `param.bin` se vytvoří podle skutečného jména, třídy a Soul Levelu postavy ze vstupního saveu.

## Příklad

Vstup:

```text
PPSA01341_before_repair/
├── SAVEDATA0PlayerProfile0/USR-DATA
└── SAVEDATA0OptionsProfile0/USR-DATA
```

Výstup:

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

## Bezpečnost

- Originální i referenční save zůstávají beze změny.
- Oba `USR-DATA` jsou bajt po bajtu identické se vstupem.
- Program ověřuje verzi hlavičky, délku dat a FNV-1a kontrolní součet.
- Poškozený nebo neznámý formát je odmítnut.
- Výsledek se nejprve vytváří v dočasné složce a po kontrole se teprve přesune do cíle.
- Neprázdná výstupní složka se nikdy nepřepíše.
- Přesto je vhodné mít vlastní zálohu saveu.

## Omezení

- Podporován je pozorovaný formát `USR-DATA` verze 7 a `param.bin` používaný v KytyPS5.
- Neznámou lokaci a čas hraní nástroj do metadat nevymýšlí.
- Program neřeší šifrování saveů, vlastnictví PSN účtu ani přenos mezi účty.
- Úspěšná kontrola souborů nenahrazuje vyzkoušení načtení ve hře. Kompatibilita samotné hry/emulátoru je mimo rozsah nástroje.

## Kontrola staženého souboru

Release obsahuje také `DeSSaveConverter.exe.sha256`. Hash lokálního souboru získáte v PowerShellu:

```powershell
(Get-FileHash .\DeSSaveConverter.exe -Algorithm SHA256).Hash
```

Porovnejte jej s hashem uvedeným v `.sha256` souboru.

## Spuštění ze zdrojového kódu

Vyžaduje Python 3.10 nebo novější; běhové závislosti nejsou potřeba.

Grafické rozhraní:

```powershell
python des_save_gui.py
```

Příkazová řádka:

```powershell
python des_save_converter.py `
  --input "PPSA01341_before_repair" `
  --reference "1\PPSA01341" `
  --output "PPSA01341_converted"
```

## Testy

```powershell
python -m unittest discover -s tests -v
```

Testy používají dočasné syntetické savey. Neukládají do repozitáře žádná uživatelská herní data.

## Vytvoření Windows executable

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Skript vytvoří izolované `.venv-build`, nainstaluje PyInstaller a vytvoří:

```text
dist/DeSSaveConverter.exe
dist/DeSSaveConverter.exe.sha256
```

## Licence

MIT — viz [LICENSE](LICENSE).
