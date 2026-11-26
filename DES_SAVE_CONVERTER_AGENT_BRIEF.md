# Zadání pro agenta: konvertor Demon’s Souls PS5 saveů

Vytvoř bezpečný CLI nástroj v **Pythonu 3, pouze se standardní knihovnou**, který převede neúplný save Demon’s Souls Remake (`PPSA01341`) obsahující dešifrované soubory `USR-DATA` **z KytyPS5 do kompletní struktury použitelné v nativním PC portu**.

## Rozsah

Toto **není dešifrování, šifrování ani podpisování PS5 saveů**. Nástroj pracuje pouze s už dešifrovanými `USR-DATA` a doplňuje chybějící systémová metadata `sce_sys`.

Hlavní pravidlo: **herní data nijak nepřepisovat**. Původní `USR-DATA` musí být po konverzi bajt po bajtu identické.

## Dostupné testovací soubory

Pracovní složka:

```text
d:\download\Demon Souls\PPSA01341
```

Funkční referenční save:

```text
1\PPSA01341\
```

Původní neúplný save před opravou:

```text
PPSA01341_before_repair\
```

Opravený výstup jako referenční výsledek:

```text
PPSA01341\
```

Neprovádět testy in-place nad těmito složkami. Testy mají pracovat s dočasnými kopiemi.

## Cílová struktura

```text
PPSA01341/
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

Neúplný vstup obsahuje pouze oba soubory `USR-DATA`.

## Navrhované CLI

```powershell
python des_save_converter.py convert `
  --input "PPSA01341_before_repair" `
  --reference "1\PPSA01341" `
  --output "converted-save"
```

Chování:

- `--input` obsahuje neúplný save.
- `--reference` obsahuje známý funkční save stejné hry a verze formátu.
- `--output` musí být nová nebo prázdná složka.
- Nikdy nepřepisovat vstup ani referenci.
- Při chybě nenechávat částečně dokončený výstup; ideálně zapisovat do dočasné složky a po validaci ji přejmenovat.
- Po zápisu znovu otevřít výsledné soubory a ověřit výsledek.
- Poskytnout srozumitelné chybové hlášky a nenulový exit code při selhání.

## Formát `USR-DATA`

Hlavička má 16 bajtů, little-endian:

| Offset | Typ | Význam |
|---|---:|---|
| `0x00` | `u32` | Verze, pozorováno `7` |
| `0x04` | `u32` | FNV-1a 32 kontrolní součet těla |
| `0x08` | `u32` | Velikost těla, tedy `len(file) - 0x10` |
| `0x0C` | `u32` | Marker, pozorováno `1` |
| `0x10` | data | Stream herních polí |

Kontrolní součet se počítá **pouze z `data[0x10:]`**:

```python
def fnv1a32(data: bytes) -> int:
    value = 0x811C9DC5
    for byte in data:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value
```

Před konverzí validovat:

```python
version == 7
marker == 1
payload_size == len(data) - 16
stored_checksum == fnv1a32(data[16:])
```

Při neplatné hlavičce nebo kontrolním součtu standardně konverzi odmítnout. Kontrolní součet automaticky nepřepočítávat, protože tím by mohla být skryta skutečná chyba vstupu.

## Čtení údajů o postavě

Pole herního saveu mají obecně podobu:

```text
key: u32 | type: u8 | value
```

Místo hledání klíčů slepým `bytes.find()` je vhodnější projít stream polí, aby nevznikla falešná shoda uvnitř binárních dat.

Známé typy:

| Typ | Hodnota |
|---:|---|
| `0x02` | 1 bajt |
| `0x03` | 2 bajty |
| `0x04` | 4 bajty |
| `0x06` | 1 bajt |
| `0x08` | `u32`, 4 bajty |
| `0x0A` | `float32`, 4 bajty |
| `0x0C` | 1 bajt |
| `0x0D` | 1 bajt délky + UTF-8 text |
| `0x0F` | 16 bajtů |
| `0x0E` | LEB128; některá pole mají následný blob |

Pro tento nástroj stačí bezpečně vyhledat následující pevné klíče ve formátu `<IB`, tedy `u32 key + u8 type`:

```python
CHARACTER_FIELDS = {
    "name":         (0x324FEFCE, 0x0D),
    "class":        (0x45B54344, 0x08),
    "vitality":     (0xF059AB80, 0x08),
    "intelligence": (0x14795A91, 0x08),
    "endurance":    (0xD02FD40F, 0x08),
    "strength":     (0x5078FC63, 0x08),
    "dexterity":    (0xA144D982, 0x08),
    "magic":        (0xB06E4ED9, 0x08),
    "faith":        (0xD6A72566, 0x08),
    "luck":         (0x7B664AD3, 0x08),
}
```

