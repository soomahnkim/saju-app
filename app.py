import calendar, json, math, os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import streamlit as st

# ───────── 기본 데이터 ─────────
STEM_K, STEM_H = list("갑을병정무기경신임계"), list("甲乙丙丁戊己庚辛壬癸")
BR_K, BR_H = list("자축인묘진사오미신유술해"), list("子丑寅卯辰巳午未申酉戌亥")
EL = ["목(木)", "화(火)", "토(土)", "금(金)", "수(水)"]
EL_COLOR = ["#3B7A57", "#B83A2E", "#C9A227", "#8A8A8A", "#1F2A44"]  # 오방색
STEM_EL = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
BR_EL = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
BR_MAIN = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8]  # 지지 본기(천간 번호)
GROUP = ["비겁", "식상", "재성", "관성", "인성"]
DM_TEXT = [
    "갑목: 큰 나무. 곧고 진취적이며 리더십이 있습니다.",
    "을목: 풀과 덩굴. 유연하고 적응력이 좋으며 섬세합니다.",
    "병화: 태양. 밝고 열정적이며 표현력이 풍부합니다.",
    "정화: 촛불. 따뜻하고 세심하며 집중력이 뛰어납니다.",
    "무토: 큰 산. 믿음직하고 포용력이 크며 중후합니다.",
    "기토: 논밭의 흙. 온화하고 현실적이며 꼼꼼합니다.",
    "경금: 바위·쇠. 결단력이 강하고 의리가 있습니다.",
    "신금: 보석. 예민하고 깔끔하며 완성도를 중시합니다.",
    "임수: 큰 강·바다. 지혜롭고 스케일이 크며 자유롭습니다.",
    "계수: 이슬·비. 영리하고 감성적이며 직관이 좋습니다.",
]
GROUP_TEXT = [
    "비겁(비견·겁재): 자아, 독립심, 동료와 경쟁. 많으면 고집과 경쟁심, 적으면 주관 부족.",
    "식상(식신·상관): 표현력, 재능, 창의. 많으면 말과 아이디어가 풍부, 적으면 표현이 소극적.",
    "재성(편재·정재): 재물, 현실감각, 실행력. 많으면 현실적이고 활동적, 적으면 재물 관리에 신경.",
    "관성(편관·정관): 직업, 책임, 명예. 많으면 책임감과 압박, 적으면 자유로우나 조직 적응에 노력.",
    "인성(편인·정인): 학문, 보호, 자격. 많으면 사려 깊고 의존적, 적으면 독립적이나 후원 부족.",
]

SEOUL = ZoneInfo("Asia/Seoul")      # 연도별 표준시 변경·서머타임 규칙 내장
SOLAR = timedelta(hours=8, minutes=28)  # 서울(127°E) 진태양시 = UTC+8:28

# ───────── 천문 계산 (태양 황경으로 절기 정밀 계산) ─────────
def to_jd(utc):
    return (utc - datetime(1970, 1, 1)).total_seconds() / 86400 + 2440587.5

def sun_lon(jd):
    t = (jd - 2451545) / 36525
    l0 = 280.46646 + 36000.76983 * t
    m = math.radians(357.52911 + 35999.05029 * t)
    c = ((1.914602 - 0.004817 * t) * math.sin(m) + 0.019993 * math.sin(2 * m)
         + 0.000289 * math.sin(3 * m))
    om = math.radians(125.04 - 1934.136 * t)
    return (l0 + c - 0.00569 - 0.00478 * math.sin(om)) % 360

def cross(target, a, b):
    """[a,b](JD) 안에서 태양 황경이 target이 되는 시각을 이분법으로 찾음"""
    diff = lambda j: ((sun_lon(j) - target + 540) % 360) - 180
    for _ in range(40):
        m = (a + b) / 2
        if diff(m) < 0:
            a = m
        else:
            b = m
    return (a + b) / 2

def jdn(y, m, d):
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045

def idx60(s, b):
    return next(i for i in range(60) if i % 10 == s and i % 12 == b)

def ten(ds, os_):
    same = ds % 2 == os_ % 2
    return [("비견", "겁재"), ("식신", "상관"), ("편재", "정재"), ("편관", "정관"),
            ("편인", "정인")][(STEM_EL[os_] - STEM_EL[ds]) % 5][0 if same else 1]

def group_of(ds, os_):
    return (STEM_EL[os_] - STEM_EL[ds]) % 5

