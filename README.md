# ⚽ Prode Mundial 2026

App de predicciones del Mundial 2026 (Canadá · México · EE.UU.) con modelo Elo + mercado,
simulación Monte Carlo, **resultados y cuotas automáticos** (API pública de ESPN) y
picks óptimos para dos prodes:

- **Prode Mercado Pago**: 6 pts marcador exacto / 3 pts acertar resultado.
- **Prode amigos**: 2 pts acertar ganador/empate + 1 pt extra por exacto.

(Los puntajes son configurables desde la pestaña **Más → Ajustes**.)

## Deploy en Vercel (vía GitHub)

1. Creá un repo nuevo en GitHub (por ej. `prode-mundial-2026`) y subí esta carpeta:
   ```bash
   cd C:\Nico\programacion\prode-mundial-2026
   git remote add origin https://github.com/TU_USUARIO/prode-mundial-2026.git
   git push -u origin main
   ```
   (El repo git ya está inicializado con su primer commit.)
2. Entrá a [vercel.com/new](https://vercel.com/new), importá el repo y dale **Deploy**.
   No hay build step: es un sitio estático + una función serverless (`api/wc.js`).
3. Abrí la URL que te da Vercel desde el celular y usá "Agregar a pantalla de inicio":
   queda como una app.

Cada `git push` re-deploya solo.

> Alternativa sin GitHub: `npx vercel` dentro de la carpeta hace el deploy directo.

## Automatización

- **Resultados**: la app consulta `/api/wc` (proxy a ESPN) al abrir y cada 3 minutos.
  Los partidos terminados se cargan solos (incluido ganador por penales en eliminatorias)
  y el modelo recalcula todo.
- **Cuotas**: para los partidos no jugados, toma la línea 1X2 de DraftKings vía ESPN,
  le quita el margen y la fusiona 80% mercado / 20% modelo.
- **Manual**: todo sigue siendo editable a mano; si ESPN falla, la app avisa y funciona igual.

## Estructura

```
index.html    → toda la app (motor + UI), sin dependencias
api/wc.js     → función serverless: ESPN scoreboard → JSON slim con scores y cuotas
manifest.json → para instalarla como app en el celular
```

## Modelo (resumen)

Rating 2026 = ensamble de Elo (eloratings.net) + consenso de mercado (cuotas DraftKings,
método de potencia). Goles por Poisson con corrección Dixon-Coles (ρ=−0.10), calibrado
contra la expectativa Elo. Localía: EE.UU. +100; México +130 (altitud); Canadá +100.
Fecha 3: empates mutuamente convenientes inflados ×1.75. Eliminatorias con prórroga/penales
amortiguados. Ratings se actualizan partido a partido (K=60) con los resultados reales.
