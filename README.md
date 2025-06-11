# `cer-tool`
Erleichterung der Korrektur von theoretischen und Programmier-Übungen in "Computational Engineering und Robotik" / "Scientific Computing", TU Darmstadt.

<!-- TOC -->
* [Voraussetzungen](#voraussetzungen)
* [Installation](#installation)
  * [Optional: Shell-Wrapper](#optional-shell-wrapper)
* [Vorbereitung](#vorbereitung)
* [Schriftliche Übungen bewerten](#schriftliche-übungen-bewerten)
  * [Bewertung vorbereiten](#bewertung-vorbereiten)
  * [Text-Feedback hinzufügen](#text-feedback-hinzufügen)
  * [Bewertung abschließen](#bewertung-abschließen)
* [Programmierübungen bewerten](#programmierübungen-bewerten)
<!-- TOC -->

## Voraussetzungen

- Windows, Linux oder MacOS
  - Linux: `xdg-utils` sollte installiert sein
- Python, getestet mit Python 3.12 und Python 3.13
- Docker (zur Korrektur der Programmierübungen)
- Moodle-Sprache muss Deutsch sein


## Installation

1. Ein [Python-venv](https://docs.python.org/3/library/venv.html) installieren und aktivieren

2. Das Repository klonen
   ```shell
   git clone https://github.com/TypingTobii/cer-tool.git
   ```

3. Das Tool mittels `pip` installieren
   ```shell
   pip install ./cer-tool
   ```

   
### Optional: Shell-Wrapper

Damit `cer-tool` auch aufgerufen werden kann, wenn das venv gerade nicht aktiv ist, kann das Skript `cer-tool.ps1` (Windows) bzw. `cer-tool.sh` (Linux/MacOS) sowie `cer-tool.paths` in einen Ordner kopiert oder symlinked werden, der sich in der PATH-Umgebungsvariable befindet.

In `cer-tool.paths` hinter `ENV=` muss dann der Pfad zum venv angegeben werden.


## Vorbereitung

Bevor das Tool nutzbar ist, müssen die Initialen gesetzt werden, die automatisch unter jeder Bewertung angefügt werden. Hierzu
```shell
cer-tool config edit
```
ausführen, `initials` eingeben, danach die gewünschten Initialen, z.B. `"MM"` eingeben und zweimal ENTER drücken.


## Schriftliche Übungen bewerten

Zur Bewertung von schriftlichen Übungen werden die folgenden Dateien benötigt:
- Die Abgaben der Studis `<submissions>`, die z.B. von Moodle über "Einreichungen" → "Aktionen" → "Alle Abgaben herunterladen" heruntergeladen werden können
- Die Bewertungstabelle zur Übung `<table>`, von Moodle über "Einreichungen" → "Aktionen" → "Bewertungstabelle herunterladen" herunterzuladen 
- Die Zuteilung der Übungen `<groups>`, also "tut_??.txt"


### Bewertung vorbereiten

Mit
```shell
cer-tool prepare -g <groups> -s <submissions>
```
werden die Abgaben der Studis durchsucht und alle zu bewertenden Abgaben in einen neu erstellten Ordner "submissions" extrahiert.

Die Abgaben können dann mit einem beliebigen PDF-Annotator oder einer beliebigen PDF-Notizen-App korrigiert werden.

Nach der Korrektur sollte die erreichte Punktzahl im Dateinamen eingetragen, also bspw. "Submission_Gr2b_Max Mustermann_133742_File 1_ --- pts.pdf" in "Submission_Gr2b_Max Mustermann_133742_File 1_ 9,5 pts.pdf" umbenannt werden. 


### Text-Feedback hinzufügen

Während der Bewertung kann Text-Feedback hinzugefügt werden, das auf Moodle später im Feld "Feedback als Kommentar" erscheint:
```shell
cer-tool edit-feedback -t <table> <name>
```
`<name>` durch einen Teil des Vor- oder Nachnamens des Studis ersetzen. Das Tool sucht dann den richtigen Eintrag in der Bewertungstabelle.


### Bewertung abschließen

Zum Abschluss
```shell
cer-tool finish -g <groups> -t <table> -sn <submission-name>
```
aufrufen, wobei `<submission-name>` die Bezeichnung der Übung, z.B. "H03", ist (diese erscheint dann für die Studis im Dateinamen der Feedbackdatei). Die annotierten Lösungen werden standardmäßig im Ordner "submissions" gesucht und die Punktzahlen aus den Dateinamen gelesen.

Das Tool erzeugt nun eine "\_out\_....csv"-Datei und eine oder mehrere zip-Dateien:

Die zip-Dateien enthalten die annotierten Feedbackdateien, die in Moodle über "Einreichungen" → "Aktionen" → "Feedbackdateien als ZIP-Datei hochladen" hochgeladen werden können. Aufgrund der maximalen Dateigröße von aktuell 25 MB müssen mehrere Dateien einzeln hintereinander hochgeladen werden.  
Die csv-Datei enthält Punktzahlen und Textfeedback, an das automatisch die Initialen angehangen wurden. Die Datei kann über "Einreichungen" → "Aktionen" → "Bewertungstabelle hochladen" hochgeladen werden. Möglicherweise ist es notwendig, die Option "Update von Datensätzen zulassen, die seit dem letzten Upload angepasst wurden" zu wählen, da sonst keine Änderungen erkannt werden. Die vom Tool ausgegebene Bewertungstabelle enthält nur die zugewiesenen Gruppen, es werden also keine anderen Bewertungen überschrieben.


## Programmierübungen bewerten

Zur Bewertung von Programmierübungen werden die folgenden Dateien benötigt:
- Die Abgaben der Studis `<submissions>`, die z.B. von Moodle über "Einreichungen" → "Aktionen" → "Alle Abgaben herunterladen" heruntergeladen werden können
- Die Bewertungstabelle zur Übung `<table>`, von Moodle über "Einreichungen" → "Aktionen" → "Bewertungstabelle herunterladen" herunterzuladen 
- Die Zuteilung der Übungen `<groups>`, also "tut_??.txt"
- Die automatischen Tests `<package>`, also "sc_pex?_grading.zip"

Die Bewertung kann mit
```shell
cer-tool grade-pex -p <package> -g <groups> -s <submissions> -t <table>
```
gestartet werden. Das Tool erstellt zuerst den Docker-Container und geht dann die Abgaben der Studis interaktiv durch. Über "e" kann die Bewertung manuell angepasst werden, "osub" bzw. "osol" öffnen die Studi-Abgabe bzw. die Musterlösung mit dem Standard-Programm für ipynb-Dateien und "r" führt die automatischen Tests erneut aus (dies ist beispielsweise hilfreich, wenn die Studi-Abgabe überschüssige Zellen enthält und die automatischen Tests daher fehlschlagen).

Die Bewertungstabelle `<table>` wird automatisch ausgefüllt und standardmäßig überschrieben. Die Datei kann [genau wie bei den schriftlichen Übungen](#bewertung-abschließen) in Moodle hochgeladen werden.