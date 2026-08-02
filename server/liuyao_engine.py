"""
六爻排盘引擎
包含：四柱计算、神煞、时间起卦、纳甲、六亲、六神、世应、空亡
"""
import math
import random
from datetime import datetime, timedelta
from typing import Optional

# ==========================================
# 基础数据表
# ==========================================

TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 五行
WUXING = {"金": 0, "木": 1, "水": 2, "火": 3, "土": 4}
WUXING_NAMES = ["金", "木", "水", "火", "土"]

# 天干五行
GAN_WX = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

# 地支五行
ZHI_WX = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 地支藏干
ZHI_CANG = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

# 八卦：乾、兑、离、震、巽、坎、艮、坤
# 用数字表示：阳爻=1, 阴爻=0，从下到上
GUA_SYMBOLS = {
    "乾": "111", "兑": "011", "离": "101", "震": "001",
    "巽": "110", "坎": "010", "艮": "100", "坤": "000",
}

# 六十四卦：key 是从下到上六个爻的二进制字符串
HEXAGRAM_MAP = {
    "111111": "乾为天", "000000": "坤为地", "010001": "水雷屯", "100010": "山水蒙",
    "010111": "水天需", "111010": "天水讼", "000010": "地水师", "010000": "水地比",
    "110111": "风天小畜", "111011": "天泽履", "000111": "地天泰", "111000": "天地否",
    "111101": "天火同人", "101111": "火天大有", "000100": "地山谦", "001000": "雷地豫",
    "011001": "泽雷随", "100110": "山风蛊", "000011": "地泽临", "110000": "风地观",
    "101001": "火雷噬嗑", "100101": "山火贲", "100000": "山地剥", "000001": "地雷复",
    "100111": "天雷无妄", "111100": "山天大畜", "100001": "山雷颐", "011110": "泽风大过",
    "010010": "坎为水", "101101": "离为火",
    "001110": "泽山咸", "011100": "雷风恒", "001111": "雷天大壮", "000101": "地火明夷",
    "101000": "火地晋", "110101": "风火家人", "101011": "火泽睽", "010100": "水山蹇",
    "001010": "雷水解", "100011": "山泽损", "110001": "风雷益", "011111": "泽天夬",
    "111110": "天风姤", "011000": "泽地萃", "000110": "地风升", "011010": "泽水困",
    "010110": "水风井", "011101": "泽火革", "101110": "火风鼎", "001001": "震为雷",
    "100100": "艮为山", "110100": "风山渐", "001011": "雷泽归妹", "001101": "雷火丰",
    "101100": "火山旅", "110110": "巽为风", "011011": "兑为泽", "010011": "风水涣",
    "110010": "水泽节", "110011": "风泽中孚", "001100": "雷山小过", "010101": "水火既济",
    "101010": "火水未济",
}

# 八宫卦序（一世到归魂）
PALACE_ORDER = [
    # 乾宫（金）
    ("111111", "乾为天"), ("111110", "天风姤"), ("111100", "天山遁"), ("111000", "天地否"),
    ("110000", "风地观"), ("100000", "山地剥"), ("101000", "火地晋"), ("101111", "火天大有"),
    # 震宫（木）
    ("001001", "震为雷"), ("001000", "雷地豫"), ("001100", "雷水解"), ("000100", "地水师"),
    ("010100", "水山蹇"), ("011100", "雷风恒"), ("010000", "水地比"), ("010011", "风水涣"),
    # 坎宫（水）
    ("010010", "坎为水"), ("010011", "水泽节"), ("010111", "水天需"), ("011111", "泽天夬"),
    ("011011", "兑为泽"), ("010110", "水风井"), ("000110", "地风升"), ("000010", "地水师"),
    # 艮宫（土）
    ("100100", "艮为山"), ("100101", "山火贲"), ("100111", "天雷无妄"), ("101111", "火天大有"),
    ("101101", "离为火"), ("100001", "山雷颐"), ("100011", "山泽损"), ("100000", "山地剥"),
    # 坤宫（土）
    ("000000", "坤为地"), ("000001", "地雷复"), ("000011", "地泽临"), ("000111", "地天泰"),
    ("001111", "雷天大壮"), ("001101", "雷火丰"), ("001100", "雷山小过"), ("001000", "雷地豫"),
    # 巽宫（木）
    ("110110", "巽为风"), ("110111", "风天小畜"), ("110101", "风火家人"), ("110001", "风雷益"),
    ("100001", "山雷颐"), ("100011", "山泽损"), ("100010", "山水蒙"), ("110010", "水泽节"),
    # 离宫（火）
    ("101101", "离为火"), ("101100", "火山旅"), ("101000", "火地晋"), ("101001", "火雷噬嗑"),
    ("100001", "山雷颐"), ("100101", "山火贲"), ("100100", "艮为山"), ("101111", "火天大有"),
    # 兑宫（金）
    ("011011", "兑为泽"), ("011010", "泽水困"), ("011000", "泽地萃"), ("011001", "泽雷随"),
    ("001001", "震为雷"), ("001011", "雷泽归妹"), ("001010", "雷水解"), ("011110", "泽风大过"),
]

