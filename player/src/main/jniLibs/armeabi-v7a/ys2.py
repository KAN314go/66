# -*- coding: utf-8 -*-
# freetv.sh 直播源 - TVBox FongMi Spider (诊断版)
# 台标优先从 M3U 拉取, 112114 兜底; 播放保持原逻辑

import os
import re
import json
import gzip
import time
import urllib.parse

try:
    from base.spider import Spider as _Base
except ImportError:
    class _Base:
        def init(self, extend=""):
            pass

try:
    from curl_cffi import requests as cffi
    HAS_CFFI = True
except ImportError:
    HAS_CFFI = False

try:
    import requests as req_lib
    HAS_REQ = True
except ImportError:
    HAS_REQ = False


# ============================================================
# 配置
# ============================================================
API_URL = "https://s.freetv.sh/api/box/v1/channels"
M3U_URL = "https://www.liaobagua.com/tv/tv.php?a=play"

# ★ 缓存路径 (改成 Download 更容易可写)
CACHE_DIR = "/sdcard/Download"
CACHE_FILE = os.path.join(CACHE_DIR, "ys_cache.json")
CACHE_TTL = 3600

HEADERS = {
    "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJpcHR2LXNhYXMtYm94Iiwic3ViIjoiNzczNyIsInRlbmFudF9pZCI6NywiZW5kX3VzZXJfaWQiOjc3MzcsImRldmljZV9pZCI6ODQ2NSwiZGV2aWNlX21hYyI6IjQ0OkZFOkVGOjg0OjZBOkQ1IiwidHlwZSI6ImJveCIsImp0aSI6IjAzMTgzOTUwNjA1YjRkMjA4MmM3NTkxMmQ0YjRhY2UwIiwiaWF0IjoxNzg3OTQzNjgxLCJleHAiOjE3OTA1MzU2ODF9.esNteZggNyKGl7mLbSLM0yt49t4MC61e5iHfsoBBrOE",
    "x-instance-key": "ai_vEJ7UylECiCUAf_Qx1PKc-H-5AFVaUxg",
    "x-tenant-slug": "yushanvideo",
    "x-box-proto": "1.0",
    "Accept-Language": "zh-CN",
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "okhttp/3.12.13",
}

M3U_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.liaobagua.com/",
}

LOGO_TEMPLATE = "https://epg.112114.xyz/logo/{name}.png"

RESTRICTED_NAMES = [
    "乐活频道", "HiPLAY", "彩虹R频道", "潘朵拉玩美", "潘朵拉粉红",
    "K频道", "彩虹MOIVE", "彩虹e台", "星颖", "HAPPY",
]

EXACT_MAP = {"凤凰卫视中文台": "大陆"}

