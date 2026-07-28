# Fractal Flight Studio

Plattformübergreifender Fraktal-Explorer in Python. Die Desktop-GUI läuft mit
Tkinter, die Pixelberechnung wird durch Numba kompiliert. Auf NVIDIA-Systemen
kann optional CUDA genutzt werden; auf allen anderen Systemen steht ein
parallelisierter CPU-Renderer zur Verfügung.

## Funktionsumfang

- Mandelbrot-, Julia-, Burning-Ship-, Multibrot- und Newton-Fraktale
- geglättete Escape-Time-Farbgebung, fünf Paletten und automatisches Tone Mapping
- Maus-Zoom am Cursor, Verschieben durch Ziehen und frei wählbares Flugziel
- kontinuierlicher Zoomflug mit separat einstellbarer Render-Skalierung
- echte getrennte `float32`- und `float64`-Kernels
- Deep-Zoom-Modus für Mandelbrot mit stabilem hochpräzisem Referenzorbit, echtem Rebasing und Glitch-Reparatur
- automatische Backend-Auswahl: CUDA, falls verfügbar, sonst Numba-CPU
- sichtbare GPU-Diagnose mit Gerät, Treiber, Compute Capability und Fehlergrund
- PNG-Export sowie direkter H.264/H.265-MP4-Export über FFmpeg
- visueller Flugplan-Editor mit exakten Keyframes, Preflight und abbrechbarem Hintergrundexport
- CLI für Einzelbilder und logarithmische Frame-Sequenzen
- persistente CUDA-Puffer und GPU-Farbgebung; adaptives Tone Mapping benötigt nur eine kleine Bildstichprobe plus RGB-Rückübertragung
- Unit-, Integrations-, CLI- und CUDA-Simulator-Tests

## Voraussetzungen

- Python 3.11 bis 3.13
- NumPy
- Numba
- Pillow
- mpmath
- Tkinter (bei den üblichen Windows- und macOS-Python-Installationen enthalten;
  unter Debian/Ubuntu gegebenenfalls `python3-tk` installieren)
- für MP4-Export: eine FFmpeg-Installation, die über `PATH` oder einen expliziten Programmpfad erreichbar ist
- für echte CUDA-Beschleunigung: aktueller NVIDIA-Treiber und die optionale
  Abhängigkeit `numba-cuda[cu12]`; das Windows-Startskript installiert sie
  automatisch, sobald `nvidia-smi` eine NVIDIA-GPU meldet

## Installation

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
fractal-studio
```

Alternativ übernimmt `scripts\run_windows.ps1` die Interpretererkennung, richtet die virtuelle Umgebung ein und startet die Anwendung. Das Skript akzeptiert Python 3.11 bis 3.13 und ignoriert den funktionslosen Microsoft-Store-Platzhalter unter `WindowsApps`. Wird über `nvidia-smi` eine NVIDIA-GPU erkannt, installiert es automatisch die CUDA-12-Abhängigkeiten. Die erste CUDA-Installation ist deutlich größer als die CPU-Installation. Mit `FRACTAL_SKIP_CUDA=1` kann sie unterdrückt werden.

Eine bereits vorhandene Umgebung kann gezielt für NVIDIA CUDA erweitert werden:

```powershell
.\scripts\enable_cuda.ps1
```

Manuell entspricht das:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[cuda12]"
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
fractal-studio
```

## Deep Zoom

Ab Version 0.6.0 unterstützt die App für das Mandelbrot-Fraktal einen
stabilisierten Perturbationsmodus. Ein geeigneter hochpräziser Referenzorbit
wird auf der CPU erzeugt und über zusammenhängende Pan-/Zoom-Frames hinweg
wiederverwendet. Die Pixelabweichungen werden weiterhin auf CPU oder CUDA in
`float64` ausgewertet. Dadurch lassen sich deutlich tiefere Zooms als mit
direkter FP64-Berechnung erreichen, ohne dass schon kleinste Verschiebungen
einen vollständig neuen numerischen Fehlerteppich erzeugen.

In der GUI stehen dazu zwei neue Einstellungen bereit:

- **Berechnungsmodus**: `auto`, `direct` oder `perturbation`
- **Referenzpräzision (Bits)**: 128 bis 1024