# 八宫五行
PALACE_WX = {
    "乾": "金", "兑": "金", "离": "火", "震": "木",
    "巽": "木", "坎": "水", "艮": "土", "坤": "土",
}

# 纳甲表（给六爻配干支）
# key: 上下卦组合 (上卦+下卦), value: 从上到下六爻的干支列表
# 简化版：根据八卦纳甲
NA_JIA = {
    # 乾金：内甲子、外壬午
    "乾": ["壬戌", "壬申", "壬午", "甲辰", "甲寅", "甲子"],  # 上爻到下爻
    # 兑金：内丁巳、外丁亥
    "兑": ["丁未", "丁酉", "丁亥", "丁卯", "丁丑", "丁巳"],
    # 离火：内己卯、外己酉
    "离": ["己巳", "己未", "己酉", "己卯", "己丑", "己亥"],
    # 震木：内庚子、外庚午
    "震": ["庚戌", "庚申", "庚午", "庚辰", "庚寅", "庚子"],
    # 巽木：内辛丑、外辛未
    "巽": ["辛卯", "辛巳", "辛未", "辛酉", "辛亥", "辛丑"],
    # 坎水：内戊寅、外戊申
    "坎": ["戊子", "戊戌", "戊申", "戊午", "戊辰", "戊寅"],
    # 艮土：内丙辰、外丙戌
    "艮": ["丙寅", "丙子", "丙戌", "丙申", "丙午", "丙辰"],
    # 坤土：内乙未、外癸丑
    "坤": ["癸酉", "癸亥", "癸丑", "乙卯", "乙巳", "乙未"],
}

# 六亲关系：我生者=子孙, 生我者=父母, 克我者=官鬼, 我克者=妻财, 同我者=兄弟
LIUQIN_REL = {
    ("金", "水"): "子孙", ("金", "木"): "妻财", ("金", "火"): "官鬼",
    ("金", "土"): "父母", ("金", "金"): "兄弟",
    ("木", "火"): "子孙", ("木", "土"): "妻财", ("木", "金"): "官鬼",
    ("木", "水"): "父母", ("木", "木"): "兄弟",
    ("水", "木"): "子孙", ("水", "火"): "妻财", ("水", "土"): "官鬼",
    ("水", "金"): "父母", ("水", "水"): "兄弟",
    ("火", "土"): "子孙", ("火", "金"): "妻财", ("火", "水"): "官鬼",
    ("火", "木"): "父母", ("火", "火"): "兄弟",
    ("土", "金"): "子孙", ("土", "水"): "妻财", ("土", "木"): "官鬼",
    ("土", "火"): "父母", ("土", "土"): "兄弟",
}

# 六神：青龙、朱雀、勾陈、腾蛇、白虎、玄武
# 甲乙日起青龙，丙丁日起朱雀，戊日起勾陈，己日起腾蛇，庚辛日起白虎，壬癸日起玄武
LIUSHEN_ORDER = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]
LIUSHEN_START = {
    "甲": 0, "乙": 0, "丙": 1, "丁": 1, "戊": 2,
    "己": 3, "庚": 4, "辛": 4, "壬": 5, "癸": 5,
}

# 世爻位置（按八宫卦序）
SHI_YAO_POS = [6, 1, 2, 3, 4, 5, 4, 3]  # 本宫、一世、二世...归魂
YING_YAO_POS = [3, 4, 5, 6, 1, 2, 1, 2]  # 应爻与世爻隔两位