KEYWORD_RULES = {
    "体育": ["CCTV-5", "CCTV5", "风云足球", "高尔夫网球", "央视台球",
             "广东体育", "五星体育", "快乐垂钓",
             "Now Sports", "NowSports", "Now Golf", "Now Prime", "NOW CH6",
             "纬来体育", "ELTA体育", "博斯", "DAZN", "智林体育",
             "欧洲体育", "EURO SPORT", "NBA"],
    "新闻": ["CCTV-13", "CCTV13", "第一财经", "东方财经",
             "广东新闻", "广州新闻", "上海新闻",
             "凤凰资讯", "无线新闻", "Now新闻", "Now直播", "Now财经",
             "华视新闻", "中视新闻", "民视新闻", "台视新闻",
             "TVBS新闻", "TVBS News", "中天新闻", "三立新闻",
             "寰宇新闻", "非凡新闻", "年代新闻", "年代much",
             "鏡電視", "壹电视新闻", "三立inews", "非凡商業",
             "德国之声", "Sky News", "NHK News", "CNN", "Bloomberg",
             "France24", "TV5", "天下卫视"],
    "影视": ["CCTV-8", "CCTV8", "CCTV-11", "CCTV11",
             "怀旧剧场", "风云剧场", "第一剧场", "CHC",
             "TVS4", "广州影视", "深圳电视剧",
             "TVB", "Now爆谷", "Now Viu", "Now 华剧", "Now 華劇",
             "NowJelli", "紫金",
             "天映", "CCM", "美亚电影",
             "八大戏", "龙华", "东森戏", "东森电影", "东森洋片",
             "纬来电影", "纬来戏", "ELTA影剧", "CineMax", "CATCH", "AMC",
             "靖天电影", "靖天映画", "靖洋", "EYE TV", "Warner",
             "好莱坞", "HITS", "龙祥", "公视戏", "Astro",
             "Disney", "ANIMAX", "CN卡通", "MOMO", "Momo"],
    "日本": ["FIGHTING TV", "サムライ", "HGTV", "NHK", "TVN"],
    "香港": ["翡翠台", "明珠台", "J2", "VIU", "HOY", "TVB",
             "凤凰", "无线新闻", "Now", "NOW", "美亚",
             "香港国际财经"],
    "台湾": ["公视", "公視", "华视", "華視", "中视", "中視",
             "民视", "民視", "台视", "台視", "东森", "東森",
             "三立", "中天", "TVBS", "八大", "龙华", "龍華",
             "纬来", "緯來", "ELTA", "寰宇", "非凡", "年代",
             "JET", "靖天", "靖洋", "博斯", "DAZN",
             "NatGeo", "HBO", "CineMax", "AMC", "Warner", "HITS",
             "好莱坞", "龙祥", "美食星球", "动物星球",
             "CN卡通", "MOMO", "Momo", "Disney", "ANIMAX", "AXN",
             "MTV", "大爱", "好消息", "国会", "客家",
             "原住民", "人间卫视", "霹雳", "国兴", "东风",
             "亚洲旅游", "afc", "Travel", "Outdoor", "TLC",
             "鏡電視", "佛衛", "高點", "信吉",
             "智林", "阿里郎", "天下卫视", "CHANNEL V",
             "BBC", "Z频道", "Fashion", "TV5", "France24",
             "Discovery", "探索", "CATCH", "台灣藝術",
             "華藏", "韓國娛樂", "MTV Live", "History",
             "德国之声", "Bloomberg", "CNN", "EURO SPORT",
             "TRACE", "Astro", "Sky News", "NHK",
             "壹电视", "镜电视"],
    "大陆": ["CCTV", "央视", "央視",
             "浙江", "湖南", "江苏", "北京", "东方卫视",
             "东南", "辽宁", "广西", "江西", "海南", "厦门",
             "广东", "广州", "深圳", "TVS", "大湾区", "岭南", "江门",
             "嘉佳", "金鹰", "卡酷"],
}

CATEGORY_ORDER = ["大陆", "日本", "香港", "台湾", "国际",
                  "新闻", "体育", "影视", "限制"]

TRAD_TO_SIMP = str.maketrans({
    "視": "视", "華": "华", "東": "东", "臺": "台", "灣": "湾",
    "龍": "龙", "電": "电", "衛": "卫", "劇": "剧", "頻": "频",
    "國": "国", "際": "际", "體": "体", "樂": "乐", "園": "园",
    "兒": "儿", "戲": "戏", "財": "财", "經": "经", "紀": "纪",
    "錄": "录", "廣": "广", "藝": "艺", "術": "术", "銀": "银",
    "導": "导", "娛": "娱", "綜": "综", "動": "动", "畫": "画",
    "聲": "声", "優": "优", "點": "点", "戶": "户", "鳥": "鸟",
    "陽": "阳", "羅": "罗", "豐": "丰", "將": "将", "軍": "军",
    "雞": "鸡", "馬": "马", "驗": "验", "歲": "岁", "萬": "万",
    "風": "风", "獨": "独", "緣": "缘", "會": "会", "內": "内",
    "後": "后", "裏": "里", "雙": "双", "傳": "传", "誠": "诚",
    "時": "时", "開": "开", "關": "关", "門": "门", "問": "问",
    "題": "题", "學": "学", "麗": "丽", "樓": "楼", "車": "车",
    "見": "见", "觀": "观", "話": "话", "語": "语", "讀": "读",
    "書": "书", "寫": "写", "記": "记", "識": "识",
    "齊": "齐", "業": "业", "線": "线", "資": "资", "訊": "讯",
    "號": "号", "別": "别", "級": "级", "區": "区", "億": "亿",
    "軸": "轴", "師": "师", "數": "数", "據": "据", "廠": "厂",
    "鐘": "钟", "擊": "击", "戰": "战",
})