def calc(d, t, male, adj):
    # 입력 시각 = 그 당시 한국의 시계 시각 → 연도별 규칙으로 UTC 변환 (서머타임 자동 반영)
    wall = datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=SEOUL)
    utc = wall.astimezone(timezone.utc).replace(tzinfo=None)
    # 일주·시주 기준 시각: 진태양시(보정 켬) 또는 입력한 시계 시각 그대로(보정 끔)
    kst = utc + SOLAR if adj else wall.replace(tzinfo=None)
    jd = to_jd(utc)  # 절기는 절대시각(UTC)으로 계산
    lon = sun_lon(jd)

    sy = kst.year  # 년주: 입춘(황경 315°) 기준
    if kst.month <= 2 and 270 <= lon < 315:
        sy -= 1
    ys, yb = (sy - 4) % 10, (sy - 4) % 12

    mi = int(((lon - 315) % 360) // 30)  # 월주: 인월부터 30°씩
    mb, ms = (2 + mi) % 12, ((ys % 5) * 2 + 2 + mi) % 10

    di = (jdn(kst.year, kst.month, kst.day) + 49) % 60  # 일주
    ds, db = di % 10, di % 12

    hb = ((kst.hour + 1) // 2) % 12  # 시주
    hs = ((ds % 5) * 2 + hb) % 10

    fwd = (ys % 2 == 0) == male  # 양남음녀 순행
    target = (315 + 30 * (mi + 1)) % 360 if fwd else (315 + 30 * mi) % 360
    tj = cross(target, jd, jd + 35) if fwd else cross(target, jd - 35, jd)
    age = max(1, int(abs(tj - jd) / 3 + 0.5))  # 3일 = 1년
    mi60 = idx60(ms, mb)
    dae = [((mi60 + (k if fwd else -k)) % 60) for k in range(1, 9)]
    return dict(p=[(ys, yb), (ms, mb), (ds, db), (hs, hb)],
                dae=[(i % 10, i % 12) for i in dae], age=age, fwd=fwd, by=sy,
                off=wall.utcoffset(), dst=bool(wall.dst()))

# ───────── 화면 ─────────
def glyph(ch, e):
    c = EL_COLOR[e]
    return (f"<div style='margin:3px auto;width:58px;height:58px;line-height:58px;"
            f"text-align:center;font-size:32px;font-weight:bold;color:{c};"
            f"background:{c}1f;border:1px solid {c};border-radius:4px'>{ch}</div>")

def share_text(r, name, when):
    p = lambda x: STEM_K[x[0]] + BR_K[x[1]]
    n = f"{name}님의 " if name else ""
    return (f"{n}사주팔자\n{when}\n\n년주 {p(r['p'][0])} / 월주 {p(r['p'][1])} / "
            f"일주 {p(r['p'][2])} / 시주 {p(r['p'][3])}\n{DM_TEXT[r['p'][2][0]]}\n\n"
            f"대운({'순행' if r['fwd'] else '역행'}, {r['age']}세 시작): "
            + " ".join(p(x) for x in r["dae"]))

SAVE = os.environ.get("SAJU_SAVE") == "1"  # 내 컴퓨터에서만 저장 기능 사용
FILE = "records.json"
load_recs = lambda: json.load(open(FILE, encoding="utf-8")) if os.path.exists(FILE) else []

def load(rec):
    bd = date.fromisoformat(rec["d"])
    st.session_state.update(name=rec["n"], y=bd.year, mo=bd.month, dd=bd.day,
                            t=time(rec["h"], rec["m"]), g=rec["g"], adj=rec["a"])
    st.session_state.r = calc(bd, st.session_state.t, rec["g"] == "남", rec["a"])

st.set_page_config(page_title="사주팔자", page_icon="命")
st.title("命 사주팔자")

if SAVE:
    with st.sidebar:
        st.subheader("저장된 사주")
        recs = load_recs()
        for i, rec in enumerate(recs):
            c1, c2 = st.columns([4, 1])
            c1.button(rec["n"] + " " + rec["d"], key=f"l{i}", on_click=load, args=(rec,))
            if c2.button("🗑", key=f"x{i}"):
                recs.pop(i)
                json.dump(recs, open(FILE, "w", encoding="utf-8"), ensure_ascii=False)
                st.rerun()

name = st.text_input("이름 (선택)", key="name")
MIN_YEAR = 1900  # 더 이전 출생까지 허용하려면 이 값을 낮추세요
years = list(range(MIN_YEAR, date.today().year + 1))
st.session_state.setdefault("y", 1990)
st.session_state.setdefault("mo", 1)
st.session_state.setdefault("dd", 1)
st.write("**생년월일**")
c1, c2, c3 = st.columns([1.3, 1, 1])
y = c1.selectbox("년", years, key="y", format_func=lambda v: f"{v}년")
mo = c2.selectbox("월", list(range(1, 13)), key="mo", format_func=lambda v: f"{v}월")
nd = calendar.monthrange(y, mo)[1]  # 해당 월의 마지막 날 (윤년 포함)
if st.session_state.dd > nd:
    st.session_state.dd = nd
dd = c3.selectbox("일", list(range(1, nd + 1)), key="dd", format_func=lambda v: f"{v}일")
d = date(y, mo, dd)
t = st.time_input("태어난 시간", value=time(12, 0), step=60, key="t")
g = st.radio("성별", ["남", "여"], horizontal=True, key="g")
adj = st.toggle("진태양시 보정 (서울 127°E 기준)", value=True, key="adj",
                help="켜면 서울의 지방 태양시(UTC+8:28)로 일주·시주를 계산합니다. 연도별 표준시 변경과 서머타임은 자동 반영됩니다.")
if st.button("사주 보기", type="primary"):
    if d > date.today():
        st.error("오늘 이후의 날짜는 계산할 수 없습니다.")
    else:
        st.session_state.r = calc(d, t, g == "남", adj)

r = st.session_state.get("r")
if r:
    dm = r["p"][2][0]
    st.subheader("사주 원국")
    mins = int(r["off"].total_seconds() // 60)
    st.caption(f"입력 시각에 적용된 한국 시간대: UTC+{mins // 60}:{mins % 60:02d}"
               + (" · 서머타임 적용" if r["dst"] else ""))
    cols = st.columns(4)
    for col, (label, i) in zip(cols, [("시주", 3), ("일주", 2), ("월주", 1), ("년주", 0)]):
        s, b = r["p"][i]
        top = "일원(나)" if i == 2 else ten(dm, s)
        col.markdown(f"<div style='text-align:center;font-size:12px'><span style='color:#9E2A2B'>"
                     f"{label}</span><br>{top}{glyph(STEM_H[s], STEM_EL[s])}"
                     f"{glyph(BR_H[b], BR_EL[b])}{ten(dm, BR_MAIN[b])}</div>",
                     unsafe_allow_html=True)
    st.write(" ".join(f"{STEM_K[s]}{BR_K[b]}{x}" for (s, b), x in zip(r["p"], "년월일시")))

    el, gr = [0] * 5, [0] * 5
    for i, (s, b) in enumerate(r["p"]):
        el[STEM_EL[s]] += 1
        el[BR_EL[b]] += 1
        if i != 2:
            gr[group_of(dm, s)] += 1
        gr[group_of(dm, BR_MAIN[b])] += 1
    st.subheader("오행 분포")
    st.write("  ".join(f"**{EL[i]} {el[i]}**" for i in range(5)))
    st.subheader("나의 일간")
    st.write(DM_TEXT[dm])
    st.subheader("십성 풀이")
    st.write("  ".join(f"**{GROUP[i]} {gr[i]}**" for i in range(5)))
    st.write("가장 강한 기운 ▶ " + GROUP_TEXT[gr.index(max(gr))])
    st.write("가장 약한 기운 ▶ " + GROUP_TEXT[gr.index(min(gr))])

    st.subheader(f"대운 ({'순행' if r['fwd'] else '역행'} · {r['age']}세 시작)")
    age_now = date.today().year - r["by"]
    cur = min(7, (age_now - r["age"]) // 10) if age_now >= r["age"] else -1
    boxes = ""
    for k, (s, b) in enumerate(r["dae"]):
        bd = "2px solid #9E2A2B" if k == cur else "1px solid #0004"
        bg = "#C9A22750" if k == cur else "#FBF6E9"
        boxes += (f"<div style='width:72px;text-align:center;font-size:11px;padding:4px;"
                  f"border:{bd};background:{bg};border-radius:4px'>"
                  f"<span style='color:#9E2A2B'>{r['age'] + 10 * k}세</span><br>{ten(dm, s)}"
                  f"<div style='font-size:24px;color:{EL_COLOR[STEM_EL[s]]}'>{STEM_H[s]}</div>"
                  f"<div style='font-size:24px;color:{EL_COLOR[BR_EL[b]]}'>{BR_H[b]}</div>"
                  f"{r['by'] + r['age'] + 10 * k}~</div>")
    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:6px'>{boxes}</div>",
                unsafe_allow_html=True)
    if cur >= 0:
        s, b = r["dae"][cur]
        st.write(f"**현재 대운: {STEM_K[s]}{BR_K[b]} ({ten(dm, s)} 운)**")

    when = f"{d.year}년 {d.month}월 {d.day}일 {t.hour}시 {t.minute:02d}분 ({g})"
    txt = share_text(r, name, when)
    st.subheader("공유")
    st.code(txt, language=None)  # 오른쪽 위 복사 버튼 → 카톡 등에 붙여넣기
    st.download_button("텍스트 파일로 저장", txt, file_name="saju.txt")
    if SAVE and st.button("이 사주 저장"):
        recs = load_recs()
        recs.append(dict(n=name or "이름없음", d=d.isoformat(), h=t.hour, m=t.minute, g=g, a=adj))
        json.dump(recs, open(FILE, "w", encoding="utf-8"), ensure_ascii=False)
        st.success("저장했습니다")
    st.caption("※ 절기는 태양 황경 계산으로 구했으며 수 분 내외의 오차가 있을 수 있습니다. "
               "풀이는 일반적인 해설로, 재미와 참고용으로 봐주세요.")
