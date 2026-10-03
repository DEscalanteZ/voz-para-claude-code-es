#!/usr/bin/env python3
"""Frases de espera mientras Claude trabaja (gancho PreToolUse).

Si tiene que mirar o investigar antes de contestar, la voz dice algo corto para que sepas que
está en ello: a partir de 4 s del mensaje («Déjame mirarlo») y luego cada 15 s («Sigo con ello,
por eso tardo»). El reloj del turno lo pone voz_leer_todo.py en ~/.claude/voz/turno.json y lo
borra voz_titular.py al terminar.
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from voz_titular import DIR, decir, es_interactiva  # noqa: E402

PRIMERO_S = 4        # antes de esto no se dice nada: las respuestas rápidas no lo necesitan
CADA_S = 15
PRIMERAS = ["Déjame mirarlo.", "Vale, te lo miro.", "Un momento, lo compruebo.", "Lo miro y te digo."]
SIGUIENTES = ["Sigo mirándolo, ¿eh?", "Estoy en ello, por eso tardo.", "Sigo con ello, dame un momento.",
              "Todavía lo estoy comprobando."]


def main() -> None:
    turno_f = DIR / "turno.json"
    if (DIR / "APAGADA").exists() or not turno_f.exists():
        return
    try:
        sesion = json.load(sys.stdin).get("session_id", "")
        t = json.loads(turno_f.read_text())
    except Exception:
        return
    if t.get("sesion") and sesion and t["sesion"] != sesion:
        return
    ahora = time.time()
    if ahora - t["inicio"] < PRIMERO_S:
        return
    if t.get("ultimo") and ahora - t["ultimo"] < CADA_S:
        return
    if not es_interactiva():
        return
    frase = random.choice(SIGUIENTES if t.get("ultimo") else PRIMERAS)
    t["ultimo"] = ahora
    turno_f.write_text(json.dumps(t))
    decir(frase)


if __name__ == "__main__":
    main()
