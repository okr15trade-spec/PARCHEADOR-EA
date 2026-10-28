# -*- coding: utf-8 -*-
"""
Interfaz web (Streamlit) del parcheador de EAs de StrategyQuant para CopyTrading.

Ejecutar desde la carpeta que contiene este archivo, patch_sqx_ea.py y CopyTradingGuard.mqh:
    streamlit run app_parcheador.py
"""
from pathlib import Path

import streamlit as st

import patch_sqx_ea as P

HERE = Path(__file__).resolve().parent
GUARD_FILE = HERE / "CopyTradingGuard.mqh"

st.set_page_config(page_title="Parcheador CopyTrading", page_icon="🛡️", layout="centered")

st.title("Parcheador de EAs para CopyTrading")
st.caption("Modifica un EA de StrategyQuant (MT5) para que deje de abrir operaciones cuando el "
           "Master de CopyTrading alcanza un límite de riesgo.")

with st.expander("Requisitos del EA"):
    st.markdown(
        "- Archivo `.mq5` **exportado directamente desde StrategyQuant** para MetaTrader 5.\n"
        "- Sin modificaciones manuales previas.\n"
        "- No sirve para EAs que no vengan de StrategyQuant (el modo de respaldo puede funcionar, "
        "pero es menos preciso) ni para EAs que ya hayan sido parcheados."
    )

with st.expander("¿Qué hace este parcheador?"):
    st.markdown(
        "1. Añade `#include \"CopyTradingGuard.mqh\"` tras el último `#include`.\n"
        "2. Inserta **una línea** dentro de `openPosition()` que impide abrir entradas nuevas "
        "mientras el Master tenga activo un bloqueo. El EA sigue gestionando las posiciones que ya tuviera.\n\n"
        "No compila nada y no modifica tu archivo original: genera una copia."
    )

if not GUARD_FILE.is_file():
    st.warning("No se encuentra `CopyTradingGuard.mqh` junto a esta aplicación. "
               "El parcheo funcionará, pero tendrás que copiar ese archivo a mano.")

mode_label = st.selectbox(
    "Modo de inserción",
    ["Automático (recomendado)", "Solo openPosition (SQX)", "Alternativo: inicio de OnTick"],
)
mode = {"Automático (recomendado)": "auto",
        "Solo openPosition (SQX)": "openposition",
        "Alternativo: inicio de OnTick": "ontick"}[mode_label]

uploaded = st.file_uploader("Archivo MQL5 de la estrategia", type=["mq5"])

if st.button("Parchear EA", type="primary", disabled=uploaded is None):
    st.session_state.pop("result", None)
    st.session_state.pop("error", None)
    try:
        text, enc, nl = P.decode_bytes(uploaded.getvalue())
        patched, info = P.patch_text(text, nl, mode)
        stem = Path(uploaded.name).stem
        st.session_state["result"] = {
            "name": f"{stem}_CopyTrading.mq5",
            "data": patched.encode(enc),
            "info": info,
            "enc": enc,
            "crlf": nl == "\r\n",
        }
    except P.PatchError as e:
        st.session_state["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        st.session_state["error"] = f"Error inesperado: {e}"

if "error" in st.session_state:
    st.error(st.session_state["error"])

res = st.session_state.get("result")
if res:
    info = res["info"]
    st.success("EA parcheado correctamente. Descarga el archivo y compílalo en MetaEditor.")
    for w in info["warnings"]:
        st.warning(w)

    st.download_button(
        f"Descargar {res['name']}",
        data=res["data"],
        file_name=res["name"],
        mime="text/plain",
        type="primary",
    )
    if GUARD_FILE.is_file():
        st.download_button(
            "Descargar CopyTradingGuard.mqh",
            data=GUARD_FILE.read_bytes(),
            file_name="CopyTradingGuard.mqh",
            mime="text/plain",
        )

    st.subheader("Cambios realizados")
    st.caption(f"Modo: {info['mode']} · punto de inserción: {info['where']} · "
               f"codificación: {res['enc']} · saltos de línea: {'CRLF' if res['crlf'] else 'LF'}")
    st.code("\n".join(f"{n:>6}: {t}" for n, t in info["inserted"]), language="cpp")

    st.info("Siguiente paso: copia el `.mq5` parcheado y `CopyTradingGuard.mqh` a la misma carpeta "
            "`MQL5\\Experts`, ábrelo en MetaEditor, compila con F7 (0 errores) y prueba en demo.")
