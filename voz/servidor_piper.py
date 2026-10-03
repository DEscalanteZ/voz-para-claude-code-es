"""Voz siempre lista: deja Piper cargado para no perder ~1,3 s por frase.

Escucha en ~/.claude/voz/piper.sock. Cada conexión trae «modelo
frase»: la genera y la
reproduce, trozo a trozo si es larga. Si llega otra frase, corta la anterior; un mensaje sin
frase la hace callar. Si este servicio no está, voz_titular.py usa hablar_piper.py.
"""
import os
import socket
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

DIR = Path(__file__).parent
SOCK = DIR / "piper.sock"
voces = {}
reproductor = None
cerrojo = threading.Lock()


def ajustes():
    """voz.json (opcional): hablante, ritmo, entonacion, variacion, tono. Sin él, la voz por defecto del modelo."""
    import json
    f = DIR / "voz.json"
    a = json.loads(f.read_text()) if f.exists() else {}
    vel_f = DIR / "velocidad.txt"
    a.setdefault("ritmo", float(vel_f.read_text().strip()) if vel_f.exists() else 0.8)
    return a


def generar(nombre, texto, ruta):
    """Genera el audio. «tono» > 1 sube la voz: se genera algo más lenta y se reproduce más
    rápida (cambiando la frecuencia de muestreo), así el ritmo final queda igual."""
    a = ajustes()
    tono = a.get("tono", 1.0)
    cfg = SynthesisConfig(speaker_id=a.get("hablante"), length_scale=a["ritmo"] * tono,
                          noise_scale=a.get("entonacion"), noise_w_scale=a.get("variacion"))
    with wave.open(ruta, "wb") as w:
        voz(nombre).synthesize_wav(texto, w, syn_config=cfg)
    if tono != 1.0:
        with wave.open(ruta, "rb") as r:
            params, datos = r.getparams(), r.readframes(r.getnframes())
        with wave.open(ruta, "wb") as w:
            w.setparams(params)
            w.setframerate(int(params.framerate * tono))
            w.writeframes(datos)


def voz(nombre):
    if nombre not in voces:
        voces[nombre] = PiperVoice.load(str(DIR / f"{nombre}.onnx"))
    return voces[nombre]


def trozos(texto, largo=260):
    """Parte un texto largo en frases de ~260 caracteres para empezar a hablar enseguida."""
    import re
    frases = re.split(r"(?<=[.!?:;])\s+|\n+", texto)
    actual = ""
    for f in frases:
        f = f.strip()
        if not f:
            continue
        if actual and len(actual) + len(f) > largo:
            yield actual
            actual = f
        else:
            actual = f"{actual} {f}".strip()
    if actual:
        yield actual


turno = [0]


def callar():
    with cerrojo:
        turno[0] += 1
        if reproductor and reproductor.poll() is None:
            reproductor.terminate()


def decir(nombre, frase):
    """Lee la frase (o un texto largo, trozo a trozo). Si llega otra, esta se calla."""
    global reproductor
    with cerrojo:
        turno[0] += 1
        mio_turno = turno[0]
        if reproductor and reproductor.poll() is None:
            reproductor.terminate()
    for trozo in trozos(frase):
        if turno[0] != mio_turno:
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=DIR / "tmp") as f:
            ruta = f.name
        generar(nombre, trozo, ruta)
        with cerrojo:
            if turno[0] != mio_turno:
                os.unlink(ruta)
                return
            reproductor = mio = subprocess.Popen(["afplay", ruta])
        mio.wait()
        os.unlink(ruta)


def main():
    (DIR / "tmp").mkdir(exist_ok=True)
    vt = DIR / "voz.txt"                    # se carga ya, antes de la primera frase
    voz(vt.read_text().strip()[6:] if vt.exists() and vt.read_text().startswith("piper:")
        else "es_ES-sharvard-medium")
    if SOCK.exists():
        SOCK.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCK))
    srv.listen(4)
    while True:
        con, _ = srv.accept()
        datos = b""
        while chunk := con.recv(65536):
            datos += chunk
        con.close()
        nombre, _, frase = datos.decode().partition("\n")
        if frase.strip():
            threading.Thread(target=decir, args=(nombre, frase), daemon=True).start()
        else:                                  # mensaje vacío = callarse ya
            callar()


if __name__ == "__main__":
    main()
