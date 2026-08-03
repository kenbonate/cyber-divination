"""测试排盘数据结构和前端渲染"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from liuyao_engine import LiuYaoEngine, HEXAGRAM_MAP

engine = LiuYaoEngine()
result = engine.get_result()

print("=== 排盘数据结构验证 ===\n")

# 验证关键字段
assert "datetime" in result
assert "sizhu" in result
assert "shensha" in result
assert "gua" in result
assert "lines" in result
assert len(result["lines"]) == 6, f"应该有6爻，实际有{len(result['lines'])}"
assert result["gua"]["ben"]["code"] in HEXAGRAM_MAP
assert HEXAGRAM_MAP[result["gua"]["ben"]["code"]] == result["gua"]["ben"]["name"]
lines_code = "".join(str(line["value"]) for line in result["lines"])
assert result["gua"]["ben"]["code"] == lines_code[3:] + lines_code[:3]

print(f"时间: {result['datetime']['solar']} ({result['datetime']['lunar']})")
print(f"四柱: {result['sizhu']['year']} {result['sizhu']['month']} {result['sizhu']['day']} {result['sizhu']['hour']}")
print(f"节气: {result['jieqi']['current']}, 月建: {result['yuejian']}")
print(f"空亡: 日空{result['xunkong']['day']} / 时空{result['xunkong']['hour']}")
print(f"本卦: {result['gua']['ben']['name']} ({result['gua']['ben']['palace']}宫{result['gua']['ben']['palace_wx']})")
print(f"变卦: {result['gua']['bian']['name'] if result['gua']['bian'] else '静卦'}")
print(f"动爻: {result['gua']['dong_yao_list']}")
print(f"世爻: 第{result['gua']['ben']['shi_yao']}爻, 应爻: 第{result['gua']['ben']['ying_yao']}爻")

print("\n=== 六爻详情（从上到下）===")
for line in reversed(result["lines"]):
    sy = " 世" if line["is_shi"] else " 应" if line["is_ying"] else ""
    chg = " [动]" if line["changing"] else ""
    print(f"  第{line['position']}爻: {line['liushen']} {line['liuqin']} {line['ganzhi']}{sy}{chg}")

print("\n=== 神煞 ===")
for k, v in result["shensha"].items():
    print(f"  {k}: {v}")

# 保存为JSON供前端测试
output_dir = os.path.join(os.path.dirname(__file__), "..", "kb_preprocess", "output")
os.makedirs(output_dir, exist_ok=True)
test_pan_path = os.path.join(output_dir, "test_pan.json")
with open(test_pan_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\n排盘数据已保存到 {test_pan_path}")
