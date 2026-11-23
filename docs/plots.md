# Wissenschaftliche Diagramme

`python tools/export_plots.py` schreibt sechs Abbildungen als PNG (3840 × 2160) und
als eigenständige, editierbare SVG-Dateien nach `outputs/Plots`. Es werden nur Pillow
und die Python-Standardbibliothek benötigt; die Werte stammen aus `physics.py`.
Mit `--fixed-proton` wird die Näherung eines feststehenden Protons gewählt.

| Datei | Dargestellte Größe |
| --- | --- |
| `01_effektives_potential` | Effektives Radialpotential bei festem **L = ℏ**, mit Zentrifugalterm und Coulombpotential; Energie in eV, Abstand in Einheiten der natürlichen Längenskala |
| `02_energieniveaus` | Erlaubte Energien für n = 1 bis 6; gemeinsame quantitative Energieachse und Ionisationsgrenze E = 0 |
| `03_bahnradien` | Diskrete Radien im Verhältnis 1:4:9:16:25:36; keine Zwischenwerte als erlaubte Zustände |
| `04_umlaufzeiten` | Diskrete Umlaufzeiten im Verhältnis 1:8:27:64:125:216 |
| `05_balmerlinien` | Berechnete **Vakuumwellenlängen** der Übergänge n = 3, 4, 5, 6 nach n = 2; gleiche Strichhöhen sind **keine Intensitätsvorhersage** |
| `06_radialwahrscheinlichkeit` | Normierte dimensionslose radiale 1s-Verteilung neben einer Markierung des festen Bohr-Abstands; die Markierung ist keine endlich hohe Wahrscheinlichkeitsdichte |

Standard ist die reduzierte Masse μ. Dann bezeichnet r den Abstand zwischen Elektron
und Proton und aμ = ℏ²/(μκ). Beim feststehenden Proton wird die Achse mit a₀ beschriftet.
Die räumliche 1s-Dichte und die radiale Verteilung sind verschiedene Größen:
Die hier gezeichnete Funktion ist aμ P(r) = 4(r/aμ)² exp(−2r/aμ).
Ihr Maximum liegt bei r = aμ, ihr Mittelwert bei 1,5 aμ.

Das Minimum des effektiven Potentials ergibt sich aus klassischer Mechanik **bei
vorgegebenem Drehimpuls**. Die Auswahl L = ℏ ist bereits Bohrs Quantisierungspostulat;
der Plot leitet dieses Postulat nicht aus der Coulombkraft her.

PNG und SVG entstehen aus denselben Zeichenoperationen und Datenkoordinaten. SVG
enthält keine externen Bilder und keine Rastereinbettungen. Serifenschriften können
beim Öffnen auf einem anderen System ersetzt werden: Georgia für Fließtext und
Cambria beziehungsweise DejaVu Serif für mathematische Symbole. Die Kurven sind
vektoriell. Für eine unveränderte Typografie beim Videoschnitt empfiehlt sich PNG.

## Beschriftungen der Filme

`draw_overlay` verändert das übergebene Renderbild nicht, sondern gibt eine RGB-Kopie
zurück. Positionen aus `screen_points`, `panel_labels` und `panel_rect` sind Bildpixel.
Die Bewegungszeit kommt ausschließlich aus den Metadaten; die Zeichenroutine
erzeugt keine neue Bewegung und interpoliert keine physikalischen Zwischenzustände.

Das Spektrumpanel stellt Energien maßstäblich dar. Bei dicht benachbarten Niveaus
werden nur deren Beschriftungen über kurze Führungslinien auseinandergezogen.
Der gezeichnete Übergangspfeil bezeichnet eine Energiedifferenz; seine Animationsdauer
ist keine vom Bohr-Modell vorhergesagte Übergangsdauer.

Im Spektrumfilm bleiben „Übergang schematisch“ und die Vakuumkennzeichnung sichtbar.
Während der Übergangsanimation nennt die Kopfzeile beide Quantenzahlen; der Zeitmaßstab
ist ausdrücklich nur der Bahnbewegung zugeordnet. Die Spektralachse umfasst 360 bis
720 nm und zeigt auch den ausgewählten Übergang oberhalb von n = 6. Ultraviolette
Linien unter 380 nm werden neutral grau dargestellt. Die Energiediagramme ergänzen
den ausgewählten Zustand bis n = 12 und entzerren nur Beschriftungen, keine Energien.
Vektorpfeile werden als normierte Pfeillängen gekennzeichnet. Im Orbitalvergleich
benennen zwei kurze Hinweise die Punktstichprobe und die gemeinsame Längenskala.
