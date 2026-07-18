"""
Práctica oral de inglés - Interfaz estilo Jarvis/Siri con voces reales
=========================================================================

Dos modos:

1) "Grabar voces de los personajes": recorres las 33 líneas del diálogo
   (tanto de Juan como de Julián) y grabas cada una con tu voz o la de un
   amigo. Se guardan como archivos .wav en la carpeta "voces/".

2) "Practicar diálogo": eliges si eres Juan o Julián. Cuando le toca al
   OTRO personaje, el programa reproduce la grabación real que guardaste
   (si existe). Si no grabaste esa línea, usa una voz robótica de
   respaldo (TTS) para no interrumpir la práctica.

Cuando te toca a ti, grabas tu línea, puedes escucharla, y luego la
aceptas para que el programa la transcriba y compare con la línea
correcta.

INSTALACIÓN (una sola vez):
------------------------------------------------------------------------
pip install SpeechRecognition pyttsx3 sounddevice numpy

(tkinter y wave ya vienen incluidos con Python)

EJECUCIÓN:
------------------------------------------------------------------------
python practica.py
"""

import sys
import os
import re
import math
import wave
import threading
import difflib

try:
    import tkinter as tk
except ImportError:
    print("tkinter no está disponible. Reinstala Python marcando la opción 'tcl/tk' en el instalador.")
    sys.exit(1)

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    print("Falta instalar 'sounddevice' y 'numpy'. Corre: pip install sounddevice numpy")
    sys.exit(1)

try:
    import speech_recognition as sr
except ImportError:
    print("Falta instalar 'SpeechRecognition'. Corre: pip install SpeechRecognition")
    sys.exit(1)

try:
    import pyttsx3
except ImportError:
    print("Falta instalar 'pyttsx3'. Corre: pip install pyttsx3")
    sys.exit(1)


SAMPLE_RATE = 16000
VOICES_DIR = "voces"

# -----------------------------------------------------------------------
# 1. EL DIÁLOGO
# -----------------------------------------------------------------------
DIALOGUE = [
    ("Julian", "Hey, Juan! How's it going?"),
    ("Juan", "Hey, Julian! I'm doing great. How about you?"),
    ("Julian", "I'm good, thanks! I have a question. What do you usually do in the morning?"),
    ("Juan", "Well, I usually wake up at six, take a shower, have breakfast, and then I go to the university."),
    ("Julian", "Nice! Do you work or do you only study?"),
    ("Juan", "I only study at TEC right now. What about you?"),
    ("Julian", "Same here. I study at TEC too."),
    ("Julian", "By the way, what do you like doing in your free time?"),
    ("Juan", "I like playing soccer, going to the beach, and hanging out with my friends. And you?"),
    ("Julian", "I like playing video games, listening to music, and watching movies."),
    ("Juan", "That's cool! Is there anything you don't like doing?"),
    ("Julian", "Yeah, I don't like waking up early. What about you?"),
    ("Juan", "I don't like washing the dishes. It's so boring."),
    ("Julian", "Haha, I know! What are your hobbies?"),
    ("Juan", "My hobbies are playing pool, gaming, and spending time with my friends."),
    ("Julian", "Nice! How often do you exercise?"),
    ("Juan", "I usually exercise three times a week. Sometimes I play soccer on weekends."),
    ("Juan", "Now let me ask you something. What days do you study?"),
    ("Julian", "I study from Monday to Friday."),
    ("Juan", "What do you usually do in the evening?"),
    ("Julian", "I usually do my homework, watch YouTube, and sometimes play video games."),
    ("Juan", "Cool. Who do you live with?"),
    ("Julian", "I live with my parents and my brother."),
    ("Juan", "Nice. What do you like doing with other people?"),
    ("Julian", "I like going to the beach, and going out with my friends."),
    ("Juan", "Sounds fun! What do you usually do on weekends?"),
    ("Julian", "I usually relax and spend time with my family."),
    ("Juan", "Great! And what outdoor activities do you do in your free time?"),
    ("Julian", "I like walking, riding my bike, and going to the beach."),
    ("Juan", "That's awesome. It was nice talking to you."),
    ("Julian", "Yeah, it was! See you at the university."),
    ("Juan", "See you! Have a good day."),
    ("Julian", "You too. Bye!"),
]


def voice_path(index, speaker):
    return os.path.join(VOICES_DIR, f"{index:02d}_{speaker}.wav")


