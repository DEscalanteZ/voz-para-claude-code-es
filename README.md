# Ya no le escribo a Claude Code: le digo «Oye, Claude», me contesta hablando y no me cuesta ni un euro

**Gratis, sin claves, y la voz y el oído no salen de tu Mac.** Dices «Oye, Claude» o el nombre que tenga tu Agente, te escucha, trabaja y te lo cuenta hablando.

**Versión 0.1** · Si algo falla o no se sostiene, [abre un aviso (issue)](https://github.com/DEscalanteZ/voz-para-claude-code-es/issues).

> 🇬🇧 **[English summary → README.en.md](README.en.md)**

Hablarle a Claude Code sin tocar el teclado, y que conteste en voz alta. Sin suscripciones ni
claves: la voz (Piper) y la transcripción (Whisper con MLX) corren en tu propio Mac.

## Qué hace

1. **Contesta hablando.** Cuando Claude Code termina una respuesta, el Mac lee en voz alta el
   primer párrafo, sin código, tablas ni rutas.
2. **Si la respuesta es larga**, lee el titular y pregunta «¿Quieres que te lea el texto
   completo?». Si dices «sí», la lee tu Mac **sin volver a pasar por el modelo**: ni gasta ni
   hace esperar. No lo pregunta si la respuesta acaba con una pregunta del propio Claude, para
   no quedarse con un «sí» que era para él.
3. **Avisa mientras trabaja.** Si tarda, dice «Déjame mirarlo» y, como mucho cada 15 segundos,
   algo como «Sigo con ello, por eso tardo». Va unido a las herramientas: lo dice cuando Claude
   usa una (leer, buscar, ejecutar); si una sola tarda mucho, se queda callado mientras dura.
4. **«Oye, Claude».** Dices «Oye, Claude, …» y la frase se transcribe, se pega en la app de
   Claude y se envía. Al terminar su respuesta hablada tienes 8 segundos para contestar sin
   repetir «Oye, Claude», como en una conversación.

## Requisitos

Mac con Apple Silicon, la app de escritorio de Claude con Claude Code, `python3`, [`uv`](https://docs.astral.sh/uv/)
(`brew install uv`) y unos 3 GB libres. La primera vez descarga ~600 MB (programas, voz y modelo
de transcripción).

## Instalación

```bash
git clone https://github.com/DEscalanteZ/voz-para-claude-code-es
cd voz-para-claude-code-es
bash instalar.sh
```

El instalador hace copia de `~/.claude/settings.json` antes de tocarlo, añade tres ganchos de
Claude Code (Stop, UserPromptSubmit y PreToolUse) sin duplicar nada y arranca dos servicios
(LaunchAgents): el de la voz y el del oído. Se para si `settings.json` no es JSON estricto o si
`~/.claude/voz/` u `~/.claude/oye/` ya tienen algo que no puso él.

**Permisos que tienes que dar tú** (los pide el Mac, todos para el mismo programa, que aparece
como «Python» o «python3.12»): Micrófono y, la primera vez que envíe algo, Accesibilidad y
Automatización. Ese Python puede usarlo también otro programa tuyo: tenlo en cuenta antes de
aceptar.

## Uso

| Quieres | Di o haz |
|---|---|
| Pedirle algo | «Oye, Claude, …» (espera el tintineo si haces pausa) |
| Que lea entera una respuesta larga | «Sí» / «léemelo» / «todo» |
| Volver a oír la última respuesta | «Léeme la última respuesta» |
| Que deje de escuchar | «Oye, Claude, a dormir» (y «Oye, Claude, despierta») |
| Silenciar la voz | crear `~/.claude/voz/APAGADA` |
| Cambiar la voz (tono, ritmo, hombre/mujer) | `~/.claude/voz/voz.json` |
| Cambiar la palabra de aviso o el vocabulario | `~/.claude/oye/config.json` |

Los cambios de voz se aplican en la siguiente frase; los del oído, al reiniciar su servicio:
`launchctl kickstart -k gui/$(id -u)/com.voz-claude-code.voz` (o `.oye`).

Para probar el oído sin micrófono: `oye/oye.py --depurar --prueba frase.wav`, dentro del
entorno de `~/.claude/oye/.venv`.

## Personalízalo: la voz y el nombre

**Todo lo que usa es gratuito** (Piper, Whisper y las voces del Mac). Puedes cambiarlo a tu gusto:

- **El nombre al que llamas.** Por defecto es «Oye, Claude», pero puedes ponerle el que quieras
  («Oye, Luna», «Oye, Max»…). En `~/.claude/oye/config.json`, cambia `nombres` por tu nombre y
  las formas en que Whisper suele escribirlo (por ejemplo `"luna|lluna"`), y `primeras` si
  prefieres otra llamada que «oye». Mira en `~/.claude/oye/oye.log` cómo lo transcribe y añade
  esas variantes. Reinicia el oído para aplicarlo.
- **Otra voz gratuita de Piper.** Hay decenas, en muchos idiomas y acentos
  ([lista y muestras](https://rhasspy.github.io/piper-samples/)). Descarga el `.onnx` y su
  `.onnx.json` en `~/.claude/voz/`, escribe en `~/.claude/voz/voz.txt` `piper:<nombre-del-modelo>`
  y reinicia el servicio de voz. En `voz.json` ajustas ritmo, tono y expresividad, y en los
  modelos con varias voces, `hablante` elige cuál.
- **Una voz del propio Mac.** Escribe en `voz.txt` el nombre exacto de una voz del sistema (las
  ves con `say -v '?'`; las «mejoradas» se descargan gratis en Ajustes del Sistema →
  Accesibilidad → Contenido leído).
- **Una voz de pago** (por ejemplo, de un servicio de voz por internet). No viene incluida, pero
  se puede enchufar: toda la voz pasa por la función `generar()` de `voz/servidor_piper.py`, que
  recibe un texto y debe dejar un fichero `.wav`. Cambiándola por una llamada a tu proveedor,
  todo lo demás funciona igual. Ten en cuenta que entonces el texto de las respuestas saldría de
  tu Mac hacia ese servicio, y que cada frase costaría dinero.

## Lo que conviene saber

- **Qué es local y qué no:** la voz y la transcripción, sí (las librerías pueden consultar
  Hugging Face para comprobar los modelos, sin enviar audio). Lo que dices con «Oye, Claude» llega
  a Claude como si lo escribieras. En los 8 segundos de conversación, si alguien habla cerca,
  también le llegaría.
- No escucha mientras habla el propio asistente. Si suena otro audio en el Mac (vídeo, música),
  la ventana de conversación se cierra y solo vale «Oye, Claude» con la orden seguida.
- Antes de pegar, trae la app de Claude al frente; si aun así no queda delante, no pega nada.
  Pega en la conversación que esté abierta: si tienes un borrador a medias, se envía junto.
  Usa el portapapeles y luego lo devuelve, pero solo como texto: una imagen copiada se pierde.
- Con el micro siempre abierto, el Mac no se duerme solo por inactividad (cerrar la tapa sí).
- Antes de una videollamada, mejor «Oye, Claude, a dormir».
- Si actualizas Python con Homebrew, el Mac puede olvidar los permisos: vuelve a darlos (el
  registro `~/.claude/oye/oye.log` dirá «SIN SONIDO» o «NO ENVIADO»).
- Un `claude -p` lanzado desde una sesión no habla: se detecta mirando los procesos.

## Desinstalar

`bash desinstalar.sh`: para y borra los dos servicios, quita solo sus tres ganchos de
`settings.json` (con copia) y borra `~/.claude/voz` y `~/.claude/oye` si los creó el instalador
(llevan una marca; si no, los deja y avisa). Los permisos del Mac se
retiran a mano en Ajustes del Sistema → Privacidad y seguridad.

## Hecho con

[Piper](https://github.com/OHF-Voice/piper1-gpl) (`piper-tts`, licencia GPL-3.0-or-later: el
instalador lo descarga, no va en este repositorio; si redistribuyes el conjunto, rigen sus
condiciones), [Whisper](https://github.com/openai/whisper) en
[MLX](https://github.com/ml-explore/mlx-examples) (`whisper-small`) y
[webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels). Voz
[`es_ES-sharvard-medium`](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_ES/sharvard/medium),
entrenada con el corpus [Sharvard](https://datashare.ed.ac.uk/handle/10283/574) de Aubanel,
García Lecumberri y Cooke (CC BY 3.0) a partir de la voz inglesa «lessac», cuyo corpus tiene
[su propia licencia](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html):
revísala si vas a usar la voz para algo más que uso personal. Antes de publicarlo, revisores en frío
intentaron tumbarlo en varias rondas; lo que encontraron está corregido o aparece arriba.

**Otros repositorios:** [patrones con agentes](https://github.com/DEscalanteZ/ai-agent-patterns-es) ·
[bitácora de averías](https://github.com/DEscalanteZ/bitacora-de-averias-es) ·
[comunicación entre dos Claude Code](https://github.com/DEscalanteZ/comunicacion-entre-dos-claude-code-es)

Si te sirve, una ⭐ ayuda a que lo encuentre más gente.

El código de este repositorio va bajo licencia MIT (ver [LICENSE](LICENSE)); cada dependencia
conserva la suya.
