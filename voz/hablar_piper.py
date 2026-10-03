"""Camino lento (sin servidor): dice una frase con la voz Piper configurada.

Uso: hablar_piper.py <modelo.onnx> <frase>. Usa los mismos ajustes que servidor_piper.py.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import servidor_piper as sp  # noqa: E402

modelo, frase = Path(sys.argv[1]).stem, sys.argv[2]
(sp.DIR / "tmp").mkdir(exist_ok=True)
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=sp.DIR / "tmp") as f:
    ruta = f.name
sp.generar(modelo, frase, ruta)
subprocess.run(["afplay", ruta])
subprocess.run(["rm", "-f", ruta])
