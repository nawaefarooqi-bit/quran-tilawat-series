"""تلاوتِ قرآن سیریز — ایک پارے (یا سورت) کی ویڈیو: انڈو پاک متن آیت بہ آیت + تلاوت۔

    python -m tilawat.build juz 1            # پارہ 1
    python -m tilawat.build surah 36         # سورۃ یٰس
    RECITER=Hudhaify_128kbps python -m tilawat.build juz 1

متن کبھی AI سے نہیں: انڈو پاک مصحف github.com/fawazahmed0/quran-api (ara-quranindopak)۔
آواز: everyayah.com کی آیت بہ آیت فائلیں (قاری RECITER سے)۔
"""
from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT = ROOT / "out"
CACHE = ROOT / "cache"
TEXT_URL = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/editions/ara-quranindopak/{s}.json"
AUDIO_URL = "https://everyayah.com/data/{reciter}/{s:03d}{a:03d}.mp3"
RECITERS = {  # فائل فولڈر → اسکرین پر نام
    "Hudhaify_128kbps": "الشيخ علي بن عبدالرحمن الحذيفي",
    "Muhammad_Ayyoub_128kbps": "الشيخ محمد أيوب",
    "Alafasy_128kbps": "الشيخ مشاري راشد العفاسي",
}
W, H = 1920, 1080

JUZ_START = [(1, 1), (2, 142), (2, 253), (3, 93), (4, 24), (4, 148), (5, 82), (6, 111), (7, 88), (8, 41),
             (9, 93), (11, 6), (12, 53), (15, 1), (17, 1), (18, 75), (21, 1), (23, 1), (25, 21), (27, 56),
             (29, 46), (33, 31), (36, 28), (39, 32), (41, 47), (46, 1), (51, 31), (58, 1), (67, 1), (78, 1)]
JUZ_NAME = ["الٓمّٓ", "سَیَقُوْلُ", "تِلْکَ الرُّسُلُ", "لَنْ تَنَالُوْا", "وَالْمُحْصَنٰتُ", "لَا یُحِبُّ اللّٰہُ", "وَاِذَا سَمِعُوْا",
            "وَلَوْ اَنَّنَا", "قَالَ الْمَلَاُ", "وَاعْلَمُوْا", "یَعْتَذِرُوْنَ", "وَمَا مِنْ دَآبَّۃٍ", "وَمَاۤ اُبَرِّئُ", "رُبَمَا",
            "سُبْحٰنَ الَّذِیْۤ", "قَالَ اَلَمْ", "اِقْتَرَبَ", "قَدْ اَفْلَحَ", "وَقَالَ الَّذِیْنَ", "اَمَّنْ خَلَقَ", "اُتْلُ مَاۤ اُوْحِیَ",
            "وَمَنْ یَّقْنُتْ", "وَمَا لِیَ", "فَمَنْ اَظْلَمُ", "اِلَیْهِ یُرَدُّ", "حٰمٓ", "قَالَ فَمَا خَطْبُكُمْ", "قَدْ سَمِعَ اللّٰهُ",
            "تَبٰرَكَ الَّذِیْ", "عَمَّ"]
SURAH_AR = ["الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس","هود","يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه","الأنبياء","الحج","المؤمنون","النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم","لقمان","السجدة","الأحزاب","سبأ","فاطر","يس","الصافات","ص","الزمر","غافر","فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف","محمد","الفتح","الحجرات","ق","الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة","الحشر","الممتحنة","الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة","المعارج","نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس","التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد","الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات","القارعة","التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر","المسد","الإخلاص","الفلق","الناس"]
URDU_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# انڈو پاک فونٹ میں کچھ نئے یونیکوڈ نشان نہیں — ہم معنی شکل (نوائے فاروقی بلاگ والا اصول)
_MARK_MAP = {"٘": "ٓ"}
_SMALL_SIGNS = {"ࣔ": "الربع", "ࣕ": "ص", "ࣖ": "ع", "ࣗ": "ق", "ࣚ": "ثلٰثة",
                "ࣛ": "السجدة", "ࣝ": "سكته", "ࣞ": "قف", "ࣟ": "وقفه", "࣢": "۵"}
_DROP = {"࣠", "࣡", "‏", "‎"}


def log(m: str) -> None:
    print(f"[tilawat] {m}", flush=True)


