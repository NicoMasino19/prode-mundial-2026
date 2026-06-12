#!/usr/bin/env python3
"""Pipeline OFFLINE de calibración con StatsBomb Open Data.

Objetivo: aterrizar las constantes del modelo de goles del prode (BASE, RHO, ventaja
de localía) en datos reales de eventos/xG de Mundiales pasados, en vez de elegirlas
sólo por backtest de Elo. También exporta una tabla de fuerza ofensiva/defensiva por
selección (estilo Dixon-Coles, MLE) que puede usarse como prior.

IMPORTANTE — alcance:
  * StatsBomb Open Data tiene datos históricos (Mundial 2022 = competition_id 43,
    season_id 106, y otros torneos), NO el Mundial 2026 en vivo.
  * Esto NO reemplaza la sincronización en vivo de la app (ESPN). Es una herramienta
    de calibración que corrés a mano y cuyos resultados se vuelcan al index.html.
  * Para datos 2026 en tiempo real sin API de pago, ver ScraperFC (FBref/Understat).

Uso:
    pip install -r requirements.txt
    python calibrate.py                 # Mundial 2022 completo
    python calibrate.py --limit 8       # rápido: primeros 8 partidos (para probar)
    python calibrate.py --comp 43 --season 106 --export ratings_2022.json

Salidas:
    - Resumen por consola: goles/partido, ρ (Dixon-Coles), ventaja de localía,
      y recomendación de constantes para CONSTS en index.html.
    - <export>.json: {equipo: {attack, defense, xg_for_p90, xg_against_p90}} si --export.
    - shotmap_<match>.png: mapa de tiros de ejemplo si --shotmap MATCH_ID (requiere mplsoccer).
"""
import argparse
import sys
import math

WC_2022 = dict(comp=43, season=106)  # referencia de la chuleta StatsBomb


def _imports():
    try:
        import pandas as pd
        import numpy as np
        from statsbombpy import sb
    except ImportError as e:
        sys.exit(
            f"Falta una dependencia ({e.name}). Instalá con:\n"
            "    pip install -r requirements.txt"
        )
    return pd, np, sb


def load_matches(sb, comp, season):
    """matches() del torneo. Devuelve DataFrame con match_id, equipos y resultado."""
    m = sb.matches(competition_id=comp, season_id=season)
    return m.sort_values("match_date").reset_index(drop=True)


def match_team_xg(sb, match_id):
    """Suma de xG (shot_statsbomb_xg) por equipo en un partido. Devuelve dict equipo->xg."""
    ev = sb.events(match_id=match_id)
    shots = ev[ev["type"] == "Shot"]
    if shots.empty or "shot_statsbomb_xg" not in shots:
        return {}
    return shots.groupby("team")["shot_statsbomb_xg"].sum().to_dict()


def build_dataset(pd, np, sb, matches, limit=None):
    """Arma la tabla por partido: local/visitante, goles reales y xG de cada lado."""
    rows = []
    sub = matches if limit is None else matches.head(limit)
    n = len(sub)
    for i, r in sub.iterrows():
        mid = r["match_id"]
        print(f"  [{i + 1}/{n}] {r['home_team']} {r['home_score']}-{r['away_score']} "
              f"{r['away_team']}", file=sys.stderr)
        xg = match_team_xg(sb, mid)
        rows.append({
            "home": r["home_team"], "away": r["away_team"],
            "hg": int(r["home_score"]), "ag": int(r["away_score"]),
            "hxg": float(xg.get(r["home_team"], float("nan"))),
            "axg": float(xg.get(r["away_team"], float("nan"))),
        })
    return pd.DataFrame(rows)


# ---------------- Dixon-Coles MLE sobre goles reales ----------------
def dc_tau(h, a, lh, la, rho):
    """Corrección Dixon-Coles para marcadores bajos (0-0,0-1,1-0,1-1)."""
    if h == 0 and a == 0:
        return 1 - lh * la * rho
    if h == 0 and a == 1:
        return 1 + lh * rho
    if h == 1 and a == 0:
        return 1 + la * rho
    if h == 1 and a == 1:
        return 1 - rho
    return 1.0


