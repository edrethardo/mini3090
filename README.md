# mini3090 — ZETTEL3090

Eine dekorative Miniatur-Platine im Stil einer RTX 3090, als Geschenk für
Jensen Huang zur NVIDIA GTC Berlin 2026.

Die Rückseite trägt die Berliner Skyline in vergoldetem Kupfer und einen
scanbaren QR-Code auf [github.com/edrethardo/zettel](https://github.com/edrethardo/zettel) —
das Projekt, das lokal mit NVIDIA Nemotron 3.5 auf einer RTX 3090 lief.

    RTX 3090 → Nemotron 3.5 → Zettel → GTC Berlin 2026

**Ein Design, ein Gerber-Satz.** Alle Platinen sind identisch; vorne steht
nur `/03` im weißen Bestückungsdruck, davor ein freies 10 × 5 mm-Feld aus
mattschwarzem Lötstopplack. Die Nummer (`01`, `02`, `03`) wird nach der
Fertigung von Hand mit Lackstift eingetragen. Bei PCBWay: Different Designs 1.
Die Auflagengröße steht an genau einer Stelle — `TOTAL` in
`hardware/gen/release.sh`.

## Das Wichtigste

Die Platine wird **generiert, nicht gezeichnet**: Python baut mit KiCads
eigener `pcbnew`-API ein echtes `.kicad_pcb`, und `kicad-cli` exportiert
daraus Gerber, Bohrdateien und die Vorschaubilder. Es gibt keine handgemalten
Gerber und keine gerenderten Bilder, die etwas zeigen, das im Layout nicht
steht.

| | |
|---|---|
| Format | 110 × 48 mm, 2 Lagen, FR-4 1,6 mm |
| Oberfläche | ENIG — die Skyline ist echtes vergoldetes Kupfer |
| Farben | schwarzer Lötstopplack, weißer Bestückungsdruck |
| Funktion | keine. Kein Schaltplan, keine Netzliste, kein Bauteil. |

## Bauen

Voraussetzungen:

- **KiCad 9** mit `kicad-cli` und den `pcbnew`-Python-Bindings
  (Ubuntu/Debian: `sudo add-apt-repository ppa:kicad/kicad-9.0-releases &&
  sudo apt install kicad`; andere Systeme: [kicad.org/download](https://www.kicad.org/download/))
- `python3` mit `venv`, `bash`, `zip`

```bash
git clone https://github.com/edrethardo/mini3090.git
cd mini3090
./setup.sh                    # einmalig: .venv mit den Python-Abhängigkeiten
./hardware/gen/release.sh     # -> ZETTEL3090_FINAL/
```

`setup.sh` sucht das Python, mit dem KiCad installiert wurde (das einzige, das
`pcbnew` importieren kann), legt damit `.venv` mit `--system-site-packages` an
und installiert `requirements.txt`. Liegt KiCads Python woanders:
`KICAD_PYTHON=/pfad/zu/python3 ./setup.sh`. Die Skripte funktionieren aus jedem
Checkout-Verzeichnis; mit `PYTHON=...` lässt sich ein anderer Interpreter setzen.

Getestet mit KiCad 9.0.9 unter Ubuntu 24.04. macOS und Windows sind nicht getestet.

Für eine schnelle Design-Iteration ohne den vollen Export:

```bash
./hardware/gen/iterate.sh     # -> build/iterate/: Board, beide Seiten gerendert, QR geprüft
```

## Ergebnis

`ZETTEL3090_FINAL/` — `ZETTEL3090_PCBWAY_STANDARD.zip` (die einzige
Fertigungsdatei), KiCad-Quellen, `PCBWAY_ORDER_SETTINGS.md`,
`PCBWAY_MANUFACTURING_NOTES.md`, `DRC_6MIL_REPORT.txt`, `DRC_4MIL_REPORT.txt`,
`SAME_NET_CLEARANCE_REPORT.txt`, Renders, Gerber-Ansichten, Detailansicht des
Nummernfeldes und `verification/REPORT.txt`.

## Aufbau des Generators

```
hardware/gen/
  layout.py      Alle Maße an einer Stelle: Kontur, Bauteilraster, Keepouts
  kicadlib.py    Dünne Hülle um pcbnew: Formen, Pads, Text, Gold-Helfer
  occupancy.py   Belegungskarte (0,05 mm/Zelle) — der Platzierungswächter
  blocks.py      Bausteine: BGA, GDDR6X, QFN, Choke, Bus, Via-Feld …
  skyline.py     Berliner Skyline aus Leiterbahnen
  qr.py          QR-Code als Kupfer + Lötstopp-Öffnungen
  build.py       Setzt das Board zusammen
  stackup.py     Schreibt Farben/Oberfläche in die Board-Datei
  project.py     .kicad_pro mit DRC-Severities und Netzklasse
  clearance.py   Kupfer-Abstände ohne Netzliste: Inseln, Beinahe-Kontakte
  strict_drc.py  DRC OHNE Unterdrückungen — bricht bei echten Fehlern ab
  gerber_raster.py / gerber_drc.py / gerber_report.py
                 Geometrische DRC auf den exportierten Gerbern (6/4 mil)
  gerber_views.py  Gerber-Ansichten + Detail des Nummernfeldes
  verify.py      Prüft die EXPORTIERTEN Daten (nicht die Absicht)
  docs/          PCBWay-Bestellwerte und Fertigungshinweise
  release.sh     Der vollständige Produktionslauf
  iterate.sh     Kurzer Design-Loop
```

### Zwei Entwurfsentscheidungen, die alles tragen

**Der Platzierungswächter.** Eine generierte Platine hat keinen Router, der
Konflikte auflöst. Jedes Objekt fragt deshalb vor dem Setzen eine Belegungs-
karte, ob seine Fläche frei ist — inklusive Bohrraster und Platinenkante.
Das ersetzt das nachträgliche Aufweichen der Design Rules: statt Fehler zu
ignorieren, entstehen sie gar nicht erst.

**Zwei Phasen.** Erst werden alle echten Bauteile platziert, dann erst die
Dekoration (Leiterbahnen, Vias, Streuteile). Andersherum belegt das Fanout
eines Speicherbausteins den Platz des nächsten, und der Wächter verwirft
lautlos genau die Bauteile, die das Design ausmachen.

### Warum die DRC Ausnahmen hat

Ohne Netzliste sind einige Regeln prinzipiell unerfüllbar: jede Leiterbahn
ist Dekoration und endet im Nichts (`track_dangling`), jede Lötstopp-Öffnung
liegt per Definition über „verschiedenen Netzen" (`solder_mask_bridge`).
Diese Regeln sind in `project.py` bewusst abgeschaltet und dort begründet.

Damit diese Liste nicht unbemerkt wächst und echte Fehler verdeckt, läuft
`strict_drc.py` denselben Check **ohne** Unterdrückungen und bricht ab, sobald
eine Regel verletzt wird, die tatsächliche Fertigbarkeit beschreibt —
Abstände, Bohrungen, Kantenabstand, Leiterbahnbreite, Restring, Schrifthöhe.

## Lizenz

[MIT](LICENSE) — Generator, Skripte und Doku.

## Rechtliches

NVIDIA, GeForce, RTX und GA102 sind Marken der NVIDIA Corporation. Dieses
Projekt ist inoffiziell, nicht funktional und steht in keiner Verbindung zu
NVIDIA. Es wurden keine NVIDIA-Schaltpläne oder -Layoutdaten verwendet; die
Anmutung ist nach öffentlich sichtbaren Platinenfotos frei nachempfunden.
Es werden keine NVIDIA-Logos oder geschützten Gestaltungselemente abgebildet.