Statistiky jsou `u32`. Jméno má za hlavičkou pole jednobajtovou délku a potom UTF-8 data.

Soul Level lze odvodit:

```python
soul_level = sum([
    vitality,
    intelligence,
    endurance,
    strength,
    dexterity,
    magic,
    faith,
    luck,
]) - 80
```

Třídy:

```python
CLASSES = {
    0: "Soldier",
    1: "Knight",
    2: "Hunter",
    3: "Priest",
    4: "Magician",
    5: "Wanderer",
    6: "Barbarian",
    7: "Thief",
    8: "Temple Knight",
    9: "Royalty",
}
```

Ověřené příklady:

- `Jirka`, Soldier, Soul Level 6
- `mobus`, Knight, Soul Level 18

Pokud pole chybí, třída je neznámá nebo vypočtený level nedává smysl, nástroj má chybu nahlásit, ne hádat.

## Vytvoření `sce_sys`

### Options profile

Zkopírovat celý:

```text
<reference>\SAVEDATA0OptionsProfile0\sce_sys
```

### Player profile

Zkopírovat z referenčního player profilu:

- `icon0.png`
- `blocks`

`param.bin` použít jako šablonu, ale přepsat údaje podle skutečné postavy.

Pozorované hodnoty `blocks` jako little-endian `u64`:

```text
PlayerProfile:  96
OptionsProfile: 48
```

Referenční `icon0.png` má 531349 bajtů a u obou profilů je shodná. Nástroj má kopírovat skutečný referenční soubor, ne velikost generovat nulami.

## Pozorovaný formát `param.bin` pro nativní PC port

Toto není standardní PS4 `PARAM.SFO`. Je to jednoduchá struktura o délce **1328 bajtů (`0x530`)**:

| Oblast | Délka | Obsah |
|---|---:|---|
| `0x000` | `0x80` | Název hry, nulami zakončený a doplněný |
| `0x080` | `0x80` | Podtitul |
| `0x100` | `0x400` | Detail |
| `0x500` | `0x30` | Zbývající data šablony |

Název:

```text
Demon's Souls
```

Player podtitul:

```text
Player - <jméno>
```

Player detail:

```text
Soul Level <level> <třída>
```

Například:

```text
Player - mobus
Soul Level 18 Knight
```

Postup:

1. Načíst referenční `param.bin`.
2. Ověřit délku `0x530` a začátek `b"Demon's Souls\0"`.
3. Vynulovat pouze rozsah podtitulu a detailu.
4. Zapsat nové UTF-8 hodnoty na pevné offsety bez následného posunu dat.
5. Zachovat zbytek šablony.
6. Nikdy nepřekročit velikost příslušné oblasti.
7. Neznámou lokaci a playtime z referenčního saveu **nekopírovat**, protože by popisovaly jinou postavu.

Pokud reference nemá tento formát, ukončit se s chybou „unsupported reference param.bin format“. Nepokoušet se jej odhadnout jako standardní SFO.

## Povinné testy

Použít například `unittest` a dočasné složky:

1. Neúplný vstup se převede na přesně osm cílových souborů.
2. Oba výstupní `USR-DATA` mají stejný SHA-256 jako vstupní.
3. Hlavička, délka a FNV-1a kontrolní součet obou `USR-DATA` zůstávají platné.
4. Player metadata obsahují správné jméno, level a třídu.
5. Options metadata odpovídají referenci.
6. Player `icon0.png` a `blocks` odpovídají referenci.
7. Poškozený kontrolní součet způsobí odmítnutí vstupu.
8. Nesprávná délka v hlavičce způsobí odmítnutí vstupu.
9. Chybějící referenční soubor způsobí čisté selhání.
10. Existující neprázdný výstup se nepřepíše.
11. Při selhání nezůstane částečný výstup.
12. Znovu načtený výstup projde stejnou validací jako vstup.

Nejprve napsat testy proti původnímu neúplnému saveu, až potom implementaci. Na závěr vypsat výsledky testů a skutečně spustit konverzi na dočasné kopii dodaných souborů.

## Nejdůležitější poznatek z opravy

Původní `USR-DATA` byla v pořádku včetně kontrolních součtů. Save nefungoval kvůli chybějícím `sce_sys`, takže konvertor nemá „opravovat“ herní data, ale především **validovat je a doplnit správnou obálku saveu**.
