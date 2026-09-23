"""Airport lookup: search by IATA code, English city/airport name, or a
curated set of Korean city aliases for commonly searched destinations.

Airport data comes from the `airportsdata` package (bundled IATA dataset,
no network access needed). Korean aliases are hand-curated below — anything
missing can still be found by its IATA code or English name.
"""
from __future__ import annotations

import airportsdata

_IATA = airportsdata.load("IATA")

# code -> Korean city/airport aliases, most-traveled destinations for Korean users.
KOREAN_ALIASES: dict[str, list[str]] = {
    # Korea
    "ICN": ["서울", "인천"], "GMP": ["서울", "김포"], "PUS": ["부산", "김해"],
    "CJU": ["제주"], "TAE": ["대구"], "KWJ": ["광주"], "USN": ["울산"],
    "RSU": ["여수"], "HIN": ["진주", "사천"], "KUV": ["군산"],
    "WJU": ["원주"], "CJJ": ["청주"], "YNY": ["양양"],
    # Japan
    "NRT": ["도쿄", "나리타"], "HND": ["도쿄", "하네다"], "KIX": ["오사카", "간사이"],
    "ITM": ["오사카", "이타미"], "NGO": ["나고야"], "FUK": ["후쿠오카"],
    "CTS": ["삿포로"], "OKA": ["오키나와"], "KOJ": ["가고시마"],
    "TAK": ["다카마쓰"], "KMJ": ["구마모토"], "HIJ": ["히로시마"],
    "MYJ": ["마쓰야마"], "KMQ": ["고마쓰"],
    # China / Taiwan / HK / Macau
    "PEK": ["베이징", "북경"], "PKX": ["베이징", "북경"], "PVG": ["상하이", "상해"],
    "SHA": ["상하이", "상해"], "CAN": ["광저우", "광주"], "SZX": ["선전", "심천"],
    "CTU": ["청두", "성도"], "XIY": ["시안", "서안"], "TAO": ["칭다오", "청도"],
    "DLC": ["다롄", "대련"], "HGH": ["항저우", "항주"], "TPE": ["타이베이", "대만", "타이완"],
    "KHH": ["가오슝"], "HKG": ["홍콩"], "MFM": ["마카오"],
    # Southeast Asia
    "SGN": ["호치민", "호찌민"], "HAN": ["하노이"], "DAD": ["다낭"],
    "CXR": ["나트랑", "냐짱"], "PQC": ["푸꾸옥"], "BKK": ["방콕"],
    "DMK": ["방콕", "돈므앙"], "HKT": ["푸켓"], "CNX": ["치앙마이"],
    "USM": ["코사무이"], "MNL": ["마닐라"], "CEB": ["세부"],
    "KLO": ["보라카이", "칼리보"], "MPH": ["보홀"], "SIN": ["싱가포르"],
    "KUL": ["쿠알라룸푸르"], "PEN": ["페낭"], "DPS": ["발리", "덴파사르"],
    "CGK": ["자카르타"],
    # Guam / Saipan / Oceania
    "GUM": ["괌"], "SPN": ["사이판"], "SYD": ["시드니"], "MEL": ["멜버른"],
    "BNE": ["브리즈번"], "AKL": ["오클랜드"],
    # North America
    "LAX": ["로스앤젤레스", "엘에이"], "SFO": ["샌프란시스코"], "JFK": ["뉴욕"],
    "EWR": ["뉴욕", "뉴어크"], "ORD": ["시카고"], "SEA": ["시애틀"],
    "HNL": ["호놀룰루", "하와이"], "LAS": ["라스베이거스"], "ATL": ["애틀랜타"],
    "YVR": ["밴쿠버"], "YYZ": ["토론토"],
    # Europe / Middle East
    "LHR": ["런던"], "LGW": ["런던"], "CDG": ["파리"], "FRA": ["프랑크푸르트"],
    "AMS": ["암스테르담"], "FCO": ["로마"], "BCN": ["바르셀로나"], "MAD": ["마드리드"],
    "IST": ["이스탄불"], "ZRH": ["취리히"], "VIE": ["비엔나", "빈"], "PRG": ["프라하"],
    "DXB": ["두바이"], "DOH": ["도하"],
}


def _build_index() -> list[dict]:
    entries = []
    for code, info in _IATA.items():
        if not info.get("city"):
            continue
        entries.append(
            {
                "iata": code,
                "city": info["city"],
                "name": info["name"],
                "country": info["country"],
                "aliases_ko": KOREAN_ALIASES.get(code, []),
            }
        )
    return entries


_ENTRIES = _build_index()
_BY_CODE = {e["iata"]: e for e in _ENTRIES}


def search(query: str, limit: int = 8) -> list[dict]:
    """Rank matches: exact code > starts-with (code/city/name/alias) > contains."""
    q = query.strip().lower()
    if len(q) < 1:
        return []

    exact, starts, contains = [], [], []
    seen = set()

    for e in _ENTRIES:
        if e["iata"] in seen:
            continue
        haystacks = [e["iata"].lower(), e["city"].lower(), e["name"].lower()] + [
            a.lower() for a in e["aliases_ko"]
        ]
        if e["iata"].lower() == q:
            exact.append(e)
        elif any(h.startswith(q) for h in haystacks):
            starts.append(e)
        elif any(q in h for h in haystacks):
            contains.append(e)
        else:
            continue
        seen.add(e["iata"])

    ranked = exact + starts + contains
    return ranked[:limit]


def label_for_code(code: str) -> str:
    e = _BY_CODE.get((code or "").upper())
    if not e:
        return code or ""
    ko = "/".join(e["aliases_ko"])
    return f"{e['city']}{' · ' + ko if ko else ''} ({e['iata']})"
