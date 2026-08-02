"""
赛博占卜 - Cloudflare Workers 后端
部署方式：wrangler deploy
免费额度：每日 10 万次请求
"""

import json
import math
import os

# ==========================================
# 配置
# ==========================================
LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"  # DeepSeek 官方
LLM_MODEL = "deepseek-chat"  # DeepSeek-V3
LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]  # 必须通过环境变量设置

# 系统提示词
SYSTEM_PROMPT = """你是一位赛博占卜师，精通六爻占卜，温暖、理性、有深度。

你的特点：
1. 每次解读必须引用古籍原文作为依据，展示推理链
2. 语气温暖但不油腻，像一位有智慧的朋友
3. 不做绝对化预测，不说"准确率""算命"等词汇
4. 最终引导用户回归自身思考，占卜是参考不是答案

输出格式：
【核心解读】
（2-3句话的核心结论，温暖有共鸣）

【古籍依据】
引用古籍原文：「xxx」——《xxx》
白话解读：（用通俗语言解释）

【给你的建议】
（1-2条可操作的建议）

注意：结尾必须标注"内容由AI生成，仅供娱乐参考"
"""

# ==========================================
# 向量检索（纯 JS 实现，无需外部库）
# ==========================================

# 全局缓存向量数据
_vectors_cache = None
_embeddings_cache = None
_texts_cache = None


def cosine_similarity(a, b):
    """余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0
    return dot / (norm_a * norm_b)


def load_vectors():
    """加载向量数据（从 KV 或本地文件）"""
    global _vectors_cache, _embeddings_cache, _texts_cache
    
    if _vectors_cache is not None:
        return _vectors_cache, _texts_cache
    
    # 从本地文件加载（Cloudflare Workers 中改为从 KV 加载）
    import os
    vec_path = os.path.join(os.path.dirname(__file__), "..", "kb_preprocess", "output", "vectors.json")
    
    # Workers 环境中使用 KV
    # vectors_data = await env.KB_VECTORS.get("vectors.json", "json")
    
    with open(vec_path, 'r', encoding='utf-8') as f:
        vectors_data = json.load(f)
    
    _vectors_cache = [item["vector"] for item in vectors_data]
    _texts_cache = [item for item in vectors_data]  # 保留完整信息
    
    return _vectors_cache, _texts_cache


def search_similar(query_embedding, top_k=5):
    """检索最相似的 chunks"""
    vectors, texts = load_vectors()
    
    # 计算所有相似度
    scores = []
    for i, vec in enumerate(vectors):
        sim = cosine_similarity(query_embedding, vec)
        scores.append((sim, i))
    
    # 排序取 top_k
    scores.sort(key=lambda x: -x[0])
    
    results = []
    for sim, idx in scores[:top_k]:
        item = texts[idx]
        results.append({
            "id": item["id"],
            "text": item["text"],
            "book": item["meta"]["book"],
            "type": item["meta"]["type"],
            "hexagram": item["meta"]["hexagram"],
            "score": round(sim, 4),
        })
    
    return results


def keyword_search(query, texts, top_k=3):
    """关键词检索作为补充"""
    # 简单分词（中文按字拆分匹配）
    keywords = set(query)
    scored = []
    
    for item in texts:
        text = item["text"]
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, item))
    
    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:top_k]]


# ==========================================
# 六爻起卦
# ==========================================

HEXAGRAM_MAP = {
    "111111": "乾为天", "000000": "坤为地", "010001": "水雷屯", "100010": "山水蒙",
    "010111": "水天需", "111010": "天水讼", "000010": "地水师", "010000": "水地比",
    "110111": "风天小畜", "111011": "天泽履", "000111": "地天泰", "111000": "天地否",
    "111101": "天火同人", "101111": "火天大有", "000100": "地山谦", "001000": "雷地豫",
    "011001": "泽雷随", "100110": "山风蛊", "000011": "地泽临", "110000": "风地观",
    "101001": "火雷噬嗑", "100101": "山火贲", "100000": "山地剥", "001000": "地雷复",
    "100111": "天雷无妄", "111100": "山天大畜", "100001": "山雷颐", "011110": "泽风大过",
    "010010": "坎为水", "101101": "离为火",
    "001110": "泽山咸", "011100": "雷风恒", "111100": "天山遁", "001111": "雷天大壮",
    "101000": "火地晋", "000101": "地火明夷", "110101": "风火家人", "101011": "火泽睽",
    "010100": "水山蹇", "001010": "雷水解", "100011": "山泽损", "110001": "风雷益",
    "011111": "泽天夬", "111110": "天风姤", "011000": "泽地萃", "000110": "地风升",
    "011010": "泽水困", "010110": "水风井", "011101": "泽火革", "101110": "火风鼎",
    "001001": "震为雷", "100100": "艮为山", "110100": "风山渐", "001011": "雷泽归妹",
    "001101": "雷火丰", "101100": "火山旅", "110110": "巽为风", "011011": "兑为泽",
    "010011": "风水涣", "011001": "水泽节", "110011": "风泽中孚", "001100": "雷山小过",
    "010101": "水火既济", "101010": "火水未济",
}


def cast_hexagram():
    """模拟六爻起卦，返回卦名和六爻"""
    import random
    lines = []
    for _ in range(6):
        # 三枚铜钱，正面=3，反面=2
        coins = [random.choice([2, 3]) for _ in range(3)]
        total = sum(coins)
        # 6=老阴(变爻) 7=少阳 8=少阴 9=老阳(变爻)
        if total == 6:
            lines.append({"value": 0, "type": "老阴", "changing": True})  # 阴爻变阳
        elif total == 7:
            lines.append({"value": 1, "type": "少阳", "changing": False})  # 阳爻
        elif total == 8:
            lines.append({"value": 0, "type": "少阴", "changing": False})  # 阴爻
        else:
            lines.append({"value": 1, "type": "老阳", "changing": True})  # 阳爻变阴
    
    # 本卦
    ben_gua_code = "".join(str(l["value"]) for l in lines)
    ben_gua = HEXAGRAM_MAP.get(ben_gua_code, "未知")
    
    # 变卦
    bian_lines = []
    for l in lines:
        if l["changing"]:
            bian_lines.append(str(1 - l["value"]))
        else:
            bian_lines.append(str(l["value"]))
    bian_gua_code = "".join(bian_lines)
    bian_gua = HEXAGRAM_MAP.get(bian_gua_code, "未知") if bian_gua_code != ben_gua_code else None
    
    return {
        "ben_gua": ben_gua,
        "bian_gua": bian_gua,
        "lines": lines,
    }


# ==========================================
# LLM 调用
# ==========================================

async def call_llm(messages):
    """调用 LLM API"""
    import aiohttp
    
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_API_URL, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"LLM API error: {resp.status} - {text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


# ==========================================
# API 路由
# ==========================================

async def handle_divination(request):
    """占卜接口"""
    body = await request.json()
    question = body.get("question", "").strip()
    
    if not question:
        return {"error": "请描述你想问的事情"}
    
    if len(question) > 500:
        return {"error": "问题太长啦，500字以内就好"}
    
    # 1. 起卦
    gua = cast_hexagram()
    
    # 2. RAG 检索
    search_query = f"{question} {gua['ben_gua']}"
    results = search_similar(search_query, top_k=3)  # 需要 embedding 才能用
    
    # 3. 构建古籍上下文
    context_parts = []
    for r in results:
        context_parts.append(f"【{r['book']}】{r['text']}")
    context = "\n\n".join(context_parts)
    
    # 4. 调用 LLM 生成解读
    user_prompt = f"""用户的问题：{question}

