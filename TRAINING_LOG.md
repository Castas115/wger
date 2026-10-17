# Training Log — Pull/Bench 4-Day Block

Dos secciones: **ajustes al programa** (qué cambió en `program.yaml` y por qué)
y **respuesta a los pesos** (lo prescrito vs lo que de verdad levantaste, para
ajustar el `one_rm_total_kg` del siguiente bloque).

## Ajustes al programa

| Fecha | Cambio | Por qué |
|---|---|---|
| 2026-10-17 | Split inicial: Pull (pull-up/chin-up/pulldown) + Bench (bench/dip/incline) | Dos main lifts pedidos: pull-up y bench, cada uno con 2 assists |
| 2026-10-17 | Tabla B1-B5 × W1-W4 definida para main+assist1+assist2 (RPE 6.5→10 por bloque, taper en B5) | Periodización por bloques dada por el usuario |
| 2026-10-17 | 4º día: legs + hombro/brazo/core/RDL | Pedido explícito de cubrir pierna, hombro, brazos, core, RDL uni/bilateral |
| 2026-10-17 | Día 3 = squat (front squat + RDL unilateral), Día 4 = hinge (RDL + zancadas) | Separar patrón squat de patrón hinge en días distintos |
| 2026-10-17 | Reparto de assists: chin-up + DB incline bench → día 3; wide neutral pulldown → día 2; dip → día 4 | Subir frecuencia de pull/push repartiendo accesorios en los días de pierna |
| 2026-10-17 | Accesorios añadidos: pullover, band pull-apart, seated OHP, lateral raise, triceps (pushdown/lying/overhead), curls (barbell→biceps curl, DB hammer curl), 1-arm DB row | Cubrir hombro/brazos que faltaban |
| 2026-10-17 | Quitado: hip thrust, cable crunch, leg extension, standing calf raise, seated leg curl, hanging knee raise | Recorte de volumen, pedido directo |
| 2026-10-17 | Nombres de ejercicio alineados a la base de datos real de wger (`wger_exercise_id` resuelto contra `/api/v2/exercise-translation/`) | Para que el import a wger no falle por nombre no encontrado |
| 2026-10-17 | `program.yaml` reestructurado como fuente única: `scripts/render_routine.py` genera `routine.html`, `scripts/import_wger_routine.py` empuja a la API de wger | Pedido: HTML autogenerado + import automático, no mantenimiento a mano |
| 2026-10-17 | Import a wger (rutina id 2, 4 días, 19 ejercicios, sin pesos) | Primera carga real a la instancia |
| 2026-10-17 | Añadido `bodyweight_kg`/`one_rm_total_kg` y `top_set_weight`/`backoff_weight` por semana (tabla %1RM tipo RPE-chart) en Pull-up y Bench | Pasar de "RPE puro" a objetivo de kg concreto por semana |

## Respuesta a los pesos

El objetivo de kg en `program.yaml` sale de una tabla %1RM estándar (reps×RPE
→ %1RM) aplicada a `one_rm_total_kg`. Es una **estimación de partida**, no
verdad revelada. Cada semana apunta aquí lo que de verdad levantaste para que
el siguiente bloque (o el siguiente ciclo de 20 semanas) recalibre
`one_rm_total_kg` con datos reales en vez de la estimación inicial.

| Fecha | Bloque/Semana | Día | Ejercicio | Prescrito (kg) | RPE objetivo | Real (kg) | RPE/RIR real | Nota |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Regla rápida para recalibrar: si el RPE real queda **más bajo** que el
objetivo con el peso prescrito, el `one_rm_total_kg` iba corto — súbelo. Si el
RPE real queda **más alto** (set más duro de lo esperado), iba largo —
bájalo. Ajustar entre bloques, no dentro del mismo bloque (para no romper la
progresión ya en marcha).
