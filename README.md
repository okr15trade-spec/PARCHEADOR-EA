# CopyTrading Master / Slave + Guardián de riesgo (MetaTrader 5)

Sistema original, basado en archivos, para replicar posiciones entre cuentas MT5 que corren **en el mismo ordenador o VPS y con el mismo usuario de Windows**, con un modo de protección para cuentas de fondeo.

> **Estado: sin compilar ni probar en MetaTrader.** Está escrito sin acceso a MetaEditor. Compila cada archivo (F7), corrige si hay algún error y prueba **siempre en demo** antes de usarlo con dinero real.
> No garantiza resultados ni el cumplimiento de las reglas de tu empresa de fondeo. Muchas prohíben el copy trading entre cuentas; léelas antes.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `CopyTrading_Master.mq5` | Se pone en la cuenta de origen. Publica las posiciones en un archivo y, con `PropFirmMode`, vigila los límites de riesgo. |
| `CopyTrading_Slave.mq5` | Se pone en cada cuenta de destino. Lee el archivo cada 0,5 s y replica. |
| `CopyTradingGuard.mqh` | Include para tus EAs de estrategia: les dice si pueden abrir operaciones nuevas. |
| `patch_sqx_ea.py` | Inserta el guardián en un `.mq5` exportado de StrategyQuant (2 líneas). |

## Instalación

1. Copia los `.mq5` y el `.mqh` a `MQL5\Experts\` (el `.mqh` puede ir en la misma carpeta que el EA).
2. Ábrelos en MetaEditor y compila (F7). Todos deben dar 0 errores.
3. **Master**: arrástralo a un gráfico de la cuenta de origen. Activa Algo Trading.
4. **Slave**: arrástralo a un gráfico de cada cuenta de destino. Activa Algo Trading. La cuenta debe ser **hedging**.
5. El archivo de comunicación está en `C:\Users\<usuario>\AppData\Roaming\MetaQuotes\Terminal\Common\Files\CopyTrading\master.txt`. Los terminales lo comparten porque es la carpeta *Common*.

## Master: parámetros

| Parámetro | Qué hace |
|---|---|
| `FileName`, `CustomFilePath` | Nombre del archivo o ruta propia dentro de `Common\Files`. Deben coincidir en el Slave. |
| `Symbols` | Símbolos a replicar separados por coma. Vacío = todos. |
| `MagicFilter` | `-1` = todas las posiciones; otro valor = solo ese Magic. |
| `GuardFile` | Archivo de señal para los EAs de estrategia (por defecto `CopyTrading\guard.txt`). |

### Modo fondeo (`PropFirmMode = true`)

El Master vigila el equity 4 veces por segundo, cuenta las operaciones del día y actúa sobre **todas las posiciones de la cuenta**, no solo las filtradas.

| Parámetro | Qué hace al saltar |
|---|---|
| `DailyLossLimitPercent` / `DailyProfitLimitPercent` | Cierra todo y bloquea hasta la hora de reinicio. Se mide contra el equity del inicio del día. |
| `TotalLossLimitPercent` / `TotalProfitLimitPercent` | Cierra todo y bloquea. Se mide contra `InitialCapital`. **No se levanta solo.** |
| `MaxTradesPerDay` | Tras X operaciones, no se permiten entradas nuevas ese día. |
| `MaxParallelTrades` | Si hay más posiciones abiertas, cierra la más reciente. |
| `MaxConsecWins` / `MaxConsecLossesPerDay` | Cierra todo tras X ganancias o pérdidas seguidas en el día. |
| `LimitTradingHours`, `TradingStartHour`, `TradingEndHour` | Fuera de la franja no se permiten entradas nuevas. |
| `ForceExitEnabled`, `ForceExitHour` | Cierra todo a esa hora y bloquea hasta el reinicio. |
| `ResetHour` | Hora en que se reinician los contadores diarios. |
| `ResetCountersOnInit` | `true` = borra contadores y bloqueos guardados al iniciar. Úsalo una vez para desbloquear un límite total y **vuelve a ponerlo en `false`**: si no, cada reinicio del EA levanta los bloqueos. |

- Todas las horas son **hora del servidor del broker**.
- Pon siempre `InitialCapital` con el tamaño de la cuenta de fondeo. Con `0` usa el balance del primer arranque.
- Si arrancas a mitad del día, el equity de inicio de día se estima como balance menos el resultado realizado de hoy.
- Comprueba cómo mide tu empresa el límite diario (balance o equity, zona horaria, hora de reinicio) y ajusta los parámetros. Aquí no hay forma de saberlo.
- Estado y contadores se guardan en variables globales del terminal. Reiniciar el EA mantiene los bloqueos.

## Slave: parámetros

| Parámetro | Qué hace |
|---|---|
| `SymbolMapping` | `EURUSD:EURUSDd;US30:US30Cash`. Sin mapeo se usa el mismo nombre. |
| `CopyMode` | `COPY_NORMAL`: aperturas, cambios de SL/TP y cierres. `COPY_INCOGNITO`: aperturas con el SL/TP inicial y cierres; no replica cambios posteriores. |
| `InverseMode` | BUY↔SELL y SL↔TP intercambiados. Es independiente del modo de copia. |
| `RiskMultiplier` | Lote Slave = lote Master × multiplicador, redondeado **hacia abajo** al paso del símbolo. Si queda por debajo del mínimo, esa operación no se copia. |
| `Slippage` | Deslizamiento máximo en puntos. |
| `MagicNumber` | Magic de las órdenes copiadas. Cada posición copiada lleva el comentario `CT<ticket del Master>`. |
| `MaxFileAgeSec` | Si el archivo del Master está más viejo que esto, no se abren posiciones nuevas (sí se siguen cerrando). `0` = desactivado. |
| `CopyExistingOnStart` | Por defecto, las posiciones que ya estaban abiertas al arrancar **no** se copian. |

## Proteger tus EAs de StrategyQuant

Sin esto, cuando el Master cierra todo por un límite, tu EA volvería a abrir operaciones al instante.

```
python patch_sqx_ea.py MiEstrategia.mq5
```

- Genera `MiEstrategia_CopyTrading.mq5` y no toca el original.
- Probado con un export de SQX (Strategy 3.9.22): añade el `#include` y **una línea dentro de `openPosition()`**, antes de `if(!openingOrdersAllowed) return(0);`. Solo frena las entradas; el EA sigue gestionando las posiciones abiertas.
- Si no encuentra ese punto, usa un modo alternativo en `OnTick()` y lo avisa.
- Compila el `.mq5` parcheado con `CopyTradingGuard.mqh` en la misma carpeta y úsalo en lugar del original.
- El guardián añade 3 parámetros `CTG_*` al EA: archivo de señal, segundos hasta dar la señal por caducada y `CTG_FailClosed` (si es `true`, no opera cuando falta la señal).
- En el probador de estrategias no aplica ningún bloqueo.

