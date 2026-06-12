# Resultados de calibración — Mundial 2022 (StatsBomb)

Corrida de `calibrate.py` sobre el torneo completo (64 partidos, `comp=43 season=106`),
con datos reales de eventos/xG de StatsBomb Open Data. Generado el 2026-06-12.

Archivos:
- [`calibracion_wc2022.txt`](calibracion_wc2022.txt) — reporte completo por consola.
- [`ratings_wc2022.json`](ratings_wc2022.json) — fuerza por equipo (attack/defense + xG p90).

## Hallazgos clave

| Métrica | Mundial 2022 (real) | App actual | Lectura |
|---|---|---|---|
| Goles / partido | **2.688** | — | torneo de pocos goles |
| xG / partido | **2.941** | — | se generó más de lo que se convirtió |
| **BASE** (goles por equipo a Δ0) | **≈ 1.34** | 1.25 | la app está bien; 1.25 es algo conservador pero coherente (calibrado 1998-2022) |
| **RHO** (corr. marcadores bajos) | **+0.18** | -0.05 | ver caveat ⬇ |
| Ventaja de localía | +0.065 (×1.07 en goles) | EE.UU./Méx/Can por sede | mínima en 2022 (sede neutral Qatar) — consistente |

### Caveat importante sobre RHO
El ρ de 2022 dio **+0.18 y pegó contra el límite** del optimizador (cota +0.20). Un ρ
positivo significaría *más* empates bajos de lo que predice el Poisson independiente. Pero:
- Es **un solo torneo** (64 partidos): ρ es notoriamente inestable con n chico.
- Qatar 2022 fue atípico (muchos 1-0/2-0 ajustados, sede neutral, clima).
- El -0.05 de la app viene de **336 partidos (1998-2022)**, muestra mucho más robusta.

**Recomendación:** NO cambiar RHO a +0.18 por esta sola corrida. Si se quiere revisar,
correr el pipeline sobre **varios Mundiales** (pooling) y recién ahí decidir. BASE 1.25→1.30
sería un ajuste defendible y chico; RHO se deja en -0.05.

### Validación cualitativa (el modelo "tiene sentido")
La tabla de fuerza ordena bien: **Francia y Argentina** (los dos finalistas) lideran ataque;
**Bélgica** último en ataque (eliminada en fase de grupos, sin generar); **Túnez** la mejor
defensa. Esto confirma que el ajuste Dixon-Coles captura señal real, no ruido.

## Cómo aplicar (manual, opcional)
1. Mirar `BASE`/`RHO` recomendados arriba. Si se decide tocar, editar `CONSTS` en
   `index.html` (línea ~264). Hoy: `BASE:1.25 ... RHO:-0.05`.
2. `ratings_wc2022.json` puede usarse como **prior de fuerza** por selección, pero ojo:
   son equipos de 2022; varios no están en 2026 y los planteles cambiaron. Sirve más como
   referencia/validación que para pisar el Elo directamente.