# 空亡（旬空）
XUNKONG = {
    "甲子": "戌亥", "甲戌": "申酉", "甲申": "午未", "甲午": "辰巳",
    "甲辰": "寅卯", "甲寅": "子丑",
}

# 农历数据（1900-2100 简化版）
# 使用简化算法

# ==========================================
# 天干地支计算
# ==========================================

def get_ganzhi(offset: int) -> str:
    """根据偏移量获取干支"""
    return TIANGAN[offset % 10] + DIZHI[offset % 12]


def get_year_ganzhi(year: int) -> str:
    """年柱"""
    # 1984年是甲子年
    offset = (year - 1984) % 60
    if offset < 0:
        offset += 60
    return get_ganzhi(offset)


def get_month_ganzhi(year_gan: str, month: int) -> str:
    """月柱（按节气后的月份）"""
    # 年干定月干
    gan_index = TIANGAN.index(year_gan)
    # 甲己之年丙作首，乙庚之岁戊为头...
    start_gan_map = {0: 2, 1: 4, 2: 6, 3: 8, 4: 0, 5: 2, 6: 4, 7: 6, 8: 8, 9: 0}
    start_gan = start_gan_map[gan_index]
    # 正月从寅开始
    zhi = DIZHI[(month + 1) % 12]  # 正月=寅
    gan = TIANGAN[(start_gan + month - 1) % 10]
    return gan + zhi


def get_day_ganzhi(timestamp: datetime) -> str:
    """日柱（简化版，基于已知基准日计算）"""
    # 基准：2024年1月1日是甲子日（实际需精确校准）
    base = datetime(2024, 1, 1)
    days_diff = (timestamp - base).days
    # 实际上 2024-01-01 是癸亥日，需要调整
    # 使用更精确的基准
    # 2000-01-01 是戊午日
    base2 = datetime(2000, 1, 1)
    days_diff2 = (timestamp - base2).days
    offset = (14 + days_diff2) % 60  # 戊午偏移
    return get_ganzhi(offset)


def get_hour_ganzhi(day_gan: str, hour_zhi: str) -> str:
    """时柱"""
    gan_index = TIANGAN.index(day_gan)
    # 甲己日起甲子，乙庚日起丙子...
    start_gan_map = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8, 5: 0, 6: 2, 7: 4, 8: 6, 9: 8}
    start_gan = start_gan_map[gan_index]
    zhi_index = DIZHI.index(hour_zhi)
    # 子时为0
    gan = TIANGAN[(start_gan + zhi_index) % 10]
    return gan + hour_zhi


# ==========================================
# 节气计算（简化版）
# ==========================================

JIEQI_DATES = {
    # 近似日期，每年变化约1-2天，简化使用固定日期
    1: [(5, "小寒"), (20, "大寒")],
    2: [(3, "立春"), (18, "雨水")],
    3: [(5, "惊蛰"), (20, "春分")],
    4: [(4, "清明"), (19, "谷雨")],
    5: [(5, "立夏"), (20, "小满")],
    6: [(5, "芒种"), (21, "夏至")],
    7: [(6, "小暑"), (22, "大暑")],
    8: [(7, "立秋"), (22, "处暑")],
    9: [(7, "白露"), (22, "秋分")],
    10: [(8, "寒露"), (23, "霜降")],
    11: [(7, "立冬"), (22, "小雪")],
    12: [(6, "大雪"), (21, "冬至")],
}

JIEQI_ORDER = [
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
    "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
    "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
    "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
]

# 月建对应（按节气）
YUEJIAN_MAP = {
    "立春": "寅", "雨水": "寅", "惊蛰": "卯", "春分": "卯",
    "清明": "辰", "谷雨": "辰", "立夏": "巳", "小满": "巳",
    "芒种": "午", "夏至": "午", "小暑": "未", "大暑": "未",
    "立秋": "申", "处暑": "申", "白露": "酉", "秋分": "酉",
    "寒露": "戌", "霜降": "戌", "立冬": "亥", "小雪": "亥",
    "大雪": "子", "冬至": "子", "小寒": "丑", "大寒": "丑",
}