`auto` schaltet bei sehr kleinen Pixelabständen selbstständig auf
Perturbationsrechnung um. Für sehr tiefe Zooms ist `perturbation` die robustere
Wahl. Die Referenz wird innerhalb eines großzügigen Pan-/Zoom-Bereichs nicht
neu verankert. Echtes Rebasing ändert nur die Zerlegung
`z = Referenzorbit + Abweichung`; die hochpräzise Pixelkoordinate wird dabei
niemals in ein absolutes FP64-`c` zurückverwandelt. Ein
Pauldelbrot-artiges Kriterium erkennt katastrophale Auslöschung und repariert
die Darstellung durch Rebasing auf `Z₀ = 0`. In der Statuszeile ist außerdem
sichtbar, ob die Referenz wiederverwendet oder neu aufgebaut wurde.

### Pan-Stabilität prüfen

Die überlappenden Bereiche zweier um eine ganzzahlige Pixelzahl verschobener
Frames lassen sich reproduzierbar vergleichen:

```powershell
.\.venv\Scripts\python.exe scripts\check_pan_stability.py --backend cuda
```

Erwartet werden `reference reused: True`, keine Klassifikationsfehler und
`result: STABLE`.

## Automatische Präzisionsleiter und Fluggrenze

Im Berechnungsmodus **`auto`** ist `float32` die schnelle Startpräzision. Bevor
die Pixelkoordinaten in diesem Format sichtbar quantisieren, wird der direkte
Renderer automatisch auf `float64` angehoben. Sobald auch direkte FP64-
Koordinaten nicht mehr genügend Abstand zwischen benachbarten Pixeln liefern,
wechselt Mandelbrot automatisch in den Perturbationsmodus. Die Statuszeile
zeigt Übergänge beispielsweise als `float32→float64` an. **`direct`** bleibt
absichtlich strikt und führt keine automatische Hochstufung durch.

Ein Flug stoppt jetzt automatisch vor der numerischen Grenze. Die Endbreite
wird aus der eingestellten Referenzpräzision, der Renderbreite und der weiterhin
in `float64` ausgewerteten Pixel-Perturbation berechnet. Dadurch werden keine
Frames mehr erzeugt, bei denen mehrere Pixel dieselbe Koordinate erhalten oder
die Perturbationsabstände unterlaufen. Höhere **Referenzpräzision (Bits)**
verschiebt diese Grenze weiter nach innen, kann aber die FP64-Grenze der
Pixelabweichungen nicht aufheben.

## Automatisches Tone Mapping

Ab Version 0.7.0 nutzt die App standardmäßig ein automatisches Tone Mapping,
damit feine Strukturen auch dann sichtbar bleiben, wenn die geglätteten
Escape-Werte innerhalb des aktuellen Ausschnitts nur einen kleinen Teil des
verfügbaren Wertebereichs belegen.

Der Modus **`auto`** kombiniert:

- eine gleichmäßig über das Bild verteilte Stichprobe von höchstens 4096 Pixeln
- robuste Schwarz-/Weißpunkt-Schätzung über Perzentile
- `asinh`-Kompression für helle Bereiche
- eine automatisch aus der Werteverteilung abgeleitete Gamma-Anpassung
- starke zeitliche Glättung während Flügen und moderate Glättung bei normaler Navigation
- schnellere Anpassung nur bei deutlich erkennbaren Szenensprüngen

Dadurch bleibt die Darstellung beim Verschieben und Fliegen wesentlich ruhiger
als bei einer pro Frame neu berechneten Histogramm-Equalisierung. Die
Automatik ist für Mandelbrot, Julia, Burning Ship und Multibrot voreingestellt.
Beim Newton-Fraktal bleibt `auto` intern linear, damit die drei kodierten
Wurzelbereiche nicht verfälscht werden. **`asinh`** verwendet dieselbe robuste
Fensterung, aber ohne die zusätzliche automatische Gamma-Korrektur. Mit
**`linear`** steht weiterhin die unveränderte Rohdarstellung zur Verfügung.

Die GUI verwendet `auto` ohne zusätzliche Konfiguration. Über die CLI und die
Python-API stehen außerdem `linear` für die unveränderte Rohdarstellung und
`asinh` für robuste Fensterung ohne automatische Gamma-Korrektur bereit.

Für MP4-Exporte ergänzt die GUI eine zweite Ebene: **Zeitlich stabilisiert** analysiert
die automatische Tonkurve zunächst in kleiner Auflösung über die gesamte exakte
Videokadenz. Ein deterministischer Vorwärts-/Rückwärts-Filter reduziert Sprünge,
ohne dass die Belichtung einem Szenenwechsel nur verzögert hinterherläuft. Der
finale Render verwendet die geplanten Parameter unverändert; dadurch bleiben
Helligkeit, Kontrast und Farbverteilung zwischen benachbarten Frames ruhiger.

