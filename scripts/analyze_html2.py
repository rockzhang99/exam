"""深度分析菁优网试卷页面DOM结构"""
import re
from html.parser import HTMLParser

class DOMAnalyzer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.result = []
        self.current_text = ""
        self.text_elements = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.stack.append((tag, attrs_dict))
        
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        if self.current_text.strip():
            path = '/'.join([t[0] + (f'.{t[1].get("class","")}' if t[1].get("class") else "")
                            for t in self.stack])
            self.text_elements.append({
                'path': path,
                'text': self.current_text.strip()[:200]
            })
        self.current_text = ""
            
    def handle_data(self, data):
        self.current_text += data

with open('../output/page_expanded.html', 'r', encoding='utf-8') as f:
    html = f.read()

analyzer = DOMAnalyzer()
try:
    analyzer.feed(html)
except Exception:
    pass

# 查找关键文本片段
keywords = ['试卷内容', '试卷分析', '知识点讲解', '同类卷', '答案', '解析', '选择题', '填空题', '解答题', '难度']
for item in analyzer.text_elements:
    for kw in keywords:
        if kw in item['text']:
            print(f"[{kw}] {item['text'][:150]}")
            print(f"   路径: {item['path'][:200]}")
            print()
            break

# 打印所有包含"试卷"的文本元素
print("\n===== 包含'试卷'的内容 =====")
for item in analyzer.text_elements:
    if '试卷' in item['text']:
        print(f"  {item['text'][:120]}")