def indopak_html(text: str) -> str:
    out = []
    for ch in text:
        if ch in _DROP:
            continue
        if ch in _SMALL_SIGNS:
            out.append(f'‌<span class="sign">{_SMALL_SIGNS[ch]}</span>‌')
        else:
            out.append(html.escape(_MARK_MAP.get(ch, ch), quote=False))
    return "".join(out)


def surah_text(s: int) -> dict[int, str]:
    p = CACHE / f"text_{s:03d}.json"
    if not p.exists():
        r = requests.get(TEXT_URL.format(s=s), timeout=60)
        r.raise_for_status()
        CACHE.mkdir(exist_ok=True)
        p.write_text(r.text, encoding="utf-8")
    d = json.loads(p.read_text(encoding="utf-8"))
    return {int(v["verse"]): v["text"] for v in d["chapter"]}


META_URL = "https://api.alquran.cloud/v1/meta"


def meta() -> dict:
    """سورت کی معلومات: مکی/مدنی، آیات، رکوع (مستند میٹا ڈیٹا؛ نہ ملے تو صرف آیات کی تعداد)"""
    p = CACHE / "meta.json"
    if not p.exists():
        try:
            r = requests.get(META_URL, timeout=60)
            r.raise_for_status()
            d = r.json()["data"]
            rk: dict[int, int] = {}
            for ref in d["rukus"]["references"]:
                rk[ref["surah"]] = rk.get(ref["surah"], 0) + 1
            out = {str(x["number"]): {"type": x["revelationType"], "ayahs": x["numberOfAyahs"], "rukus": rk.get(x["number"])}
                   for x in d["surahs"]["references"]}
            CACHE.mkdir(exist_ok=True)
            p.write_text(json.dumps(out), encoding="utf-8")
        except Exception as e:
            log(f"میٹا ڈیٹا نہیں ملا ({e}) — صرف آیات کی تعداد")
            return {}
    return json.loads(p.read_text(encoding="utf-8"))


def banner_html(s: int) -> str:
    """مصحف کی طرح سورت کا جھنڈا: آیاتہا · سورۃ … مکیۃ/مدنیۃ · رکوعاتہا"""
    m = meta().get(str(s), {})
    ayahs = m.get("ayahs") or len(surah_text(s))
    kind = {"Meccan": "مَكِّيَّةٌ", "Medinan": "مَدَنِيَّةٌ"}.get(m.get("type"), "")
    side = lambda label, n: f'<div class="cart small"><span>{label}</span> <b>{str(n).translate(AR_DIGITS)}</b></div>' if n else ""
    return (f'<div class="banner">{side("اٰيَاتُهَا", ayahs)}'
            f'<div class="cart main"><span>سُوْرَةُ {SURAH_AR[s - 1]}</span> <i>{kind}</i></div>'
            f'{side("رُكُوْعَاتُهَا", m.get("rukus"))}</div>')


def ayah_list(kind: str, n: int) -> list[tuple[int, int]]:
    if kind == "surah":
        return [(n, a) for a in sorted(surah_text(n))]
    s0, a0 = JUZ_START[n - 1]
    s1, a1 = JUZ_START[n] if n < 30 else (115, 1)
    out = []
    for s in range(s0, min(s1, 114) + 1):
        for a in sorted(surah_text(s)):
            if (s, a) >= (s0, a0) and (s, a) < (s1, a1):
                out.append((s, a))
    return out


def juz_of(s: int, a: int) -> int:
    j = 1
    for i, start in enumerate(JUZ_START, 1):
        if (s, a) >= start:
            j = i
    return j