## Bedienung

- Mausrad: hinein- und herauszoomen
- linke Maustaste ziehen: Ansicht verschieben
- rechte Maustaste: Flugziel setzen
- „Flug starten“: kontinuierlich zum Ziel zoomen; stoppt automatisch an der numerischen Präzisionsgrenze
- „PNG exportieren“: Bild in aktueller Fensterauflösung speichern
- „Flugplan …“: aktuelle Ansichten und Katalogziele als exakte X/Y/Zoom-Keyframes anlegen, pro Segment `focus` oder `linear` wählen und Zwischenpositionen prüfen
- „Flugplan-Wiedergabe“: den vollständigen Plan abspielen, pausieren, stoppen, per Zeitleiste durchsuchen, zwischen Keyframes springen oder mit 0,5×/1×/2× wiedergeben
- „Video exportieren …“: Auflösung und Framerate planen, FFmpeg prüfen, einen Low-Resolution-Preflight ausführen und anschließend direkt als MP4 rendern

Die Echtzeitwiedergabe verwendet dieselbe zeitabhängige Kamera-, Qualitäts- und Palettenauswertung wie Preflight und MP4-Export. Der Playhead folgt einer monotonen Echtzeituhr. Ist das Rendering langsamer als die Timeline, werden veraltete Zwischenpositionen nicht nachgeholt; nach dem fertigen Frame wird direkt die aktuellste Position gerendert.

Für normale Vorschau und Flug kann die Render-Skalierung getrennt auf 50 %, 75 % oder 100 % gesetzt werden. Auf CUDA-Systemen ist 100 % voreingestellt; auf CPU-Systemen 75 %. Die Statuszeile trennt Rechnen/Transfer von der Tk-Anzeige.

### MP4-Workflow

1. Im **Flugplan** mindestens zwei Keyframes anlegen; der erste muss bei 0 Sekunden liegen. Für starke Zooms ist der voreingestellte Mittelpunktmodus **`focus`** gedacht: Er richtet die Kamera früh auf das nächste Ziel aus und verhindert, dass in Zwischenpunkte hineingezoomt wird. **`linear`** eignet sich für bewusst geradlinige X/Y-Fahrten.
2. Im Dialog **Video exportieren** Auflösung, konstante Framerate, Codec, CRF, Zieldatei und den Tone-Mapping-Modus wählen. **Zeitlich stabilisiert** ist für Videos voreingestellt; **Automatisch pro Frame** erhält das frühere Verhalten für Vergleiche.
3. FFmpeg prüfen und den Preflight starten. Der Preflight rendert kleine Stichproben entlang des exakten Pfads und meldet numerische, visuelle oder Backend-Fehler.
4. Nach einem erfolgreichen Preflight den MP4-Export starten. Im stabilisierten Modus analysiert ein kleiner Vorlauf zuerst jeden exakten Videozeitpunkt, glättet die ermittelten Tonkurven vorwärts und rückwärts und verwendet diese Parameter anschließend fest für den Full-Resolution-Render. Danach werden die RGB-Frames direkt an FFmpeg gestreamt; eine PNG-Zwischensequenz ist nicht erforderlich.

Preflight, Tone-Mapping-Analyse und Export laufen außerhalb des Tk-Hauptthreads. Der Fortschritt unterscheidet Analyse und finalen Render; ein Abbruch wirkt in beiden Phasen. Änderungen an Pfad, Tone-Mapping-Modus oder relevanten Rendereinstellungen verlangen einen neuen Preflight. Die zeitliche Glättung ist deterministisch und verwendet keinen Zustand aus der interaktiven Vorschau.

## CLI

Einzelbild:

```bash
fractal-render render \
  --fractal mandelbrot \
  --center-x -0.743643887037151 \
  --center-y 0.131825904205330 \
  --view-width 0.002 \
  --iterations 1200 \
  --width 1920 --height 1080 \
  --backend auto \
  --palette electric \
  --tone-mapping auto \
  --output deep-zoom.png
```

Julia-Menge:

```bash
fractal-render render --fractal julia --julia-real -0.8 --julia-imag 0.156 \
  --width 1280 --height 720 --output julia.png
```

Frame-Sequenz für einen Zoomflug:

```bash
fractal-render flight \
  --target-x -0.743643887037151 \
  --target-y 0.131825904205330 \
  --target-width 0.00002 \
  --frames 180 --output-dir rendered_frames
```

Die PNG-Sequenz kann anschließend beispielsweise mit FFmpeg kodiert werden:

