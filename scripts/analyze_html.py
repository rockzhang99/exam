"""验证试卷提取输出完整性（V5 逐题截图版）"""
import os
import json
import glob

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

subdirs = [d for d in glob.glob(os.path.join(OUTPUT_DIR, "*")) if os.path.isdir(d)]
subdirs.sort(key=os.path.getmtime, reverse=True)

if not subdirs:
    print("output/ 下没有提取目录")
    exit(1)

target_dir = subdirs[0]
print(f"分析目录: {target_dir}")
print("=" * 60)

# 文件清单
for fname in ["index.html", "answers.html", "meta.json"]:
    fpath = os.path.join(target_dir, fname)
    exists = os.path.exists(fpath)
    size = os.path.getsize(fpath) if exists else 0
    print(f"  {fname}: {'OK' if exists else 'MISSING'} ({size:,} bytes)")

# images 目录
img_dir = os.path.join(target_dir, "images")
if os.path.exists(img_dir):
    q_imgs = glob.glob(os.path.join(img_dir, "q_*.png"))
    a_imgs = glob.glob(os.path.join(img_dir, "a_*.png"))
    print(f"  images/q_*.png: {len(q_imgs)} 个")
    print(f"  images/a_*.png: {len(a_imgs)} 个")

    # 检查图片大小（是否合理，不是空图片）
    for label, files in [("题目", q_imgs[:3]), ("答案", a_imgs[:3])]:
        for f in files:
            size = os.path.getsize(f)
            fname = os.path.basename(f)
            print(f"    {fname}: {size:,} bytes {'[空]' if size < 500 else ''}")

# meta
meta_path = os.path.join(target_dir, "meta.json")
if os.path.exists(meta_path):
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    print("\n--- Meta ---")
    for k, v in meta.items():
        print(f"  {k}: {v}")

# 检查 index.html 不含来源/组卷
index_path = os.path.join(target_dir, "index.html")
if os.path.exists(index_path):
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    has_source = "来源" in html
    has_zujuan = "组卷" in html
    has_analysis = "试卷分析" in html
    has_fieldtip = "fieldtip" in html and "display:none" not in html
    print(f"\n--- index.html ---")
    print(f"  来源标签: {'存在' if has_source else '已移除'}")
    print(f"  组卷信息: {'存在' if has_zujuan else '已移除'}")
    print(f"  试卷分析: {'存在' if has_analysis else '已移除'}")
    print(f"  fieldtip: {'存在(未隐藏)' if has_fieldtip else '已隐藏'}")

answers_path = os.path.join(target_dir, "answers.html")
if os.path.exists(answers_path):
    with open(answers_path, "r", encoding="utf-8") as f:
        html = f.read()
    has_source = "来源" in html
    has_fieldtip = "fieldtip" in html and "display:none" not in html
    print(f"\n--- answers.html ---")
    print(f"  来源标签: {'存在' if has_source else '已移除'}")
    print(f"  fieldtip: {'存在(未隐藏)' if has_fieldtip else '已隐藏'}")
