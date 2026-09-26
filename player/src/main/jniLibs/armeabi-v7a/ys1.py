# -*- coding: utf-8 -*-
# 玉山直播 - 稳定优化版
# 数据源: https://www.liaobagua.com/tv/tv.php?a=play

import os
import re
import time
import json
import gzip
import ssl
import urllib.request
import urllib.parse

try:
    import requests
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

try:
    from base.spider import Spider as _Base
except ImportError:
    class _Base(object):
        def init(self, extend=""):
            pass


M3U_URL = "https://www.liaobagua.com/tv/tv.php?a=play"

# 缓存目录（改成你 TVBox 的目录）
CACHE_DIR = "/sdcard/tvbox/py"
CACHE_FILE = os.path.join(CACHE_DIR, "ys_cache.json")
CACHE_TTL = 3600        # 缓存有效期 1 小时
FETCH_TIMEOUT = 5       # 拉 M3U 超时 5 秒
FETCH_RETRY = 1         # 失败后再试 1 次

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]

LOGO_CDN = "https://epg.112114.eu.org/logo/{}.png"

RESTRICTED = {"乐活频道", "HiPLAY", "彩虹R频道", "潘朵拉玩美", "潘朵拉粉红",
              "K频道", "彩虹MOIVE", "彩虹e台", "星颖", "HAPPY"}

CATEGORY_RULES = {
    "体育": ["CCTV-5", "CCTV5", "风云足球", "高尔夫网球", "央视台球",
             "广东体育", "五星体育", "快乐垂钓", "Now Sports", "Now Golf",
             "纬来体育", "ELTA体育", "博斯", "DAZN", "欧洲体育",
             "EURO SPORT", "NBA"],
    "新闻": ["CCTV-13", "CCTV13", "第一财经", "东方财经", "广东新闻",
             "凤凰资讯", "无线新闻", "Now新闻", "华视新闻", "中视新闻",
             "民视新闻", "台视新闻", "TVBS新闻", "中天新闻", "三立新闻",
             "寰宇新闻", "非凡新闻", "年代新闻", "德国之声", "Sky News",
             "CNN", "Bloomberg", "France24", "TV5"],
    "影视": ["CCTV-8", "CCTV8", "CCTV-11", "CCTV11", "怀旧剧场",
             "风云剧场", "第一剧场", "CHC", "TVS4", "广州影视",
             "深圳电视剧", "TVB", "Now爆谷", "Now Viu", "紫金",
             "天映", "美亚电影", "东森电影", "东森洋片", "纬来电影",
             "纬来戏", "ELTA影剧", "CineMax", "AMC", "Warner",
             "好莱坞", "HITS", "龙祥", "Disney", "ANIMAX", "CN卡通"],
    "日本": ["FIGHTING TV", "サムライ", "HGTV", "NHK", "TVN"],
    "香港": ["翡翠台", "明珠台", "J2", "VIU", "HOY", "TVB", "凤凰",
             "无线新闻", "Now", "NOW", "美亚"],
    "台湾": ["公视", "公視", "华视", "華視", "中视", "中視", "民视",
             "民視", "台视", "台視", "东森", "東森", "三立", "中天",
             "TVBS", "八大", "龙华", "龍華", "纬来", "緯來", "ELTA",
             "寰宇", "非凡", "年代", "JET", "靖天", "博斯", "DAZN",
             "HBO", "CineMax", "AMC", "HITS", "好莱坞", "龙祥",
             "Discovery", "探索", "大爱", "好消息", "客家",
             "人间卫视", "霹雳", "亚洲旅游", "TLC", "鏡電視",
             "壹电视", "镜电视"],
    "大陆": ["CCTV", "央视", "央視", "浙江", "湖南", "江苏", "北京",
             "东方卫视", "东南", "辽宁", "广西", "江西", "海南",
             "厦门", "广东", "广州", "深圳", "TVS", "大湾区",
             "岭南", "江门", "嘉佳", "金鹰", "卡酷"],
}

CATEGORY_ORDER = ["大陆", "香港", "台湾", "日本", "国际",
                  "新闻", "体育", "影视", "其他"]

LOGO_ALIAS = {
    "CCTV5PLUS": "CCTV5+", "CCTV5+": "CCTV5+",
    "凤凰中文": "凤凰卫视中文台", "凤凰资讯": "凤凰卫视资讯台",
    "凤凰香港": "凤凰卫视香港台", "凤凰电影": "凤凰卫视电影台",
    "无线新闻": "无线新闻台", "无线财经": "无线财经资讯台",
    "TVB": "翡翠台", "VIUTV": "ViuTV", "HOYTV": "HOY TV",
    "民视": "民视新闻台", "中天": "中天新闻台", "东森": "东森新闻台",
    "三立": "三立新闻台", "TVBS": "TVBS新闻台", "年代": "年代新闻",
    "八大": "八大第一台", "非凡": "非凡新闻台", "纬来": "纬来综合台",
    "龙华": "龙华偶像台", "大爱": "大爱一台",
    "翡翠台": "翡翠台", "明珠台": "明珠台",
}


