"""
J.A.R.V.I.S. — Judge, Assist, Repeat, Verify, Improve Speech

P.H.O.E.N.I.X. - Pronunciation, Hearing, Oral Evaluation & Natural Interactive eXperience

N.O.V.A. - Native-like Oral Vocabulary Assistant
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

NUEVO — Comandos de voz manos libres (con palabra de activación):
   En ambos modos de práctica (con calificación y casual), el programa
   escucha continuamente en segundo plano, pero SOLO actúa si primero
   dices "Jarvis" o "Fénix" (tus dos nombres finalistas). Todo lo demás
   que digas se ignora sin interrumpir. Después de decir la palabra de
   activación puedes decir: "repite", "siguiente", "anterior", "graba",
   "detente", "escucha mi grabación", "acepta", "menú" o "ayuda".
   Ejemplo: "Jarvis, siguiente" o "Fénix, repite".
   El micrófono se pausa automáticamente mientras el programa reproduce
   audio o mientras grabas tu línea, para evitar que se escuche a sí mismo.

NUEVO — Frases interactivas del asistente (grabables con tu voz):
   Desde el menú principal puedes grabar frases del propio "asistente"
   (no de Juan/Julián), como el saludo de bienvenida al iniciar el
   programa o una frase de confirmación al elegir tu personaje. Si no
   las grabas, usa voz robótica de respaldo (igual que con el diálogo).

INSTALACIÓN (una sola vez):
------------------------------------------------------------------------
pip install SpeechRecognition pyttsx3 sounddevice numpy

(tkinter y wave ya vienen incluidos con Python)
(NO se necesita pyaudio: el micrófono de comandos de voz en segundo plano
 usa 'sounddevice', la misma librería que ya usa el resto del programa
 para grabar tus líneas.)

EJECUCIÓN:
------------------------------------------------------------------------
python practica.py
"""

import sys
import os
import re
import json
import math
import wave
import threading
import difflib
import unicodedata

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
DIALOGOS_DIR = "dialogos"  # conversaciones personalizadas creadas por el usuario

# Modos de práctica del diálogo
MODE_FULL = "full"        # graba, transcribe y califica tus líneas
MODE_CASUAL = "casual"    # solo escuchas al otro personaje; tú hablas libre, sin calificar

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


# -----------------------------------------------------------------------
# 1.5 FRASES INTERACTIVAS DEL ASISTENTE (no son parte del diálogo Juan/Julián)
# -----------------------------------------------------------------------
# Se pueden grabar con tu voz desde el menú principal. Si no se graban,
# se usa la voz robótica (TTS) de respaldo, igual que con el diálogo.
SYSTEM_PHRASES = {
    "bienvenida": "Hola señor, un gusto escucharlo de nuevo.",
    "buena_eleccion": "Buena elección.",
    "te_escucho": "Dime, señor.",
}

# Etiquetas legibles para la pantalla de grabación de frases del asistente
SYSTEM_PHRASE_LABELS = {
    "bienvenida": "Saludo al iniciar el programa",
    "buena_eleccion": "Al elegir tu personaje",
    "te_escucho": "Al activarte con 'Jarvis' o 'Fénix' sin dar un comando",
}