def guardar_wav(path, audio_int16, samplerate):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(audio_int16.tobytes())


def cargar_wav(path):
    with wave.open(path, "rb") as wf:
        n = wf.getnframes()
        sr_file = wf.getframerate()
        data = wf.readframes(n)
        audio = np.frombuffer(data, dtype=np.int16)
    return audio, sr_file


# -----------------------------------------------------------------------
# 2. COMPARAR texto dicho vs esperado
# -----------------------------------------------------------------------
# Cualquier caracter que NO sea letra, número o espacio se considera
# puntuación y se elimina antes de comparar (comas, puntos, signos de
# interrogación/exclamación, apóstrofes, guiones, etc). Así el usuario
# nunca es penalizado por no "pronunciar" un signo de puntuación.
_APOSTROFE_RE = re.compile(r"['’]")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def limpiar_texto(texto):
    """Quita toda la puntuación y normaliza espacios/mayúsculas,
    dejando solo las palabras para poder compararlas de forma justa.

    Los apóstrofes se eliminan SIN dejar espacio (how's -> hows, don't -> dont)
    para que las contracciones no se partan en dos palabras. El resto de
    signos (comas, puntos, ?, !, etc.) se reemplazan por espacio."""
    texto = _APOSTROFE_RE.sub("", texto.lower())
    sin_puntuacion = _PUNCT_RE.sub(" ", texto)
    return " ".join(sin_puntuacion.split())


def comparar_texto(esperado, dicho):
    esperado_norm = limpiar_texto(esperado)
    dicho_norm = limpiar_texto(dicho)

    ratio = difflib.SequenceMatcher(None, esperado_norm, dicho_norm).ratio()

    if ratio >= 0.85:
        return True, ratio, None

    palabras_esperadas = esperado_norm.split()
    palabras_dichas = dicho_norm.split()
    diff = list(difflib.ndiff(palabras_esperadas, palabras_dichas))

    faltaron = [w[2:] for w in diff if w.startswith("- ")]
    sobraron = [w[2:] for w in diff if w.startswith("+ ")]

    detalle = ""
    if faltaron:
        detalle += f"Te faltaron o cambiaste: {', '.join(faltaron)}\n"
    if sobraron:
        detalle += f"Dijiste de más/diferente: {', '.join(sobraron)}"

    return False, ratio, detalle.strip()


# -----------------------------------------------------------------------
# 3. MOTOR DE VOZ - grabar, reproducir archivo, reproducir grabación,
#    transcribir, y TTS de respaldo.
# -----------------------------------------------------------------------
class VoiceEngine:
    def __init__(self):
        self.recording = False
        self.frames = []
        self.stream = None
        self.last_recording = None  # numpy int16 array
        self.current_level = 0.0    # nivel de volumen en vivo (0..1), para animar el HUD

    def speak(self, text, on_done=None):
        def run():
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            if on_done:
                on_done()

        threading.Thread(target=run, daemon=True).start()

    def play_file_or_speak(self, filepath, text, on_done=None):
        if filepath and os.path.exists(filepath):
            def run():
                audio, sr_file = cargar_wav(filepath)
                sd.play(audio, sr_file)
                sd.wait()
                if on_done:
                    on_done()

            threading.Thread(target=run, daemon=True).start()
        else:
            self.speak(text, on_done=on_done)

    def start_recording(self):
        self.frames = []
        self.recording = True
        self.current_level = 0.0

        def callback(indata, frames, time_info, status):
            if self.recording:
                self.frames.append(indata.copy())
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                # escala aproximada para audio int16 de micrófono normal
                self.current_level = max(0.0, min(1.0, rms / 3500.0))

        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback)
        self.stream.start()

    def stop_recording(self):
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.current_level = 0.0
        self.last_recording = np.concatenate(self.frames, axis=0) if self.frames else None
        return self.last_recording

    def load_existing(self, filepath):
        if os.path.exists(filepath):
            audio, _ = cargar_wav(filepath)
            self.last_recording = audio.reshape(-1, 1)
            return True
        return False

    def play_last_recording(self, on_done=None):
        if self.last_recording is None:
            if on_done:
                on_done()
            return

        def run():
            sd.play(self.last_recording, SAMPLE_RATE)
            sd.wait()
            if on_done:
                on_done()

        threading.Thread(target=run, daemon=True).start()

    def save_last_recording(self, filepath):
        if self.last_recording is not None:
            guardar_wav(filepath, self.last_recording, SAMPLE_RATE)

    def transcribe_last_recording(self):
        if self.last_recording is None:
            return None
        recognizer = sr.Recognizer()
        audio_data = sr.AudioData(self.last_recording.tobytes(), SAMPLE_RATE, 2)
        try:
            return recognizer.recognize_google(audio_data, language="en-US")
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None


