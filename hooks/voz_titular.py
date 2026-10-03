#!/usr/bin/env python3
"""Lee en voz alta el titular de cada respuesta de Claude Code (gancho Stop).

- Lee el primer párrafo (hasta ~320 caracteres), sin código, tablas, rutas ni enlaces.
- Respuesta larga: lee el titular y pregunta «¿Quieres que te lea el texto completo?». El texto
  limpio queda en ~/.claude/voz/pendiente_larga.txt; si contestas «sí», lo lee voz_leer_todo.py
  (gancho UserPromptSubmit) sin volver a pasar por el modelo. No lo pregunta si la respuesta
  acaba con una pregunta del propio modelo, para no quedarse con un «sí» que era para él.
- Solo habla en sesiones con alguien delante (app de escritorio o terminal): nunca en `claude -p`.
- Se apaga creando ~/.claude/voz/APAGADA. La voz se elige en ~/.claude/voz/voz.txt.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DIR = Path.home() / ".claude" / "voz"
INTERACTIVAS = {"claude-desktop", "cli"}
MAX_CHARS = 320
LARGA = 700        # caracteres de texto limpio a partir de los cuales se ofrece leerlo entero
PREGUNTA = " ¿Quieres que te lea el texto completo?"


def es_interactiva() -> bool:
    """Sesión con alguien delante: app o terminal, y ningún proceso padre en modo -p.

    Un `claude -p` lanzado desde una sesión de la app hereda CLAUDE_CODE_ENTRYPOINT=claude-desktop
    (comprobado), así que la variable sola no basta.
    """
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") not in INTERACTIVAS:
        return False
    pid = os.getppid()
    for _ in range(6):
        try:
            r = subprocess.run(["ps", "-o", "ppid=,args=", "-p", str(pid)],
                               capture_output=True, text=True, timeout=2)
        except Exception:
            return True
        linea = r.stdout.strip()
        if not linea:
            break
        ppid, _, args = linea.partition(" ")
        if re.search(r"\bclaude\b.*\s(-p|--print)(\s|$)", args):
            return False
        pid = int(ppid) if ppid.strip().isdigit() else 1
        if pid <= 1:
            break
    return True


def limpiar(texto: str) -> str:
    """Todo el texto, apto para leer en voz alta: sin código, tablas, rutas ni enlaces."""
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    lineas = [l for l in texto.splitlines() if not l.lstrip().startswith(("|", ">"))]
    t = "\n".join(lineas)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"`[^`]*`", "", t)
    t = re.sub(r"(~|/)[\w./-]+", "", t)
    t = re.sub(r"[*_#>]+", "", t)
    t = re.sub(r"(?m)^\s*(?:[-•]|\d+\.)\s*", "", t)
    t = t.replace("·", ",").replace("—", ", ").replace("→", ", ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t).strip()
    return t


def voz_actual() -> str:
    voz_f = DIR / "voz.txt"
    return voz_f.read_text().strip() if voz_f.exists() else "Mónica"


def callar() -> None:
    """Corta lo que esté diciendo la voz (también una lectura larga a medias)."""
    if (DIR / "APAGADA").exists():
        return
    if not voz_actual().startswith("piper:"):
        subprocess.run(["pkill", "-x", "say"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "hablar_piper.py"], stderr=subprocess.DEVNULL)
    try:
        import socket
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.settimeout(1)
        c.connect(str(DIR / "piper.sock"))
        c.sendall(b"x\n")
        c.close()
    except OSError:
        subprocess.run(["pkill", "-f", "afplay .*/\\.claude/voz/"], stderr=subprocess.DEVNULL)


def decir(frase: str) -> None:
    """Manda la frase a la voz configurada (servidor ya cargado o, si no, camino lento)."""
    voz = voz_actual()
    if not voz.startswith("piper:"):
        subprocess.run(["pkill", "-x", "say"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "hablar_piper.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "afplay .*/\\.claude/voz/"], stderr=subprocess.DEVNULL)
    sock = DIR / "piper.sock"
    if voz.startswith("piper:") and sock.exists():
        try:
            import socket
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            c.settimeout(1)
            c.connect(str(sock))
            c.sendall(f"{voz[6:]}\n{frase}".encode())
            c.close()
            return
        except OSError:
            pass
    if voz.startswith("piper:"):
        orden = [str(DIR / ".venv/bin/python"), str(DIR / "hablar_piper.py"),
                 str(DIR / (voz[6:] + ".onnx")), frase]
    else:
        orden = ["say", "-v", voz, "-r", "190", frase]
    subprocess.Popen(orden, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def titular(texto: str) -> str:
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)  # bloques de código fuera
    parrafo = ""
    for bloque in re.split(r"\n\s*\n", texto):
        lineas = [l for l in bloque.splitlines()
                  if l.strip() and not l.lstrip().startswith(("|", ">"))]
        if lineas:
            parrafo = " ".join(lineas)
            break
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", parrafo)   # [texto](enlace) -> texto
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"`[^`]*`", "", t)                          # rutas y código en línea
    t = re.sub(r"(~|/)[\w./-]+", "", t)                    # rutas sueltas
    t = re.sub(r"[*_#>]+", "", t)
    t = re.sub(r"^\s*[-•]\s*", "", t)
    t = t.replace("·", ",").replace("—", ", ").replace("→", ", ")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > MAX_CHARS:
        corte = max(t.rfind(". ", 0, MAX_CHARS), t.rfind(": ", 0, MAX_CHARS))
        t = t[: corte + 1] if corte > 80 else t[:MAX_CHARS].rsplit(" ", 1)[0]
    return t


def main() -> None:
    try:
        (DIR / "turno.json").unlink()      # fin del turno: se acaban las frases de espera
    except FileNotFoundError:
        pass
    if not es_interactiva():
        return
    if (DIR / "APAGADA").exists():
        return
    try:
        datos = json.load(sys.stdin)
    except Exception:
        return
    mensaje = datos.get("last_assistant_message") or ""
    frase = titular(mensaje)
    if not frase:
        return
    completo = limpiar(mensaje)
    pendiente = DIR / "pendiente_larga.txt"
    (DIR / "ultima_respuesta.txt").write_text(completo)
    # Si la respuesta acaba con una pregunta SUYA, el «sí»/«no» que venga es para el modelo:
    # entonces no se ofrece leerla entera (si no, la voz se comería esa respuesta).
    # Se mira el último párrafo con texto: «¿Lo subo? Dime y lo hago.», «¿Sigo? 🙂» o una
    # pregunta seguida de un enlace también cuentan como pregunta.
    # Ante la duda, no se ofrece: basta un «?» en los tres últimos párrafos con texto o en los
    # últimos 400 caracteres (una pregunta seguida de una ruta, un enlace o una nota).
    bloques = [b for b in re.split(r"\n\s*\n", mensaje.strip()) if re.search(r"\w", b)]
    acaba_preguntando = any("?" in b for b in bloques[-3:]) or "?" in mensaje.strip()[-400:]
    if len(completo) > LARGA and not acaba_preguntando:
        pendiente.write_text(json.dumps({"sesion": datos.get("session_id", ""), "texto": completo},
                                        ensure_ascii=False))
        frase += PREGUNTA
    elif pendiente.exists():
        pendiente.unlink()
    decir(frase)


if __name__ == "__main__":
    main()
