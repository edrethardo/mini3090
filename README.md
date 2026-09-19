# mini3090 — ZETTEL3090

Eine dekorative Miniatur-Platine im Stil einer RTX 3090, als Geschenk für
Jensen Huang zur NVIDIA GTC Berlin 2026.

Die Rückseite trägt die Berliner Skyline in vergoldetem Kupfer und einen
scanbaren QR-Code auf [github.com/edrethardo/zettel](https://github.com/edrethardo/zettel) —
das Projekt, das lokal mit NVIDIA Nemotron 3.5 auf einer RTX 3090 lief.

    RTX 3090 → Nemotron 3.5 → Zettel → GTC Berlin 2026

Drei physisch identische Platinen, `01/03`, `02/03` und `03/03`, jeweils auf
Vorder- und Rückseite nummeriert. Die Auflagengröße steht an genau einer
Stelle — `SERIALS` in `hardware/gen/release.sh`.

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

```bash
./hardware/gen/release.sh          # -> ZETTEL3090_FINAL/
```

Voraussetzungen: KiCad 9 (`kicad-cli` + `pcbnew`-Python-Bindings) sowie das
venv unter `.venv` (segno, opencv-python-headless, numpy).

```bash
python3 -m venv --system-site-packages .venv   # --system-site-packages: pcbnew
.venv/bin/pip install segno opencv-python-headless numpy pillow
```

Für eine schnelle Design-Iteration ohne den vollen Export:

```bash
./hardware/gen/iterate.sh /tmp/z   # baut 01, rendert beide Seiten, prüft den QR
```

## Ergebnis

`ZETTEL3090_FINAL/` — Quellen, drei Gerber-Pakete, Vorschaubilder,
Prüfprotokolle und `ORDER_README.md` mit den exakten Herstelleroptionen.

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
  strict_drc.py  DRC OHNE Unterdrückungen — bricht bei echten Fehlern ab
  verify.py      Prüft die EXPORTIERTEN Daten (nicht die Absicht)
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

## Rechtliches

NVIDIA, GeForce, RTX und GA102 sind Marken der NVIDIA Corporation. Dieses
Projekt ist inoffiziell, nicht funktional und steht in keiner Verbindung zu
NVIDIA. Es wurden keine NVIDIA-Schaltpläne oder -Layoutdaten verwendet; die
Anmutung ist nach öffentlich sichtbaren Platinenfotos frei nachempfunden.
Es werden keine NVIDIA-Logos oder geschützten Gestaltungselemente abgebildet.
