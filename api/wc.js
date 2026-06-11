// Vercel Serverless Function: proxy ESPN -> resultados + cuotas del Mundial 2026
// GET /api/wc  (opcional: ?dates=YYYYMMDD-YYYYMMDD)
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard";

// Convierte cuota americana a decimal
function amToDec(am) {
  const n = parseFloat(String(am).replace("+", ""));
  if (!isFinite(n) || n === 0) return null;
  return n > 0 ? 1 + n / 100 : 1 + 100 / Math.abs(n);
}

// Parser puro (testeable): payload ESPN -> partidos slim
function parseScoreboard(data) {
  const out = [];
  for (const ev of data.events || []) {
    const comp = (ev.competitions || [])[0];
    if (!comp) continue;
    const cs = comp.competitors || [];
    const home = cs.find(c => c.homeAway === "home"), away = cs.find(c => c.homeAway === "away");
    if (!home || !away) continue;
    const st = (comp.status && comp.status.type) || {};
    let oddsOut = null;
    const o = (comp.odds || [])[0];
    if (o && o.moneyline) {
      const pick = side => {
        const s = o.moneyline[side];
        if (!s) return null;
        const v = (s.close && s.close.odds) || (s.open && s.open.odds);
        return v != null ? amToDec(v) : null;
      };
      const h = pick("home"), d = pick("draw"), a = pick("away");
      if (h && d && a) oddsOut = { h, d, a };
    }
    out.push({
      id: ev.id,
      date: ev.date,
      stage: (ev.season && ev.season.slug) || "",
      home: home.team && home.team.displayName,
      away: away.team && away.team.displayName,
      homeScore: home.score != null ? parseInt(home.score, 10) : null,
      awayScore: away.score != null ? parseInt(away.score, 10) : null,
      homeWinner: !!home.winner, // útil para penales (empate con ganador)
      awayWinner: !!away.winner,
      state: st.state || "pre",          // pre | in | post
      completed: !!st.completed,
      odds: oddsOut
    });
  }
  return out;
}

module.exports = async (req, res) => {
  try {
    let dates = (req.query && req.query.dates) || "20260611-20260719";
    if (!/^\d{8}(-\d{8})?$/.test(dates)) dates = "20260611-20260719"; // validación
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(`${ESPN}?dates=${encodeURIComponent(dates)}&limit=200`, {
      headers: { "User-Agent": "Mozilla/5.0 (prode-mundial-2026)" },
      signal: ctrl.signal
    }).finally(() => clearTimeout(timer));
    if (!r.ok) throw new Error("ESPN " + r.status);
    const data = await r.json();
    const matches = parseScoreboard(data);
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=300");
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.status(200).json({ ok: true, fetched: new Date().toISOString(), matches });
  } catch (e) {
    res.status(200).json({ ok: false, error: String(e && e.message || e), matches: [] });
  }
};
module.exports.parseScoreboard = parseScoreboard;
module.exports.amToDec = amToDec;