def _log(msg):
    print("[玉山] %s" % msg, flush=True)


def _clean_name(s):
    return re.sub(r'\s*\[[^\]]*\]\s*$', '', str(s or '')).strip()


def _fallback_logo(name):
    if not name:
        return ""
    n = re.sub(
        r'(?:[-\s_·]*)(?:高清|超清|标清|蓝光|HD|FHD|UHD|4K|SD|1080P|8M|超高清)$',
        '', str(name).strip(), flags=re.IGNORECASE)
    norm = re.sub(r'[\s\-_\.\(\)\[\]（）【】·]', '', n).upper()
    m = re.search(r'CCTV(\d+)(\+|PLUS)?', norm)
    if m:
        return LOGO_CDN.format("CCTV" + m.group(1) + ("+" if m.group(2) else ""))
    for k in sorted(LOGO_ALIAS, key=len, reverse=True):
        if k.upper() in norm:
            return LOGO_CDN.format(urllib.parse.quote(LOGO_ALIAS[k]))
    if re.search(r'[\u4e00-\u9fff]', n):
        return LOGO_CDN.format(urllib.parse.quote(n))
    return ""


def _detect_cat(name):
    if not name:
        return "国际"
    low = name.lower()
    for cat in CATEGORY_ORDER:
        for kw in CATEGORY_RULES.get(cat, []):
            if kw.lower() in low:
                return cat
    return "国际"


# ============================================================
# 网络拉取
# ============================================================
def _fetch_once(ua):
    """单次拉取，超时 5 秒"""
    headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.liaobagua.com/",
    }

    # 优先 requests
    if HAS_REQ:
        try:
            r = requests.get(M3U_URL, headers=headers, verify=False,
                             timeout=FETCH_TIMEOUT, allow_redirects=True)
            if r.status_code == 200 and r.text and "#EXTM3U" in r.text:
                return r.text
        except Exception:
            pass

    # 兜底 urllib
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx))
        rq = urllib.request.Request(M3U_URL, headers=headers)
        with opener.open(rq, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read()
            if raw.startswith(b"\x1f\x8b"):
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="ignore")
            if text and "#EXTM3U" in text:
                return text
    except Exception:
        pass

    return ""


def fetch_m3u():
    """拉 M3U，失败换 UA 重试一次"""
    for i in range(FETCH_RETRY + 1):
        ua = UA_LIST[i % len(UA_LIST)]
        text = _fetch_once(ua)
        if text:
            _log("第 %d 次尝试成功 (%d 字节)" % (i + 1, len(text)))
            return text
        if i < FETCH_RETRY:
            _log("第 %d 次失败，换 UA 重试" % (i + 1))
            time.sleep(0.3)
    _log("全部尝试失败")
    return ""


# ============================================================
# M3U 解析 / 分组
# ============================================================
def parse_m3u(text):
    out = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = re.search(r'tvg-name="([^"]*)"', line)
            tvg = m.group(1).strip() if m else ""
            m = re.search(r'tvg-logo="([^"]*)"', line)
            logo = m.group(1).strip() if m else ""
            display = ""
            last_q = line.rfind('"')
            if last_q >= 0:
                tail = line[last_q + 1:]
                if "," in tail:
                    display = tail.split(",", 1)[1].strip()
            elif "," in line:
                display = line.split(",", 1)[1].strip()
            cur = {"tvg": tvg, "display": display, "logo": logo,
                   "url": "", "ua": "", "referer": ""}
            continue
        if line.startswith("#EXTVLCOPT"):
            if cur is None:
                continue
            if "http-user-agent=" in line:
                cur["ua"] = line.split("=", 1)[1].strip()
            elif "http-referrer=" in line:
                cur["referer"] = line.split("=", 1)[1].strip()
            continue
        if line.startswith("#"):
            continue
        if cur is not None and line.startswith(("http://", "https://")):
            cur["url"] = line
            out.append(cur)
            cur = None
    return out


def build_channels(text):
    raw = parse_m3u(text)
    grouped = {}
    restricted = []
    for item in raw:
        display = _clean_name(item["display"] or item["tvg"])
        if not display:
            continue
        rec = {
            "name": display,
            "url": item["url"],
            "logo": item["logo"] or _fallback_logo(display),
            "ua": item["ua"],
            "referer": item["referer"],
        }
        if item["tvg"] in RESTRICTED or display in RESTRICTED:
            rec["cat"] = "限制"
            restricted.append(rec)
            continue
        rec["cat"] = _detect_cat(display)
        grouped.setdefault(rec["cat"], []).append(rec)

    result = []
    for cat in CATEGORY_ORDER:
        if cat == "限制":
            continue
        if cat in grouped and grouped[cat]:
            result.append([cat, grouped.pop(cat)])
    for cat, lst in grouped.items():
        if lst:
            result.append([cat, lst])
    if restricted:
        result.append(["限制", restricted])
    return result


