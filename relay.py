"""Fetch VA-2 (Luria vs Kiggans) results from the Virginia Dept. of Elections ENR API
and write a compact luria.json. Virginia's API sends no CORS header, so the public
page reads this relayed copy instead."""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

API = "https://enr.elections.virginia.gov/results/public/api/elections"
ELECTION = "2026-November-General"
CONTEST = "Member, House of Representatives (2nd District)"
LOCALITIES = {
    "virginia-beach-city": "Virginia Beach",
    "chesapeake-city": "Chesapeake",
    "suffolk-city": "Suffolk",
    "franklin-city": "Franklin",
    "isle-of-wight-county": "Isle of Wight",
    "southampton-county": "Southampton",
    "accomack-county": "Accomack",
    "northampton-county": "Northampton",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "election-night-relay/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def en(names):
    return next((n["text"] for n in names if n.get("languageId") == "en"), names[0]["text"] if names else "")


def contest(data):
    for b in data.get("ballotItems", []):
        if en(b["name"]) == CONTEST:
            return b
    return None


def summarize(b):
    opts = []
    for o in b["summaryResults"]["ballotOptions"]:
        opts.append({
            "name": en(o["name"]),
            "party": (o.get("party") or {}).get("abbreviation") or "",
            "votes": o.get("voteCount") or 0,
            "winner": bool(o.get("isWinner")),
            "writeIn": bool(o.get("isWriteIn")),
            "groups": {en(g["groupName"]): g.get("voteCount") or 0 for g in o.get("groupResults", [])},
        })
    rs = b.get("reportingStatus") or {}
    return {
        "candidates": opts,
        "reporting": rs.get("reportingUnits") or 0,
        "total": rs.get("totalUnits") or 0,
        "voteTotal": b.get("voteTotal") or 0,
        "asOf": rs.get("asOf"),
    }


def build():
    state = get(f"{API}/virginia/{ELECTION}/data")
    b = contest(state)
    if not b:
        raise RuntimeError("VA-2 contest not found")
    out = summarize(b)
    out["official"] = bool(state["election"].get("isOfficialResults"))
    out["stateLastUpdated"] = state["election"].get("lastUpdated")
    out["localities"] = []
    for slug, label in LOCALITIES.items():
        try:
            lb = contest(get(f"{API}/{slug}/{ELECTION}/data"))
            if lb:
                s = summarize(lb)
                s["name"] = label
                s["slug"] = slug
                out["localities"].append(s)
        except Exception as e:  # one locality failing should not drop the whole update
            out["localities"].append({"name": label, "slug": slug, "error": str(e)[:120]})
    out["relayedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "luria.json"
    data = build()
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(data["relayedAt"], f'{data["reporting"]}/{data["total"]}',
          [(c["name"], c["votes"]) for c in data["candidates"]])