ALIAS_MAP = {
    "凤凰卫视中文台": "凤凰卫视",
    "凤凰卫视资讯台": "凤凰资讯",
    "凤凰卫视香港台": "凤凰香港",
    "无线新闻台": "无线新闻",
    "无线财经台": "无线财经",
    "TVB明珠台": "明珠台",
    "TVB翡翠台": "翡翠台",
    "TVB无线新闻": "无线新闻",
    "公视主频": "公视",
    "公视台语台": "公视台语",
    "公视三台": "公视3",
    "华视主频": "华视",
    "中视主频": "中视",
    "民视无线台": "民视",
    "民视新闻台": "民视新闻",
    "民视台湾台": "民视台湾",
    "民视第一台": "民视第一",
    "台视主频": "台视",
    "东森幼幼台": "东森幼幼",
    "东森综合台": "东森综合",
    "东森新闻台": "东森新闻",
    "东森戏剧台": "东森戏剧",
    "东森电影台": "东森电影",
    "东森洋片台": "东森洋片",
    "东森财经新闻": "东森财经",
    "三立台湾台": "三立台湾",
    "三立都会台": "三立都会",
    "三立新闻台": "三立新闻",
    "三立综合台": "三立综合",
    "TVBS新闻台": "TVBS新闻",
    "TVBS欢乐台": "TVBS欢乐",
    "TVBS综合台": "TVBS综合",
    "中天新闻台": "中天新闻",
    "中天综合台": "中天综合",
    "中天娱乐台": "中天娱乐",
    "八大综合台": "八大综合",
    "八大第一台": "八大第一",
    "八大娱乐台": "八大娱乐",
    "八大戏剧台": "八大戏剧",
    "纬来体育台": "纬来体育",
    "纬来电影台": "纬来电影",
    "纬来戏剧台": "纬来戏剧",
    "纬来育乐台": "纬来育乐",
    "纬来综合台": "纬来综合",
    "纬来日本台": "纬来日本",
    "龙华戏剧台": "龙华戏剧",
    "龙华偶像台": "龙华偶像",
    "龙华电影台": "龙华电影",
    "龙华动画台": "龙华动画",
    "龙华洋片台": "龙华洋片",
    "龙华日韩台": "龙华日韩",
    "非凡新闻台": "非凡新闻",
    "非凡商业台": "非凡商业",
    "年代新闻台": "年代新闻",
    "寰宇新闻台": "寰宇新闻",
    "寰宇综合台": "寰宇综合",
    "靖天电影台": "靖天电影",
    "靖天映画台": "靖天映画",
    "靖洋戏剧台": "靖洋戏剧",
    "靖天国际台": "靖天国际",
    "大爱电视台": "大爱",
    "大爱二台": "大爱2",
    "好消息一台": "好消息",
    "好消息二台": "好消息2",
    "国会频道1": "国会1",
    "国会频道2": "国会2",
    "客家电视台": "客家电视",
    "原住民族电视台": "原住民",
    "人间卫视": "人间卫视",
    "霹雳台湾台": "霹雳台湾",
    "国兴卫视": "国兴卫视",
    "东风卫视": "东风",
    "亚洲旅游台": "亚洲旅游",
    "美食星球": "美食星球",
    "动物星球": "动物星球",
    "历史频道": "History",
    "探索频道": "Discovery",
    "国家地理": "NatGeo",
    "国家地理野生": "NatGeoWild",
    "FIGHTING TV サムライ": "FIGHTINGTV",
    "NHK World Premium": "NHKWorld",
    "CNN International": "CNN",
    "CNN国际": "CNN",
    "BBC World News": "BBC",
    "BBC新闻": "BBC",
    "Bloomberg TV": "Bloomberg",
    "彭博财经": "Bloomberg",
    "France 24": "France24",
    "TV5MONDE": "TV5",
    "Sky News HD": "SkyNews",
    "DW中文": "德国之声",
    "半岛电视台": "半岛",
}


