"""Fetch NBC News national results (AP data) for Senate, House and governor races and
write a compact national.json for jwalberg.com/election. NBC's feed sends no CORS header,
so the public page reads this relayed copy instead."""
import json
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://www.nbcnews.com/firecracker/api/v2/national-results/2026-elections/"
PARTIES = ("dem", "rep", "ind")


def get(slug):
    req = urllib.request.Request(BASE + slug, headers={"User-Agent": "Mozilla/5.0 (election-night-relay)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def statewide(d):
    """Races from a statewide table (Senate, governor): winner, flip flag, leader."""
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