def voice_path(item_id):
    """item_id puede ser '00_Julian' (línea de diálogo) o
    'sistema_bienvenida' (frase interactiva del asistente)."""
    return os.path.join(VOICES_DIR, f"{item_id}.wav")


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
# 1.6 CONVERSACIONES PERSONALIZADAS (creadas por el usuario)
# -----------------------------------------------------------------------
# Cada conversación se guarda como un .json en la carpeta "dialogos/", con
# los nombres de los dos participantes y la lista de líneas en orden, cada
# una ya asignada a quién la dice (sin ambigüedad aunque el mismo
# participante diga varias líneas seguidas).
def _slugify(texto):
    """Convierte un nombre en un identificador de archivo seguro
    (sin acentos, espacios ni símbolos)."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", sin_acentos.strip().lower()).strip("_")
    return slug or "conversacion"


def listar_dialogos_personalizados():
    """Devuelve una lista de dicts con cada conversación guardada en
    dialogos/*.json: {'id', 'nombre', 'participantes', 'lineas'}."""
    if not os.path.isdir(DIALOGOS_DIR):
        return []
    resultado = []
    for fname in sorted(os.listdir(DIALOGOS_DIR)):
        if not fname.lower().endswith(".json"):
            continue
        path = os.path.join(DIALOGOS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            participantes = data.get("participantes") or ["A", "B"]
            if len(participantes) < 2:
                participantes = participantes + ["B"]
            lineas = [tuple(linea) for linea in data.get("lineas", [])]
            resultado.append({
                "id": os.path.splitext(fname)[0],
                "nombre": data.get("nombre", os.path.splitext(fname)[0]),
                "participantes": (participantes[0], participantes[1]),
                "lineas": lineas,
            })
        except Exception:
            continue
    return resultado


def guardar_dialogo_personalizado(nombre, participantes, lineas):
    """Guarda una conversación nueva y devuelve su id (usado luego como
    subcarpeta en voces/ para no mezclar audios de distintas conversaciones)."""
    os.makedirs(DIALOGOS_DIR, exist_ok=True)
    base_slug = _slugify(nombre)
    slug = base_slug
    n = 2
    while os.path.exists(os.path.join(DIALOGOS_DIR, f"{slug}.json")):
        slug = f"{base_slug}_{n}"
        n += 1
    data = {
        "nombre": nombre,
        "participantes": list(participantes),
        "lineas": [[hablante, texto] for hablante, texto in lineas],
    }
    with open(os.path.join(DIALOGOS_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return slug


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
# 2.5 COMANDOS DE VOZ — interpretación de lo que dice el usuario
# -----------------------------------------------------------------------
# Cada acción tiene varias formas comunes de decirla. Usamos coincidencia
# difusa (difflib) para tolerar errores del reconocimiento de voz, y
# quitamos acentos para no depender de que Google STT los transcriba bien.
# Cada acción tiene frases en español E inglés, porque esta es una app de
# práctica de inglés y el usuario puede querer dar los comandos en inglés.
VOICE_COMMANDS = {
    "repetir": ["repite", "repitelo", "repite la linea", "otra vez", "de nuevo",
                "vuelve a decir eso", "puedes repetir", "que dijiste",
                "repeat", "say that again", "one more time", "again", "say it again"],
    "siguiente": ["siguiente", "continua", "continuemos", "avanza",
                  "proxima linea", "sigamos", "seguir",
                  "next", "continue", "go on", "move on", "next line"],
    "anterior": ["anterior", "atras", "retrocede", "regresa", "linea anterior",
                 "vuelve atras",
                 "previous", "go back", "back", "previous line", "go to the previous line"],
    "grabar": ["graba", "grabar", "empieza a grabar", "inicia grabacion",
               "quiero grabar", "voy a grabar",
               "record", "start recording", "let's record", "record it"],
    "detener": ["detente", "para", "termina", "deten la grabacion", "stop",
                "ya termine", "listo de grabar",
                "stop recording", "done", "i'm done", "finish recording"],
    "escuchar_mia": ["escucha mi grabacion", "reproduce mi grabacion",
                      "como sono", "escuchame", "reproduce lo que dije",
                      "listen to my recording", "play my recording", "how did it sound",
                      "play it back"],
    "aceptar": ["acepta", "aceptar", "listo", "envia mi respuesta", "califica",
                "revisa",
                "accept", "submit", "grade it", "check it", "check my answer"],
    "menu": ["menu", "salir", "volver al menu", "regresa al menu", "sal de aqui",
             "go to menu", "exit", "quit", "go back to the menu"],
    "ayuda": ["ayuda", "comandos", "que puedo decir", "opciones",
              "que comandos hay",
              "help", "commands", "what can i say", "options", "what commands are there"],
}

UMBRAL_COMANDO = 0.72

# Palabra de activación: los comandos SOLO se procesan si el usuario dice
# primero uno de estos nombres (tus dos finalistas). Todo lo demás que
# diga se ignora sin interrumpir la práctica. Se incluye "phoenix" además
# de "fenix" para que también funcione si lo dices en inglés.
WAKE_WORDS = ["jarvis", "fenix", "phoenix"]
UMBRAL_WAKE_WORD = 0.72


def _quitar_acentos(texto):
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalizar_comando(texto):
    return _quitar_acentos(limpiar_texto(texto))


def detectar_wake_word(texto):
    """Busca 'Jarvis' o 'Fénix' en lo que dijo el usuario (tolerante a
    errores de transcripción). Si lo encuentra, devuelve el texto que
    viene DESPUÉS de la palabra de activación (puede quedar vacío si solo
    dijo el nombre). Si no la encuentra, devuelve None: no era para
    nosotros, se ignora sin más."""
    dicho_norm = _normalizar_comando(texto)
    if not dicho_norm:
        return None
    palabras = dicho_norm.split()
    for i, palabra in enumerate(palabras):
        for wake in WAKE_WORDS:
            ratio = difflib.SequenceMatcher(None, wake, palabra).ratio()
            if ratio >= UMBRAL_WAKE_WORD:
                return " ".join(palabras[i + 1:])
    return None


def interpretar_comando(texto):
    """Devuelve el nombre de la acción reconocida, o None si no coincide
    con ningún comando conocido."""
    dicho_norm = _normalizar_comando(texto)
    if not dicho_norm:
        return None

    mejor_accion = None
    mejor_ratio = 0.0

    for accion, frases in VOICE_COMMANDS.items():
        for frase in frases:
            frase_norm = _normalizar_comando(frase)
            if frase_norm in dicho_norm or dicho_norm in frase_norm:
                return accion
            ratio = difflib.SequenceMatcher(None, frase_norm, dicho_norm).ratio()
            if ratio > mejor_ratio:
                mejor_ratio = ratio
                mejor_accion = accion

    if mejor_ratio >= UMBRAL_COMANDO:
        return mejor_accion
    return None


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
# 3.5 OYENTE DE COMANDOS DE VOZ (manos libres, en segundo plano)
# -----------------------------------------------------------------------
class VoiceCommandListener:
    """Escucha el micrófono continuamente en un hilo de fondo y llama a
    on_command(texto) cada vez que reconoce una frase completa. No bloquea
    la interfaz. Se puede pausar/reanudar (por ejemplo mientras el programa
    reproduce audio, para que no se escuche a sí mismo).

    IMPORTANTE: usa 'sounddevice' para capturar el micrófono (la misma
    librería que ya usa el resto del programa para grabar líneas), NO
    'sr.Microphone', así que NO necesita PyAudio. Hace su propia detección
    de silencio (VAD simple por energía/RMS) para saber cuándo empieza y
    termina una frase, y luego usa 'speech_recognition' solo para mandar
    ese audio ya capturado a reconocer_google (igual que hace
    VoiceEngine.transcribe_last_recording)."""

    BLOCK_SIZE = 1600           # ~0.1s por bloque a 16kHz
    SILENCE_SECONDS = 0.8       # silencio necesario para cerrar una frase
    MIN_PHRASE_SECONDS = 0.4    # ignora ruidos/sonidos demasiado cortos
    MIN_THRESHOLD = 300.0

    def __init__(self, on_command):
        self.on_command = on_command
        self.enabled = False
        self._stream = None
        self._buffer = []
        self._silence_blocks = 0
        self._threshold = self.MIN_THRESHOLD
        self._lock = threading.Lock()

    def start(self):
        """Bloqueante brevemente (calibra ruido ambiente ~0.5s). Llamar desde
        un hilo secundario para no congelar la interfaz."""
        with self._lock:
            if self.enabled:
                return
            try:
                self._buffer = []
                self._silence_blocks = 0

                # Calibración rápida de ruido ambiente: graba medio segundo
                # en silencio y usa eso para fijar el umbral de voz.
                calib = sd.rec(int(0.5 * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                                channels=1, dtype="int16")
                sd.wait()
                ambient_rms = float(np.sqrt(np.mean(calib.astype(np.float32) ** 2)))
                self._threshold = max(self.MIN_THRESHOLD, ambient_rms * 2.5)

                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                    blocksize=self.BLOCK_SIZE, callback=self._audio_callback,
                )
                self._stream.start()
                self.enabled = True
            except Exception as e:
                print(f"[Comandos de voz] No se pudo iniciar el micrófono: {e}")
                self.enabled = False

    def stop(self):
        with self._lock:
            if not self.enabled:
                return
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self.enabled = False
            self._buffer = []
            self._silence_blocks = 0

    def pause(self):
        self.stop()

    def resume(self):
        self.start()

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.enabled:
            return
        chunk = indata.copy()
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

        if rms > self._threshold:
            self._buffer.append(chunk)
            self._silence_blocks = 0
            return

        if not self._buffer:
            return  # todavía no ha empezado a hablar, no hay nada que cerrar

        self._buffer.append(chunk)  # un poco de silencio de cola suena más natural
        self._silence_blocks += 1
        silencio_seg = self._silence_blocks * (frames / SAMPLE_RATE)
        if silencio_seg < self.SILENCE_SECONDS:
            return

        chunks = self._buffer
        self._buffer = []
        self._silence_blocks = 0
        total_seg = sum(c.shape[0] for c in chunks) / SAMPLE_RATE
        if total_seg >= self.MIN_PHRASE_SECONDS:
            threading.Thread(target=self._process_phrase, args=(chunks,), daemon=True).start()

    def _process_phrase(self, chunks):
        audio = np.concatenate(chunks, axis=0)
        recognizer = sr.Recognizer()
        audio_data = sr.AudioData(audio.tobytes(), SAMPLE_RATE, 2)
        # Probamos inglés primero (esta es una app de práctica de inglés)
        # y si no reconoce nada, caemos a español. Un solo intento exitoso
        # es suficiente; solo seguimos probando si el primero no entendió.
        texto = None
        for lang in ("en-US", "es-ES"):
            try:
                texto = recognizer.recognize_google(audio_data, language=lang)
                if texto:
                    break
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                return
        if texto and self.on_command:
            self.on_command(texto)


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
        self.geometry("620x780")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.voice = VoiceEngine()
        self.cmd_listener = VoiceCommandListener(on_command=self._on_voice_command_raw)

        # estado de práctica
        self.dialogue_index = 0
        self.mi_personaje = None
        self.otro_personaje = None
        self.correctas = 0
        self.total_mias = 0
        self.subtitles_on = True
        self.current_hablante = None
        self.current_texto = None
        self.practice_mode = MODE_FULL

        # conversación activa: por defecto la de Juan & Julián que trae la app.
        # Al elegir una conversación personalizada, estos tres se reemplazan.
        self.active_dialogue = DIALOGUE
        self.active_dialogue_id = ""   # "" = conversación original (rutas de voz sin cambios)
        self.active_participantes = ("Juan", "Julian")

        # estado del editor de conversaciones personalizadas
        self.editor_participantes = []
        self.editor_lineas = []
        self.editor_entry = None
        self.editor_listbox = None

        # estado del grabador de voces
        self.rec_index = 0

        self.anim_phase = 0.0
        self.anim_state = "idle"  # idle | speaking | listening
        self.anim_cx = 310
        self.anim_cy = 140
        self.canvas = None
        self.continue_btn = None
        self.back_btn = None
        self.status_dot_label = None
        self.mic_status_label = None
        self.mic_toggle_btn = None
        self.record_btn = None
        self.play_btn = None
        self.accept_btn = None
        self.replay_btn = None

        # estado del flujo "Jarvis" -> (respuesta) -> comando en dos pasos
        self.awaiting_command = False
        self.awaiting_timer_id = None
        self.AWAITING_TIMEOUT_MS = 6000

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_main_menu()
        # Saluda al iniciar el programa (usa tu voz si grabaste la frase
        # "bienvenida", si no, cae en voz robótica de respaldo).
        self.after(400, lambda: self._decir_frase_sistema("bienvenida"))

    def _on_close(self):
        self.cmd_listener.stop()
        self.destroy()

    # ---------------- conversación activa ----------------
    def _item_id(self, i, hablante):
        """Id de archivo de voz para la línea i de la conversación ACTIVA.
        La conversación original usa las rutas de siempre (voces/00_Juan.wav);
        cada conversación personalizada usa su propia subcarpeta
        (voces/<id>/00_Nombre.wav) para no mezclar audios entre conversaciones."""
        if self.active_dialogue_id:
            return f"{self.active_dialogue_id}/{i:02d}_{hablante}"
        return f"{i:02d}_{hablante}"

    def _usar_dialogo_default(self):
        self.active_dialogue = DIALOGUE
        self.active_dialogue_id = ""
        self.active_participantes = ("Juan", "Julian")

    # ---------------- utilidades visuales compartidas ----------------
    def _clear(self):
        self.cmd_listener.stop()
        self._cancel_awaiting_timeout()
        self.awaiting_command = False
        for widget in self.winfo_children():
            widget.destroy()
        self.status_dot_label = None
        self.mic_status_label = None
        self.mic_toggle_btn = None

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

    # ---------------- comandos de voz manos libres ----------------
    def _build_voice_command_bar(self, parent):
        """Fila con el indicador del micrófono de comandos y su botón de
        silenciar/activar. Solo se usa en las pantallas de práctica."""
        self.mic_status_label = tk.Label(parent, text="🎤 Activando comandos de voz...",
                                          font=FONT_SMALL, fg=MUTED, bg=BG)
        self.mic_status_label.pack(pady=(2, 4))
        self.mic_toggle_btn = self._hud_button(parent, "🔇 Silenciar comandos", self._toggle_cmd_listener,
                                                width=26, accent=MUTED)
        self.mic_toggle_btn.pack(pady=(0, 6))
        threading.Thread(target=self._start_cmd_listener_async, daemon=True).start()

    def _start_cmd_listener_async(self):
        self.cmd_listener.start()
        self.after(0, self._update_mic_status)

    def _toggle_cmd_listener(self):
        if self.cmd_listener.enabled:
            self.cmd_listener.stop()
            self._update_mic_status()
        else:
            threading.Thread(target=self._start_cmd_listener_async, daemon=True).start()

    def _update_mic_status(self):
        if self.mic_status_label is None or not self.mic_status_label.winfo_exists():
            return
        if self.awaiting_command:
            self.mic_status_label.config(text="🎤 Te escucho... di tu comando", fg=ACCENT)
        elif self.cmd_listener.enabled:
            self.mic_status_label.config(text="🎤 Di \"Jarvis\" o \"Fénix\" + tu comando", fg=ACCENT)
        else:
            self.mic_status_label.config(text="🎤 Comandos en pausa (micrófono apagado)", fg=MUTED)
        if self.mic_toggle_btn is not None and self.mic_toggle_btn.winfo_exists():
            if self.cmd_listener.enabled:
                self.mic_toggle_btn.config(text="🔇 SILENCIAR COMANDOS")
            else:
                self.mic_toggle_btn.config(text="🔊 ACTIVAR COMANDOS")

    def _decir_frase_sistema(self, key, on_done=None):
        """Reproduce una frase interactiva del asistente (ej. saludo,
        'buena elección'). Usa la grabación con tu voz si existe, o cae en
        voz robótica de respaldo."""
        texto = SYSTEM_PHRASES.get(key, "")
        if not texto:
            if on_done:
                on_done()
            return
        path = voice_path(f"sistema_{key}")
        self.voice.play_file_or_speak(path, texto, on_done=on_done)

    def _cmd_pause(self):
        self.cmd_listener.pause()

    def _cmd_resume_async(self):
        threading.Thread(target=self._start_cmd_listener_async, daemon=True).start()

    def _on_voice_command_raw(self, texto):
        # Este callback llega desde el hilo del reconocedor de voz;
        # lo pasamos al hilo principal de Tk con .after().
        self.after(0, lambda: self._handle_voice_command(texto))

    def _mostrar_comando_detectado(self, texto, accion):
        if self.mic_status_label is None or not self.mic_status_label.winfo_exists():
            return
        if accion:
            self.mic_status_label.config(text=f'🎤 Escuché: "{texto}" → {accion}', fg=OK)
        else:
            self.mic_status_label.config(text=f'🎤 Te oí, pero no reconocí un comando: "{texto}"', fg=MUTED)
        self.after(2000, self._update_mic_status)

    def _voice_help(self):
        self._cmd_pause()
        ayuda_texto = ("Di Jarvis o Fénix. Espera a que te responda, y luego di tu comando: "
                       "repite, siguiente, anterior, graba, detente, escucha mi grabación, acepta, o menú.")
        self.voice.speak(ayuda_texto, on_done=lambda: self.after(0, self._cmd_resume_async))

    # -------- flujo de dos pasos: "Jarvis" -> respuesta -> comando --------
    def _start_awaiting_timeout(self):
        self._cancel_awaiting_timeout()
        self.awaiting_timer_id = self.after(self.AWAITING_TIMEOUT_MS, self._awaiting_timeout)

    def _cancel_awaiting_timeout(self):
        if self.awaiting_timer_id is not None:
            try:
                self.after_cancel(self.awaiting_timer_id)
            except Exception:
                pass
            self.awaiting_timer_id = None

    def _awaiting_timeout(self):
        self.awaiting_timer_id = None
        self.awaiting_command = False
        self._update_mic_status()

    def _responder_activacion(self):
        """Se dijo el nombre de activación pero sin un comando después.
        Responde brevemente (con tu voz si grabaste 'te_escucho') para
        confirmar que está escuchando, y luego se queda en modo "esperando
        comando": la SIGUIENTE frase que digas (sin necesidad de repetir
        'Jarvis') se interpretará directamente como el comando."""
        self._cmd_pause()

        def after_resp():
            self._cmd_resume_async()
            self._update_mic_status()
            self._start_awaiting_timeout()

        self._decir_frase_sistema("te_escucho", on_done=lambda: self.after(0, after_resp))

    def _handle_voice_command(self, texto):
        if not self.cmd_listener.enabled:
            return

        # Paso 2: ya dijiste "Jarvis" antes y estamos esperando tu comando,
        # así que esta frase completa ES el comando (sin necesitar decir
        # "Jarvis" de nuevo).
        if self.awaiting_command:
            self.awaiting_command = False
            self._cancel_awaiting_timeout()
            accion = interpretar_comando(texto)
            self._mostrar_comando_detectado(texto, accion)
            self._ejecutar_accion(accion)
            return

        resto = detectar_wake_word(texto)
        if resto is None:
            return  # no dijo "Jarvis" ni "Fénix": no era para nosotros, se ignora

        if not resto.strip():
            # Paso 1: dijo solo "Jarvis" (o "Fénix"), sin comando junto.
            # Confirmamos y esperamos el comando como una frase aparte.
            self.awaiting_command = True
            self._mostrar_comando_detectado(texto, None)
            self._responder_activacion()
            return

        # También se sigue permitiendo decir todo junto: "Jarvis, siguiente".
        accion = interpretar_comando(resto)
        self._mostrar_comando_detectado(texto, accion)
        self._ejecutar_accion(accion)

    def _ejecutar_accion(self, accion):
        if accion == "ayuda":
            self._voice_help()
            return
        if accion == "menu":
            self._build_main_menu()
            return
        if accion is None:
            return

        boton_por_accion = {
            "repetir": "replay_btn",
            "siguiente": "continue_btn",
            "anterior": "back_btn",
            "grabar": "record_btn",
            "detener": "record_btn",
            "escuchar_mia": "play_btn",
            "aceptar": "accept_btn",
        }
        attr = boton_por_accion.get(accion)
        btn = getattr(self, attr, None) if attr else None
        if btn is not None and btn.winfo_exists() and str(btn.cget("state")) == "normal":
            btn.invoke()

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
        # el menú principal siempre parte de la conversación original;
        # las conversaciones personalizadas se activan solo al elegirlas.
        self._usar_dialogo_default()

        self._hud_header(self, "Práctica oral", "Juan & Julián · Protocolo de conversación en inglés")

        self._hud_button(self, "🎙 Grabar voces de los personajes",
                          lambda: self._build_recorder_ui("dialogo")).pack(pady=8)
        self._hud_button(self, "🗣 Grabar frases del asistente (Jarvis)",
                          lambda: self._build_recorder_ui("sistema"), accent=MUTED).pack(pady=8)
        self._hud_button(self, "▶ Practicar diálogo (con calificación)",
                          lambda: self._elegir_modo(MODE_FULL)).pack(pady=8)
        self._hud_button(self, "🎧 Práctica casual (solo escuchar)",
                          lambda: self._elegir_modo(MODE_CASUAL), accent=MUTED).pack(pady=8)

        self._hud_separator(self, width=380)

        self._hud_button(self, "📝 Crear conversación nueva", self._build_editor_names,
                          accent=MUTED).pack(pady=8)
        self._hud_button(self, "📂 Mis conversaciones guardadas", self._build_custom_dialogue_list,
                          accent=MUTED).pack(pady=8)

        grabadas = sum(
            1 for i, (hablante, _) in enumerate(DIALOGUE) if os.path.exists(voice_path(f"{i:02d}_{hablante}"))
        )
        grabadas_sistema = sum(
            1 for key in SYSTEM_PHRASES if os.path.exists(voice_path(f"sistema_{key}"))
        )
        n_personalizadas = len(listar_dialogos_personalizados())
        tk.Label(self, text=spaced(f"voces grabadas: {grabadas} / {len(DIALOGUE)}"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(24, 0))
        tk.Label(self, text=spaced(f"frases del asistente: {grabadas_sistema} / {len(SYSTEM_PHRASES)}"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(4, 0))
        tk.Label(self, text=spaced(f"conversaciones personalizadas: {n_personalizadas}"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(4, 0))

    # ---------------- selector de personaje ----------------
    def _elegir_modo(self, mode):
        """Se dice 'buena elección' al elegir el tipo de práctica, y luego
        pasa a la pantalla de elegir personaje."""
        self._decir_frase_sistema("buena_eleccion")
        self._build_role_selector(mode)

    def _build_role_selector(self, mode=MODE_FULL):
        self._clear()
        self.canvas = None
        subtitulo = ("¿Quién quieres ser en la conversación?" if mode == MODE_FULL
                     else "¿Quién quieres ser? (solo escucharás al otro personaje)")
        self._hud_header(self, "Selecciona tu rol", subtitulo)

        frame = tk.Frame(self, bg=BG)
        frame.pack()

        p1, p2 = self.active_participantes
        self._hud_button(frame, p1, lambda: self._start(p1, mode), width=13).grid(row=0, column=0, padx=10)
        self._hud_button(frame, p2, lambda: self._start(p2, mode), width=13).grid(row=0, column=1, padx=10)

        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2",
                  command=self._build_main_menu).pack(pady=34)

    # =========================================================
    #  EDITOR: CREAR UNA CONVERSACIÓN PERSONALIZADA
    # =========================================================
    def _build_editor_names(self):
        """Paso 1: nombres de los dos participantes de la nueva conversación."""
        self._clear()
        self.canvas = None
        self._hud_header(self, "Nueva conversación", "Escribe los nombres de los dos participantes")

        frame = tk.Frame(self, bg=BG)
        frame.pack(pady=10)

        tk.Label(frame, text=spaced("participante 1"), font=FONT_SMALL, fg=MUTED, bg=BG).grid(
            row=0, column=0, sticky="w", pady=8, padx=(0, 10))
        e1 = tk.Entry(frame, font=FONT_BODY, bg=PANEL, fg=FG, insertbackground=FG, width=20, relief="flat")
        e1.grid(row=0, column=1)

        tk.Label(frame, text=spaced("participante 2"), font=FONT_SMALL, fg=MUTED, bg=BG).grid(
            row=1, column=0, sticky="w", pady=8, padx=(0, 10))
        e2 = tk.Entry(frame, font=FONT_BODY, bg=PANEL, fg=FG, insertbackground=FG, width=20, relief="flat")
        e2.grid(row=1, column=1)

        error_label = tk.Label(self, text="", font=FONT_SMALL, fg=WARN, bg=BG)
        error_label.pack(pady=(6, 0))

        def continuar():
            p1 = e1.get().strip()
            p2 = e2.get().strip()
            if not p1 or not p2:
                error_label.config(text="Escribe los dos nombres para continuar.")
                return
            if p1.lower() == p2.lower():
                error_label.config(text="Los dos nombres deben ser diferentes.")
                return
            self.editor_participantes = [p1, p2]
            self.editor_lineas = []
            self._build_editor_lines()

        self._hud_button(self, "Continuar →", continuar, width=20).pack(pady=20)
        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack(pady=6)

    def _build_editor_lines(self):
        """Paso 2: escribir cada línea y asignarla a uno de los dos
        participantes (un botón por participante evita cualquier
        confusión sobre quién dice qué, incluso si el mismo participante
        dice varias líneas seguidas)."""
        self._clear()
        self.canvas = None
        p1, p2 = self.editor_participantes
        self._hud_header(self, "Agregar líneas", f"{p1} & {p2} · escribe la línea y elige quién la dice")

        entry_frame = tk.Frame(self, bg=BG)
        entry_frame.pack(pady=(0, 8))
        self.editor_entry = tk.Entry(entry_frame, font=FONT_BODY, bg=PANEL, fg=FG,
                                      insertbackground=FG, width=46, relief="flat")
        self.editor_entry.grid(row=0, column=0)
        self.editor_entry.focus_set()
        self.editor_entry.bind("<Return>", lambda e: self._editor_add_line(p1))

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=(0, 10))
        self._hud_button(btn_row, f"+ {p1}", lambda: self._editor_add_line(p1), width=18).grid(
            row=0, column=0, padx=6)
        self._hud_button(btn_row, f"+ {p2}", lambda: self._editor_add_line(p2), width=18, accent=MUTED).grid(
            row=0, column=1, padx=6)

        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(pady=(2, 6))
        self.editor_listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), bg=PANEL, fg=FG,
                                          width=66, height=11, relief="flat", highlightthickness=1,
                                          highlightbackground=ACCENT_SOFT, selectbackground=ACCENT_SOFT,
                                          activestyle="none")
        self.editor_listbox.pack(side="left")
        scroll = tk.Scrollbar(list_frame, command=self.editor_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.editor_listbox.config(yscrollcommand=scroll.set)

        ctrl_row = tk.Frame(self, bg=BG)
        ctrl_row.pack(pady=(6, 10))
        self._hud_button(ctrl_row, "🗑 Eliminar seleccionada", self._editor_eliminar_seleccionada,
                          width=24, accent=WARN).grid(row=0, column=0, padx=6)
        self._hud_button(ctrl_row, "✅ Finalizar conversación", self._build_editor_finish,
                          width=24, accent=OK).grid(row=0, column=1, padx=6)

        tk.Button(self, text=spaced("← cancelar y volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack(pady=(6, 0))

        self._editor_refresh_listbox()

    def _editor_refresh_listbox(self):
        self.editor_listbox.delete(0, tk.END)
        for i, (hablante, texto) in enumerate(self.editor_lineas, start=1):
            self.editor_listbox.insert(tk.END, f"{i}. {hablante}: {texto}")

    def _editor_add_line(self, hablante):
        """Agrega la línea escrita, ya asignada al participante que
        presionó su botón. No importa si el participante anterior es el
        mismo: cada línea queda anotada individualmente en orden, así que
        no hay interferencia entre líneas consecutivas del mismo hablante."""
        texto = self.editor_entry.get().strip()
        if not texto:
            self.editor_entry.focus_set()
            return
        self.editor_lineas.append((hablante, texto))
        self.editor_entry.delete(0, tk.END)
        self.editor_entry.focus_set()
        self._editor_refresh_listbox()
        self.editor_listbox.see(tk.END)

    def _editor_eliminar_seleccionada(self):
        sel = self.editor_listbox.curselection()
        if not sel:
            return
        del self.editor_lineas[sel[0]]
        self._editor_refresh_listbox()

    def _build_editor_finish(self):
        """Paso 3: decide que la conversación terminó, le pone un nombre y
        la guarda en dialogos/*.json."""
        if not self.editor_lineas:
            return
        self._clear()
        self.canvas = None
        self._hud_header(self, "Guardar conversación", "Ponle un nombre a esta conversación")

        entry = tk.Entry(self, font=FONT_BODY, bg=PANEL, fg=FG, insertbackground=FG, width=32, relief="flat")
        entry.insert(0, f"{self.editor_participantes[0]} y {self.editor_participantes[1]}")
        entry.pack(pady=10)
        entry.focus_set()
        entry.icursor(tk.END)

        error_label = tk.Label(self, text="", font=FONT_SMALL, fg=WARN, bg=BG)
        error_label.pack()

        tk.Label(self, text=spaced(f"{len(self.editor_lineas)} líneas en total"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(4, 0))

        def guardar():
            nombre = entry.get().strip()
            if not nombre:
                error_label.config(text="Escribe un nombre para la conversación.")
                return
            guardar_dialogo_personalizado(nombre, self.editor_participantes, self.editor_lineas)
            self._build_main_menu()

        self._hud_button(self, "💾 Guardar", guardar, width=20, accent=OK).pack(pady=16)
        tk.Button(self, text=spaced("← volver a editar líneas"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_editor_lines).pack(pady=6)

    # =========================================================
    #  MIS CONVERSACIONES PERSONALIZADAS GUARDADAS
    # =========================================================
    def _build_custom_dialogue_list(self):
        self._clear()
        self.canvas = None
        dialogos = listar_dialogos_personalizados()
        self._hud_header(self, "Mis conversaciones", "Elige una conversación personalizada")

        if not dialogos:
            tk.Label(self, text="Todavía no has creado ninguna conversación.\nUsa 'Crear conversación nueva' en el menú.",
                     font=("Segoe UI", 12), fg=MUTED, bg=BG, justify="center").pack(pady=30)
        else:
            for d in dialogos:
                p1, p2 = d["participantes"]
                etiqueta = f"{d['nombre']} ({p1} & {p2}, {len(d['lineas'])} líneas)"
                self._hud_button(self, etiqueta, lambda d=d: self._elegir_dialogo_personalizado(d),
                                  width=44).pack(pady=5)

        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack(pady=(24, 0))

    def _elegir_dialogo_personalizado(self, d):
        self.active_dialogue = d["lineas"]
        self.active_dialogue_id = d["id"]
        self.active_participantes = d["participantes"]
        self._build_custom_dialogue_actions(d["nombre"])

    def _build_custom_dialogue_actions(self, nombre):
        self._clear()
        self.canvas = None
        p1, p2 = self.active_participantes
        self._hud_header(self, nombre, f"{p1} & {p2} · {len(self.active_dialogue)} líneas")

        self._hud_button(self, "🎙 Grabar voces de esta conversación",
                          lambda: self._build_recorder_ui("dialogo")).pack(pady=8)
        self._hud_button(self, "▶ Practicar (con calificación)",
                          lambda: self._elegir_modo(MODE_FULL)).pack(pady=8)
        self._hud_button(self, "🎧 Práctica casual (solo escuchar)",
                          lambda: self._elegir_modo(MODE_CASUAL), accent=MUTED).pack(pady=8)

        grabadas = sum(
            1 for i, (hablante, _) in enumerate(self.active_dialogue)
            if os.path.exists(voice_path(self._item_id(i, hablante)))
        )
        tk.Label(self, text=spaced(f"voces grabadas: {grabadas} / {len(self.active_dialogue)}"),
                 font=FONT_SMALL, fg=MUTED, bg=BG).pack(pady=(20, 0))

        tk.Button(self, text=spaced("← mis conversaciones"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_custom_dialogue_list).pack(pady=(20, 4))
        tk.Button(self, text=spaced("← menú principal"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack()

    # =========================================================
    #  MODO 1: GRABAR VOCES (personajes del diálogo, o frases del asistente)
    # =========================================================
    def _dialogo_items(self):
        return [
            {"id": self._item_id(i, hablante), "label": hablante, "texto": texto}
            for i, (hablante, texto) in enumerate(self.active_dialogue)
        ]

    def _sistema_items(self):
        return [
            {"id": f"sistema_{key}", "label": SYSTEM_PHRASE_LABELS.get(key, key), "texto": texto}
            for key, texto in SYSTEM_PHRASES.items()
        ]

    def _build_recorder_ui(self, modo="dialogo"):
        self._clear()
        self.rec_modo = modo
        self.rec_items = self._dialogo_items() if modo == "dialogo" else self._sistema_items()
        self.rec_index = 0

        self.anim_cx, self.anim_cy = 310, 120
        self.canvas = tk.Canvas(self, width=620, height=230, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(10, 5))

        titulo = "Grabando voces de los personajes" if modo == "dialogo" else "Grabando frases del asistente"
        tk.Label(self, text=spaced(titulo), font=FONT_SUB, fg=MUTED, bg=BG).pack(pady=(0, 4))

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
        if self.rec_index >= len(self.rec_items):
            self._build_main_menu()
            return

        item = self.rec_items[self.rec_index]
        path = voice_path(item["id"])
        ya_existe = os.path.exists(path)

        self.rec_speaker_label.config(text=spaced(item["label"]) + ("  ✅" if ya_existe else ""))
        self.rec_line_label.config(text=item["texto"])
        self.rec_progress_label.config(text=spaced(f"línea {self.rec_index + 1} de {len(self.rec_items)}"))
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
        item = self.rec_items[self.rec_index]
        path = voice_path(item["id"])
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
    def _start(self, mi, mode=MODE_FULL):
        p1, p2 = self.active_participantes
        self.mi_personaje = mi
        self.otro_personaje = p2 if mi == p1 else p1
        self.practice_mode = mode
        self.dialogue_index = 0
        self.correctas = 0
        self.total_mias = 0
        self._build_main_ui()
        self.anim_state = "speaking"
        self._decir_frase_sistema("buena_eleccion", on_done=lambda: self.after(0, self._process_next_line))

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

        self.record_btn = None
        self.play_btn = None
        self.accept_btn = None
        if self.practice_mode == MODE_FULL:
            self.record_btn = self._hud_button(self.btn_frame, "🎙 Grabar", self._toggle_record, width=21)
            self.record_btn.grid(row=0, column=0, padx=6, pady=4)
            self.play_btn = self._hud_button(self.btn_frame, "▶ Escuchar", self._play_recording, width=14, accent=MUTED)
            self.play_btn.config(state="disabled")
            self.play_btn.grid(row=0, column=1, padx=6, pady=4)
            self.accept_btn = self._hud_button(self.btn_frame, "✔ Aceptar", self._accept_recording, width=14, accent=OK)
            self.accept_btn.config(state="disabled")
            self.accept_btn.grid(row=0, column=2, padx=6, pady=4)
        else:
            tk.Label(self.btn_frame, text=spaced("modo casual · sin grabación ni calificación"),
                     font=FONT_SMALL, fg=MUTED, bg=BG).grid(row=0, column=0, columnspan=3, pady=4)

        self.progress_label = tk.Label(self, text="", font=FONT_SMALL, fg=MUTED, bg=BG)
        self.progress_label.pack(pady=(16, 0))

        self.replay_btn = self._hud_button(self, "🔁 Escuchar de nuevo", self._replay_audio, width=26, accent=MUTED)
        self.replay_btn.config(state="disabled")
        self.replay_btn.pack(pady=(10, 0))

        # Barra de comandos de voz manos libres (activa en ambos modos)
        self._build_voice_command_bar(self)

        tk.Button(self, text=spaced("← volver al menú"), font=FONT_SMALL, fg=MUTED, bg=BG,
                  bd=0, relief="flat", cursor="hand2", command=self._build_main_menu).pack(pady=(4, 0))

        self.continue_btn = None
        self.back_btn = None
        self._animate()

    def _show_summary(self):
        self._clear()
        self.canvas = None
        if self.practice_mode == MODE_CASUAL:
            self._hud_header(self, "Diálogo terminado", "¡Buen trabajo practicando la conversación!")
            tk.Label(self, text="Terminaste todo el diálogo en modo casual.",
                     font=("Segoe UI", 14), fg=FG, bg=BG).pack(pady=10)
        else:
            self._hud_header(self, "Diálogo terminado", "Resumen de tu sesión de práctica")
            tk.Label(self, text=f"{self.correctas} / {self.total_mias} líneas correctas",
                     font=("Segoe UI", 16), fg=FG, bg=BG).pack(pady=10)
        self._hud_button(self, "Reiniciar", self._build_main_menu, width=18).pack(pady=30)

    def _process_next_line(self):
        if self.dialogue_index >= len(self.active_dialogue):
            self._show_summary()
            return

        hablante, texto = self.active_dialogue[self.dialogue_index]
        self.current_hablante, self.current_texto = hablante, texto
        self.progress_label.config(text=spaced(f"línea {self.dialogue_index + 1} de {len(self.active_dialogue)}"))
        self.feedback_label.config(text="")
        if self.continue_btn is not None:
            self.continue_btn.destroy()
            self.continue_btn = None
        if self.back_btn is not None:
            self.back_btn.destroy()
            self.back_btn = None

        if hablante == self.otro_personaje:
            path = voice_path(self._item_id(self.dialogue_index, hablante))
            usa_grabacion = os.path.exists(path)
            texto_estado = (
                f"🔊 Reproduciendo la voz grabada de {self.otro_personaje}..."
                if usa_grabacion
                else f"🤖 {self.otro_personaje} (sin grabación, voz de respaldo)..."
            )
            self.status_label.config(text=texto_estado)
            self.line_label.config(text=self._line_display_text(hablante, texto))
            if self.practice_mode == MODE_FULL:
                self.record_btn.config(state="disabled")
                self.play_btn.config(state="disabled")
                self.accept_btn.config(state="disabled")
            self.replay_btn.config(state="disabled")
            self.anim_state = "speaking"

            def after_speak():
                self._cmd_resume_async()
                self.anim_state = "idle"
                self.replay_btn.config(state="normal")
                self.status_label.config(text=f"¿Quieres escuchar a {self.otro_personaje} de nuevo? Si no, continúa.")
                if self.practice_mode == MODE_CASUAL:
                    self._mostrar_controles_casual()
                else:
                    self.continue_btn = self._hud_button(self.btn_frame, "➡ Continuar", self._advance,
                                                           width=44, accent=ACCENT)
                    self.continue_btn.grid(row=1, column=0, columnspan=3, pady=(10, 0))

            self._cmd_pause()
            self.voice.play_file_or_speak(path, texto, on_done=lambda: self.after(0, after_speak))
        elif self.practice_mode == MODE_CASUAL:
            self.status_label.config(text=f"Tu turno ({self.mi_personaje}) — dilo en voz alta cuando quieras.")
            self.line_label.config(text=self._line_display_text(hablante, texto))
            self.replay_btn.config(state="disabled")
            self.anim_state = "idle"
            self._mostrar_controles_casual()
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
        es_mi_turno_full = (self.current_hablante == self.mi_personaje) and self.practice_mode == MODE_FULL
        self.replay_btn.config(state="disabled")
        if es_mi_turno_full:
            self.record_btn.config(state="disabled")
            self.play_btn.config(state="disabled")
            self.accept_btn.config(state="disabled")
        self.anim_state = "speaking"
        path = voice_path(self._item_id(self.dialogue_index, self.current_hablante))

        def done():
            self._cmd_resume_async()
            self.anim_state = "idle"
            self.replay_btn.config(state="normal")
            if es_mi_turno_full:
                self.record_btn.config(state="normal")
                hay_audio = self.voice.last_recording is not None
                self.play_btn.config(state="normal" if hay_audio else "disabled")
                self.accept_btn.config(state="normal" if hay_audio else "disabled")

        self._cmd_pause()
        self.voice.play_file_or_speak(path, self.current_texto, on_done=lambda: self.after(0, done))

    def _toggle_record(self):
        if not self.voice.recording:
            self._cmd_pause()
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
            self._cmd_resume_async()

    def _play_recording(self):
        self.anim_state = "speaking"
        self.play_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.accept_btn.config(state="disabled")
        self.replay_btn.config(state="disabled")

        def done():
            self._cmd_resume_async()
            self.anim_state = "idle"
            self.play_btn.config(state="normal")
            self.record_btn.config(state="normal")
            self.accept_btn.config(state="normal")
            self.replay_btn.config(state="normal")

        self._cmd_pause()
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
        _, texto_esperado = self.active_dialogue[self.dialogue_index]

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

    def _mostrar_controles_casual(self):
        """Muestra Continuar (y Retroceder si no es la primera línea) en modo casual."""
        if self.dialogue_index > 0:
            self.back_btn = self._hud_button(self.btn_frame, "⏪ Retroceder", self._retroceder,
                                              width=20, accent=MUTED)
            self.back_btn.grid(row=1, column=0, padx=(0, 4), pady=(10, 0))
            self.continue_btn = self._hud_button(self.btn_frame, "Continuar ⏩", self._advance,
                                                   width=20, accent=ACCENT)
            self.continue_btn.grid(row=1, column=1, columnspan=2, padx=(4, 0), pady=(10, 0))
        else:
            self.continue_btn = self._hud_button(self.btn_frame, "Continuar ⏩", self._advance,
                                                   width=44, accent=ACCENT)
            self.continue_btn.grid(row=1, column=0, columnspan=3, pady=(10, 0))

    def _retroceder(self):
        if self.dialogue_index > 0:
            self.dialogue_index -= 1
        self._process_next_line()

    def _advance(self):
        if self.continue_btn is not None:
            self.continue_btn.destroy()
            self.continue_btn = None
        self.dialogue_index += 1
        self._process_next_line()


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()