# -----------------------------------------------------------------------
# 4. INTERFAZ GRÁFICA — tema HUD estilo Jarvis
# -----------------------------------------------------------------------
BG = "#050a12"
PANEL = "#0d1626"
ACCENT = "#2dd4ff"
ACCENT_SOFT = "#123246"
FG = "#d7f6ff"
MUTED = "#5c7a90"
WARN = "#f87171"
OK = "#4ade80"

FONT_TITLE = ("Consolas", 21, "bold")
FONT_SUB = ("Consolas", 10, "bold")
FONT_HUD = ("Consolas", 11, "bold")
FONT_BODY = ("Segoe UI", 14)
FONT_SMALL = ("Consolas", 9, "bold")


def spaced(text):
    """Texto en mayúsculas con espaciado entre letras, look HUD."""
    return " ".join(text.upper())


class JarvisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("J.A.R.V.I.S. — Práctica oral")
        self.geometry("620x750")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.voice = VoiceEngine()

        # estado de práctica
        self.dialogue_index = 0
        self.mi_personaje = None
        self.otro_personaje = None
        self.correctas = 0
        self.total_mias = 0
        self.subtitles_on = True
        self.current_hablante = None
        self.current_texto = None

        # estado del grabador de voces
        self.rec_index = 0

        self.anim_phase = 0.0
        self.anim_state = "idle"  # idle | speaking | listening
        self.anim_cx = 310
        self.anim_cy = 140
        self.canvas = None
        self.continue_btn = None
        self.status_dot_label = None

        self._build_main_menu()

    # ---------------- utilidades visuales compartidas ----------------
    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.status_dot_label = None

    def _hud_button(self, parent, text, command, width=28, accent=None, height=2):
        accent = accent or ACCENT
        label = text.upper()
        width = max(width, len(label) + 3)
        btn = tk.Button(
            parent, text=label, command=command,
            font=FONT_HUD, fg=accent, bg=PANEL,
            activebackground=ACCENT_SOFT, activeforeground=accent,
            bd=0, highlightthickness=1, highlightbackground=accent, highlightcolor=accent,
            relief="flat", width=width, height=height, cursor="hand2",
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_SOFT))
        btn.bind("<Leave>", lambda e: btn.config(bg=PANEL))
        return btn

    def _hud_separator(self, parent, width=480):
        tk.Frame(parent, bg=ACCENT_SOFT, height=1, width=width).pack(pady=(6, 18))

    def _hud_header(self, parent, title, subtitle=None, online=True):
        tk.Label(parent, text=spaced(title), font=FONT_TITLE, fg=ACCENT, bg=BG).pack(pady=(46, 4))
        if subtitle:
            tk.Label(parent, text=subtitle, font=("Segoe UI", 10), fg=MUTED, bg=BG).pack(pady=(0, 4))
        row = tk.Frame(parent, bg=BG)
        row.pack(pady=(2, 6))
        self.status_dot_label = tk.Label(row, text="●", font=("Consolas", 10), fg=ACCENT, bg=BG)
        self.status_dot_label.pack(side="left", padx=(0, 6))
        tk.Label(row, text=spaced("sistema listo") if online else spaced("procesando"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(side="left")
        self._blink_dot()
        self._hud_separator(parent)

    def _blink_dot(self):
        if self.status_dot_label is None or not self.status_dot_label.winfo_exists():
            return
        cur = self.status_dot_label.cget("fg")
        self.status_dot_label.config(fg=(MUTED if cur == ACCENT else ACCENT))
        self.after(650, self._blink_dot)

    # ---------------- toggle de subtítulos (switch real) ----------------
    def _build_subtitle_toggle(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(pady=(0, 8))
        tk.Label(frame, text=spaced("subtítulos"), font=FONT_SMALL, fg=MUTED, bg=BG).pack(side="left", padx=(0, 10))
        self.subtitle_toggle_canvas = tk.Canvas(frame, width=58, height=26, bg=BG, highlightthickness=0, cursor="hand2")
        self.subtitle_toggle_canvas.pack(side="left")
        self.subtitle_toggle_canvas.bind("<Button-1>", lambda e: self._toggle_subtitles())
        self.subtitle_state_label = tk.Label(frame, text="", font=FONT_SMALL, fg=ACCENT, bg=BG)
        self.subtitle_state_label.pack(side="left", padx=(10, 0))
        self._draw_subtitle_toggle()

    def _draw_subtitle_toggle(self):
        c = self.subtitle_toggle_canvas
        c.delete("all")
        on = self.subtitles_on
        w, h = 58, 26
        accent = ACCENT if on else "#374151"
        track = ACCENT_SOFT if on else "#161b26"
        r = h / 2
        c.create_oval(1, 1, h - 1, h - 1, fill=track, outline=accent, width=1.5)
        c.create_oval(w - h + 1, 1, w - 1, h - 1, fill=track, outline=accent, width=1.5)
        c.create_rectangle(r, 1, w - r, h - 1, fill=track, outline="")
        c.create_line(r, 1, w - r, 1, fill=accent, width=1.5)
        c.create_line(r, h - 1, w - r, h - 1, fill=accent, width=1.5)
        kr = r - 4
        kx = w - r if on else r
        c.create_oval(kx - kr, r - kr, kx + kr, r + kr, fill=accent, outline="")
        if hasattr(self, "subtitle_state_label"):
            self.subtitle_state_label.config(text=("ON" if on else "OFF"), fg=(ACCENT if on else MUTED))

    def _toggle_subtitles(self):
        self.subtitles_on = not self.subtitles_on
        self._draw_subtitle_toggle()
        self._refresh_line_display()

    def _line_display_text(self, hablante, texto):
        if self.subtitles_on:
            return texto
        if hablante == self.otro_personaje:
            return "🔊 ..."
        return "🎙 (recuerda la línea)"

    def _refresh_line_display(self):
        if self.current_texto is None:
            return
        self.line_label.config(text=self._line_display_text(self.current_hablante, self.current_texto))

    # ---------------- el anillo HUD (arc reactor) ----------------
    def _hud_ticks(self, cx, cy, r1, r2, count, color, rotation=0.0, dim=False, level=0.0):
        for i in range(count):
            angle = (2 * math.pi * i / count) + rotation
            long_tick = (i % 4 == 0)
            wave = max(0.0, 0.4 + 0.6 * math.sin(self.anim_phase * 3 + i * 1.1))
            extra = level * wave * 22
            rr1 = r1 - (6 if long_tick else 0) - extra
            rr2 = r2 + extra * 0.35
            x1 = cx + rr1 * math.cos(angle)
            y1 = cy + rr1 * math.sin(angle)
            x2 = cx + rr2 * math.cos(angle)
            y2 = cy + rr2 * math.sin(angle)
            w = 3 if long_tick else 2
            col = color if (long_tick or not dim) else ACCENT_SOFT
            self.canvas.create_line(x1, y1, x2, y2, fill=col, width=w)

    def _hud_arc_segments(self, cx, cy, r, color, rotation=0.0):
        seg_count = 10
        gap_deg = 6
        span = 140
        start = math.degrees(rotation) % 360
        for i in range(seg_count):
            a0 = start + i * (span / seg_count)
            a1 = a0 + (span / seg_count) - gap_deg
            self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=a0, extent=(a1 - a0),
                                    style="arc", outline=color, width=4)

    def _hud_crosshair(self, cx, cy, r1, r2, color):
        for angle in (0, 90, 180, 270):
            rad = math.radians(angle)
            x1 = cx + r1 * math.cos(rad)
            y1 = cy + r1 * math.sin(rad)
            x2 = cx + r2 * math.cos(rad)
            y2 = cy + r2 * math.sin(rad)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

    def _hud_corners(self, cx, cy, r, color, size=12):
        for angle in (45, 135, 225, 315):
            rad = math.radians(angle)
            x = cx + r * math.cos(rad)
            y = cy + r * math.sin(rad)
            self.canvas.create_line(x - size, y, x + size, y, fill=color, width=1)
            self.canvas.create_line(x, y - size, x, y + size, fill=color, width=1)

    def _glow_circle(self, cx, cy, r, color):
        self.canvas.create_oval(cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10,
                                 outline=color, width=6, stipple="gray25")
        self.canvas.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                                 outline=color, width=3, stipple="gray50")

    def _animate(self):
        if self.canvas is None or not self.canvas.winfo_exists():
            return

        self.canvas.delete("all")
        cx, cy = self.anim_cx, self.anim_cy

        if self.anim_state == "idle":
            color = ACCENT
            speed = 0.035
            level = 0.14 + 0.05 * math.sin(self.anim_phase)
        elif self.anim_state == "listening":
            color = WARN
            speed = 0.22
            level = 0.22 + self.voice.current_level * 0.9
        else:  # speaking
            color = ACCENT
            speed = 0.16
            level = (0.32 + 0.25 * abs(math.sin(self.anim_phase * 2.3))
                     + 0.15 * abs(math.sin(self.anim_phase * 5.1)))

        self.anim_phase += speed

        self.canvas.create_oval(cx - 118, cy - 118, cx + 118, cy + 118,
                                 outline=ACCENT_SOFT, width=1, dash=(2, 6))
        self._hud_ticks(cx, cy, 80, 92, 44, color, rotation=self.anim_phase * 0.4,
                         dim=(self.anim_state == "idle"), level=level)
        self.canvas.create_oval(cx - 70, cy - 70, cx + 70, cy + 70, outline=color, width=1)
        self.canvas.create_oval(cx - 50, cy - 50, cx + 50, cy + 50, outline=color, width=1)
        self._hud_arc_segments(cx, cy, 60, color, rotation=-self.anim_phase * 0.6)
        self._hud_crosshair(cx, cy, 92, 106, color)
        self._hud_corners(cx, cy, 116, color)

        base_core = 24
        core_r = base_core + level * 20
        self._glow_circle(cx, cy, core_r, color)
        self.canvas.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r, outline=color, width=2)
        inner_r = core_r * 0.5
        self.canvas.create_oval(cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r, fill=color, outline="")

        self.after(40, self._animate)

    # ---------------- menú principal ----------------
    def _build_main_menu(self):
        self._clear()
        self.canvas = None

        self._hud_header(self, "Práctica oral", "Juan & Julián · Protocolo de conversación en inglés")

        self._hud_button(self, "🎙 Grabar voces de los personajes", self._build_recorder_ui).pack(pady=8)
        self._hud_button(self, "▶ Practicar diálogo", self._build_role_selector).pack(pady=8)

        grabadas = sum(
            1 for i, (hablante, _) in enumerate(DIALOGUE) if os.path.exists(voice_path(i, hablante))
        )
        tk.Label(self, text=spaced(f"voces grabadas: {grabadas} / {len(DIALOGUE)}"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(24, 0))

    # ---------------- selector de personaje ----------------
    def _build_role_selector(self):
        self._clear()
        self.canvas = None
        self._hud_header(self, "Selecciona tu rol", "¿Quién quieres ser en la conversación?")

        frame = tk.Frame(self, bg=BG)
        frame.pack()

        self._hud_button(frame, "Juan", lambda: self._start("Juan"), width=13).grid(row=0, column=0, padx=10)
        self._hud_button(frame, "Julián", lambda: self._start("Julian"), width=13).grid(row=0, column=1, padx=10)

        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2",
                  command=self._build_main_menu).pack(pady=34)

    # =========================================================
    #  MODO 1: GRABAR VOCES DE LOS PERSONAJES
    # =========================================================
    def _build_recorder_ui(self):
        self._clear()
        self.rec_index = 0

        self.anim_cx, self.anim_cy = 310, 120
        self.canvas = tk.Canvas(self, width=620, height=230, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(10, 5))

        self.rec_status = tk.Label(self, text="", font=("Segoe UI", 11), fg=MUTED, bg=BG)
        self.rec_status.pack()

        self.rec_speaker_label = tk.Label(self, text="", font=FONT_HUD, fg=ACCENT, bg=BG)
        self.rec_speaker_label.pack(pady=(10, 4))

        self.rec_line_label = tk.Label(self, text="", font=FONT_BODY, fg=FG, bg=BG,
                                        wraplength=540, justify="center")
        self.rec_line_label.pack(pady=(0, 12))

        row1 = tk.Frame(self, bg=BG)
        row1.pack(pady=6)
        self.rec_record_btn = self._hud_button(row1, "🎙 Grabar", self._rec_toggle_record, width=21)
        self.rec_record_btn.grid(row=0, column=0, padx=5)
        self.rec_play_btn = self._hud_button(row1, "▶ Escuchar", self._rec_play, width=14, accent=MUTED)
        self.rec_play_btn.grid(row=0, column=1, padx=5)
        self.rec_save_btn = self._hud_button(row1, "💾 Guardar", self._rec_save, width=14, accent=OK)
        self.rec_save_btn.grid(row=0, column=2, padx=5)

        row2 = tk.Frame(self, bg=BG)
        row2.pack(pady=12)
        self._hud_button(row2, "⏮ Anterior", self._rec_prev, width=13, accent=MUTED).grid(row=0, column=0, padx=5)
        self._hud_button(row2, "⏭ Saltar", self._rec_skip, width=13, accent=MUTED).grid(row=0, column=1, padx=5)
        tk.Button(row2, text=spaced("← menú"), font=FONT_SMALL, fg=MUTED, bg=BG, bd=0, relief="flat",
                  cursor="hand2", command=self._build_main_menu).grid(row=0, column=2, padx=12)

        self.rec_progress_label = tk.Label(self, text="", font=FONT_SMALL, fg=MUTED, bg=BG)
        self.rec_progress_label.pack(pady=(16, 0))

        self._animate()
        self._load_recorder_line()

    def _load_recorder_line(self):
        if self.rec_index >= len(DIALOGUE):
            self._build_main_menu()
            return

        hablante, texto = DIALOGUE[self.rec_index]
        path = voice_path(self.rec_index, hablante)
        ya_existe = os.path.exists(path)

        self.rec_speaker_label.config(text=spaced(hablante) + ("  ✅" if ya_existe else ""))
        self.rec_line_label.config(text=texto)
        self.rec_progress_label.config(text=spaced(f"línea {self.rec_index + 1} de {len(DIALOGUE)}"))
        self.rec_status.config(text="Presiona Grabar para registrar esta línea con tu voz.")
        self.rec_record_btn.config(text="🎙 GRABAR", fg=ACCENT)

        if ya_existe:
            self.voice.load_existing(path)
            self.rec_play_btn.config(state="normal")
            self.rec_save_btn.config(state="normal")
        else:
            self.voice.last_recording = None
            self.rec_play_btn.config(state="disabled")
            self.rec_save_btn.config(state="disabled")

        self.anim_state = "idle"

    def _rec_toggle_record(self):
        if not self.voice.recording:
            self.voice.start_recording()
            self.anim_state = "listening"
            self.rec_status.config(text="Grabando... presiona Detener cuando termines.")
            self.rec_record_btn.config(text="⏹ DETENER", fg=WARN)
            self.rec_play_btn.config(state="disabled")
            self.rec_save_btn.config(state="disabled")
        else:
            self.voice.stop_recording()
            self.anim_state = "idle"
            self.rec_record_btn.config(text="🎙 GRABAR DE NUEVO", fg=ACCENT)
            hay_audio = self.voice.last_recording is not None
            self.rec_play_btn.config(state="normal" if hay_audio else "disabled")
            self.rec_save_btn.config(state="normal" if hay_audio else "disabled")
            self.rec_status.config(text="Escúchala y presiona Guardar si te gustó.")

    def _rec_play(self):
        self.anim_state = "speaking"
        self.rec_play_btn.config(state="disabled")

        def done():
            self.anim_state = "idle"
            self.rec_play_btn.config(state="normal")

        self.voice.play_last_recording(on_done=lambda: self.after(0, done))

    def _rec_save(self):
        hablante, _ = DIALOGUE[self.rec_index]
        path = voice_path(self.rec_index, hablante)
        self.voice.save_last_recording(path)
        self.rec_status.config(text="✅ Guardada. Pasando a la siguiente línea...")
        self.rec_index += 1
        self.after(400, self._load_recorder_line)

    def _rec_skip(self):
        self.rec_index += 1
        self._load_recorder_line()

    def _rec_prev(self):
        self.rec_index = max(0, self.rec_index - 1)
        self._load_recorder_line()

    # =========================================================
    #  MODO 2: PRACTICAR DIÁLOGO
    # =========================================================
    def _start(self, mi):
        self.mi_personaje = mi
        self.otro_personaje = "Julian" if mi == "Juan" else "Juan"
        self.dialogue_index = 0
        self.correctas = 0
        self.total_mias = 0
        self._build_main_ui()
        self._process_next_line()

    def _build_main_ui(self):
        self._clear()

        self.anim_cx, self.anim_cy = 310, 145
        self.canvas = tk.Canvas(self, width=620, height=280, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(14, 4))

        self._build_subtitle_toggle(self)

        self.status_label = tk.Label(self, text="", font=("Segoe UI", 11), fg=MUTED, bg=BG)
        self.status_label.pack()

        self.line_label = tk.Label(self, text="", font=FONT_BODY, fg=FG, bg=BG,
                                    wraplength=540, justify="center")
        self.line_label.pack(pady=(10, 6))

        self.feedback_label = tk.Label(self, text="", font=("Segoe UI", 11), fg=WARN, bg=BG,
                                        wraplength=540, justify="center")
        self.feedback_label.pack(pady=(0, 10))

        self.btn_frame = tk.Frame(self, bg=BG)
        self.btn_frame.pack(pady=10)

        self.record_btn = self._hud_button(self.btn_frame, "🎙 Grabar", self._toggle_record, width=21)
        self.record_btn.grid(row=0, column=0, padx=6, pady=4)
        self.play_btn = self._hud_button(self.btn_frame, "▶ Escuchar", self._play_recording, width=14, accent=MUTED)
        self.play_btn.config(state="disabled")
        self.play_btn.grid(row=0, column=1, padx=6, pady=4)
        self.accept_btn = self._hud_button(self.btn_frame, "✔ Aceptar", self._accept_recording, width=14, accent=OK)
        self.accept_btn.config(state="disabled")
        self.accept_btn.grid(row=0, column=2, padx=6, pady=4)

        self.progress_label = tk.Label(self, text="", font=FONT_SMALL, fg=MUTED, bg=BG)
        self.progress_label.pack(pady=(16, 0))

        self.replay_btn = self._hud_button(self, "🔁 Escuchar de nuevo", self._replay_audio, width=26, accent=MUTED)
        self.replay_btn.config(state="disabled")
        self.replay_btn.pack(pady=(10, 0))

        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack(pady=(8, 0))

        self.continue_btn = None
        self._animate()

    def _show_summary(self):
        self._clear()
        self.canvas = None
        self._hud_header(self, "Diálogo terminado", "Resumen de tu sesión de práctica")
        tk.Label(self, text=f"{self.correctas} / {self.total_mias} líneas correctas",
                 font=("Segoe UI", 16), fg=FG, bg=BG).pack(pady=10)
        self._hud_button(self, "Reiniciar", self._build_main_menu, width=18).pack(pady=30)

    def _process_next_line(self):
        if self.dialogue_index >= len(DIALOGUE):
            self._show_summary()
            return

        hablante, texto = DIALOGUE[self.dialogue_index]
        self.current_hablante, self.current_texto = hablante, texto
        self.progress_label.config(text=spaced(f"línea {self.dialogue_index + 1} de {len(DIALOGUE)}"))
        self.feedback_label.config(text="")
        if self.continue_btn is not None:
            self.continue_btn.destroy()
            self.continue_btn = None

        if hablante == self.otro_personaje:
            path = voice_path(self.dialogue_index, hablante)
            usa_grabacion = os.path.exists(path)
            texto_estado = (
                f"🔊 Reproduciendo la voz grabada de {self.otro_personaje}..."
                if usa_grabacion
                else f"🤖 {self.otro_personaje} (sin grabación, voz de respaldo)..."
            )
            self.status_label.config(text=texto_estado)
            self.line_label.config(text=self._line_display_text(hablante, texto))
            self.record_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.accept_btn.config(state="disabled")
            self.replay_btn.config(state="disabled")
            self.anim_state = "speaking"

            def after_speak():
                self.anim_state = "idle"
                self.replay_btn.config(state="normal")
                self.status_label.config(text=f"¿Quieres escuchar a {self.otro_personaje} de nuevo? Si no, continúa.")
                self.continue_btn = self._hud_button(self.btn_frame, "➡ Continuar", self._advance,
                                                       width=44, accent=ACCENT)
                self.continue_btn.grid(row=1, column=0, columnspan=3, pady=(10, 0))

            self.voice.play_file_or_speak(path, texto, on_done=lambda: self.after(0, after_speak))
        else:
            self.total_mias += 1
            self.status_label.config(text=f"Tu turno ({self.mi_personaje}) — presiona Grabar y di la línea:")
            self.line_label.config(text=self._line_display_text(hablante, texto))
            self.record_btn.config(state="normal", text="🎙 GRABAR", fg=ACCENT)
            self.play_btn.config(state="disabled")
            self.accept_btn.config(state="disabled")
            self.replay_btn.config(state="normal")
            self.anim_state = "idle"

    def _replay_audio(self):
        if self.current_texto is None or self.current_hablante is None:
            return
        es_mi_turno = (self.current_hablante == self.mi_personaje)
        self.replay_btn.config(state="disabled")
        if es_mi_turno:
            self.record_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.accept_btn.config(state="disabled")
        self.anim_state = "speaking"
        path = voice_path(self.dialogue_index, self.current_hablante)

        def done():
            self.anim_state = "idle"
            self.replay_btn.config(state="normal")
            if es_mi_turno:
                self.record_btn.config(state="normal")
                hay_audio = self.voice.last_recording is not None
                self.play_btn.config(state="normal" if hay_audio else "disabled")
                self.accept_btn.config(state="normal" if hay_audio else "disabled")

        self.voice.play_file_or_speak(path, self.current_texto, on_done=lambda: self.after(0, done))

    def _toggle_record(self):
        if not self.voice.recording:
            self.voice.start_recording()
            self.anim_state = "listening"
            self.status_label.config(text="Escuchando... presiona Detener cuando termines.")
            self.record_btn.config(text="⏹ DETENER", fg=WARN)
            self.play_btn.config(state="disabled")
            self.accept_btn.config(state="disabled")
            self.replay_btn.config(state="disabled")
            self.feedback_label.config(text="")
        else:
            self.voice.stop_recording()
            self.anim_state = "idle"
            self.record_btn.config(text="🎙 GRABAR DE NUEVO", fg=ACCENT)
            hay_audio = self.voice.last_recording is not None
            self.play_btn.config(state="normal" if hay_audio else "disabled")
            self.accept_btn.config(state="normal" if hay_audio else "disabled")
            self.replay_btn.config(state="normal")
            self.status_label.config(text="Escucha tu grabación o acéptala para revisarla.")

    def _play_recording(self):
        self.anim_state = "speaking"
        self.play_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.accept_btn.config(state="disabled")
        self.replay_btn.config(state="disabled")

        def done():
            self.anim_state = "idle"
            self.play_btn.config(state="normal")
            self.record_btn.config(state="normal")
            self.accept_btn.config(state="normal")
            self.replay_btn.config(state="normal")

        self.voice.play_last_recording(on_done=lambda: self.after(0, done))

    def _accept_recording(self):
        self.accept_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.play_btn.config(state="disabled")
        self.replay_btn.config(state="disabled")
        self.status_label.config(text="Analizando lo que dijiste...")

        def run():
            texto_dicho = self.voice.transcribe_last_recording()
            self.after(0, lambda: self._show_feedback(texto_dicho))

        threading.Thread(target=run, daemon=True).start()

    def _show_feedback(self, dicho):
        _, texto_esperado = DIALOGUE[self.dialogue_index]

        if dicho is None:
            self.feedback_label.config(fg=WARN, text="No pude entender el audio. Intenta de nuevo.")
            self.record_btn.config(state="normal", text="🎙 GRABAR DE NUEVO", fg=ACCENT)
            self.status_label.config(text=f"Tu turno ({self.mi_personaje}):")
            return

        correcto, ratio, detalle = comparar_texto(texto_esperado, dicho)

        if correcto:
            self.correctas += 1
            self.feedback_label.config(
                fg=OK,
                text=f'✅ ¡Bien dicho! Escuché: "{dicho}"  (similitud {ratio:.0%})'
            )
        else:
            msg = f'❌ Escuché: "{dicho}"  (similitud {ratio:.0%})\nLínea correcta: "{texto_esperado}"'
            if detalle:
                msg += "\n" + detalle
            self.feedback_label.config(fg=WARN, text=msg)

        self.status_label.config(text="Graba de nuevo si quieres, o presiona Continuar.")
        self.record_btn.config(state="normal", text="🎙 GRABAR DE NUEVO", fg=ACCENT)
        self.play_btn.config(state="normal")

        self.continue_btn = self._hud_button(self.btn_frame, "➡ Continuar", self._advance, width=44, accent=ACCENT)
        self.continue_btn.grid(row=1, column=0, columnspan=3, pady=(10, 0))

    def _advance(self):
        if self.continue_btn is not None:
            self.continue_btn.destroy()
            self.continue_btn = None
        self.dialogue_index += 1
        self._process_next_line()


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