def fit_dixon_coles(np, df):
    """MLE de attack/defense por equipo + ventaja de localía (home) + rho.

    λ_local = exp(att_local - def_visit + home);  λ_visit = exp(att_visit - def_local).
    Restricción: media de attack = 0 (identificabilidad).
    Negative log-likelihood VECTORIZADA + L-BFGS-B (converge en segundos con 32 equipos).
    """
    from scipy.optimize import minimize
    from scipy.special import gammaln
    teams = sorted(set(df["home"]) | set(df["away"]))
    idx = {t: i for i, t in enumerate(teams)}
    nt = len(teams)
    H = df["home"].map(idx).to_numpy()
    A = df["away"].map(idx).to_numpy()
    hg = df["hg"].to_numpy().astype(float)
    ag = df["ag"].to_numpy().astype(float)
    const = gammaln(hg + 1) + gammaln(ag + 1)  # parte fija del Poisson

    def unpack(p):
        att = np.concatenate([p[:nt - 1], [-p[:nt - 1].sum()]])  # suma cero
        deff = np.concatenate([p[nt - 1:2 * nt - 1], [-p[nt - 1:2 * nt - 1].sum()]])
        return att, deff, p[2 * nt - 1], p[2 * nt]

    def negll(p):
        att, deff, home, rho = unpack(p)
        lh = np.exp(att[H] - deff[A] + home)
        la = np.exp(att[A] - deff[H])
        # Corrección Dixon-Coles vectorizada para los 4 marcadores bajos
        tau = np.ones_like(lh)
        m00 = (hg == 0) & (ag == 0); tau[m00] = 1 - lh[m00] * la[m00] * rho
        m01 = (hg == 0) & (ag == 1); tau[m01] = 1 + lh[m01] * rho
        m10 = (hg == 1) & (ag == 0); tau[m10] = 1 + la[m10] * rho
        m11 = (hg == 1) & (ag == 1); tau[m11] = 1 - rho
        tau = np.clip(tau, 1e-9, None)
        ll = (np.log(tau) - lh + hg * np.log(lh) - la + ag * np.log(la) - const).sum()
        return -ll

    p0 = np.zeros(2 * nt + 1)
    p0[2 * nt - 1] = 0.25   # home advantage inicial
    p0[2 * nt] = -0.05      # rho inicial (igual que la app)
    bounds = [(-3, 3)] * (2 * nt - 1) + [(-1, 1), (-0.2, 0.2)]
    res = minimize(negll, p0, method="L-BFGS-B", bounds=bounds,
                   options=dict(maxiter=5000))
    att, deff, home, rho = unpack(res.x)
    return teams, att, deff, home, rho


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comp", type=int, default=WC_2022["comp"])
    ap.add_argument("--season", type=int, default=WC_2022["season"])
    ap.add_argument("--limit", type=int, default=None,
                    help="Procesar sólo los primeros N partidos (prueba rápida).")
    ap.add_argument("--export", type=str, default=None,
                    help="Ruta JSON para volcar la tabla de fuerza por equipo.")
    ap.add_argument("--shotmap", type=int, default=None,
                    help="match_id para generar un mapa de tiros de ejemplo (mplsoccer).")
    args = ap.parse_args()

    # Consolas Windows (cp1252) no imprimen λ/≈/Δ: forzamos UTF-8 si se puede.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    pd, np, sb = _imports()

    print(f"# Descargando torneo comp={args.comp} season={args.season} …", file=sys.stderr)
    matches = load_matches(sb, args.comp, args.season)
    print(f"# {len(matches)} partidos. Descargando eventos …", file=sys.stderr)
    df = build_dataset(pd, np, sb, matches, limit=args.limit)

    # ---- Estadísticas agregadas ----
    gpm = (df["hg"] + df["ag"]).mean()
    home_goals, away_goals = df["hg"].mean(), df["ag"].mean()
    valid_xg = df.dropna(subset=["hxg", "axg"])
    xg_pm = (valid_xg["hxg"] + valid_xg["axg"]).mean() if not valid_xg.empty else float("nan")

    print("\n================ CALIBRACIÓN (datos reales StatsBomb) ================")
    print(f"Partidos usados:            {len(df)}")
    print(f"Goles por partido:          {gpm:.3f}  (local {home_goals:.3f} / visit {away_goals:.3f})")
    print(f"xG por partido:             {xg_pm:.3f}")
    print(f"Goles por equipo (≈ BASE a Δ0): {gpm / 2:.3f}")

    teams, att, deff, home, rho = fit_dixon_coles(np, df)
    print("\n---- Ajuste Dixon-Coles (máxima verosimilitud) ----")
    print(f"Ventaja de localía (home):  {home:+.3f}  (en goles: ×{math.exp(home):.3f})")
    print(f"rho (corr. marcadores bajos): {rho:+.3f}")

    print("\n---- Recomendación para CONSTS en index.html ----")
    print(f"BASE ≈ {gpm / 2:.2f}   (actual en la app: 1.25)")
    print(f"RHO  ≈ {rho:+.2f}   (actual en la app: -0.05)")
    print("Nota: CC/SS dependen de la escala Elo y se siguen calibrando por backtest;")
    print("      este script valida el NIVEL de goles (BASE) y la correlación (RHO).")

    # ---- Tabla de fuerza por equipo (orden por ataque) ----
    order = np.argsort(-att)
    print("\n---- Fuerza por selección (Dixon-Coles, attack/defense) ----")
    print(f"{'Equipo':24} {'ATT':>7} {'DEF':>7}")
    for i in order:
        print(f"{teams[i]:24} {att[i]:+7.3f} {deff[i]:+7.3f}")

    if args.export:
        import json
        # xG por equipo agregada (for/against por 90)
        xg_for, xg_against, mins = {}, {}, {}
        for _, r in df.iterrows():
            for side, opp, gf in (("home", "away", "hxg"), ("away", "home", "axg")):
                t = r[side]
                if not math.isnan(r[gf]):
                    xg_for[t] = xg_for.get(t, 0) + r[gf]
                    mins[t] = mins.get(t, 0) + 1
            if not math.isnan(r["hxg"]):
                xg_against[r["away"]] = xg_against.get(r["away"], 0) + r["hxg"]
            if not math.isnan(r["axg"]):
                xg_against[r["home"]] = xg_against.get(r["home"], 0) + r["axg"]
        out = {}
        for i, t in enumerate(teams):
            g = max(mins.get(t, 1), 1)
            out[t] = dict(attack=round(float(att[i]), 4), defense=round(float(deff[i]), 4),
                          xg_for_p90=round(xg_for.get(t, 0) / g, 3),
                          xg_against_p90=round(xg_against.get(t, 0) / g, 3))
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(dict(home_advantage=round(float(home), 4), rho=round(float(rho), 4),
                           teams=out), f, ensure_ascii=False, indent=2)
        print(f"\n# Exportado a {args.export}")

    if args.shotmap:
        try:
            from mplsoccer import VerticalPitch
            import matplotlib.pyplot as plt
            ev = sb.events(match_id=args.shotmap)
            shots = ev[ev["type"] == "Shot"].copy()
            shots["x"] = shots["location"].apply(lambda l: l[0])
            shots["y"] = shots["location"].apply(lambda l: l[1])
            pitch = VerticalPitch(pitch_type="statsbomb", half=True,
                                  pitch_color="#0D1117", line_color="#2A3145")
            fig, ax = pitch.draw(figsize=(8, 6))
            pitch.scatter(shots["x"], shots["y"], ax=ax,
                          s=300 + shots["shot_statsbomb_xg"] * 1500,
                          c=shots["shot_outcome"].map({"Goal": "#06D6A0"}).fillna("#E84855"),
                          alpha=0.85, zorder=4)
            out_png = f"shotmap_{args.shotmap}.png"
            fig.savefig(out_png, dpi=120, bbox_inches="tight")
            print(f"# Shot map guardado en {out_png}")
        except Exception as e:
            print(f"# No se pudo generar el shot map: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