def audio(reciter: str, s: int, a: int, dest: Path) -> Path:
    c = CACHE / "audio" / reciter / f"{s:03d}{a:03d}.mp3"
    if not c.exists():
        for attempt in range(4):
            try:
                r = requests.get(AUDIO_URL.format(reciter=reciter, s=s, a=a), timeout=90)
                if r.ok and len(r.content) > 2000:
                    c.parent.mkdir(parents=True, exist_ok=True)
                    c.write_bytes(r.content)
                    break
            except requests.RequestException:
                pass
        else:
            raise RuntimeError(f"تلاوت کی آڈیو نہیں ملی: {reciter} {s}:{a}")
    shutil.copy(c, dest)
    return dest


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:IP;src:url('__IP__') format('woff2')}
@font-face{font-family:NQ;src:url('__NQ__') format('truetype')}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden}
body{background:radial-gradient(1400px 800px at 50% 40%,#1b5a44 0%,#0f3b2c 55%,#082419 100%);color:#fbf5e6;position:relative}
.pat{position:absolute;inset:0;opacity:.06;background-image:
 repeating-linear-gradient(45deg,#e8c97a 0 1px,transparent 1px 34px),repeating-linear-gradient(-45deg,#e8c97a 0 1px,transparent 1px 34px)}
.frame{position:absolute;inset:26px;border:2px solid rgba(214,177,94,.75);border-radius:26px}
.frame:after{content:'';position:absolute;inset:10px;border:1px solid rgba(214,177,94,.35);border-radius:20px}
.top{position:absolute;top:58px;left:90px;right:90px;display:flex;justify-content:space-between;align-items:center;direction:rtl}
.chip{font-family:NQ,serif;font-size:40px;line-height:1.9;color:#f3dc9a;background:rgba(0,0,0,.18);
 border:1px solid rgba(214,177,94,.55);border-radius:999px;padding:0 34px}
.chip b{font-family:IP,serif;font-weight:400;color:#fff7dd;font-size:42px}
.ayah{position:absolute;top:170px;bottom:190px;left:130px;right:130px;display:flex;align-items:center;justify-content:center}
.ayah p{font-family:IP,serif;direction:rtl;text-align:center;color:#fffaf0;line-height:2.15;font-size:__FS__px;
 text-shadow:0 2px 10px rgba(0,0,0,.35);word-spacing:4px}
.sign{font-size:.45em;vertical-align:1em;color:#e8c97a;margin:0 2px}
.num{display:inline-flex;align-items:center;justify-content:center;font-family:NQ,serif;font-size:.42em;line-height:1;
 min-width:1.9em;height:1.9em;padding-left:.35em;padding-right:.35em;border-radius:999px;border:3px solid #d6b15e;color:#f3dc9a;margin-right:18px;vertical-align:.35em;padding-top:.25em}
.bism p{font-size:92px;color:#f6e3a6}
.banner{position:absolute;top:168px;left:150px;right:150px;display:flex;direction:rtl;gap:22px;align-items:center;justify-content:center}
.cart{font-family:IP,serif;color:#123c2e;background:linear-gradient(180deg,#fdf7e3,#efdcaa);border:3px solid #b08d3c;
 box-shadow:inset 0 0 0 5px #fdf7e3,inset 0 0 0 7px #c9a24e,0 6px 18px rgba(0,0,0,.35);border-radius:60px;
 display:flex;align-items:center;justify-content:center;gap:16px;white-space:nowrap}
.cart.main{min-width:760px;height:118px;padding:0 60px;font-size:58px}
.cart.main i{font-style:normal;font-size:.62em;color:#5c4a1c}
.cart.small{height:92px;padding:0 34px;font-size:38px}
.cart.small b{font-family:NQ,serif;font-weight:400;color:#7a5d17;font-size:1.05em;padding-top:.2em}
.withban{top:310px}
.foot{position:absolute;bottom:58px;left:90px;right:90px;display:flex;justify-content:space-between;align-items:center;direction:rtl}
.rec{font-family:NQ,serif;font-size:30px;line-height:1.9;color:#d9c79a}
.brand{display:flex;align-items:center;gap:16px;font-family:NQ,serif;font-size:34px;color:#f3dc9a;direction:rtl}
.brand img{width:92px;height:92px;border-radius:50%;box-shadow:0 0 0 3px rgba(214,177,94,.6)}
.bar{position:absolute;bottom:30px;left:28px;height:5px;background:linear-gradient(90deg,#b08d3c,#f0d58a);border-radius:3px}
</style></head><body><div class="pat"></div><div class="frame"></div>
<div class="top"><div class="chip">سورۃ <b>__SURAH__</b></div><div class="chip">پارہ __JUZN__ — <b>__JUZ__</b></div></div>
__BANNER__<div class="ayah __CLS__"><p id="t">__TEXT__</p></div>
<div class="foot"><div class="brand"><img src="__LOGO__"><span>نوائے فاروقی</span></div><div class="rec">__REC__</div></div>
<div class="bar" style="width:__BAR__px"></div>
<script>
const t=document.getElementById('t'),box=t.parentElement;let fs=parseFloat(getComputedStyle(t).fontSize);
while((t.scrollHeight>box.clientHeight||t.scrollWidth>box.clientWidth)&&fs>34){fs-=3;t.style.fontSize=fs+'px';}
document.title='ok';
</script></body></html>"""


def render_cards(items: list[dict], tmp: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright
    subs = {"__IP__": (ASSETS / "indopak.woff2").as_uri(), "__NQ__": (ASSETS / "nastaliq.ttf").as_uri(),
            "__LOGO__": (ASSETS / "logo.png").as_uri()}
    paths = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, it in enumerate(items):
            page = PAGE
            for k, v in {**subs, **it["subs"]}.items():
                page = page.replace(k, v)
            f = tmp / f"card{i:04d}.html"
            f.write_text(page, encoding="utf-8")
            pg.goto(f.as_uri())
            pg.wait_for_function("document.title==='ok'")
            pg.wait_for_timeout(60)
            out = tmp / f"card{i:04d}.jpg"
            pg.screenshot(path=str(out), type="jpeg", quality=90)
            paths.append(out)
        b.close()
    return paths


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def build(kind: str, n: int, reciter: str) -> Path:
    ayahs = ayah_list(kind, n)
    log(f"{kind} {n}: {len(ayahs)} آیات، قاری {reciter}")
    rec_name = RECITERS.get(reciter, reciter)
    OUT.mkdir(exist_ok=True)
    out = OUT / (f"para-{n:02d}.mp4" if kind == "juz" else f"surah-{n:03d}.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        seq = []          # (card subs, audio path)
        for s, a in ayahs:
            j = juz_of(s, a)
            base = {"__SURAH__": SURAH_AR[s - 1], "__JUZN__": str(j).translate(URDU_DIGITS), "__JUZ__": JUZ_NAME[j - 1],
                    "__REC__": "تلاوت: " + rec_name}
            if a == 1 and s not in (1, 9):           # ہر سورت سے پہلے بسم اللہ (الفاتحہ میں یہ پہلی آیت ہے، التوبہ میں نہیں)
                seq.append(({**base, "__TEXT__": indopak_html(surah_text(1)[1]), "__CLS__": "bism withban", "__FS__": "92",
                             "__BANNER__": banner_html(s)},
                            audio(reciter, 1, 1, tmp / f"b{s}.mp3")))
            txt = indopak_html(surah_text(s)[a]) + f' <span class="num">{str(a).translate(AR_DIGITS)}</span>'
            first = a == 1 and s in (1, 9)
            seq.append(({**base, "__TEXT__": txt, "__CLS__": "withban" if first else "", "__FS__": "96",
                         "__BANNER__": banner_html(s) if first else ""}, audio(reciter, s, a, tmp / f"{s}_{a}.mp3")))
        durs = [dur(m) + 0.35 for _, m in seq]
        total = sum(durs)
        acc, items = 0.0, []
        for (subs, _), d in zip(seq, durs):
            acc += d
            items.append({"subs": {**subs, "__BAR__": str(int(1864 * acc / total))}})
        log(f"کل دورانیہ {total / 60:.1f} منٹ — {len(items)} کارڈ بن رہے ہیں")
        cards = render_cards(items, tmp)
        parts = []
        for i, ((_, mp3), img, d) in enumerate(zip(seq, cards, durs)):
            seg = tmp / f"seg{i:04d}.mp4"
            ff("-loop", "1", "-framerate", "1", "-i", str(img), "-i", str(mp3),
               "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-r", "1", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-af", "apad=pad_dur=0.35",
               "-t", f"{d:.3f}", str(seg))
            parts.append(seg)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out))
        shutil.copy(cards[min(1, len(cards) - 1)], OUT / (out.stem + "-card.jpg"))
        chapters, t = [], 0.0
        for (subs, _), d in zip(seq, durs):
            if subs.get("__BANNER__") or not chapters:
                chapters.append(f"{int(t // 3600):d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d} سورۃ {subs['__SURAH__']}")
            t += d
        (OUT / (out.stem + "-chapters.txt")).write_text("\n".join(chapters), encoding="utf-8")
    log(f"تیار: {out} ({out.stat().st_size / 1e6:.1f} MB, {total / 60:.1f} منٹ)")
    return out


if __name__ == "__main__":
    kind, n = sys.argv[1], int(sys.argv[2])
    build(kind, n, os.environ.get("RECITER") or "Hudhaify_128kbps")