起卦结果：本卦「{gua['ben_gua']}」{"，变卦「" + gua['bian_gua'] + "」" if gua['bian_gua'] else "（无变卦）"}

以下是古籍中相关的记载，请参考这些内容进行解读：

{context}

请按照格式要求给出解读。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    
    reading = await call_llm(messages)
    
    return {
        "question": question,
        "hexagram": gua,
        "reading": reading,
        "sources": [
            {"book": r["book"], "text": r["text"][:200]} for r in results
        ],
    }


async def handle_request(request):
    """主路由"""
    url = request.url
    
    # CORS
    if request.method == "OPTIONS":
        return Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    
    headers = {"Access-Control-Allow-Origin": "*"}
    
    if url.endswith("/api/divination") and request.method == "POST":
        result = await handle_divination(request)
        return Response(
            json.dumps(result, ensure_ascii=False),
            headers={**headers, "Content-Type": "application/json"}
        )
    
    if url.endswith("/api/health"):
        return Response(
            json.dumps({"status": "ok", "name": "赛博占卜 API"}),
            headers={**headers, "Content-Type": "application/json"}
        )
    
    return Response("赛博占卜 API v0.1", headers=headers)


# Cloudflare Workers 入口
def on_fetch(request, env):
    import asyncio
    return asyncio.ensure_future(handle_request(request))


# ==========================================
# 本地开发入口
# ==========================================
if __name__ == "__main__":
    print("赛博占卜 API 服务")
    print("请使用 wrangler dev 启动 Workers 开发服务器")
    print("或使用下面的测试代码：")
    
    # 简单测试
    gua = cast_hexagram()
    print(f"\n测试起卦: 本卦={gua['ben_gua']}, 变卦={gua['bian_gua']}")
