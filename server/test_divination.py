"""
快速测试：不启动服务，直接跑一次占卜看效果
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import do_divination, RAGRetriever, DB_PATH

if not os.path.exists(DB_PATH):
    print("[ERROR] 向量数据库未构建！先运行 kb_preprocess/step3_vectorize.py")
    sys.exit(1)

retriever = RAGRetriever(DB_PATH)
print(f"向量库已加载: {retriever.collection.count()} 条\n")

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
        print(f"\n本卦: {result['hexagram']['ben_gua']}")
        if result['hexagram']['bian_gua']:
            print(f"变卦: {result['hexagram']['bian_gua']}")
        print(f"\n{result['reading']}")
        print(f"\n参考古籍 ({len(result['sources'])}条):")
        for s in result['sources']:
            print(f"  [{s['book']}] 相似度={s['score']:.2f}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    
    print()
