# mini3090

Ein Mini-3090-PCB — ein Geschenk für Jensen Huang.

Eine verkleinerte, funktionale Hommage an die RTX 3090: eine Platine im
Miniaturformat, die die Silhouette und Anmutung der Karte aufgreift.

## Stand

Frühe Konzeptphase. Noch keine Schaltung, kein Layout, keine Firmware.

## Offene Entscheidungen

- Maßstab & Formfaktor (Kartenlänge, Slotblende ja/nein)
- Funktion: reines Schauobjekt, Beleuchtung (LEDs), oder MCU-getrieben
  (Display, Lüfteranimation, USB)
- Fertigung: Leiterplattenhersteller, Lagenzahl, Lötstopplack-/Bestückungsdruck-Farbe
- Verpackung / Präsentation (das Geschenk ist Teil des Produkts)

## Struktur

```
hardware/   Schaltplan, Layout, Fertigungsdaten (Gerber, BOM, Pick&Place)
firmware/   Code, falls eine MCU verbaut wird
docs/       Recherche, Referenzbilder, Maße, Notizen
```

## Rechtliches

NVIDIA, GeForce und RTX sind Marken der NVIDIA Corporation. Dieses Projekt ist
inoffiziell und steht in keiner Verbindung zu NVIDIA. Keine NVIDIA-Logos oder
geschützten Designelemente in Fertigungsdaten, die veröffentlicht werden.
