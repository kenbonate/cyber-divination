"""
赛博占卜 - FastAPI 后端服务
启动: uvicorn app:app --reload --port 8000
"""
import os
import sys
import json
import numpy as np
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kb_preprocess"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from liuyao_engine import LiuYaoEngine
from divination_prompt import SYSTEM_PROMPT, build_messages, build_followup_messages

# ==========================================
# 配置
# ==========================================
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "kb_preprocess")
OUTPUT_DIR = os.path.join(KB_DIR, "output")
EMBEDDINGS_PATH = os.environ.get("EMBEDDINGS_PATH", os.path.join(OUTPUT_DIR, "embeddings.npy"))
VECTORS_PATH = os.environ.get("VECTORS_PATH", os.path.join(OUTPUT_DIR, "vectors.json"))
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")  # 通过环境变量设置
LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"
LLM_MODEL = "deepseek-chat"  # DeepSeek-V3

# 备用：阿里云百炼（取消注释并设置环境变量 ALIYUN_API_KEY 即可切换）
# ALIYUN_API_KEY = os.environ.get("ALIYUN_API_KEY", "")
# ALIYUN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
# ALIYUN_MODEL = "qwen-plus"

# ==========================================
# 六爻排盘（使用 liuyao_engine）
# ==========================================

def cast_hexagram_full():
    """使用专业排盘引擎起卦"""
    engine = LiuYaoEngine()
    return engine.get_result()


# ==========================================
# RAG 检索
# ==========================================

