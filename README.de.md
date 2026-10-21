<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>Ersetzen Sie beschädigte Seiten einer gescannten PDF durch neue Scans. Zuordnen, prüfen, exportieren. Nichts verlässt Ihren Rechner.</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

Sie haben eine alte gescannte PDF mit ein paar ruinierten Seiten und neue Scans genau dieser Seiten in beliebiger Reihenfolge. Darnleaf schlägt vor, welche Seite jeder neue Scan ersetzt, zeigt Ihnen die Belege und schreibt eine reparierte PDF samt JSON-Quittung für jede Änderung.

- **Keine automatische Reparatur.** Jeder Treffer ist Sicher, Prüfen oder Kein Treffer. Der Export bleibt gesperrt, bis Sie jedes Prüfen bestätigt haben, und leere Seiten sind immer Prüfen, ebenso Seiten, bei denen der zweite Kandidat fast gleich gut abschneidet.
- **Kein Neuschreiben.** Seiten, die Sie nicht angefasst haben, sind die ursprünglichen Seitenobjekte und werden ohne erneutes Rendern gespeichert. Die Originaldatei wird nie beschrieben.
- **Kein Dienst.** Ein kleiner Server auf 127.0.0.1, ohne Konto, ohne Upload, ohne Telemetrie. Die Seite lädt keine entfernten Schriften oder Skripte.

## Ausprobieren

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

Mit **Mitgeliefertes Beispiel ausprobieren** läuft der ganze Ablauf an einem synthetischen Heft mit 40 Seiten durch. Sie können auch eigene Dateien ablegen. Die [Replay-Demo](https://arthur031221.github.io/Darnleaf/) spielt im Browser einen echten Lauf dieses Beispiels ab. Dateien nimmt sie nicht an. Mit `darnleaf serve original.pdf rescans/*.jpg` werden die Dateien gleich geladen und die Zuordnung gestartet.

```console
$ darnleaf sample job
wrote job/original.pdf, 7 rescans and truth.json
$ darnleaf match job/original.pdf job/rescans/*.jpg
rescan                        page  status  reason
rescan-01.jpg                   33  check   page 35 scores almost as high (margin 0.02)
rescan-02.jpg                   11  clear   205 consistent features, margin 0.60
rescan-03.jpg                    2  check   blank pages carry no evidence: confirm the position yourself
rescan-04.jpg                   22  clear   428 consistent features, margin 0.94
rescan-05.jpg                   31  check   page 32 scores almost as high (margin 0.05)
rescan-06.jpg                   27  clear   230 consistent features, margin 0.78
rescan-07.jpg                    -  none    no original page shares enough features or text with this rescan
$ darnleaf apply job/original.pdf job/rescans/*.jpg -o job/repaired.pdf
replaced 3 of 40 pages -> job/repaired.pdf
receipt -> job/repaired.receipt.json
```

`apply` hat nur die drei Sicher-Treffer verwendet. Die Prüfen-Fälle warten im Prüfbildschirm oder auf `--assign FILE=PAGE`.

## Messwerte

Gemessen an synthetischen Heften aus gemeinfreiem Text (*Stolz und Vorurteil*): 90 neue Scans über zehn zurückgehaltene Seeds (101 bis 110). Die Seiten werden mit Kaffeefleck, Knick und Schmierstelle beschädigt. Die neuen Scans bekommen Schräglage, Rauschen, Unschärfe und zufällige Vierteldrehungen. Die Schwellen wurden nur an den Seeds 1 bis 3 eingestellt. Nachstellen mit `python scripts/benchmark.py --seeds 101-110`.

| Seitenart | Neue Scans | Sicher | Prüfen | Kein Treffer | Sicher, aber falsch | Richtige Antwort gelistet |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Text | 43 | 42 | 1 | 0 | 0 | 43 |
| Abbildung | 3 | 3 | 0 | 0 | 0 | 3 |
| Wiederholtes Formular | 24 | 0 | 24 | 0 | 0 | 24 |
| Leere Seite | 10 | 0 | 9 | 1 | 0 | 9 |
| Nicht im Heft | 10 | 0 | 0 | 10 | 0 | 10 |
| **Alle** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

Von 45 Sicher-Treffern war keiner falsch. Bei nur 45 Versuchen kann die echte Fehlerrate trotzdem bis zu etwa 6,7 % betragen (Dreierregel, 95 % Konfidenz). Der erste Vorschlag stimmte bei 95,6 % der Scans (oder war zu Recht Kein Treffer).

Lesen Sie diese Zahlen als Obergrenze. Original und neuer Scan stammen aus derselben sauberen Bitmap und passen deshalb besser zusammen als ein echter Flachbettscan einer abgenutzten Seite. Bei echten Dokumenten sind mehr Prüfen und Kein Treffer zu erwarten. Außerdem sind alle 45 Sicher-Treffer Text- und Bildseiten mit unterschiedlichem Inhalt, und Formulare und leere Seiten sind über alle Seeds hinweg dieselben festen Seiten.

Handyfotos liegen selten parallel zur Seite. Mit `--tilt 0.04` wird jeder neue Scan derselben zehn Seeds so verzerrt, als wäre er schräg fotografiert worden, jede Ecke um bis zu 4 % der Seite verschoben. Version 0.4.0 liefert 46 Sicher ohne einen Fehler, und der erste Vorschlag stimmt (oder ist korrekt Kein Treffer) bei 77 von 90. Version 0.3.0 kam auf 31 Sicher und 46 von 90, weil sie nur flache Scans modellierte. Leere Seiten werden bei Schräglage zu Kein Treffer, weil die Tischkante wie Tinte wirkt: Ordnen Sie sie von Hand zu. Der Lauf liegt in `docs/benchmark-tilted.json`.

## Installation

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 oder neuer. Noch nicht auf PyPI. Die volle Testsuite läuft unter Linux. Die Tests für CLI, Export und Bildverarbeitung laufen in CI auch unter macOS und Windows, der Matcher wurde aber nur unter Linux geprüft.

## Grenzen

- Verweigert verschlüsselte PDFs, digital signierte PDFs, PDFs mit Formularfeldern und Seiten, deren `Rotate` kein Vielfaches von 90 ist.
- Bis zu 200 Seiten im Original, 40 neue Scans, 400 MB für das Original und 60 MB je Scan.
- Seiten mit Anmerkungen werden nicht ersetzt, solange Sie nicht erlauben, die Anmerkungen zu verwerfen.
- Zwei fast identische Seiten lassen sich allein am Bild nicht unterscheiden, sie werden deshalb Prüfen, wenn der zweite Kandidat nah dran ist. Eine leere Seite liefert keinen Beleg und ist immer Prüfen.
- Die Oberfläche ist in neun Sprachen übersetzt, auch die Begründung unter jeder Zuordnung. Die Ausgabe von `darnleaf match` ist englisch. HEIC-Fotos vom iPhone brauchen `pip install "darnleaf[heic]"`.

Mehr dazu in der englischen Dokumentation: [docs/usage.md](docs/usage.md) und [docs/how-it-works.md](docs/how-it-works.md). Zum Mitmachen siehe [CONTRIBUTING.md](CONTRIBUTING.md). MIT-Lizenz, siehe [LICENSE](LICENSE).

Assisted by Claude/Codex.
