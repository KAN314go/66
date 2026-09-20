# -*- coding: utf-8 -*-
# freetv.sh 直播源 - 直接解析 M3U
# M3U: https://www.liaobagua.com/tv/tv.php?a=play

import re
import gzip
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


M3U_URL = "https://www.liaobagua.com/tv/tv.php?a=play"

UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

FETCH_HEADERS = {
    "User-Agent": UA_BROWSER,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.liaobagua.com/",
}

RESTRICTED_NAMES = [
    "乐活频道", "HiPLAY", "彩虹R频道", "潘朵拉玩美", "潘朵拉粉红",
    "K频道", "彩虹MOIVE", "彩虹e台", "星颖", "HAPPY",
]

EXACT_MAP = {"凤凰卫视中文台": "大陆"}

KEYWORD_RULES = {
    "体育": ["CCTV-5", "CCTV5", "风云足球", "高尔夫网球", "央视台球",
             "广东体育", "五星体育", "快乐垂钓", "Now Sports", "NowSports",
             "Now Golf", "Now Prime", "NOW CH6", "纬来体育", "ELTA体育",
             "博斯", "DAZN", "智林体育", "欧洲体育", "EURO SPORT", "NBA"],
    "新闻": ["CCTV-13", "CCTV13", "第一财经", "东方财经", "广东新闻",
             "广州新闻", "上海新闻", "凤凰资讯", "无线新闻", "Now新闻",
             "Now直播", "Now财经", "华视新闻", "中视新闻", "民视新闻",
             "台视新闻", "TVBS新闻", "TVBS News", "中天新闻", "三立新闻",
             "寰宇新闻", "非凡新闻", "年代新闻", "年代much", "鏡電視",
             "壹电视新闻", "三立inews", "非凡商業", "德国之声", "Sky News",
             "NHK News", "CNN", "Bloomberg", "France24", "TV5", "天下卫视"],
    "影视": ["CCTV-8", "CCTV8", "CCTV-11", "CCTV11", "怀旧剧场",
             "风云剧场", "第一剧场", "CHC", "TVS4", "广州影视",
             "深圳电视剧", "TVB", "Now爆谷", "Now Viu", "Now 华剧",
             "Now 華劇", "NowJelli", "紫金", "天映", "CCM", "美亚电影",
             "八大戏", "龙华", "东森戏", "东森电影", "东森洋片",
             "纬来电影", "纬来戏", "ELTA影剧", "CineMax", "CATCH", "AMC",
             "靖天电影", "靖天映画", "靖洋", "EYE TV", "Warner",
             "好莱坞", "HITS", "龙祥", "公视戏", "Astro",
             "Disney", "ANIMAX", "CN卡通", "MOMO", "Momo"],
    "日本": ["FIGHTING TV", "サムライ", "HGTV", "NHK", "TVN"],
    "香港": ["翡翠台", "明珠台", "J2", "VIU", "HOY", "TVB", "凤凰",
             "无线新闻", "Now", "NOW", "美亚", "香港国际财经"],
    "台湾": ["公视", "公視", "华视", "華視", "中视", "中視", "民视", "民視",
             "台视", "台視", "东森", "東森", "三立", "中天", "TVBS",
             "八大", "龙华", "龍華", "纬来", "緯來", "ELTA", "寰宇",
             "非凡", "年代", "JET", "靖天", "靖洋", "博斯", "DAZN",
             "NatGeo", "HBO", "CineMax", "AMC", "Warner", "HITS",
             "好莱坞", "龙祥", "美食星球", "动物星球", "CN卡通", "MOMO",
             "Momo", "Disney", "ANIMAX", "AXN", "MTV", "大爱", "好消息",
             "国会", "客家", "原住民", "人间卫视", "霹雳", "国兴", "东风",
             "亚洲旅游", "afc", "Travel", "Outdoor", "TLC", "鏡電視",
             "佛衛", "高點", "信吉", "智林", "阿里郎", "天下卫视",
             "CHANNEL V", "BBC", "Z频道", "Fashion", "TV5", "France24",
             "Discovery", "探索", "CATCH", "台灣藝術", "華藏", "韓國娛樂",
             "MTV Live", "History", "德国之声", "Bloomberg", "CNN",
             "EURO SPORT", "TRACE", "Astro", "Sky News", "NHK",
             "壹电视", "镜电视"],
    "大陆": ["CCTV", "央视", "央視", "浙江", "湖南", "江苏", "北京",
             "东方卫视", "东南", "辽宁", "广西", "江西", "海南", "厦门",
             "广东", "广州", "深圳", "TVS", "大湾区", "岭南", "江门",
             "嘉佳", "金鹰", "卡酷"],
}

CATEGORY_ORDER = ["大陆", "日本", "香港", "台湾", "国际",
                  "新闻", "体育", "影视", "限制"]


def clean_display_name(name):
    """去掉末尾的 [1080p] 之类"""
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


