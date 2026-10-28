#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_sqx_ea.py - Parchea un EA de MetaTrader 5 (.mq5) exportado de StrategyQuant
para que respete la señal del EA CopyTrading_Master.

Qué hace (solo texto, no compila nada):
  1) Añade  #include "CopyTradingGuard.mqh"  tras el último #include del archivo.
  2) Inserta una comprobación en el punto donde el EA abre operaciones nuevas:
       - Modo "openposition" (preferido, probado con exports de SQX): dentro de
         openPosition(), justo antes de  if(!openingOrdersAllowed) return(0);
         Solo frena ENTRADAS; el EA sigue gestionando las posiciones abiertas.
       - Modo "ontick" (alternativa): al principio de OnTick().
  3) Guarda el resultado como <nombre>_CopyTrading.mq5 (el original no se toca).

Uso por línea de comandos:
  python patch_sqx_ea.py MiEstrategia.mq5
  python patch_sqx_ea.py MiEstrategia.mq5 -o Salida.mq5
  python patch_sqx_ea.py MiEstrategia.mq5 --check        (no escribe nada)
  python patch_sqx_ea.py MiEstrategia.mq5 --mode ontick

Uso con interfaz web (Streamlit):  streamlit run app_parcheador.py

Después: copia CopyTradingGuard.mqh junto al .mq5 parcheado (o a MQL5\\Include),
compila con F7 en MetaEditor y usa el EA parcheado en lugar del original.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

MARK = "[CT-GUARD]"
INCLUDE = '#include "CopyTradingGuard.mqh"'