def get_jieqi_info(dt: datetime) -> dict:
    """获取当前节气信息（简化版）"""
    month = dt.month
    day = dt.day
    
    # 简化处理：找到最近的节气
    jieqi_list = JIEQI_DATES.get(month, [])
    current_jieqi = None
    next_jieqi = None
    
    for i, (d, name) in enumerate(jieqi_list):
        if day >= d:
            current_jieqi = name
            # 找下一个节气
            if i + 1 < len(jieqi_list):
                next_jieqi = (jieqi_list[i + 1][0], jieqi_list[i + 1][1])
            else:
                next_month = month % 12 + 1
                next_list = JIEQI_DATES.get(next_month, [])
                if next_list:
                    next_jieqi = (next_list[0][0], next_list[0][1])
    
    if not current_jieqi:
        # 找上个月的最后一个节气
        prev_month = month - 1 if month > 1 else 12
        prev_list = JIEQI_DATES.get(prev_month, [])
        if prev_list:
            current_jieqi = prev_list[-1][1]
    
    # 月建
    yuejian = YUEJIAN_MAP.get(current_jieqi, DIZHI[(month + 1) % 12])
    
    return {
        "current": current_jieqi,
        "next": next_jieqi,
        "yuejian": yuejian,
    }


# ==========================================
# 农历转换（简化版）
# ==========================================

LUNAR_MONTH_NAMES = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
LUNAR_DAY_NAMES = [
    "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
]


def solar_to_lunar(year: int, month: int, day: int) -> dict:
    """公历转农历（简化版，使用近似算法）"""
    # 这是一个简化实现，实际应使用精确数据表
    # 这里返回一个近似值
    base = datetime(1900, 1, 31)  # 1900年春节
    target = datetime(year, month, day)
    days = (target - base).days
    
    # 简化：假设每年约354天
    lunar_year = 1900
    lunar_month = 0
    lunar_day = 0
    
    while days > 0:
        year_days = 354
        if (lunar_year % 4 == 0 and lunar_year % 100 != 0) or (lunar_year % 400 == 0):
            # 简化闰年处理
            pass
        if days >= year_days:
            days -= year_days
            lunar_year += 1
        else:
            month_days = 30 if lunar_month % 2 == 0 else 29
            if days >= month_days:
                days -= month_days
                lunar_month += 1
            else:
                lunar_day = days
                break
    
    return {
        "year": lunar_year,
        "month": lunar_month + 1,
        "day": lunar_day + 1,
        "month_name": LUNAR_MONTH_NAMES[lunar_month % 12],
        "day_name": LUNAR_DAY_NAMES[lunar_day] if lunar_day < 30 else f"初{lunar_day + 1}",
    }


# ==========================================
# 神煞计算
# ==========================================

SHENSHA_RULES = {
    # 文昌：以年干或日干查，甲乙巳午...
    "文昌": {
        "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
        "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
    },
    # 驿马：申子辰马在寅...
    "驿马": {
        "申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申",
        "戌": "申", "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳",
        "卯": "巳", "未": "巳",
    },
    # 将星：寅午戌将星在午...
    "将星": {
        "寅": "午", "午": "午", "戌": "午", "申": "子", "子": "子",
        "辰": "子", "巳": "酉", "酉": "酉", "丑": "酉", "亥": "卯",
        "卯": "卯", "未": "卯",
    },
    # 桃花：申子辰桃花在酉...
    "桃花": {
        "申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯",
        "戌": "卯", "巳": "午", "酉": "午", "丑": "午", "亥": "子",
        "卯": "子", "未": "子",
    },
    # 天喜
    "天喜": {
        "子": "酉", "丑": "申", "寅": "未", "卯": "午", "辰": "巳", "巳": "辰",
        "午": "卯", "未": "寅", "申": "丑", "酉": "子", "戌": "亥", "亥": "戌",
    },
    # 天医：以月支查
    "天医": {
        "寅": "丑", "卯": "寅", "辰": "卯", "巳": "辰", "午": "巳", "未": "午",
        "申": "未", "酉": "申", "戌": "酉", "亥": "戌", "子": "亥", "丑": "子",
    },
    # 谋星（简化）
    "谋星": {
        "子": "戌", "丑": "酉", "寅": "申", "卯": "未", "辰": "午", "巳": "巳",
        "午": "辰", "未": "卯", "申": "寅", "酉": "丑", "戌": "子", "亥": "亥",
    },
    # 华盖：寅午戌见戌...
    "华盖": {
        "寅": "戌", "午": "戌", "戌": "戌", "申": "辰", "子": "辰",
        "辰": "辰", "巳": "丑", "酉": "丑", "丑": "丑", "亥": "未",
        "卯": "未", "未": "未",
    },
    # 灾煞（简化）
    "灾煞": {
        "申": "午", "子": "午", "辰": "午", "寅": "子", "午": "子",
        "戌": "子", "巳": "酉", "酉": "酉", "丑": "酉", "亥": "卯",
        "卯": "卯", "未": "卯",
    },
    # 劫煞
    "劫煞": {
        "申": "巳", "子": "巳", "辰": "巳", "寅": "亥", "午": "亥",
        "戌": "亥", "巳": "申", "酉": "申", "丑": "申", "亥": "寅",
        "卯": "寅", "未": "寅",
    },
    # 禄神
    "禄神": {
        "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
        "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
    },
    # 阳刃（羊刃）
    "阳刃": {
        "甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
        "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥",
    },
}