# ★ 全局状态记录
_STATUS = {"source": "none", "detail": "", "cache_path": CACHE_FILE}


def _log(msg):
    print("[freetv] %s" % msg, flush=True)


def clean_name(name):
    return re.sub(r'\s*\[[^\]]*\]\s*$', '', str(name or '')).strip()


def detect_category(name):
    if not name:
        return "国际"
    if name in EXACT_MAP:
        return EXACT_MAP[name]
    low = name.lower()
    for cat, kws in KEYWORD_RULES.items():
        for kw in kws:
            if kw.lower() in low:
                return cat
    return "国际"


def clean_for_logo(name):
    if not name:
        return ""
    s = str(name).strip()
    s = re.sub(r'[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+', '', s)
    s = s.replace("ᴴᴰ", "").replace("ᴴ", "").replace("ᴰ", "")
    s = re.sub(r'(?i)[\s\-_\.]*(HD|FHD|UHD|SD|4K|8K|高清|标清|超清|蓝光|直播)[\s\-_\.]*', '', s)
    s = s.translate(TRAD_TO_SIMP)
    if s in ALIAS_MAP:
        return ALIAS_MAP[s]
    m = re.match(r'(?i)^\s*CCTV[\s\-_]*(\d+)\s*(\+)?', s)
    if m:
        return "CCTV" + m.group(1) + (m.group(2) or "")
    s = s.strip(" -_.·").replace(" ", "")
    if s in ALIAS_MAP:
        return ALIAS_MAP[s]
    return s


