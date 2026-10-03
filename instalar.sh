#!/bin/bash
# Voz para Claude Code: (1) lee en voz alta el titular de cada respuesta, ofrece leer entero lo
# largo y avisa mientras trabaja; (2) «Oye, Claude» para hablarle sin tocar nada.
# Voz (Piper) y transcripción (Whisper con MLX) en local; lo que dices con «Oye, Claude» llega a
# Claude como si lo escribieras.
# Se puede ejecutar más de una vez: no duplica nada y guarda copia de settings.json antes de tocarlo.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
VOZ="$HOME/.claude/voz"; HOOKS="$HOME/.claude/hooks"; OYE="$HOME/.claude/oye"
LA="$HOME/Library/LaunchAgents"; U=$(id -u)

echo "== 1/6 Comprobaciones"
[ "$(uname -m)" = "arm64" ] || { echo "ALTO: este Mac no es Apple Silicon; «Oye, Claude» usa MLX y no funcionará."; exit 1; }
command -v uv >/dev/null || { echo "ALTO: falta 'uv' (gestor de Python). Instálalo con: brew install uv   y vuelve a lanzar este script."; exit 1; }
python3 -c "import json" 2>/dev/null || { echo "ALTO: falta python3 (herramientas de línea de comandos de Apple): xcode-select --install"; exit 1; }
LIBRE=$(df -g "$HOME" | awk 'NR==2{print $4}')
[ "$LIBRE" -ge 3 ] || { echo "ALTO: quedan ${LIBRE} GB libres; hacen falta unos 2 GB más margen (voz + modelo de transcripción)."; exit 1; }
S="$HOME/.claude/settings.json"
[ ! -f "$S" ] || python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$S" 2>/dev/null || { echo "ALTO: $S no es JSON estricto (¿comentarios o comas finales?). Arréglalo antes; no toco nada."; exit 1; }
for D in "$VOZ" "$OYE"; do   # solo se instala encima de lo que puso este mismo kit
  [ -d "$D" ] && [ -n "$(ls -A "$D" 2>/dev/null)" ] && [ ! -f "$D/.voz-claude-code" ] && { echo "ALTO: $D ya existe y no es de este kit. No lo piso: revisa a mano."; exit 1; }
done

