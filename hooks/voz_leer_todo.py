#!/usr/bin/env python3
"""Respuesta a «¿Quieres que te lea el texto completo?» (gancho UserPromptSubmit).

- «sí», «léemelo», «todo», «entero»…  → se lee en el Mac y el mensaje NO llega al modelo.
- «no», «solo el resumen», «déjalo»…  → se olvida, y tampoco llega al modelo.
- Cualquier otra cosa                  → se olvida lo pendiente y el mensaje sigue su curso
                                         (y si estaba leyendo algo largo, se calla).
- En cualquier momento: «léeme la última respuesta (entera)».
La pregunta caduca a los 90 s y solo vale en la misma conversación en que se hizo.
"""
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from voz_titular import DIR, callar, decir, es_interactiva  # noqa: E402

VIGENCIA_S = 90
# Solo respuestas que son claramente a «¿Quieres que te lea el texto completo?». Además, la voz
# solo pregunta eso cuando la respuesta NO acaba con una pregunta propia del modelo, para que un
# «sí» dirigido al modelo nunca se quede aquí.
SI = re.compile(r"^(si|si,? (si|claro|venga|por favor|leemelo|leelo|todo|entero|completo)|venga,? si|leemelo|leelo( entero| todo)?|"
                r"todo|entero|completo|el texto completo|el completo|lee(lo)? (todo|entero))\W*$")
NO = re.compile(r"^(no|no,? gracias|solo el resumen|el resumen|dejalo|no hace falta)\W*$")
ULTIMA = re.compile(r"^(leeme|lee|repite(me)?) (la )?(ultima )?(respuesta|lo ultimo)( entera| completa)?\W*$")


def normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower().strip())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"^[¡¿\W]+", "", t).rstrip(" .!?¡¿")


def parar(motivo: str) -> None:
    print(json.dumps({"decision": "block", "reason": motivo}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    if not es_interactiva():
        return
    try:
        entrada = json.load(sys.stdin)
        dicho = normal(entrada.get("prompt") or "")
    except Exception:
        return
    # reloj del turno para las frases de espera (voz_avance.py)
    (DIR / "turno.json").write_text(json.dumps({"sesion": entrada.get("session_id", ""),
                                                 "inicio": time.time()}))
    pendiente = DIR / "pendiente_larga.txt"
    if not (SI.match(dicho) or ULTIMA.match(dicho)):
        callar()                       # mensaje nuevo: si estaba leyendo algo largo, se calla
    if ULTIMA.match(dicho) and (DIR / "ultima_respuesta.txt").exists():
        decir((DIR / "ultima_respuesta.txt").read_text())
        parar("🔊 Te leo la última respuesta entera (en tu Mac, sin pasar por el modelo).")
    if not pendiente.exists():
        return
    vigente = time.time() - pendiente.stat().st_mtime < VIGENCIA_S
    try:
        p = json.loads(pendiente.read_text())
    except Exception:
        p = {}
    if p.get("sesion") and entrada.get("session_id") and p["sesion"] != entrada["session_id"]:
        return                         # la pregunta se hizo en otra conversación: no es para esta
    pendiente.unlink()
    texto = p.get("texto", "")
    if not vigente or not texto:
        return
    if SI.match(dicho):
        decir(texto)
        parar("🔊 Te lo leo entero (en tu Mac, sin pasar por el modelo).")
    if NO.match(dicho):
        parar("Vale, me quedo en el resumen.")


if __name__ == "__main__":
    main()