# ============================================================
# Spider
# ============================================================
class Spider(_Base):

    def init(self, extend=""):
        self._channels = None
        self._flat = []
        self._m3u_logo_raw = {}
        self._m3u_logo_clean = {}

        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(cfg, dict):
                    if cfg.get("api"):
                        global API_URL
                        API_URL = str(cfg["api"])
                    if cfg.get("m3u"):
                        global M3U_URL
                        M3U_URL = str(cfg["m3u"])
            except Exception:
                pass

    def _fetch(self, url, headers, timeout=15):
        h = dict(headers)
        if HAS_CFFI:
            try:
                r = cffi.get(url, headers=h, impersonate="chrome131",
                             verify=False, timeout=timeout, allow_redirects=True)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
        if HAS_REQ:
            try:
                r = req_lib.get(url, headers=h, verify=False,
                                timeout=timeout, allow_redirects=True)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            rq = urllib.request.Request(url, headers=h)
            with opener.open(rq, timeout=timeout) as resp:
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def _fetch_m3u_logos(self):
        if self._m3u_logo_raw or self._m3u_logo_clean:
            return
        _log("从 M3U 拉台标: %s" % M3U_URL)
        try:
            text = self._fetch(M3U_URL, M3U_HEADERS, timeout=12)
            if not text:
                _log("M3U 内容为空")
                return
            _log("M3U 长度: %d" % len(text))
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("#EXTINF"):
                    continue
                logo_m = re.search(r'tvg-logo="([^"]*)"', line)
                if not logo_m:
                    continue
                logo_url = logo_m.group(1).strip()
                if not logo_url:
                    continue
                tvg_name_m = re.search(r'tvg-name="([^"]*)"', line)
                tvg_name = tvg_name_m.group(1).strip() if tvg_name_m else ""
                name_m = re.search(r',\s*(.+)$', line)
                display = name_m.group(1).strip() if name_m else ""
                for nm in (tvg_name, display):
                    if nm and nm not in self._m3u_logo_raw:
                        self._m3u_logo_raw[nm] = logo_url
                for nm in (tvg_name, display):
                    if not nm:
                        continue
                    key = clean_for_logo(nm)
                    if key and key not in self._m3u_logo_clean:
                        self._m3u_logo_clean[key] = logo_url
            _log("M3U 原名字索引 %d 条, 归一化索引 %d 条" % (
                len(self._m3u_logo_raw), len(self._m3u_logo_clean)))
        except Exception as e:
            _log("M3U 解析失败: %s" % str(e)[:50])

    def _build_logo(self, name, api_logo):
        n = str(name or "").strip()
        if n in self._m3u_logo_raw:
            return self._m3u_logo_raw[n]
        key = clean_for_logo(n)
        if key and key in self._m3u_logo_clean:
            return self._m3u_logo_clean[key]
        if api_logo:
            api_logo = str(api_logo).strip()
            if api_logo.startswith("//"):
                api_logo = "https:" + api_logo
            if api_logo.startswith("http"):
                return api_logo
        if not LOGO_TEMPLATE or not key:
            return ""
        return LOGO_TEMPLATE.format(name=urllib.parse.quote(key))

    # ============================================================
    # 缓存读写 + 状态记录
    # ============================================================
    def _read_cache(self):
        try:
            if not os.path.exists(CACHE_FILE):
                return None, 0
            age = time.time() - os.path.getmtime(CACHE_FILE)
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data, age
        except Exception as e:
            _log("读缓存失败: %s" % str(e)[:60])
            return None, 0

    def _write_cache(self, channels):
        global _STATUS
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            serializable = [[cat, lst] for cat, lst in channels]
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False)
            _log("缓存已写入: %s" % CACHE_FILE)
            return True
        except Exception as e:
            _log("缓存写入失败: %s" % str(e)[:80])
            _STATUS["detail"] = "cache_write_fail:" + str(e)[:40]
            return False

    # ============================================================
    # 加载
    # ============================================================
    def _load_channels(self):
        global _STATUS
        if self._channels is not None:
            return self._channels

        # 1. 读缓存
        cached, age = self._read_cache()
        if cached and age < CACHE_TTL:
            _log("用缓存 (%.0f 秒前)" % age)
            _STATUS = {"source": "cache", "detail": "%.0fs" % age,
                       "cache_path": CACHE_FILE}
            self._channels = cached
            return self._channels

        # 2. 拉网络
        _log("拉取网络...")
        self._fetch_m3u_logos()

        grouped = {}
        restricted = []
        page = 1
        page_size = 100
        total = 0
        fetch_ok = False

        while page <= 50:
            qs = urllib.parse.urlencode({"page": page, "page_size": page_size})
            url = API_URL + "?" + qs
            body = self._fetch(url, HEADERS)
            if not body:
                break
            try:
                j = json.loads(body)
            except Exception:
                break
            items = []
            if isinstance(j, dict):
                d = j.get("data") or {}
                if isinstance(d, dict):
                    items = d.get("items") or []
            if not items:
                break
            total += len(items)
            fetch_ok = True

            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("title")
                           or item.get("channel_name") or "").strip()
                purl = str(item.get("stream_url") or item.get("url")
                           or item.get("play_url") or "").strip()
                if not name or not purl:
                    continue
                display = clean_name(name)
                api_logo = ""
                for k in ("logo", "icon", "channel_logo", "cover",
                          "tvg_logo", "tvg-logo", "image", "pic"):
                    v = item.get(k)
                    if v and isinstance(v, str) and len(v) > 5:
                        api_logo = v
                        break
                logo = self._build_logo(name, api_logo)
                record = {"name": display, "url": purl, "logo": logo}
                if name in RESTRICTED_NAMES:
                    restricted.append(record)
                    continue
                cat = detect_category(name)
                grouped.setdefault(cat, []).append(record)

            if len(items) < page_size:
                break
            page += 1

        # 3. 失败回退
        if not fetch_ok:
            if cached:
                _log("⚠ 网络失败, 用旧缓存 (%.0f 小时前)" % (age / 3600))
                _STATUS = {"source": "stale", "detail": "%.1fh" % (age / 3600),
                           "cache_path": CACHE_FILE}
                self._channels = cached
                return self._channels
            _log("⚠ 网络失败, 无缓存")
            _STATUS = {"source": "fail", "detail": "no-cache",
                       "cache_path": CACHE_FILE}
            self._channels = []
            return self._channels

        ordered = []
        for cat in CATEGORY_ORDER:
            if cat == "限制":
                continue
            if cat in grouped:
                ordered.append((cat, grouped.pop(cat)))
        for cat, lst in grouped.items():
            ordered.append((cat, lst))
        if restricted:
            ordered.append(("限制", restricted))

        self._channels = ordered
        _log("共 %d 频道, %d 组" % (total, len(ordered)))

        # 4. 写缓存
        write_ok = self._write_cache(ordered)
        _STATUS = {"source": "network",
                   "detail": "cache_ok" if write_ok else "cache_fail",
                   "cache_path": CACHE_FILE}
        return ordered

    def _build_flat(self):
        if self._flat:
            return self._flat
        flat = []
        for cat, lst in self._load_channels():
            for ch in lst:
                flat.append({
                    "name": ch["name"],
                    "url": ch["url"],
                    "logo": ch.get("logo", ""),
                    "cat": cat,
                })
        self._flat = flat
        return flat

    # ============================================================
    # TVBox 接口
    # ============================================================
    def homeContent(self, filter):
        global _STATUS
        _STATUS = {"source": "none", "detail": "", "cache_path": CACHE_FILE}

        ordered = self._load_channels()

        marker = {
            "cache": "⚡",
            "network": "🌐",
            "stale": "💾",
            "fail": "❌",
            "none": "❓",
        }.get(_STATUS.get("source"), "❓")

        # 缓存是否可写提示
        note = _STATUS.get("detail", "")
        if _STATUS.get("source") == "network" and note == "cache_fail":
            marker = "🌐⚠"

        classes = []
        for cat, lst in ordered:
            classes.append({
                "type_id": cat,
                "type_name": "%s %s (%d)" % (marker, cat, len(lst)),
            })

        if not classes:
            classes = [{
                "type_id": "empty",
                "type_name": "%s 无频道 [%s]" % (marker, note or "empty"),
            }]

        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid).strip()
        flat = self._build_flat()
        vids = []
        for i, ch in enumerate(flat):
            if ch["cat"] != tid:
                continue
            vids.append({
                "vod_id": "live#%d" % i,
                "vod_name": ch["name"],
                "vod_pic": ch.get("logo", ""),
                "vod_remarks": "",
                "style": {"type": "rect", "ratio": 1.33},
            })
        return {
            "list": vids, "page": 1, "pagecount": 1,
            "limit": len(vids) or 20, "total": len(vids),
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        s = str(ids[0])
        if s.startswith("live#"):
            try:
                idx = int(s.split("#", 1)[1])
            except Exception:
                return {"list": []}
            flat = self._build_flat()
            if 0 <= idx < len(flat):
                ch = flat[idx]
                return {"list": [{
                    "vod_id": s,
                    "vod_name": ch["name"],
                    "vod_pic": ch.get("logo", ""),
                    "vod_remarks": "",
                    "vod_play_from": "直播",
                    "vod_play_url": "%s$%s" % (ch["name"], ch["url"]),
                }]}
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        s = str(id or "").strip()
        if "$" in s:
            s = s.split("$")[-1]
        if s.startswith("live#"):
            try:
                idx = int(s.split("#", 1)[1])
            except Exception:
                return {"parse": 0, "jx": 0, "url": "", "header": {}}
            flat = self._build_flat()
            if 0 <= idx < len(flat):
                return {
                    "parse": 0, "jx": 0,
                    "url": flat[idx]["url"],
                    "header": {},
                }
        if s.startswith("http"):
            return {"parse": 0, "jx": 0, "url": s, "header": {}}
        return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def localProxy(self, param):
        return [404, "text/plain", b""]

    def action(self, action_str):
        return ""