# 贵人
GUiren = {
    "甲": ["丑", "未"], "乙": ["子", "申"], "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "戊": ["丑", "未"], "己": ["子", "申"], "庚": ["丑", "未"], "辛": ["寅", "午"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
}


def calc_shensha(year_gz: str, day_gz: str, yuejian: str) -> dict:
    """计算神煞"""
    year_gan = year_gz[0]
    day_gan = day_gz[0]
    year_zhi = year_gz[1]
    day_zhi = day_gz[1]
    
    result = {}
    
    # 文昌（以日干为主）
    result["文昌"] = SHENSHA_RULES["文昌"].get(day_gan, "")
    # 驿马（以日支查）
    result["驿马"] = SHENSHA_RULES["驿马"].get(day_zhi, "")
    # 将星（以日支查）
    result["将星"] = SHENSHA_RULES["将星"].get(day_zhi, "")
    # 桃花（以日支查）
    result["桃花"] = SHENSHA_RULES["桃花"].get(day_zhi, "")
    # 天喜（以年支查）
    result["天喜"] = SHENSHA_RULES["天喜"].get(year_zhi, "")
    # 天医（以月建查）
    result["天医"] = SHENSHA_RULES["天医"].get(yuejian, "")
    # 谋星（以日支查，简化）
    result["谋星"] = SHENSHA_RULES["谋星"].get(day_zhi, "")
    # 华盖（以日支查）
    result["华盖"] = SHENSHA_RULES["华盖"].get(day_zhi, "")
    # 灾煞（以日支查）
    result["灾煞"] = SHENSHA_RULES["灾煞"].get(day_zhi, "")
    # 劫煞（以日支查）
    result["劫煞"] = SHENSHA_RULES["劫煞"].get(day_zhi, "")
    # 禄神（以日干查）
    result["禄神"] = SHENSHA_RULES["禄神"].get(day_gan, "")
    # 阳刃（以日干查）
    result["阳刃"] = SHENSHA_RULES["阳刃"].get(day_gan, "")
    # 贵人（以日干查）
    gr = GUiren.get(day_gan, [])
    result["贵人"] = "".join(gr)
    
    return result


# ==========================================
# 六爻排盘核心
# ==========================================

