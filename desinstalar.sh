#!/bin/bash
# Quita la voz y «Oye, Claude» sin tocar nada más de la configuración de Claude Code.
set -u
U=$(id -u); LA="$HOME/Library/LaunchAgents"
for e in com.voz-claude-code.voz com.voz-claude-code.oye; do
  launchctl bootout "gui/$U/$e" 2>/dev/null; rm -f "$LA/$e.plist"
done
S="$HOME/.claude/settings.json"
if [ -f "$S" ]; then
  cp "$S" "$S.antes_quitar_voz_$(date +%Y%m%d%H%M%S)"
  python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
for ev, g in list(d.get("hooks", {}).items()):
    d["hooks"][ev] = [x for x in g if not any(n in h.get("command", "") for h in x.get("hooks", [])
                                              for n in ("voz_titular.py", "voz_leer_todo.py", "voz_avance.py"))]
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print("ganchos de voz quitados de settings.json (copia guardada al lado)")
PY
fi
rm -f "$HOME/.claude/hooks/voz_titular.py" "$HOME/.claude/hooks/voz_leer_todo.py" "$HOME/.claude/hooks/voz_avance.py"
for D in "$HOME/.claude/voz" "$HOME/.claude/oye"; do
  if [ -f "$D/.voz-claude-code" ]; then rm -rf "$D"; else [ -d "$D" ] && echo "No borro $D: no lo puso este instalador."; fi
done
echo "Los permisos de Micrófono, Accesibilidad y Automatización de «python3.12» se quitan a mano en"
echo "Ajustes del Sistema → Privacidad y seguridad (ese Python puede usarlo otro programa)."
echo "Quitado. El modelo de transcripción (~480 MB) sigue en ~/.cache/huggingface por si otra herramienta lo usa; se puede borrar a mano."
