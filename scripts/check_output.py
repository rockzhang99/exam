import re

base = "d:/4Project/exam/公众号文章/2026-07-08-11-302025-2026学年山东省济南市市中区育秀中学八年级（下）期末数学模拟试卷（2）"

with open(f'{base}/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 找三个区域
sections = ['试卷内容', '试卷答案', '试卷分析']
for s in sections:
    # 找此区域的 section-content
    pattern = re.escape(s) + r'.*?<div class="section-content">(.*?)</div>\s*</div>'
    m = re.search(pattern, html, re.DOTALL)
    if m:
        content = m.group(1).strip()
        print(f"\n===== {s} (长度: {len(content)}) =====")
        # 只显示前300字符
        text = re.sub(r'<[^>]+>', ' ', content)
        text = re.sub(r'\s+', ' ', text).strip()
        print(text[:300])
    else:
        print(f"\n===== {s}: 未找到 =====")

# 检查内容中是否嵌入了答案
sanwser_count = html.count('sanwser')
print(f'\n\nsanwser 类出现次数: {sanwser_count}')
s_sh_count = html.count('class="s sh"')
print(f'正确答案标记(s sh)出现次数: {s_sh_count}')