class LiuYaoEngine:
    """六爻排盘引擎"""
    
    def __init__(self, dt: Optional[datetime] = None, method: str = "time"):
        """
        dt: 占卜时间，None 表示当前时间
        method: 起卦方法，time=时间起卦法
        """
        self.dt = dt or datetime.now()
        self.method = method
        
        # 计算四柱
        self._calc_sizhu()
        # 计算节气
        self._calc_jieqi()
        # 计算神煞
        self._calc_shensha()
        # 起卦
        self._cast_gua()
        # 排盘
        self._arrange_pan()
    
    def _calc_sizhu(self):
        """计算四柱"""
        self.year_gz = get_year_ganzhi(self.dt.year)
        self.month_gz = get_month_ganzhi(self.year_gz[0], self.dt.month)
        self.day_gz = get_day_ganzhi(self.dt)
        
        # 时柱
        hour = self.dt.hour
        # 时辰
        if hour >= 23 or hour < 1:
            hour_zhi = "子"
        elif hour < 3:
            hour_zhi = "丑"
        elif hour < 5:
            hour_zhi = "寅"
        elif hour < 7:
            hour_zhi = "卯"
        elif hour < 9:
            hour_zhi = "辰"
        elif hour < 11:
            hour_zhi = "巳"
        elif hour < 13:
            hour_zhi = "午"
        elif hour < 15:
            hour_zhi = "未"
        elif hour < 17:
            hour_zhi = "申"
        elif hour < 19:
            hour_zhi = "酉"
        elif hour < 21:
            hour_zhi = "戌"
        else:
            hour_zhi = "亥"
        
        self.hour_zhi = hour_zhi
        self.hour_gz = get_hour_ganzhi(self.day_gz[0], hour_zhi)
        
        self.sizhu = {
            "year": self.year_gz,
            "month": self.month_gz,
            "day": self.day_gz,
            "hour": self.hour_gz,
        }
    
    def _calc_jieqi(self):
        """计算节气"""
        self.jieqi = get_jieqi_info(self.dt)
        self.yuejian = self.jieqi["yuejian"]
    
    def _calc_shensha(self):
        """计算神煞"""
        self.shensha = calc_shensha(self.year_gz, self.day_gz, self.yuejian)
    
    def _cast_gua(self):
        """时间起卦法"""
        year = self.dt.year
        month = self.dt.month
        day = self.dt.day
        hour = self.dt.hour
        
        # 时间起卦：年+月+日为上卦，年+月+日+时为下卦
        # 上卦数
        shang_num = (year + month + day) % 8
        if shang_num == 0:
            shang_num = 8
        
        # 下卦数
        xia_num = (year + month + day + hour) % 8
        if xia_num == 0:
            xia_num = 8
        
        # 动爻
        dong_num = (year + month + day + hour) % 6
        if dong_num == 0:
            dong_num = 6
        
        # 八卦顺序：乾1、兑2、离3、震4、巽5、坎6、艮7、坤8
        bagua_order = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
        shang_gua = bagua_order[shang_num - 1]
        xia_gua = bagua_order[xia_num - 1]
        
        self.shang_gua = shang_gua
        self.xia_gua = xia_gua
        self.dong_yao = dong_num  # 1-6，从下到上
        
        # 组合六爻
        shang_symbol = GUA_SYMBOLS[shang_gua]  # 上卦，从上到下
        xia_symbol = GUA_SYMBOLS[xia_gua]       # 下卦，从上到下
        
        # HEXAGRAM_MAP 编码：从上到下，shang + xia
        self.gua_code = shang_symbol + xia_symbol
        self.ben_gua_name = HEXAGRAM_MAP.get(self.gua_code, "未知")
        
        # 解析六爻（从下到上）
        bottom_up = self.gua_code[::-1]  # 反转：从下到上
        self.lines = []
        for i in range(6):
            pos = i + 1
            value = int(bottom_up[i])
            is_changing = (pos == self.dong_yao)
            self.lines.append({
                "position": pos,
                "value": value,
                "changing": is_changing,
            })
        
        # 变卦
        bian_bottom_up = "".join(
            str(1 - l["value"] if l["changing"] else l["value"])
            for l in self.lines
        )
        self.bian_code = bian_bottom_up[::-1]  # 转为从上到下
        self.bian_gua_name = HEXAGRAM_MAP.get(self.bian_code)
    
    def _calc_bian_details(self) -> list:
        """计算变卦六爻详情：干支、五行、六亲"""
        if not self.bian_code:
            return []
        
        # 变卦上下卦（从上到下，前三为上卦，后三为下卦）
        bian_shang = self.bian_code[:3]
        bian_xia = self.bian_code[3:]
        bian_shang_gua = {v: k for k, v in GUA_SYMBOLS.items()}.get(bian_shang, "?")
        bian_xia_gua = {v: k for k, v in GUA_SYMBOLS.items()}.get(bian_xia, "?")
        
        # 变卦纳甲（上三爻 + 下三爻，从下到上）
        shang_najia = NA_JIA.get(bian_shang_gua, ["??"] * 3)
        xia_najia = NA_JIA.get(bian_xia_gua, ["??"] * 3)
        all_najia = list(reversed(xia_najia)) + list(reversed(shang_najia))
        # all_najia[0] 是最下爻，all_najia[5] 是最上爻
        
        details = []
        for i in range(6):
            ganzhi = all_najia[i]
            zhi = ganzhi[1]
            zhi_wx = ZHI_WX.get(zhi, "?")
            liuqin = LIUQIN_REL.get((self.palace_wx, zhi_wx), "未知")
            details.append({
                "position": i + 1,
                "ganzhi": ganzhi,
                "zhi": zhi,
                "zhi_wx": zhi_wx,
                "liuqin": liuqin,
            })
        return details
    
    def _arrange_pan(self):
        """排盘：纳甲、六亲、六神、世应"""
        # 1. 确定卦宫（找出本卦属于哪一宫）
        self.palace, self.palace_wx = self._find_palace()
        
        # 2. 纳甲（给每个爻配干支）
        self._na_jia()
        
        # 3. 安六亲
        self._an_liuqin()
        
        # 4. 配六神
        self._pei_liushen()
        
        # 5. 定世应
        self._ding_shiying()
        
        # 6. 空亡
        self._calc_xunkong()
    
    def _find_palace(self) -> tuple:
        """确定卦宫：八纯卦直接返回，其余用上卦"""
        if self.shang_gua == self.xia_gua:
            return self.shang_gua, PALACE_WX[self.shang_gua]
        return self.shang_gua, PALACE_WX.get(self.shang_gua, "土")
    
    def _na_jia(self):
        """纳甲：上卦外卦 + 下卦内卦"""
        # NA_JIA 索引0-2为外卦（上三爻），索引3-5为内卦（下三爻）
        shang_outer = NA_JIA[self.shang_gua][:3]   # 上卦外卦（六五四爻，从上到下）
        xia_inner = NA_JIA[self.xia_gua][3:]       # 下卦内卦（三二一爻，从上到下）
        
        # 六爻从上到下：上三爻 + 下三爻
        all_top_down = shang_outer + xia_inner
        # 转为从下到上（lines 是从下到上排列的）
        all_bottom_up = list(reversed(all_top_down))
        
        for i, line in enumerate(self.lines):
            line["ganzhi"] = all_bottom_up[i]
            line["gan"] = all_bottom_up[i][0]
            line["zhi"] = all_bottom_up[i][1]
    
    def _an_liuqin(self):
        """安六亲：根据卦宫五行和爻支五行"""
        for line in self.lines:
            zhi = line["zhi"]
            zhi_wx = ZHI_WX[zhi]
            liuqin = LIUQIN_REL.get((self.palace_wx, zhi_wx), "未知")
            line["liuqin"] = liuqin
    
    def _pei_liushen(self):
        """配六神：根据日干"""
        day_gan = self.day_gz[0]
        start_idx = LIUSHEN_START.get(day_gan, 0)
        
        # 六神从初爻开始配
        for i, line in enumerate(self.lines):
            shen_idx = (start_idx + i) % 6
            line["liushen"] = LIUSHEN_ORDER[shen_idx]
    
    def _ding_shiying(self):
        """定世应：简化版"""
        if self.shang_gua == self.xia_gua:
            shi_pos, ying_pos = 6, 3
        else:
            # 根据动爻位置估算（简化）
            shi_pos = self.dong_yao
            ying_pos = ((shi_pos + 2) % 6) or 6
        
        self.shi_yao = shi_pos
        self.ying_yao = ying_pos
        
        for line in self.lines:
            line["is_shi"] = (line["position"] == shi_pos)
            line["is_ying"] = (line["position"] == ying_pos)
    
    def _calc_xunkong(self):
        """计算空亡（旬空）"""
        # 根据日柱干支查旬空
        day_gan = self.day_gz[0]
        day_zhi = self.day_gz[1]
        
        # 找到对应的甲子旬
        gan_idx = TIANGAN.index(day_gan)
        zhi_idx = DIZHI.index(day_zhi)
        
        # 计算旬首
        xun_offset = (zhi_idx - gan_idx) % 12
        xun_shou_zhi_idx = (zhi_idx - xun_offset) % 12
        xun_shou_gan_idx = (gan_idx - xun_offset) % 10
        
        xun_shou = TIANGAN[xun_shou_gan_idx] + DIZHI[xun_shou_zhi_idx]
        
        # 查表
        if xun_shou in XUNKONG:
            self.xunkong = XUNKONG[xun_shou]
        else:
            # 计算：旬首地支后的两个为空亡
            xk1 = DIZHI[(xun_shou_zhi_idx + 10) % 12]
            xk2 = DIZHI[(xun_shou_zhi_idx + 11) % 12]
            self.xunkong = xk1 + xk2
        
        # 时旬空（简化：时柱旬空）
        hour_gan = self.hour_gz[0]
        hour_zhi = self.hour_gz[1]
        gan_idx_h = TIANGAN.index(hour_gan)
        zhi_idx_h = DIZHI.index(hour_zhi)
        xun_offset_h = (zhi_idx_h - gan_idx_h) % 12
        xun_shou_zhi_idx_h = (zhi_idx_h - xun_offset_h) % 12
        xk1_h = DIZHI[(xun_shou_zhi_idx_h + 10) % 12]
        xk2_h = DIZHI[(xun_shou_zhi_idx_h + 11) % 12]
        self.hour_xunkong = xk1_h + xk2_h
    
    def get_result(self) -> dict:
        """获取完整排盘结果"""
        return {
            "datetime": {
                "solar": self.dt.strftime("%Y-%m-%d %H:%M"),
                "lunar": self._get_lunar_str(),
            },
            "jieqi": self.jieqi,
            "sizhu": self.sizhu,
            "shensha": self.shensha,
            "gua": {
                "ben": {
                    "name": self.ben_gua_name,
                    "shang": self.shang_gua,
                    "xia": self.xia_gua,
                    "code": self.gua_code,
                    "palace": self.palace,
                    "palace_wx": self.palace_wx,
                    "shi_yao": self.shi_yao,
                    "ying_yao": self.ying_yao,
                },
                "bian": {
                    "name": self.bian_gua_name,
                    "code": self.bian_code,
                    "lines": self._calc_bian_details(),
                } if self.bian_gua_name else None,
                "dong_yao": self.dong_yao,
            },
            "lines": self.lines,
            "xunkong": {
                "day": self.xunkong,
                "hour": self.hour_xunkong,
            },
            "yuejian": self.yuejian,
        }
    
    def _get_lunar_str(self) -> str:
        """获取农历字符串"""
        lunar = solar_to_lunar(self.dt.year, self.dt.month, self.dt.day)
        return f"{lunar['month_name']}月{lunar['day_name']}"


