# Calibración con StatsBomb (offline)

Herramienta **offline** para aterrizar el modelo de goles del prode en datos reales
de eventos/xG de Mundiales pasados, usando [`statsbombpy`](https://github.com/statsbomb/statsbombpy)
(StatsBomb Open Data, gratis, sin credenciales).

## Qué hace

1. Descarga los partidos y eventos de un torneo (por defecto **Mundial 2022**,
   `competition_id=43`, `season_id=106`).
2. Calcula goles y **xG** por equipo y partido.
3. Ajusta un modelo **Dixon-Coles** por máxima verosimilitud: fuerza ofensiva/defensiva
   por selección, **ventaja de localía** y **ρ** (correlación de marcadores bajos).
4. Imprime una **recomendación de constantes** para `CONSTS` en `index.html`
   (`BASE` = nivel de goles, `RHO` = correlación) y una tabla de fuerza por equipo.
5. Opcional: exporta la tabla a JSON (`--export`) y dibuja un shot-map (`--shotmap`).

## Por qué es offline y no toca el runtime

- `statsbombpy` es **Python** (pandas/numpy/scipy) — no corre en el frontend, que es
  JS puro en el browser. Por eso vive en `tools/` y se ejecuta a mano.
- StatsBomb Open Data es **histórico** (2022 y anteriores), **no** el Mundial 2026 en
  vivo. Esto **no reemplaza** la sincronización en vivo (ESPN) de la app.
- El flujo es: corrés el script → mirás las recomendaciones → si querés, editás a mano
  las constantes (`BASE`, `RHO`) o los ratings en `index.html`. Nada se aplica solo.

> Para datos del Mundial **2026 en tiempo real** sin API de pago, la chuleta sugiere
> [`ScraperFC`](https://github.com/oseymour/ScraperFC) (scraping de FBref/Understat).
> No está integrado acá.

## Uso

```bash
pip install -r requirements.txt

python calibrate.py                 # Mundial 2022 completo (64 partidos)
python calibrate.py --limit 8       # rápido: primeros 8 partidos (prueba)
python calibrate.py --export ratings_2022.json
python calibrate.py --comp 43 --season 106 --shotmap 3869685
```

Otros torneos open-data útiles (ver `sb.competitions()`): Euro 2020/2024, Women's
World Cup, etc. Cuantos **más partidos**, más estables los ratings.

## Interpretar la salida

```
Goles por partido:          ...     -> nivel de scoring del torneo
Goles por equipo (≈ BASE):  ...     -> compará con BASE en CONSTS (app: 1.25)
rho (Dixon-Coles):          ...     -> compará con RHO en CONSTS (app: -0.05)
Ventaja de localía:         ...     -> sanity-check del homeBonus de la app
ATT / DEF por equipo        ...     -> prior de fuerza ofensiva/defensiva
```

### Advertencias importantes

- **Tamaño de muestra:** un Mundial son ~64 partidos y cada selección juega 3–7. Con
  pocos partidos (o con `--limit`) los `ATT`/`DEF` se vuelven inestables y **pegan en
  los límites** del optimizador (±3, ρ=±0.2). Para estimaciones serias, **agrupá varios
  torneos** (ej. correr 2018+2022 y promediar) o tratá estos números como referencia,
  no como verdad absoluta.
- `BASE` y `RHO` salen directo de los datos; `CC` y `SS` dependen de la **escala Elo**
  y se siguen calibrando por backtest (ver comentario en `index.html`). Este script
  valida el **nivel de goles** y la **correlación**, no la pendiente Elo→λ.
- El warning `NoAuthWarning: open data access only` es **normal** y esperado.

## Archivos

- `calibrate.py` — pipeline principal.
- `requirements.txt` — dependencias.
