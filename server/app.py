"""
赛博占卜 - FastAPI 后端服务
启动: uvicorn app:app --reload --port 8000
"""
import os
import sys
import chromadb
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kb_preprocess"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from liuyao_engine import LiuYaoEngine
from divination_prompt import SYSTEM_PROMPT, build_messages, build_followup_messages, parse_reading_sections

# ==========================================
# 配置
# ==========================================
DB_PATH = os.environ.get("VECTORDB_PATH", os.path.join(os.path.dirname(__file__), "..", "kb_preprocess", "vectordb"))
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")  # 通过环境变量设置
LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"
LLM_MODEL = "deepseek-chat"  # DeepSeek-V3

# 备用：阿里云百炼
# LLM_API_KEY = os.environ.get("ALIYUN_API_KEY", "sk-ws-H.EHPIPHM...")
# LLM_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
# LLM_MODEL = "qwen-plus"

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
    """向量检索器"""
    
    def __init__(self, db_path: str):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_collection("liuyao_knowledge")
    
    def search(self, query: str, hexagram: Optional[str] = None, top_k: int = 5) -> list[dict]:
        """检索相关古籍内容
        
        Args:
            query: 检索查询词
            hexagram: 可选，追加卦名精确匹配
            top_k: 返回条数上限
        """
        # 语义检索
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
        )
        
        items = []
        for i in range(len(results["ids"][0])):
            items.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "meta": results["metadatas"][0][i],
                "score": max(0, min(1, round(1 - results["distances"][0][i], 4))),  # 距离转相似度，截断在 [0,1]
            })
        
        # 如果有卦名，追加精确匹配（去重）
        if hexagram:
            hex_results = self.collection.query(
                query_texts=[hexagram],
                n_results=3,
            )
            existing_ids = {item["id"] for item in items}
            for i in range(len(hex_results["ids"][0])):
                hid = hex_results["ids"][0][i]
                if hid not in existing_ids:
                    items.append({
                        "id": hid,
                        "text": hex_results["documents"][0][i],
                        "meta": hex_results["metadatas"][0][i],
                        "score": max(0, min(1, round(1 - hex_results["distances"][0][i], 4))),
                    })
        
        # 按分数排序
        items.sort(key=lambda x: -x["score"])
        return items[:top_k]


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
        raise Exception(f"LLM API 错误 [{resp.status_code}]: {resp.text}")
    
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
    sources_ben_gua = retriever.search(ben_gua, top_k=3)
    
    # 2c. 如果有变卦，也检索变卦
    sources_bian_gua = []
    if bian_gua:
        sources_bian_gua = retriever.search(bian_gua, top_k=2)
    
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
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 向量数据库未构建: {DB_PATH}")
        print("请先运行: python kb_preprocess/step3_vectorize.py")
    else:
        retriever = RAGRetriever(DB_PATH)
        print(f"[OK] 向量库已加载: {retriever.collection.count()} 条")
    yield


app = FastAPI(
    title="赛博占卜 API",
    description="有书为证的AI占卜",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许 GitHub Pages 等任意来源
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# 备选：强制给所有响应添加 CORS 头（处理异常响应时 CORSMiddleware 不生效的情况）
from starlette.middleware.base import BaseHTTPMiddleware

class ForceCORSHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            from fastapi.responses import Response
            resp = Response()
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
            resp.headers["Access-Control-Allow-Headers"] = "*"
            resp.headers["Access-Control-Max-Age"] = "86400"
            return resp
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.add_middleware(ForceCORSHeadersMiddleware)


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
        "vectors": retriever.collection.count() if retriever else 0,
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
        raise HTTPException(status_code=500, detail=f"占卜失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"追问失败: {str(e)}")


# ==========================================
# 命令行入口
# ==========================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  赛博占卜 API 服务启动中...")
    print(f"  向量库: {DB_PATH}")
    print(f"  LLM: {LLM_MODEL}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
