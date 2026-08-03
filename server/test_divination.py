"""
快速测试：不启动服务，直接跑一次占卜看效果
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kb_preprocess"))

from app import do_divination, RAGRetriever, KB_DIR, OUTPUT_DIR, EMBEDDINGS_PATH, VECTORS_PATH
from liuyao_engine import LiuYaoEngine

print("=" * 50)
print("1. 验证铜钱法随机性（不带 LLM）")
print("=" * 50)

for i in range(5):
    pan = LiuYaoEngine().get_result()
    ben = pan["gua"]["ben"]["name"]
    bian = pan["gua"]["bian"]["name"] if pan["gua"]["bian"] else "静卦"
    dong = pan["gua"]["dong_yao_list"]
    dong_str = f"动爻{dong}" if dong else "静卦"
    print(f"  #{i+1}: 本卦={ben:<8s} 变卦={bian:<8s} {dong_str}")

print()
print("=" * 50)
print("2. 带 RAG+LLM 的完整占卜测试")
print("=" * 50)

if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(VECTORS_PATH):
    print("[ERROR] 向量文件未构建！先运行 kb_preprocess/step3_vectorize.py")
    sys.exit(1)

retriever = RAGRetriever(EMBEDDINGS_PATH, VECTORS_PATH)
print(f"向量库已加载: {retriever.count()} 条\n")

test_questions = [
    "我最近想换工作，不知道时机是否合适",
    "和男朋友最近总是吵架，这段感情还能继续吗",
]

for q in test_questions:
    print("=" * 60)
    print(f"问: {q}")
    print("=" * 60)
    
    try:
        result = do_divination(q, retriever)
        pan = result["pan"]
        ben = pan["gua"]["ben"]["name"]
        bian = pan["gua"]["bian"]["name"] if pan["gua"]["bian"] else "静卦"
        dong = pan["gua"]["dong_yao_list"]
        dong_str = f"动爻{dong}" if dong else "静卦"
        print(f"\n本卦: {ben}  变卦: {bian}  {dong_str}")
        print(f"\n{result['reading']}")
        print(f"\n参考古籍 ({len(result['sources'])}条):")
        for s in result['sources']:
            print(f"  [{s['book']}] 相似度={s['score']:.2f}")
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
    
    print()