# ============================================================
# 缓存读写
# ============================================================
def read_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return None, 0
        age = time.time() - os.path.getmtime(CACHE_FILE)
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, age
    except Exception:
        return None, 0


def write_cache(channels):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False)
        return True
    except Exception as e:
        _log("缓存写入失败: %s" % str(e)[:60])
        return False


def load_channels():
    """
    加载频道：内存 → 磁盘 → 网络
    核心策略：网络失败时用磁盘（哪怕过期），保证不空白
    """
    # 1. 先看磁盘缓存
    cached, age = read_cache()
    if cached and age < CACHE_TTL:
        _log("用缓存 (%.0f 秒前)" % age)
        return cached

    # 2. 拉新的
    _log("拉取 M3U...")
    text = fetch_m3u()

    if text:
        channels = build_channels(text)
        if channels:
            write_cache(channels)
            total = sum(len(lst) for _, lst in channels)
            _log("成功: %d 组 / %d 频道" % (len(channels), total))
            return channels

    # 3. 拉取失败或解析失败 → 用旧缓存（哪怕过期）
    if cached:
        _log("⚠ 拉取失败，用旧缓存 (%d 小时前)" % (age // 3600))
        return cached

    _log("⚠ 无可用数据")
    return []


# ============================================================
# TVBox Spider
# ============================================================
class Spider(_Base):

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._channels = None

    def getName(self):
        return "玉山直播"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _load(self):
        # 进程内内存缓存
        if self._channels is None:
            self._channels = load_channels()
        return self._channels

    def homeContent(self, filter=False):
        channels = self._load()
        classes = []
        for cat, lst in channels:
            if not lst:
                continue
            classes.append({
                "type_id": cat,
                "type_name": "%s (%d)" % (cat, len(lst)),
            })
        if not classes:
            classes = [{"type_id": "empty", "type_name": "无频道"}]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        tid = str(tid or "").strip()
        channels = self._load()
        vids = []
        for cat, lst in channels:
            if cat != tid:
                continue
            for i, ch in enumerate(lst):
                vids.append({
                    "vod_id": "%s@%d" % (cat, i),
                    "vod_name": ch["name"],
                    "vod_pic": ch.get("logo", ""),
                    "vod_remarks": cat,
                })
        return {"list": vids, "page": 1, "pagecount": 1,
                "limit": len(vids), "total": len(vids)}

    def _find(self, cat, idx):
        channels = self._load()
        for c, lst in channels:
            if c == cat and 0 <= idx < len(lst):
                return lst[idx]
        return None

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        s = str(ids[0])
        if "@" not in s:
            return {"list": []}
        cat, idx_s = s.rsplit("@", 1)
        try:
            idx = int(idx_s)
        except Exception:
            return {"list": []}
        ch = self._find(cat, idx)
        if not ch:
            return {"list": []}
        return {"list": [{
            "vod_id": s,
            "vod_name": ch["name"],
            "vod_pic": ch.get("logo", ""),
            "vod_remarks": cat,
            "vod_play_from": "玉山直播",
            "vod_play_url": "%s$%s" % (ch["name"], s),
        }]}

    def playerContent(self, flag, pid, vipFlags=None):
        s = str(pid or "")
        if "$" in s:
            s = s.split("$", 1)[1]
        if "@" not in s:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        cat, idx_s = s.rsplit("@", 1)
        try:
            idx = int(idx_s)
        except Exception:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        ch = self._find(cat, idx)
        if not ch:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        headers = {
            "User-Agent": ch.get("ua") or UA_LIST[0],
            "Referer": ch.get("referer") or "https://www.liaobagua.com/",
        }
        return {"parse": 0, "jx": 0, "url": ch["url"], "header": headers}

    def searchContent(self, key, quick=False, pg="1"):
        key = str(key or "").lower().strip()
        if not key:
            return {"list": []}
        out = []
        for cat, lst in self._load():
            for i, ch in enumerate(lst):
                if key in ch["name"].lower():
                    out.append({
                        "vod_id": "%s@%d" % (cat, i),
                        "vod_name": ch["name"],
                        "vod_pic": ch.get("logo", ""),
                        "vod_remarks": cat,
                    })
        return {"list": out}

    def localProxy(self, param):
        return [404, "text/plain", b""]

    def destroy(self):
        return ""


if __name__ == '__main__':
    pass