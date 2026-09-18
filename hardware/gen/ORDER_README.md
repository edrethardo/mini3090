# ZETTEL3090 — Bestellung

Zwei dekorative, unbestückte Platinen. Optisch eine Miniatur einer
RTX-3090-Platine; die Rückseite trägt die Berliner Skyline in vergoldetem
Kupfer und einen scanbaren QR-Code auf das Projekt.

    RTX 3090 → Nemotron 3.5 → Zettel → GTC Berlin 2026

Quelle der Wahrheit ist das KiCad-Projekt unter `source/`. Sämtliche
Fertigungsdaten in diesem Paket wurden von `kicad-cli` aus genau diesen
Board-Dateien exportiert — nichts wurde nachträglich von Hand bearbeitet.

---

## 1. Fertigungsoptionen

Beim Hersteller (PCBWay, JLCPCB, Aisler, …) exakt so einstellen:

| Option | Wert |
|---|---|
| Lagen | **2** |
| Abmessungen | **110 × 48 mm** |
| Materialstärke | **1,6 mm** |
| Basismaterial | **FR-4** |
| Kupfer | **1 oz (35 µm)**, außen |
| Lötstopplack | **Schwarz** |
| Bestückungsdruck | **Weiß** |
| Oberfläche | **ENIG (chemisch Gold)** — nicht HASL |
| Bestückung | **keine** (unbestückte Platine) |
| Stückzahl | **je 5** (Mindestmenge; gebraucht werden 2, je 1 pro Design) |
| Goldfinger / abgeschrägte Kante | **nein** (nicht nötig, die Kontakte sind dekorativ) |
| Sondertext / Fertigungsnummer | **nein** bzw. „auf Rückseite unterdrücken" |

**ENIG ist nicht optional.** Die Skyline, das Wortbild ZETTEL, die
Seriennummer, die Kontaktfinger und der Die-Bereich entstehen dadurch, dass
Kupfer gezielt vom Lötstopplack ausgespart wird. Mit HASL wird daraus
stumpfes, unregelmäßiges Zinn statt Gold.

Der Hinweis „Fertigungsnummer / order number auf der Platine" sollte
abgewählt oder auf „an eine von uns gewählte Stelle" gesetzt werden — sonst
druckt der Hersteller eine Auftragsnummer mitten in die Skyline.

## 2. Welches ZIP für welche Platine

Die beiden Designs sind **physisch identisch** bis auf die Seriennummer, die
jeweils auf Vorder- **und** Rückseite steht.

| Platine | Datei | Aufdruck |
|---|---|---|
| 1 von 2 | `board_01_of_02/ZETTEL3090_01_of_02_gerbers.zip` | `01/02` |
| 2 von 2 | `board_02_of_02/ZETTEL3090_02_of_02_gerbers.zip` | `02/02` |

Das sind **zwei getrennte Bestellpositionen**. Ein ZIP hochladen, bestellen,
dann das zweite ZIP als neue Position hochladen. Beide ZIPs enthalten bereits
die Bohrdateien; separat hochladen ist nicht nötig.

## 3. Inhalt der ZIP-Dateien

| Datei | Lage |
|---|---|
| `ZETTEL3090_xx-F_Cu.gbr` | Kupfer oben |
| `ZETTEL3090_xx-B_Cu.gbr` | Kupfer unten |
| `ZETTEL3090_xx-F_Mask.gbr` | Lötstopp oben |
| `ZETTEL3090_xx-B_Mask.gbr` | Lötstopp unten |
| `ZETTEL3090_xx-F_Silkscreen.gbr` | Bestückungsdruck oben |
| `ZETTEL3090_xx-B_Silkscreen.gbr` | Bestückungsdruck unten |
| `ZETTEL3090_xx-Edge_Cuts.gbr` | Außenkontur |
| `ZETTEL3090_xx-PTH.drl` | durchkontaktierte Bohrungen |
| `ZETTEL3090_xx-NPTH.drl` | nicht durchkontaktierte Bohrungen (4 Befestigungslöcher, 2,2 mm) |
| `*-drl_map.gbr` | Bohrplan (Beleg, nicht fertigungsrelevant) |
| `*.gbrjob` | Gerber-Job-Datei mit Lagenzuordnung |

Format: Gerber X2, mm, absolute Koordinaten, Bohrungen Excellon.

## 4. Was geprüft wurde

`verification/REPORT.txt` enthält den vollständigen Prüflauf. Geprüft werden
die **exportierten Daten**, nicht die Absicht des Generators:

- alle sieben Gerber-Lagen und beide Bohrdateien vorhanden und nicht leer
- Außenkontur misst exakt 110,00 × 48,00 mm (aus `Edge.Cuts` gemessen)
- QR-Code wird aus dem gerenderten Bild der Rückseite dekodiert und ergibt
  `https://github.com/edrethardo/zettel`
- QR: Fehlerkorrektur H, 4 Module Ruhezone, 0,51 mm Modulgröße
- keine Bohrung, kein Bestückungsdruck innerhalb des QR-Symbols
- Rückseiten-Text ist im Board gespiegelt abgelegt und liest sich von der
  Rückseite betrachtet korrekt
- Seriennummer auf Vorder- und Rückseite derselben Platine, keine Reste der
  anderen Nummer
- Goldflächen bleiben unter 50 % der Platinenfläche — Schwarz dominiert

### Zur DRC

`verification/strict_drc_xx.txt` zeigt den DRC-Lauf **ohne** die
Unterdrückungen. Übrig bleiben nur zwei Kategorien:

- **netzabhängig** (`track_dangling`, `solder_mask_bridge`, `via_dangling`):
  Die Platine hat keinen Schaltplan und damit keine Netzliste. Jede Leiterbahn
  ist Dekoration und endet folgerichtig im Nichts; jede Lötstopp-Öffnung liegt
  per Definition über „verschiedenen Netzen", weil es keine gibt. Diese Regeln
  sind hier prinzipiell nicht erfüllbar und ohne Fertigungsrelevanz.
- **kosmetisch** (`silk_over_copper`, `silk_overlap`): Weißer Druck auf
  vergoldetem Kupfer ist gewollt — die Die-Beschriftung und die Bauteil-
  bezeichner.

Alles, was echte Fertigbarkeit beschreibt — Abstände, Bohrungsgrößen,
Kantenabstand, Leiterbahnbreite, Restring, Schrifthöhe, Loch-zu-Loch — ist
**fehlerfrei**. Das prüft `strict_drc.py` automatisch und bricht ab, sobald
eine dieser Regeln verletzt wird.

## 5. Neu erzeugen

```bash
cd /data/projects/mini3090
./hardware/gen/release.sh            # -> ZETTEL3090_FINAL/
```

Braucht KiCad 9 (`kicad-cli`, `pcbnew`-Python-Bindings) und das venv unter
`.venv` (segno, opencv, numpy).

## 6. Rechtliches

NVIDIA, GeForce, RTX und GA102 sind Marken der NVIDIA Corporation. Dieses
Projekt ist inoffiziell, nicht funktional und steht in keiner Verbindung zu
NVIDIA. Es wurden keine NVIDIA-Schaltpläne oder -Layoutdaten verwendet; die
Anmutung ist nach öffentlich sichtbaren Platinenfotos frei nachempfunden.
Es werden keine NVIDIA-Logos oder geschützten Gestaltungselemente abgebildet.