### Parcheador con interfaz web (Streamlit)

Alternativa a la línea de comandos: una página local en la que subes el `.mq5`, pulsas un botón y descargas el resultado.

1. Instala Python (python.org, marcando **«Add python.exe to PATH»**).
2. Deja en la misma carpeta `app_parcheador.py`, `patch_sqx_ea.py`, `CopyTradingGuard.mqh`, `requirements.txt` y `ejecutar_parcheador.bat`.
3. Haz doble clic en `ejecutar_parcheador.bat`. Instala Streamlit la primera vez y abre la página en el navegador (normalmente `http://localhost:8501`).
   - Sin el `.bat`, abre una consola en esa carpeta y ejecuta `python -m pip install streamlit` y después `python -m streamlit run app_parcheador.py`.
4. En la página: sube el `.mq5`, deja el modo en «Automático», pulsa **Parchear EA** y descarga el `.mq5` parcheado y `CopyTradingGuard.mqh`.
5. Compílalo en MetaEditor (F7) como en el resto de casos.

La página corre en tu ordenador y no envía el archivo a ningún sitio. Para cerrarla, cierra la ventana de consola.

## Límites conocidos

- Solo cuentas **hedging**. En netting las posiciones se fusionan y la copia no es fiable.
- Se replican **posiciones**. Las órdenes pendientes del Master no se copian, solo cuando se ejecutan.
- Los cierres parciales del Master no se replican; la copia se cierra entera cuando el Master cierra la última parte.
- Si tu broker modifica el comentario de las posiciones, el Slave no podrá identificarlas.
- Si el Master abre y cierra en menos de unos 0,5 s, el Slave puede no llegar a verla.
- El formato del archivo es texto simple (no JSON) y no usa servidor externo ni inicio de sesión.

## Prueba en demo antes de usar

1. Compila los tres archivos. Deben dar 0 errores.
2. Dos cuentas demo en el mismo PC. Abre una operación manual en el Master: debe aparecer en el Slave con SL/TP. Cámbiale el SL, ciérrala.
3. Prueba `InverseMode`, `RiskMultiplier` y el mapeo de símbolos.
4. Con `PropFirmMode` y un límite diario muy bajo (por ejemplo 0,05 %), comprueba que cierra todo, que el panel se pone en rojo y que el EA parcheado no vuelve a abrir.
5. Comprueba que el bloqueo diario se levanta a la hora de `ResetHour` y que el total solo con `ResetCountersOnInit`.
