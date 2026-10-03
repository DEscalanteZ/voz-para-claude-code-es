# I don't type to Claude Code anymore: I say "Oye, Claude", it answers out loud, and it costs me nothing

**Free, no API keys, and the voice and the ears stay on your Mac.**

**Version 0.1** · Spanish-first project; the full guide is in [README.md](README.md).

Talk to Claude Code hands-free and hear its answers. No subscriptions or API keys: the voice
(Piper) and the transcription (Whisper on MLX) run locally on your Mac.

- **Spoken answers:** when Claude Code finishes, a hook reads the first paragraph aloud (no code,
  tables or paths).
- **Long answers:** it reads the headline and asks whether to read the whole text. If you say
  "sí", your Mac reads it **without another model call**. It doesn't ask when the answer ends
  with Claude's own question, so your "yes" still reaches Claude.
- **Progress cues:** if Claude takes a while, it says (in Spanish) "Déjame mirarlo" and, at most
  every 15 s, "Sigo con ello". It's tied to tool calls, so it stays quiet during one long call.
- **"Oye, Claude":** a background service listens for the wake phrase, transcribes the request,
  checks the Claude app is in front, pastes it and presses Enter. After a spoken answer you get
  an 8-second window to reply without the wake phrase.

**Requirements:** Apple Silicon Mac, the Claude desktop app with Claude Code, `python3`, `uv`,
~3 GB free. Install with `bash instalar.sh`; remove with `bash desinstalar.sh`. You grant
Microphone, Accessibility and Automation to the Python interpreter it uses (which other
programs may share: be aware before accepting).

Everything it uses is free. You can rename the assistant ("Oye, Luna"…), pick any free Piper voice
(many languages) or a macOS system voice, tune pitch and pace, or plug in a paid voice service by
replacing `generar()` in `voz/servidor_piper.py` (text would then leave your Mac, and cost money). The interface
and phrases are in Spanish; the wake phrase can be changed in `config.json`.

MIT licensed (this repository's code). Piper (`piper-tts`) is GPL-3.0-or-later and is downloaded by the
installer, not bundled; the `es_ES-sharvard-medium` voice is trained on the Sharvard corpus (CC BY 3.0)
and fine-tuned from the "lessac" voice, whose corpus has its own licence: check it before non-personal use.