class PatchError(Exception):
    """Error de parcheo con un código de salida asociado."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Lectura / escritura con la codificación original
# --------------------------------------------------------------------------
def decode_bytes(raw: bytes):
    """Devuelve (texto, codificacion, salto_de_linea)."""
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        enc = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    else:
        try:
            raw.decode("utf-8")
            enc = "utf-8"
        except UnicodeDecodeError:
            enc = "cp1252"
    text = raw.decode(enc)
    nl = "\r\n" if "\r\n" in text else "\n"
    return text, enc, nl


def read_text(path: Path):
    return decode_bytes(path.read_bytes())


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


# --------------------------------------------------------------------------
# Búsqueda de los puntos de inserción
# --------------------------------------------------------------------------
def find_openposition_anchor(text: str):
    """Devuelve (indice_inicio_sentencia, indentacion, tiene_isExitLevel) o None."""
    m = re.search(r"\b(?:ulong|long|int|bool)\s+openPosition\s*\(", text)
    if not m:
        return None
    brace = text.find("{", m.end())
    if brace < 0:
        return None
    signature = text[m.start():brace]
    has_exit_level = re.search(r"\bisExitLevel\b", signature) is not None
    pat = re.compile(r"^([ \t]*)if\s*\(\s*!\s*openingOrdersAllowed\s*\)\s*return\s*\(?\s*0\s*\)?\s*;",
                     re.MULTILINE)
    a = pat.search(text, brace)
    if not a:
        return None
    return a.start(), a.group(1), has_exit_level


def find_ontick_anchor(text: str):
    m = re.search(r"\bvoid\s+OnTick\s*\(\s*(?:void)?\s*\)\s*\{", text)
    if not m:
        return None
    return m.end()


def insert_include(text: str, nl: str) -> str:
    lines = text.split(nl)
    last_inc = -1
    for i, ln in enumerate(lines):
        if re.match(r"\s*#include\s*[<\"]", ln):
            last_inc = i
    if last_inc < 0:
        for i, ln in enumerate(lines):
            if re.match(r"\s*#property\b", ln):
                last_inc = i
    lines.insert(last_inc + 1, f"{INCLUDE} // {MARK}")
    return nl.join(lines)


# --------------------------------------------------------------------------
# Parcheo (función reutilizable)
# --------------------------------------------------------------------------
def patch_text(text: str, nl: str, mode: str = "auto"):
    """
    Parchea el texto de un .mq5.
    Devuelve (texto_parcheado, info). Lanza PatchError si no se puede.
    info = {"mode", "where", "warnings": [..], "inserted": [(n_linea, texto), ..]}
    """
    if MARK in text or "CopyTradingGuard.mqh" in text or "CTG_AllowOpen" in text:
        raise PatchError("Este EA ya está parcheado (o ya usa CopyTradingGuard). "
                         "Usa el .mq5 original de StrategyQuant.", 2)
    if "OnTick" not in text:
        raise PatchError("No parece un EA de MetaTrader 5: no se encuentra OnTick.", 2)

    warnings = []
    anchor = None
    if mode in ("auto", "openposition"):
        anchor = find_openposition_anchor(text)
        if anchor:
            mode = "openposition"
        elif mode == "openposition":
            raise PatchError("No se encuentra 'if(!openingOrdersAllowed) return(0);' "
                             "dentro de openPosition().", 3)
        else:
            warnings.append("No se encuentra el punto de entrada de SQX (openPosition); "
                            "se usa el modo ontick.")
            mode = "ontick"

    if mode == "openposition":
        idx, indent, has_exit = anchor
        cond = "!isExitLevel && !CTG_AllowOpen()" if has_exit else "!CTG_AllowOpen()"
        ins = f"{indent}if({cond}) return(0); // {MARK} bloqueo del Master{nl}"
        patched = text[:idx] + ins + text[idx:]
        where = f"openPosition(), línea {line_of(text, idx)}"
    else:
        end = find_ontick_anchor(text)
        if end is None:
            raise PatchError("No se encuentra 'void OnTick() {'. "
                             "Inserta a mano al inicio de OnTick:  if(CTG_SkipTick()) return;", 3)
        ins = f"{nl}   if(CTG_SkipTick()) return; // {MARK} bloqueo del Master"
        patched = text[:end] + ins + text[end:]
        where = f"OnTick(), línea {line_of(text, end)}"
        warnings.append("Modo ontick: con bloqueo total se salta todo el tick "
                        "(también la gestión de posiciones abiertas).")

    patched = insert_include(patched, nl)
    inserted = [(i + 1, ln.strip()) for i, ln in enumerate(patched.split(nl)) if MARK in ln]
    return patched, {"mode": mode, "where": where, "warnings": warnings, "inserted": inserted}


# --------------------------------------------------------------------------
# Línea de comandos
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Parchea un EA .mq5 de StrategyQuant para CopyTrading Guard")
    ap.add_argument("input", help="archivo .mq5 exportado de StrategyQuant")
    ap.add_argument("-o", "--output", help="archivo de salida (por defecto <nombre>_CopyTrading.mq5)")
    ap.add_argument("--mode", choices=["auto", "openposition", "ontick"], default="auto")
    ap.add_argument("--check", action="store_true", help="solo comprobar, no escribir")
    ap.add_argument("--no-copy-include", action="store_true",
                    help="no copiar CopyTradingGuard.mqh junto al archivo de salida")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: no existe {src}")
        return 1
    text, enc, nl = read_text(src)

    try:
        patched, info = patch_text(text, nl, args.mode)
    except PatchError as e:
        print(f"ERROR: {e}")
        return e.code

    for w in info["warnings"]:
        print(f"AVISO: {w}")
    print(f"Modo: {info['mode']}")
    print(f"Codificacion: {enc} | saltos de linea: {'CRLF' if nl == chr(13) + chr(10) else 'LF'}")
    print(f"Comprobacion insertada en {info['where']}")
    print("#include insertado tras el ultimo #include")

    if args.check:
        print("(--check: no se ha escrito nada)")
        return 0

    out = Path(args.output) if args.output else src.with_name(src.stem + "_CopyTrading" + src.suffix)
    out.write_bytes(patched.encode(enc))
    print(f"Escrito: {out}")

    if not args.no_copy_include:
        inc_src = Path(__file__).resolve().parent / "CopyTradingGuard.mqh"
        inc_dst = out.parent / "CopyTradingGuard.mqh"
        if inc_src.is_file() and not inc_dst.exists():
            shutil.copyfile(inc_src, inc_dst)
            print(f"Copiado: {inc_dst}")
        elif not inc_dst.exists():
            print("RECUERDA: copia CopyTradingGuard.mqh junto al .mq5 parcheado (o a MQL5\\Include).")
    print("Siguiente paso: abre el .mq5 en MetaEditor, compila (F7) y prueba en cuenta demo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