class Spider(_Base):

    def init(self, extend=""):
        self._channels = None
        self._flat = []
        self._log_printed = False

        if extend:
            try:
                import json
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(cfg, dict) and cfg.get("m3u"):
                    global M3U_URL
                    M3U_URL = str(cfg["m3u"])
            except Exception:
                pass

    def _log(self, msg):
        print("[freetv] %s" % msg, flush=True)

    # ============================================================
    # 拉取 m3u
    # ============================================================
    def _fetch_m3u(self):
        h = dict(FETCH_HEADERS)

        if HAS_CFFI:
            try:
                r = cffi.get(M3U_URL, headers=h, impersonate="chrome131",
                             verify=False, timeout=15, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    self._log("cffi 拉到 %d 字节" % len(r.text))
                    return r.text
                self._log("cffi %d" % r.status_code)
            except Exception as e:
                self._log("cffi err: %s" % str(e)[:40])

        if HAS_REQ:
            try:
                r = req_lib.get(M3U_URL, headers=h, verify=False,
                                timeout=15, allow_redirects=True)
                if r.status_code == 200 and r.text:
                    self._log("req 拉到 %d 字节" % len(r.text))
                    return r.text
                self._log("req %d" % r.status_code)
            except Exception as e:
                self._log("req err: %s" % str(e)[:40])

        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            rq = urllib.request.Request(M3U_URL, headers=h)
            with opener.open(rq, timeout=15) as resp:
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", errors="ignore")
                self._log("urllib 拉到 %d 字节" % len(text))
                return text
        except Exception as e:
            self._log("urllib err: %s" % str(e)[:40])

        return ""

    # ============================================================
    # 解析 m3u
    # ============================================================
    def _parse_m3u(self, text):
        """
        逐行解析:
          #EXTINF:-1 tvg-name="X" tvg-logo="Y" group-title="Z",显示名
          #EXTVLCOPT:http-user-agent=xxx
          #EXTVLCOPT:http-referrer=xxx
          http://xxx.m3u8
        返回 [{'name':.., 'display':.., 'logo':.., 'group':..,
               'url':.., 'ua':.., 'referer':..}, ...]
        """
        out = []
        lines = text.splitlines()
        i = 0
        cur = None

        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line:
                continue

            if line.startswith("#EXTINF"):
                # 开始新频道
                tvg_name_m = re.search(r'tvg-name="([^"]*)"', line)
                tvg_name = tvg_name_m.group(1).strip() if tvg_name_m else ""

                logo_m = re.search(r'tvg-logo="([^"]*)"', line)
                logo = logo_m.group(1).strip() if logo_m else ""

                group_m = re.search(r'group-title="([^"]*)"', line)
                group = group_m.group(1).strip() if group_m else ""

                # 逗号后的显示名
                display = ""
                if "," in line:
                    display = line.split(",", 1)[1].strip()

                cur = {
                    "tvg_name": tvg_name,
                    "display": display,
                    "logo": logo,
                    "group": group,
                    "url": "",
                    "ua": "",
                    "referer": "",
                }
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
                # 其它指令忽略
                continue

            # 普通行: 视为 URL
            if cur is not None and (line.startswith("http://") or line.startswith("https://")):
                cur["url"] = line
                out.append(cur)
                cur = None

        return out

    # ============================================================
    # 加载频道
    # ============================================================
    def _load_channels(self):
        if self._channels is not None:
            return self._channels

        self._log("拉取 M3U: %s" % M3U_URL)
        text = self._fetch_m3u()
        if not text:
            self._log("M3U 拿不到")
            self._channels = []
            return self._channels

        raw_list = self._parse_m3u(text)
        self._log("解析出 %d 个频道" % len(raw_list))

        grouped = {}
        restricted = []
        no_logo_count = 0

        for item in raw_list:
            # 显示名优先级: 逗号后的名 > tvg-name
            display = item["display"] or item["tvg_name"]
            display = clean_display_name(display)
            if not display:
                continue

            name_for_cat = item["tvg_name"] or display
            logo = item["logo"]
            if not logo:
                no_logo_count += 1

            record = {
                "name": display,
                "url": item["url"],
                "logo": logo,
                "ua": item["ua"],
                "referer": item["referer"],
            }

            # 限制频道
            if name_for_cat in RESTRICTED_NAMES:
                restricted.append(record)
                continue

            cat = detect_category(name_for_cat)
            grouped.setdefault(cat, []).append(record)

        # 按 CATEGORY_ORDER 排序
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
        self._log("分组后: %d 组, 无图频道: %d" % (len(ordered), no_logo_count))

        # 打印每组前 3 个示例
        for cat, lst in ordered[:3]:
            self._log("  %s (%d):" % (cat, len(lst)))
            for ch in lst[:3]:
                self._log("    %s | logo=%s" % (
                    ch["name"], ch["logo"][:50] if ch["logo"] else "(无)"
                ))

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
                    "logo": ch["logo"],
                    "ua": ch.get("ua", ""),
                    "referer": ch.get("referer", ""),
                    "cat": cat,
                })
        self._flat = flat
        return self._flat

    # ============================================================
    # TVBox 接口
    # ============================================================
    def homeContent(self, filter):
        ordered = self._load_channels()
        classes = []
        for cat, lst in ordered:
            classes.append({
                "type_id": cat,
                "type_name": "%s (%d)" % (cat, len(lst)),
            })
        if not classes:
            classes = [{"type_id": "empty", "type_name": "无频道"}]
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
                "vod_pic": ch["logo"],
                "vod_remarks": "",
                "style": {"type": "rect", "ratio": 1.33},
            })

        return {
            "list": vids,
            "page": 1,
            "pagecount": 1,
            "limit": len(vids) or 20,
            "total": len(vids),
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
                    "vod_pic": ch["logo"],
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
                ch = flat[idx]
                # 按 m3u 里的 EXTVLCOPT 设置 header
                headers = {
                    "User-Agent": ch.get("ua") or UA_BROWSER,
                }
                if ch.get("referer"):
                    headers["Referer"] = ch["referer"]
                else:
                    headers["Referer"] = "https://www.liaobagua.com/"
                return {
                    "parse": 0, "jx": 0,
                    "url": ch["url"],
                    "header": headers,
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