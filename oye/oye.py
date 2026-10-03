#!/usr/bin/env python3
"""«Oye, Claude»: hablarle a Claude Code sin tocar nada.

Escucha el micrófono. Al oír «Oye, Claude…» transcribe la frase EN EL MAC (Whisper con MLX) y la
pega y envía en la app de Claude. La respuesta la lee en voz alta el gancho voz_titular.py.

- No escucha mientras habla el asistente (para no oírse a sí mismo).
- Modo conversación: al callar el asistente, 8 s en los que no hace falta repetir «Oye, Claude».
  Si suena otro audio en el Mac (vídeo, música), esa ventana se cierra.
- Antes de pegar comprueba que la app de delante es Claude; si no, no pega nada.
- Solo guarda en el registro lo que envía, nunca lo que se habla en la sala.
- «Oye, Claude, a dormir» / «Oye, Claude, despierta», o el fichero ~/.claude/voz/OYE_PAUSADO.
- Configuración en config.json (palabra de aviso, app, vocabulario).
- Prueba sin micrófono: oye.py --depurar --prueba a.wav [pausa_s] b.wav ... (VOZ = el asistente calla)
"""
import json
import os
import queue
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np

CASA = Path(__file__).parent
CONFIG = json.loads((CASA / "config.json").read_text()) if (CASA / "config.json").exists() else {}
REGISTRO = CASA / "oye.log"
PAUSA = Path.home() / ".claude" / "voz" / "OYE_PAUSADO"
TURNO = Path.home() / ".claude" / "voz" / "turno.json"   # existe mientras el asistente trabaja
DEPURAR = "--depurar" in sys.argv
MODELO = "mlx-community/whisper-small-mlx"

TASA = 16000
TRAMO_MS = 30
MUESTRAS_TRAMO = TASA * TRAMO_MS // 1000
FIN_FRASE_S = 0.6        # silencio que cierra una frase
ESPERA_ORDEN_S = 1.5     # tras «Oye, Claude», cuánto espero a que sigas hablando
VENTANA_S = 8           # modo conversación: tras hablar el asistente, escucha sin «Oye, Claude»
SIN_ORDEN_S = 8          # si dices solo «Oye, Claude», cuánto espero la orden
MIN_FRASE_S = 0.4
MAX_FRASE_S = 20

# El nombre al que se llama, y lo que Whisper suele entender en su lugar. Se
# cambia en config.json → "nombres": expresión regular de la segunda palabra.
NOMBRES = CONFIG.get("nombres", r"claude|claud|claudet+e?|clod|clode|clot|klod")
# Primera palabra: «oye» y cómo la suele escribir Whisper. En config.json → "primeras".
PRIMERAS = CONFIG.get("primeras", r"oye|oie|olle|oyes|hey|ey|oiga")
AVISO = re.compile(r"^\W*(?:" + PRIMERAS + r")\W+(?:" + NOMBRES + r")\b\W*(.*)$")
APP = CONFIG.get("app", "Claude")          # app donde se escribe la orden
PARAR = {"cancela", "cancelar", "nada", "olvidalo", "dejalo"}


def turno_en_marcha() -> bool:
    """El asistente está trabajando (si se interrumpió un turno, el fichero viejo no cuenta)."""
    try:
        return time.time() - TURNO.stat().st_mtime < 600
    except FileNotFoundError:
        return False


def apuntar(texto: str) -> None:
    if "--prueba" in sys.argv:
        return
    with REGISTRO.open("a") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")


def normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


TINTINEO = {"hasta": 0.0}