class RAGRetriever:
    """基于 numpy 的本地向量检索器（无需 ChromaDB）"""

    def __init__(self, embeddings_path: str, vectors_path: str):
        print(f"[RAG] 加载向量文件...")
        self.embeddings = np.load(embeddings_path).astype("float32")
        # 预归一化，用点积等价计算余弦相似度
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embeddings_norm = self.embeddings / norms
        print(f"[RAG] 向量矩阵: {self.embeddings.shape}")

        with open(vectors_path, "r", encoding="utf-8") as f:
            self.records = json.load(f)
        print(f"[RAG] 记录数: {len(self.records)}")

        # 复用步骤3的 embedding 函数，保证查询与入库模型一致
        from step3_vectorize import get_embedding_fn
        self.embedding_fn, self.fn_type = get_embedding_fn()
        print(f"[RAG] Embedding 模型: {self.fn_type}")

    def _encode(self, texts: List[str]) -> np.ndarray:
        embs = np.array(self.embedding_fn(texts), dtype="float32")
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embs / norms

    def _search_once(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """单次语义检索"""
        query_emb = self._encode([query])  # (1, dim)
        scores = np.dot(query_emb, self.embeddings_norm.T)[0]  # (n,)

        k = min(top_k, len(self.records))
        top_idx = np.argsort(scores)[::-1][:k]

        return [
            {
                "id": self.records[i]["id"],
                "text": self.records[i]["text"],
                "meta": self.records[i]["meta"],
                "score": max(0.0, min(1.0, round(float(scores[i]), 4))),
            }
            for i in top_idx
        ]

    def search(self, query: str, hexagram: Optional[str] = None, top_k: int = 5) -> list[dict]:
        """检索相关古籍内容

        Args:
            query: 检索查询词
            hexagram: 可选，按元数据中的卦名追加精确匹配
            top_k: 返回条数上限
        """
        # 语义检索
        items = self._search_once(query, top_k=top_k)

        # 如果有卦名，追加按元数据过滤的精确匹配（去重）
        if hexagram:
            query_emb = self._encode([hexagram])[0]
            scores = np.dot(query_emb, self.embeddings_norm.T)
            exact_items = []
            for i, record in enumerate(self.records):
                if hexagram in record["meta"].get("hexagram", ""):
                    exact_items.append({
                        "id": record["id"],
                        "text": record["text"],
                        "meta": record["meta"],
                        "score": max(0.0, min(1.0, round(float(scores[i]), 4))),
                    })
            exact_ids = {item["id"] for item in exact_items}
            semantic_items = [item for item in items if item["id"] not in exact_ids]
            exact_items.sort(key=lambda x: -x["score"])
            semantic_items.sort(key=lambda x: -x["score"])
            items = exact_items + semantic_items
        else:
            # 按分数排序
            items.sort(key=lambda x: -x["score"])
        return items[:top_k]

    def count(self) -> int:
        return len(self.records)


# ==========================================
# LLM 调用
# ==========================================

def call_llm(messages: list[dict]) -> str:
    """调用 LLM API"""
    import requests
    
    if not LLM_API_KEY:
        raise Exception("未配置 DEEPSEEK_API_KEY 环境变量，请设置后重试")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    
    resp = requests.post(LLM_API_URL, json=payload, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        # 不暴露原始API错误详情给用户，避免泄漏密钥等敏感信息
        error_text = resp.text[:200] if resp.text else "无详情"
        raise Exception(f"LLM API 错误 [{resp.status_code}]，请稍后重试")
    
    return resp.json()["choices"][0]["message"]["content"]


# ==========================================
# 占卜核心流程
# ==========================================

def do_divination(question: str, retriever: RAGRetriever) -> dict:
    """执行一次完整占卜"""
    # 1. 起卦（专业排盘）
    pan = cast_hexagram_full()
    ben_gua = pan["gua"]["ben"]["name"]
    bian_gua = pan["gua"]["bian"]["name"] if pan["gua"]["bian"] else None
    
    # 2. RAG 检索（多轮，确保覆盖相似情形）
    # 2a. 语义检索：用户问题 + 本卦名
    search_query = f"{question} {ben_gua}"
    sources_semantic = retriever.search(search_query, top_k=4)
    
    # 2b. 卦名精确匹配：本卦名
    sources_ben_gua = retriever.search(ben_gua, hexagram=ben_gua, top_k=3)
    
    # 2c. 如果有变卦，也检索变卦
    sources_bian_gua = []
    if bian_gua:
        sources_bian_gua = retriever.search(bian_gua, hexagram=bian_gua, top_k=2)
    
    # 2d. 相似情形检索：纯用问题做一次语义检索（找同类型问事场景的古人案例）
    sources_similar = retriever.search(question, top_k=3)
    
    # 3. 合并去重排序
    seen_ids = set()
    all_sources = []
    
    # 按优先级插入：语义检索 > 本卦 > 变卦 > 相似情形
    for s in (sources_semantic + sources_ben_gua + sources_bian_gua + sources_similar):
        if s["id"] not in seen_ids:
            seen_ids.add(s["id"])
            all_sources.append(s)
    
    # 按分数排序，取 top 6
    all_sources.sort(key=lambda x: -x["score"])
    top_sources = all_sources[:6]
    
    # 4. 构建分类的古籍上下文
    # 按匹配类型分组
    hex_matched = []   # 卦名直接匹配的
    semantic = []      # 语义匹配的
    
    for s in top_sources:
        s_hex = s["meta"].get("hexagram", "")
        entry = (
            f"【{s['meta']['book']}】（卦名：{s_hex}，相关度：{s['score']:.0%}）\n"
            f"{s['text']}"
        )
        if ben_gua in s_hex or (bian_gua and bian_gua in s_hex):
            hex_matched.append(entry)
        else:
            semantic.append(entry)
    
    context_parts = []
    if hex_matched:
        context_parts.append("### 本卦/变卦直接相关的古籍记载\n" + "\n\n".join(hex_matched))
    if semantic:
        context_parts.append("### 同类情形的古籍案例（与你的问题相似但不限于同一卦名）\n" + "\n\n".join(semantic))
    if not context_parts:
        context_parts.append("（未检索到相关古籍记载，请使用你自身的易经知识进行解读。）")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # 5. 使用提示词工程模块构建 messages
    messages = build_messages(question, pan, context)
    
    # 6. 调用 LLM
    reading = call_llm(messages)
    
    return {
        "question": question,
        "pan": pan,
        "reading": reading,
        "sources": [
            {"book": s["meta"]["book"], "text": s["text"][:300], "score": s["score"]}
            for s in top_sources[:3]
        ],
    }


# ==========================================
# FastAPI 应用
# ==========================================

# 全局检索器（启动时加载）
retriever: Optional[RAGRetriever] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时加载向量库"""
    global retriever
    if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(VECTORS_PATH):
        print(f"[ERROR] 向量文件未找到:")
        print(f"  embeddings: {EMBEDDINGS_PATH}")
        print(f"  vectors:    {VECTORS_PATH}")
        print("请先运行: python kb_preprocess/step3_vectorize.py")
    else:
        retriever = RAGRetriever(EMBEDDINGS_PATH, VECTORS_PATH)
        print(f"[OK] 向量库已加载: {retriever.count()} 条")
    yield


app = FastAPI(
    title="赛博占卜 API",
    description="有书为证的AI占卜",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许任意来源（后续可改为具体域名以增强安全性）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ==========================================
# 前端页面托管
# ==========================================
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


class DivinationRequest(BaseModel):
    question: str


class DivinationResponse(BaseModel):
    question: str
    pan: dict
    reading: str
    sources: list[dict]


class FollowUpRequest(BaseModel):
    question: str
    original_question: str
    original_reading: str
    pan: dict


class FollowUpResponse(BaseModel):
    question: str
    reading: str


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "vectors": retriever.count() if retriever else 0,
        "llm_configured": bool(LLM_API_KEY),
    }


@app.post("/api/divination", response_model=DivinationResponse)
async def divination(req: DivinationRequest):
    if not retriever:
        raise HTTPException(status_code=503, detail="向量数据库未就绪")
    
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="请描述你想问的事情")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="问题太长，500字以内")
    
    try:
        result = do_divination(question, retriever)
        return result
    except Exception as e:
        # 不泄露内部错误细节给客户端
        import traceback
        print(f"[ERROR] 占卜失败: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="占卜失败，服务内部错误，请稍后重试")


@app.post("/api/follow-up", response_model=FollowUpResponse)
async def follow_up(req: FollowUpRequest):
    """追问接口：基于已有的占卜结果进行深入提问"""
    followup_question = req.question.strip()
    if not followup_question:
        raise HTTPException(status_code=400, detail="请输入你想追问的问题")
    if len(followup_question) > 300:
        raise HTTPException(status_code=400, detail="追问问题太长，300字以内")
    
    try:
        messages = build_followup_messages(
            original_question=req.original_question,
            original_reading=req.original_reading,
            followup_question=followup_question,
            pan=req.pan,
        )
        reading = call_llm(messages)
        return {"question": followup_question, "reading": reading}
    except Exception as e:
        print(f"[ERROR] 追问失败: {e}")
        raise HTTPException(status_code=500, detail="追问失败，服务内部错误，请稍后重试")


# ==========================================
# 命令行入口
# ==========================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  赛博占卜 API 服务启动中...")
    print(f"  向量文件: {EMBEDDINGS_PATH}")
    print(f"  元数据:   {VECTORS_PATH}")
    print(f"  LLM: {LLM_MODEL}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