```bash
ffmpeg -framerate 30 -i rendered_frames/frame_%05d.png \
  -c:v libx264 -pix_fmt yuv420p fractal-flight.mp4
```

## GPU-Diagnose

```powershell
.\.venv\Scripts\python.exe -m fractal_flight_studio.doctor
```

Oder nach Installation des Kommandozeileneinstiegs:

```powershell
fractal-doctor
```

Bei erfolgreicher Erkennung nennt die Ausgabe die NVIDIA-GPU und CUDA ist in der App als `cuda-numba` sichtbar. Die Schaltfläche **GPU-Diagnose** zeigt dieselben Daten. Im Modus `auto` wird CUDA bevorzugt; ein CPU-Fallback wird mit Fehlergrund im Status angezeigt.

## Benchmark

CPU und CUDA im tatsächlichen Frame-Pfad vergleichen:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py --backend all --repeats 5
```

Der Benchmark misst Fraktalberechnung, Farbgebung und die für Tkinter notwendige Rückübertragung, aber nicht die eigentliche Tk-Anzeige. Er verwirft JIT- und Puffer-Warm-up und meldet Medianwerte. Das JSON-Ergebnis eignet sich für reproduzierbare Vergleiche.

GPU-Auslastung parallel beobachten:

```powershell
.\scripts\monitor_gpu.ps1
```

Bei einer kleinen Renderfläche oder vielen schnell divergierenden Pixeln kann eine RTX 3060 trotz hoher Frameleistung nur wenige Prozent mittlere Auslastung zeigen: Der Kernel läuft dann kurz und wartet anschließend auf Python/Tkinter. Maßgeblich sind daher zusätzlich die Millisekunden in der App-Statuszeile und die Benchmarkwerte.

## Tests

```bash
python -m pytest
```

Der CUDA-Test nutzt den Numba-CUDA-Simulator und benötigt keine physische GPU.
Ein echter Leistungs- und Treibertest muss trotzdem auf Zielhardware erfolgen.

## Windows-Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Das Skript installiert PyInstaller in der lokalen virtuellen Umgebung. Ein
Windows-Build muss unter Windows erzeugt werden; PyInstaller ist kein
Cross-Compiler.

## Architektur

```text
GUI / CLI
   ↓
RenderRequest + Viewport
   ↓
Backend-Auswahl (wiederverwendete Instanzen)
   ├── Numba-CPU → automatische Präzision → Stichprobe → Tone Mapping → CPU-Farbgebung
   └── Numba-CUDA → automatische Präzision → persistente Puffer → kleine GPU-Stichprobe → GPU-Farbgebung
   ↓
RGB-Frame
   ↓
PNG / Tkinter-Anzeige
```

Die numerische `render()`-Schnittstelle bleibt für Tests und Analysen erhalten. Für die interaktive Anzeige nutzt `render_frame()` einen optimierten Backendpfad. CUDA lässt Iterationswerte und Innenmaske auch beim automatischen Tone Mapping auf der GPU. Nur eine gleichmäßig verteilte Stichprobe von höchstens 4096 Werten wird für die robuste Parameterbestimmung zum Host übertragen; anschließend erfolgen Tone-Kurve, Palette und Farbzyklen auf der GPU und nur das fertige RGB-Bild wird zurückkopiert.

## Aktuelle Grenzen

- Das CUDA-Ergebnis wird für die Tkinter-Anzeige in den Hauptspeicher kopiert.
  Für maximale 4K-Frameraten wäre später ein GPU-natives Präsentationsbackend
  wie WebGPU/wgpu oder Qt-RHI sinnvoll.
- Generische GPU-Beschleunigung für AMD, Intel und Apple ist noch
  nicht implementiert. Auf diesen Systemen arbeitet der Numba-CPU-Renderer.
- Der Referenzorbit und die hochpräzisen Viewport-Koordinaten werden auf der CPU erzeugt, die Pixelabweichungen selbst aber weiterhin in `float64` ausgewertet. Die App stoppt Flüge deshalb vor der aus Referenzbits und FP64-Perturbation abgeleiteten Grenze. Für noch tiefere Zooms wären skalierte Perturbation, Multi-Reference-Verfahren oder Series Approximation erforderlich.
- 3D-Fraktale wie Mandelbulb sind noch nicht enthalten.

Diese Grenzen sind bewusst: Das Repo liefert einen vollständig testbaren,
überschaubaren MVP und eine saubere Basis für WebGPU, skalierte Perturbation und 3D.