echo "== 2/6 Voz (Piper, en local)"
mkdir -p "$VOZ/tmp" "$HOOKS" "$OYE"
touch "$VOZ/.voz-claude-code" "$OYE/.voz-claude-code"
for f in "$KIT"/voz/*; do   # al relanzar, no se pisan los ajustes que hayas cambiado
  # (no «cp -n»: devuelve error si ya existe y set -e cortaría el script al relanzarlo)
  case "$(basename "$f")" in voz.json|voz.txt) [ -e "$VOZ/$(basename "$f")" ] || cp "$f" "$VOZ/" ;; *) cp "$f" "$VOZ/" ;; esac
done
[ -x "$VOZ/.venv/bin/python" ] || uv venv -q -p 3.12 "$VOZ/.venv"
uv pip install -q -p "$VOZ/.venv" "piper-tts==1.8.0"
M=es_ES-sharvard-medium; URLVOZ=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium
for x in onnx onnx.json; do
  # se baja a un .part y solo se renombra si termina: una descarga cortada no deja la voz rota
  [ -s "$VOZ/$M.$x" ] || { curl -fsSL -o "$VOZ/$M.$x.part" "$URLVOZ/$M.$x" && mv "$VOZ/$M.$x.part" "$VOZ/$M.$x"; } || { rm -f "$VOZ/$M.$x.part"; echo "ALTO: no se pudo descargar la voz ($M.$x)."; exit 1; }
done

echo "== 3/6 Ganchos de Claude Code (titular en voz alta + «¿te lo leo entero?»)"
cp "$KIT"/hooks/voz_titular.py "$KIT"/hooks/voz_leer_todo.py "$KIT"/hooks/voz_avance.py "$HOOKS/"
[ -f "$S" ] || echo '{}' > "$S"
cp "$S" "$S.antes_kit_voz_$(date +%Y%m%d%H%M%S)"
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
h = d.setdefault("hooks", {})
def poner(evento, orden):
    lista = h.setdefault(evento, [])
    if any(orden in x.get("command", "") for g in lista for x in g.get("hooks", [])):
        return
    lista.append({"hooks": [{"type": "command", "command": orden, "timeout": 5}]})
poner("Stop", 'python3 "$HOME/.claude/hooks/voz_titular.py"')
poner("UserPromptSubmit", 'python3 "$HOME/.claude/hooks/voz_leer_todo.py"')
poner("PreToolUse", 'python3 "$HOME/.claude/hooks/voz_avance.py"')
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("   settings.json actualizado (copia guardada al lado)")
PY

echo "== 4/6 «Oye, Claude» (transcripción local con Whisper)"
cp "$KIT"/oye/oye.py "$OYE/"; [ -e "$OYE/config.json" ] || cp "$KIT"/oye/config.json "$OYE/"
[ -x "$OYE/.venv/bin/python" ] || uv venv -q -p 3.12 "$OYE/.venv"
uv pip install -q -p "$OYE/.venv" "mlx-whisper==0.4.3" "sounddevice==0.5.6" "webrtcvad-wheels==2.0.14.post1" "numpy==2.5.3"
echo "   descargando el modelo de transcripción (~480 MB, solo la primera vez)…"
"$OYE/.venv/bin/python" -c "import mlx_whisper, numpy as np; mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32), path_or_hf_repo='mlx-community/whisper-small-mlx', language='es')" 2>&1 | grep -vE "it/s|Fetching" || true
"$OYE/.venv/bin/python" -c "from huggingface_hub import snapshot_download as s; s('mlx-community/whisper-small-mlx', local_files_only=True)" >/dev/null 2>&1 || { echo "ALTO: no se pudo descargar el modelo de transcripción (¿sin internet?). Vuelve a lanzar el script."; exit 1; }

echo "== 5/6 Arranque automático (LaunchAgents)"
mkdir -p "$LA"
mk() {  # etiqueta, python, script, log
cat > "$LA/$1.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$1</string>
  <key>ProgramArguments</key><array><string>$2</string><string>$3</string></array>
  <key>WorkingDirectory</key><string>$(dirname "$3")</string>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>EnvironmentVariables</key><dict><key>LANG</key><string>es_ES.UTF-8</string></dict>
  <key>StandardOutPath</key><string>$4</string><key>StandardErrorPath</key><string>$4</string>
</dict></plist>
PL
launchctl bootout "gui/$U/$1" 2>/dev/null && sleep 2 || true
launchctl bootstrap "gui/$U" "$LA/$1.plist" || { sleep 3; launchctl bootstrap "gui/$U" "$LA/$1.plist"; }
}
mk com.voz-claude-code.voz "$VOZ/.venv/bin/python" "$VOZ/servidor_piper.py" "$VOZ/servidor.log"
mk com.voz-claude-code.oye "$OYE/.venv/bin/python" "$OYE/oye.py" "$OYE/salida.log"

echo "== 6/6 Prueba de voz"
sleep 5
python3 -c "import sys; sys.path.insert(0, sys.argv[1]); from voz_titular import decir; decir('¡Hola! Ya tengo voz. Cuando quieras, di: Oye, Claude.')" "$HOOKS"
echo
PY=$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$OYE/.venv/bin/python")
APP_PY="$(dirname "$(dirname "$PY")")/Resources/Python.app"   # el Python de Homebrew pide los permisos como esta app
[ -d "$APP_PY" ] && PY="$APP_PY"
echo "LISTO. Faltan permisos que tienes que dar tú (ventanas del Mac). El programa puede salir"
echo "como «Python» o como «python3.12»: es el mismo."
echo "  • Micrófono → Permitir."
echo "  • La primera vez que envíe algo: Accesibilidad (encender el interruptor) y"
echo "    Automatización («quiere controlar System Events / Claude») → Permitir."
echo "  Accesibilidad admite añadirlo a mano con «+»: $PY"
echo "  (Micrófono no tiene «+»: si no sale su ventana, reinicia el servicio para que la pida otra vez.)"
echo "Registro de lo que oye: $OYE/oye.log"
