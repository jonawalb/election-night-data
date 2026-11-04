"""Fetch NBC News national results (AP data) for Senate, House and governor races and
write a compact national.json for jwalberg.com/election. NBC's feed sends no CORS header,
so the public page reads this relayed copy instead."""
import json
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://www.nbcnews.com/firecracker/api/v2/national-results/2026-elections/"
PARTIES = ("dem", "rep", "ind")
STATES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
          "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
          "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
          "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
          "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
          "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
          "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
          "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
          "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
          "Wisconsin": "WI", "Wyoming": "WY"}


def cands(tooltip, n=3):
    """Top candidates by vote: [name, party, pct, votes, winner, incumbent]."""
    cs = sorted(tooltip.get("candidates") or [], key=lambda c: -(c.get("votes") or 0))[:n]
    return [[c.get("name", ""), (c.get("party") or "").lower()[:3], c.get("percentVote") or 0, c.get("votes") or 0,
             1 if c.get("isWinner") else 0, 1 if c.get("isIncumbent") else 0] for c in cs]


def house_races(d):
    out = []
    for key, v in (d.get("mapData") or {}).items():
        t = (v or {}).get("tooltip") if isinstance(v, dict) else None
        if not t or not t.get("candidates"):
            continue
        name = t.get("raceName", "")
        state, _, dist = name.partition(" District ")
        if not dist:
            state, dist = name.replace(" At Large", ""), "AL"
        out.append({"st": STATES.get(state, state[:2].upper()), "d": dist, "pctIn": t.get("percentIn") or 0,
                    "rem": t.get("remainingVote"), "call": t.get("callStatusCode") or "", "cl": cands(t)})
    out.sort(key=lambda r: (r["st"], int(r["d"]) if r["d"].isdigit() else 0))
    return out


def get(slug):
    req = urllib.request.Request(BASE + slug, headers={"User-Agent": "Mozilla/5.0 (election-night-relay)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def statewide(d):
    """Races from a statewide table (Senate, governor): winner, flip flag, leader, vote detail."""
    mp = d.get("mapData") or {}
    races = []
    for s in d["tableData"]["states"]:
        row = {"st": s["stateAbbr"], "name": s["stateName"], "pctIn": s.get("percentIn") or 0, "c": {}}
        for p in PARTIES:
            c = s.get(p) or {}
            if c.get("lastName"):
                row["c"][p] = {"n": c["lastName"], "pct": c.get("percentVote") or 0}
            if c.get("isWinner"):
                row["win"] = p
                row["flip"] = bool(c.get("isFlip"))
        t = (mp.get(s["stateAbbr"].replace(" Special", "")) or {}).get("tooltip") or {}
        if t.get("candidates"):
            row["cl"] = cands(t)
            row["rem"] = t.get("remainingVote")
        races.append(row)
    return races


def bop(d):
    bar = (d.get("bopData") or {}).get("bar") or {}
    out = {}
    for p in PARTIES:
        b = bar.get(p) or {}
        out[p] = {k: b.get(k) for k in ("total", "flips", "netGain", "notUpForElection") if b.get(k) is not None}
    out["up"] = bar.get("upForElection")
    return out


def key_flips(d):
    """Called flips among NBC's key races (the only place House flips are listed by district)."""
    flips = []
    for grp in (d.get("racesToWatchData") or {}).get("results", []):
        for r in grp.get("resultsByOffice", []):
            for c in r.get("candidates", []):
                if c.get("isGain") and c.get("isWinner"):
                    flips.append({"st": r["stateAbbr"], "dist": r.get("houseNumber") or "",
                                  "n": (c.get("firstName", "") + " " + c.get("lastName", "")).strip(),
                                  "p": c.get("party", "").lower()[:3]})
    return flips


def main(out):
    sen, house, gov = get("senate-results"), get("house-results"), get("governor-results")

    s_races = statewide(sen)
    g_races = statewide(gov)
    hb = bop(house)
    seats = house["tableData"].get("seatsByParty") or {}
    model = house.get("houseModelData") or {}

    data = {
        "source": "NBC News / Associated Press",
        "asOf": sen.get("lastModified"),
        "senate": {
            "bop": bop(sen),
            "majority": 51,
            "races": s_races,
            "called": sum(1 for r in s_races if r.get("win")),
        },
        "house": {
            "bop": hb,
            "majority": 218,
            "uncalled": seats.get("uncalled"),
            "model": {k: model.get(k) for k in ("dem", "rep")} if model else None,
            "keyFlips": key_flips(house),
            "characterization": model.get("characterization") if model else None,
            "races": house_races(house),
            "states": [{"st": s["stateAbbr"], "d": s["dem"]["seatsWon"], "r": s["rep"]["seatsWon"],
                        "u": s.get("uncalledRaces", 0), "t": s.get("totalSeats", 0)}
                       for s in house["tableData"]["states"]],
        },
        "governor": {
            "races": g_races,
            "called": sum(1 for r in g_races if r.get("win")),
        },
        "relayedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    sb = data["senate"]["bop"]
    print(datetime.now(timezone.utc).isoformat(timespec="seconds"),
          f"S D{sb['dem'].get('total')} R{sb['rep'].get('total')} | H D{hb['dem'].get('total')} R{hb['rep'].get('total')} "
          f"u{seats.get('uncalled')} | G called {data['governor']['called']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "national.json")