def sonido(nombre: str) -> None:
    TINTINEO["hasta"] = time.time() + 1.5
    subprocess.Popen(["afplay", f"/System/Library/Sounds/{nombre}.aiff"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def asistente_hablando() -> bool:
    """Suena la voz del asistente (o un audio que lance él desde ~/.claude/voz)."""
    r = subprocess.run(["pgrep", "-f", "hablar_piper.py|^say |afplay .*/\\.claude/voz/"],
                       capture_output=True)
    return r.returncode == 0


def mac_sonando() -> bool:
    """El Mac está reproduciendo algo (vídeo, música, audio…): coreaudiod marca «audio-out».
    """
    if time.time() < TINTINEO["hasta"]:      # nuestro propio «tink»/«pop» no cuenta
        return False
    r = subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True)
    # Solo salidas puras: «Resources: audio-out …». Las que llevan también «audio-in» son
    # dispositivos de procesado de voz (dictado, llamadas) y saltan sin que suene nada.
    return any("audio-out" in l and "audio-in" not in l
               for l in r.stdout.splitlines() if "Resources:" in l)


# Palabras habituales: ayudan a que las órdenes lleguen bien escritas. Solo se usan para la
# orden, nunca para buscar el aviso (con el nombre en la pista se lo inventaría sobre el ruido).
VOCABULARIO = CONFIG.get("vocabulario", "Claude, Claude Code.")


def transcribir(audio: np.ndarray, pista: str = None) -> str:
    import mlx_whisper
    r = mlx_whisper.transcribe(audio.astype(np.float32), path_or_hf_repo=MODELO,
                               language="es", condition_on_previous_text=False,
                               initial_prompt=pista)
    # Whisper se inventa frases sobre el ruido («¡Suscríbete!», «Gracias por ver»…):
    # fuera los trozos que él mismo da por no-voz o con muy poca seguridad.
    buenos = [g["text"] for g in r.get("segments", [])
              if g.get("no_speech_prob", 0) < 0.8 and g.get("avg_logprob", 0) > -1.4
              and g.get("compression_ratio", 0) < 2.4]          # texto repetitivo = inventado
    # Además, si se queda enganchado repitiendo («X, X, X, X…»), se corta la repetición.
    buenos = [re.sub(r"((?:\S+[ ,]*){1,3}?)(?:\1){2,}", r"\1", b) for b in buenos]
    texto = " ".join(buenos).strip()
    if re.search(r"suscr[ií]bete|gracias por ver|amara\.org|subt[ií]tulos", normal(texto)):
        return ""
    return texto


def enviar_a_claude(texto: str) -> None:
    """Pega el texto en la app de Claude y pulsa Intro, devolviendo el portapapeles.

    Antes de pegar comprueba que la app de delante es de verdad Claude: si no lo es (otro
    escritorio, pantalla bloqueada), no pega nada, para no escribir en otra aplicación.
    """
    utf8 = {**os.environ, "LANG": "es_ES.UTF-8", "LC_ALL": "es_ES.UTF-8"}
    antes = subprocess.run(["pbpaste"], capture_output=True, env=utf8).stdout
    try:
        subprocess.run(["pbcopy"], input=texto.encode(), env=utf8)
        guion = f'''
tell application "{APP}" to activate
delay 0.2
tell application "System Events"
    if (name of first application process whose frontmost is true) is not "{APP}" then error "Claude no quedó delante"
    keystroke "v" using command down
    delay 0.15
    key code 36
end tell'''
        subprocess.run(["osascript", "-e", guion], check=True, timeout=15, capture_output=True)
        time.sleep(0.8)
    finally:
        subprocess.run(["pbcopy"], input=antes, env=utf8)


class Oido:
    """Corta el sonido del micro en frases usando un detector de voz."""

    def __init__(self):
        import webrtcvad
        self.vad = webrtcvad.Vad(2)
        self.simulado = False   # en pruebas, el reloj es el propio audio

    def reloj(self, n):
        return n * TRAMO_MS / 1000 if self.simulado else time.time()

    def frases(self, tramos):
        """tramos: iterable de arrays int16 de 30 ms. Devuelve (audio, hora_fin)."""
        voz, silencio, dentro, n = [], 0, False, 0
        for tramo in tramos:
            n += 1
            if not dentro and n % 10 == 0:
                yield None, self.reloj(n)          # latido: deja cerrar órdenes por tiempo
            if isinstance(tramo, str):           # «FIN_VOZ»: el asistente acaba de callar
                yield tramo, self.reloj(n)
                continue
            if tramo is None:      # el asistente está hablando: se descarta lo que hubiera
                voz, silencio, dentro = [], 0, False
                continue
            hay_voz = self.vad.is_speech(tramo.tobytes(), TASA)
            if hay_voz:
                voz.append(tramo); silencio = 0; dentro = True
            elif dentro:
                voz.append(tramo); silencio += 1
                if silencio * TRAMO_MS / 1000 >= FIN_FRASE_S or len(voz) * TRAMO_MS / 1000 > MAX_FRASE_S:
                    audio = np.concatenate(voz)
                    if len(audio) / TASA >= MIN_FRASE_S:
                        yield audio.astype(np.float32) / 32768.0, self.reloj(n)
                    voz, silencio, dentro = [], 0, False


def cerebro(frases, enviar=enviar_a_claude, avisar=sonido, reloj=time.time):
    """Decide qué frases van al asistente. Devuelve lo enviado (para las pruebas)."""
    enviados, orden, ultima, ventana, otro_hasta = [], None, 0.0, 0.0, 0.0
    for audio, fin in frases:
        if isinstance(audio, str):
            if audio == "OTRO_AUDIO":                 # suena un vídeo/música: solo con «Oye, Claude»
                ventana = 0.0
                otro_hasta = fin + 1.0
            elif not PAUSA.exists() and orden is None and not turno_en_marcha():
                ventana = fin + VENTANA_S                 # el asistente acaba de contestar (no una frase de
                                                          # espera mientras sigue trabajando)
            continue
        if orden is not None:
            limite = SIN_ORDEN_S if orden == "" else ESPERA_ORDEN_S
            ahora = fin if audio is None else fin - len(audio) / TASA
            if ahora - ultima >= limite:              # se acabó la orden: va al asistente
                enviados += despachar(orden, enviar, avisar); orden = None
        if audio is None:
            continue
        texto = transcribir(audio, VOCABULARIO if orden is not None else None)
        if DEPURAR: print(f"  [{fin:.1f}s dur={len(audio)/TASA:.1f} orden={orden!r}] {texto!r}")
        if orden is not None:                         # ya oí «Oye, Claude»: sigo recogiendo
            orden = (orden + " " + texto).strip(); ultima = fin - FIN_FRASE_S
            if fin < otro_hasta:                      # con un vídeo sonando no se sigue recogiendo:
                enviados += despachar(orden, enviar, avisar); orden = None   # lo demás sería el vídeo
            continue
        m = AVISO.match(normal(texto))
        empezo = fin - len(audio) / TASA
        if not m and texto and empezo < ventana and not PAUSA.exists():
            ventana = 0.0                             # respuesta sin «Oye, Claude», dentro de la ventana
            avisar("Tink")
            orden, ultima = transcribir(audio, VOCABULARIO) or texto, fin - FIN_FRASE_S
            continue
        if not m:
            continue
        r2 = re.match(r"^\W*\w+(?:\s+a)?\W+\w+(.*)$", texto, re.S)
        resto = (r2.group(1) if r2 else "").strip(" ,.;:!?¡¿…")
        if PAUSA.exists():                            # dormido: solo atiende a «despierta»
            if normal(resto).startswith("despierta"):
                PAUSA.unlink(); (PAUSA.parent / "APAGADA").unlink(missing_ok=True)
                avisar("Glass"); apuntar("despierto por voz")
            continue
        avisar("Tink")
        ventana = 0.0
        orden, ultima = resto, fin - FIN_FRASE_S
        if fin < otro_hasta:                          # con un vídeo sonando, va tal cual o nada:
            if orden:                                 # esperar la frase siguiente cogería el vídeo
                enviados += despachar(orden, enviar, avisar)
            else:
                avisar("Basso"); apuntar("aviso oído con otro audio sonando y sin orden: descartado")
            orden = None
    if orden:
        enviados += despachar(orden, enviar, avisar)
    return enviados


def despachar(orden, enviar, avisar):
    n = normal(orden).strip(" .,!?¡¿")
    if not n or n in PARAR:
        apuntar("aviso oído, sin orden"); return []
    if n.startswith(("a dormir", "duermete")):
        if "--prueba" not in sys.argv:
            PAUSA.touch(); (PAUSA.parent / "APAGADA").touch()     # dormir = oído y voz
        avisar("Bottle"); apuntar("pausa por voz"); return []
    try:
        enviar(orden)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        avisar("Basso")
        apuntar("NO ENVIADO: el Mac no deja escribir en Claude; faltan permisos para python3.12: Accesibilidad y/o Automatización (controlar «System Events» y la app)")
        return []
    avisar("Pop")
    apuntar(f"enviado: {orden}")
    return [orden]


def micro():
    """Tramos del micrófono en vivo; None si al GRABARLOS sonaba el asistente (o cualquier audio suyo).

    Un hilo mira cada 0,2 s si suena algo y cada tramo se etiqueta en el momento de grabarse.
    Así no importa que la transcripción vaya con retraso: lo grabado mientras sonaba un audio
    se descarta siempre. Se guarda medio segundo de margen por el eco de la sala.
    """
    import threading
    import sounddevice as sd
    cola = queue.Queue()
    estado = {"suena": False, "hasta": 0.0, "asistente": False, "otro_audio": False}

    def vigilar():
        # Mientras habla el asistente no se escucha. Si suena OTRA cosa en el Mac (vídeo, música…) se
        # sigue escuchando, pero solo vale «Oye, Claude»: la ventana sin aviso se cierra. (No se ensordece del todo:
        # hay apps que dejan la salida de audio abierta sin sonar y lo dejarían sordo.)
        while True:
            habla = asistente_hablando()
            estado["otro_audio"] = (not habla) and mac_sonando()
            if habla:
                estado["suena"] = True; estado["hasta"] = time.time() + 0.7
            elif time.time() > estado["hasta"]:
                estado["suena"] = False
            estado["asistente"] = habla or (estado["asistente"] and estado["suena"])
            time.sleep(0.4)

    threading.Thread(target=vigilar, daemon=True).start()

    def llega(datos, *_):
        cola.put((datos[:, 0].copy(), estado["suena"], estado["asistente"], estado["otro_audio"]))

    with sd.InputStream(samplerate=TASA, channels=1, dtype="int16",
                        blocksize=MUESTRAS_TRAMO, callback=llega):
        primeros = [cola.get()[0] for _ in range(60)]          # ~2 s para comprobar el micro
        nivel = int(np.abs(np.concatenate(primeros)).max())
        apuntar(f"escuchando (nivel del micro {nivel})" if nivel > 0 else
                "SIN SONIDO: el micro llega en silencio absoluto; falta el permiso de micrófono")
        era_asistente = False
        while True:
            tramo, suena, habla, otro = cola.get()
            if era_asistente and not suena and not otro:   # acaba de callar el asistente y no suena nada más
                yield "FIN_VOZ"
            if otro:
                yield "OTRO_AUDIO"                     # cierra la ventana de conversación
            era_asistente = habla if suena else False
            yield None if suena else tramo


def recortar_registros():
    for f in (REGISTRO, CASA / "salida.log"):
        if f.exists():
            lineas = f.read_text(errors="ignore").splitlines()[-500:]
            f.write_text("\n".join(lineas) + "\n")


def principal():
    if "--prueba" in sys.argv:
        # --prueba a.wav [pausa_s] b.wav ...: una sola tira de audio con silencios entre medias
        import wave
        oido = Oido(); oido.simulado = True
        trozos, hueco = [], 2.5
        for arg in sys.argv[sys.argv.index("--prueba") + 1:]:
            if arg.replace(".", "").isdigit():
                hueco = float(arg); continue
            if arg == "VOZ":
                trozos.append("FIN_VOZ"); continue
            with wave.open(arg) as w:
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                if w.getframerate() != TASA:
                    x = np.linspace(0, len(pcm), int(len(pcm) * TASA / w.getframerate()), endpoint=False)
                    pcm = np.interp(x, np.arange(len(pcm)), pcm).astype(np.int16)
            trozos += [np.zeros(int(TASA * hueco), dtype=np.int16), pcm]
            hueco = 2.5
        tramos = []
        for t in trozos + [np.zeros(TASA * 10, dtype=np.int16)]:
            if isinstance(t, str):
                tramos.append(t); continue
            tramos += [t[i:i + MUESTRAS_TRAMO] for i in range(0, len(t) - MUESTRAS_TRAMO + 1, MUESTRAS_TRAMO)]
        salida = cerebro(oido.frases(tramos), enviar=lambda t: print("ENVIARÍA:", t),
                         avisar=lambda s: print("  (sonido", s + ")"))
        print("RESULTADO:", salida)
        return
    recortar_registros()
    transcribir(np.zeros(TASA, dtype=np.float32))   # carga el modelo antes de escuchar
    cerebro(Oido().frases(micro()))


if __name__ == "__main__":
    principal()