# ==========================================
# 测试
# ==========================================

if __name__ == "__main__":
    engine = LiuYaoEngine()
    result = engine.get_result()
    
    print("=== 六爻排盘结果 ===")
    print(f"时间：{result['datetime']['solar']} ({result['datetime']['lunar']})")
    print(f"四柱：{result['sizhu']['year']} {result['sizhu']['month']} {result['sizhu']['day']} {result['sizhu']['hour']}")
    print(f"节气：{result['jieqi']['current']}，月建：{result['yuejian']}")
    print(f"空亡：日空{result['xunkong']['day']} / 时空{result['xunkong']['hour']}")
    print(f"本卦：{result['gua']['ben']['name']}（{result['gua']['ben']['palace']}宫/{result['gua']['ben']['palace_wx']}）")
    if result['gua']['bian']:
        print(f"变卦：{result['gua']['bian']['name']}")
    print(f"世爻：第{result['gua']['ben']['shi_yao']}爻，应爻：第{result['gua']['ben']['ying_yao']}爻")
    print(f"动爻：第{result['gua']['dong_yao']}爻")
    print("\n六爻排盘：")
    for line in reversed(result['lines']):
        yao_type = "━━━" if line['value'] == 1 else "━ ━"
        if line['changing']:
            yao_type += " ⚡"
        shi = " 世" if line['is_shi'] else ""
        ying = " 应" if line['is_ying'] else ""
        print(f"  {line['liushen']:3s} {line['liuqin']:3s} {line['ganzhi']:4s} {yao_type}{shi}{ying}")
