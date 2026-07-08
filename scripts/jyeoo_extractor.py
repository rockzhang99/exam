"""
菁优网试卷提取脚本 V6
- 每道题独立截图（小图），隐藏 fieldtip（组卷/引用/难度）
- 题目图片 → index.html
- 选择题+填空题答案汇总 → answers.html（纯文字表格，无截图）
- 不需要解答题答案、不需要试卷分析模块
保存到 output/ 目录
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from playwright.async_api import async_playwright

# UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TARGET_URL = "https://www.jyeoo.com/math/report/detail/72AixfqffL0mxwW2oWzdwCa5IJnPE18hMD90CYhRm2mVwtrLQc1jZQ"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
AUTH_FILE = os.path.join(OUTPUT_DIR, "auth_state.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def extract_answers_from_content(html_content: str) -> str:
    """从试卷内容HTML中提取答案汇总表格"""
    answers = []

    choice_correct = re.findall(
        r'<span class="qseq">(\d+)．</span>.*?'
        r'class="s sh">([^<]+)<',
        html_content, re.DOTALL
    )

    if choice_correct:
        answers.append('<div class="answer-group">')
        answers.append('<h4>一、选择题答案</h4>')
        answers.append('<table style="border-collapse:collapse;width:100%">')
        answers.append('<tr style="background:#f5f5f5"><th style="padding:8px;border:1px solid #ddd">题号</th><th style="padding:8px;border:1px solid #ddd">答案</th></tr>')
        for num, ans in choice_correct:
            answers.append(f'<tr><td style="padding:8px;border:1px solid #ddd;text-align:center">{num}</td><td style="padding:8px;border:1px solid #ddd;text-align:center;font-weight:bold;color:#07C160">{ans.strip()}</td></tr>')
        answers.append('</table></div>')

    fill_matches = re.findall(
        r'data-cate="2".*?<span class="qseq">(\d+)．</span>.*?<div class="sanwser">(.*?)</div>',
        html_content, re.DOTALL
    )
    if fill_matches:
        answers.append('<div class="answer-group">')
        answers.append('<h4>二、填空题答案</h4>')
        answers.append('<table style="border-collapse:collapse;width:100%">')
        answers.append('<tr style="background:#f5f5f5"><th style="padding:8px;border:1px solid #ddd">题号</th><th style="padding:8px;border:1px solid #ddd">答案</th></tr>')
        for num, ans in fill_matches:
            answers.append(f'<tr><td style="padding:8px;border:1px solid #ddd;text-align:center">{num}</td><td style="padding:8px;border:1px solid #ddd;text-align:center;font-weight:bold;color:#07C160">{ans.strip()}</td></tr>')
        answers.append('</table></div>')

    if not answers:
        answers.append('<p style="color:#999;font-style:italic">未提取到答案信息</p>')

    return '\n'.join(answers)


def build_image_page_html(title: str, images: list, subtitle: str = "") -> str:
    """构建纯图片 HTML 页面。
    images 列表中每项可以是:
      - 纯图片文件名 (如 "q_001.png")  → 自动包 <img>
      - 已构造好的 HTML 标签 (如 "<h3>...") → 直接透传
      - 特殊标记 "__SEP__标题文字" → 渲染为题型分隔 <h3>
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tags = []
    for item in images:
        stripped = item.strip()
        if stripped.startswith("<"):
            # 已经是完整的 HTML 标签，直接插入
            tags.append(f"            {stripped}")
        elif stripped.startswith("__SEP__"):
            # 题型分隔标记
            label = stripped.replace("__SEP__", "")
            tags.append(
                f'            <h3 style="font-size:16px;color:#333;margin:16px 0 8px;padding-left:8px;border-left:3px solid #07c160;">{label}</h3>'
            )
        else:
            # 纯图片文件名
            tags.append(
                f'            <img src="{stripped}" style="max-width:100%;display:block;margin-bottom:0;">'
            )
    img_tags = "\n".join(tags)

    subtitle_html = f'<p style="text-align:center;color:#999;font-size:13px;margin-bottom:16px;">{subtitle}</p>' if subtitle else ''

    return f'''<!DOCTYPE html>
<html lang="zh_CN">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=0,viewport-fit=cover">
    <title>{title}</title>
    <style>
        #page-content, #js_article_bottom_bar, .__page_content__ {{ max-width: 667px; margin: 0 auto; }}
        img {{ max-width: 100%; display: block; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif; }}
    </style>
</head>
<body class="zh_CN wx_wap_page wx_wap_desktop_fontsize_2 mm_appmsg">
<div id="js_article" style="position:relative;" class="rich_media">
  <div id="js_base_container" class="rich_media_inner">
    <div id="page-content" class="rich_media_area_primary">
      <div class="rich_media_area_primary_inner">
        <div id="img-content" class="rich_media_wrp">

          <h1 class="rich_media_title" id="activity-name" style="font-size:22px;font-weight:bold;text-align:center;padding:20px 16px 8px;color:#333;">
            {title}
          </h1>

          <div id="meta_content" class="rich_media_meta_list" style="text-align:center;padding-bottom:8px;">
            <span class="rich_media_meta rich_media_meta_text" style="color:#999;font-size:13px;">
              编辑于 {now}
            </span>
          </div>
          {subtitle_html}

          <div id="js_content" class="rich_media_content">
{img_tags}
          </div>
          <div id="page_bottom_area"></div>
        </div>
      </div>
    </div>
  </div>
</div>
</body>
</html>'''


def build_answer_html(title: str, summary: str) -> str:
    """构建纯答案汇总 HTML（选择题+填空题答案表格，无截图）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'''<!DOCTYPE html>
<html lang="zh_CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>{title} - 答案</title>
    <style>
        body {{ font-family: -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; max-width:667px; margin:0 auto; padding:16px; }}
        h1 {{ font-size:20px; text-align:center; padding:12px 0 8px; }}
        h4 {{ font-size:16px; margin:16px 0 8px; padding-left:8px; border-left:3px solid #07c160; }}
        table {{ width:100%; border-collapse:collapse; margin-bottom:16px; }}
        th {{ background:#f5f5f5; padding:8px; border:1px solid #ddd; }}
        td {{ padding:8px; border:1px solid #ddd; text-align:center; }}
        .meta {{ text-align:center; color:#999; font-size:12px; padding-bottom:8px; }}
    </style>
</head>
<body>
    <h1>{title} - 答案</h1>
    <div class="meta">编辑于 {now}</div>
    {summary}
</body>
</html>'''


async def inject_hide_stylesheet(page):
    """【纯CSS注入】截图前注入样式表，隐藏答案高亮/fieldtip/按钮，不修改DOM"""
    await page.evaluate("""() => {
        if (document.getElementById('jyeoo-hide-style')) return;
        var style = document.createElement('style');
        style.id = 'jyeoo-hide-style';
        style.textContent = [
            '.sh, .s.sh { color: inherit !important; font-weight: inherit !important; background: none !important; }',
            '.fieldtip { display: none !important; }',
            '.sanwser { display: none !important; }',
            '[class*="showAnswer"], [class*="ShowAnswer"], [class*="answerBtn"], [class*="AnswerBtn"] { display: none !important; }',
            // 禁用 QUES_LI 上的 hover 效果，避免截图中出现鼠标悬停样式
            '.QUES_LI:hover { background: none !important; }',
            '.QUES_LI:hover * { color: inherit !important; background: none !important; border: none !important; box-shadow: none !important; outline: none !important; }',
        ].join('\\n');
        document.head.appendChild(style);
    }""")


async def remove_hide_stylesheet(page):
    """移除注入的隐藏样式表，恢复页面正常显示"""
    await page.evaluate("""() => {
        var style = document.getElementById('jyeoo-hide-style');
        if (style) style.remove();
    }""")


async def screenshot_questions(page, output_dir: str, prefix: str):
    """
    逐题截图，保存为 prefix_001.png, prefix_002.png ...
    返回标题列表和图片文件名列表
    """
    os.makedirs(output_dir, exist_ok=True)

    elements = await page.query_selector_all(".QUES_LI")
    if not elements:
        print(f"[SCREENSHOT:{prefix}] 未找到 .QUES_LI 元素")
        return [], []

    # 先注入CSS隐藏样式，不修改DOM
    await inject_hide_stylesheet(page)
    # 鼠标移到页面左上角，避免 hover 效果被截入图片
    await page.mouse.move(0, 0)
    await page.wait_for_timeout(500)

    images = []
    type_headers = []  # 题型标题信息
    current_type = ""
    type_map = {"1": "选择题", "2": "填空题", "9": "解答题"}
    type_labels = {"选择题": "一、选择题", "填空题": "二、填空题", "解答题": "三、解答题"}

    # 先统计各题型数量
    type_counts = {}
    for el in elements:
        html_part = await el.inner_html()
        if html_part and len(html_part) > 20:
            cate_match = re.search(r'data-cate="(\d+)"', html_part)
            qtype = type_map.get(cate_match.group(1), "其他") if cate_match else "其他"
            type_counts[qtype] = type_counts.get(qtype, 0) + 1

    for idx, el in enumerate(elements):
        try:
            html_part = await el.inner_html()
            if not html_part or len(html_part) <= 20:
                continue

            # 判断题型，需要时在 images 列表中加入分隔标记
            cate_match = re.search(r'data-cate="(\d+)"', html_part)
            qtype = type_map.get(cate_match.group(1), "其他") if cate_match else "其他"
            if qtype != current_type and qtype in type_labels:
                current_type = qtype
                count = type_counts.get(qtype, 0)
                separator_name = f"__SEP__{type_labels[qtype]}（共{count}题）"
                images.append(separator_name)

            # 先滚动元素到视口中央，确保截图完整
            try:
                await el.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
                await page.wait_for_timeout(300)
            except Exception:
                pass

            # 截图当前题目
            filename = f"{prefix}_{idx + 1:03d}.png"
            filepath = os.path.join(output_dir, filename)
            await el.screenshot(path=filepath)
            images.append(filename)
        except Exception as e:
            print(f"  [WARN] 第 {idx + 1} 题截图失败: {e}")

    return images


async def click_all_show_answer_buttons(page):
    """点击页面上所有'显示答案'按钮"""
    # 注册 dialog 处理器，自动关闭所有弹窗
    async def dismiss_dialog(dialog):
        print(f"  [DIALOG] {dialog.type}: {dialog.message}")
        await dialog.dismiss()
    page.on("dialog", dismiss_dialog)

    # 多种选择器尝试
    btns = []
    for selector in [
        "[class*='showAnswer']",
        ".show-answer",
        ":has-text('显示答案')",
    ]:
        try:
            btns = await page.query_selector_all(selector)
            if btns:
                break
        except Exception:
            btns = []

    if not btns:
        try:
            btns = await page.locator("text=显示答案").all()
        except Exception:
            btns = []

    print(f"[ANSWERS] 找到 {len(btns)} 个显示答案按钮")

    clicked = 0
    for btn in btns:
        try:
            # 检查页面是否仍然存活
            try:
                await page.evaluate("() => 1")
            except Exception:
                print("  [WARN] 页面已关闭，停止点击")
                break

            await btn.click(no_wait_after=True, timeout=3000)
            clicked += 1
            await page.wait_for_timeout(300)
        except Exception as e:
            print(f"  [WARN] 第 {clicked + 1} 个按钮点击失败: {e}")

    # 最后等待页面稳定（加存活检查）
    try:
        await page.wait_for_timeout(2000)
    except Exception:
        print("  [WARN] 等待页面稳定时，页面已关闭")

    page.remove_listener("dialog", dismiss_dialog)
    print(f"[ANSWERS] 成功点击 {clicked} 个按钮")
    return clicked


async def extract_paper(page, target_url: str, output_base_dir: str) -> dict | None:
    """提取单张试卷，返回 meta 信息字典；失败返回 None"""
    print(f"\n{'=' * 60}")
    print(f"[PAPER] {target_url}")
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        print(f"  [ERROR] 页面加载失败: {target_url}")
        return None
    await page.wait_for_timeout(5000)

    # ===== 提取试卷标题 =====
    paper_title = ""
    for sel in ["h1", ".report-title", "[class*='paper-title']", "title"]:
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if text and '菁优网' in text:
                text = text.split('_')[0].split(' - ')[0].strip()
            if text and len(text) > 5:
                paper_title = text
                break
    if not paper_title:
        paper_title = "未知试卷标题"
    print(f"[TITLE] {paper_title}")

    # ===== 输出目录 =====
    safe_title = sanitize_filename(paper_title)[:50]
    folder_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}"
    article_dir = os.path.join(output_base_dir, folder_name)
    img_dir = os.path.join(article_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    # ===== 确保在"试卷内容" tab =====
    content_tab = await page.query_selector("text=试卷内容")
    if content_tab:
        try:
            await content_tab.click()
            await page.wait_for_timeout(3000)
        except Exception:
            pass

    # ===== 步骤1: 逐题截图（无答案高亮）→ index.html =====
    print("[STEP 1] 逐题截图试卷内容...")
    content_images = await screenshot_questions(page, img_dir, "q")

    content_img_entries = []
    for img in content_images:
        if img.startswith("__SEP__"):
            content_img_entries.append(img)
        else:
            content_img_entries.append(f"images/{img}")

    content_html = build_image_page_html(paper_title, content_img_entries if content_img_entries else [])
    with open(os.path.join(article_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(content_html)
    q_count = len([i for i in content_images if not i.startswith("__SEP__")])
    print(f"[SAVE] index.html ({q_count} 题截图)")

    # ===== 步骤2: 答案 → answers.html =====
    print("[STEP 2] 提取选择题+填空题答案...")
    await remove_hide_stylesheet(page)
    await page.wait_for_timeout(500)
    await click_all_show_answer_buttons(page)
    await page.wait_for_timeout(3000)

    summary_html = ""
    try:
        parent_html = await page.evaluate("""() => {
            const parent = document.querySelector('.body-content, #reportContent, .content');
            return parent ? parent.innerHTML : '';
        }""")
        if parent_html:
            summary_html = extract_answers_from_content(parent_html)
    except Exception:
        pass

    answers_html = build_answer_html(paper_title, summary_html if summary_html else '<p>未提取到答案信息</p>')
    with open(os.path.join(article_dir, "answers.html"), "w", encoding="utf-8") as f:
        f.write(answers_html)
    print(f"[SAVE] answers.html")

    meta = {
        "url": target_url,
        "title": paper_title,
        "fetch_time": datetime.now().isoformat(),
        "content_images": q_count,
    }
    with open(os.path.join(article_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[DONE] {paper_title}  ({q_count} 题)")
    return meta


async def ensure_login(context, page):
    """确保已登录；返回 True 表示已通过"""
    await page.goto("https://www.jyeoo.com/math/report/school", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)

    current_url = page.url
    if "login" in current_url.lower() or "passport" in current_url.lower():
        print("=" * 60)
        print("[LOGIN] 请在浏览器中手动登录, 完成后按 Enter")
        print("=" * 60)
        input(">>> ")
        await context.storage_state(path=AUTH_FILE)
        print("[OK] 登录态已保存")


async def main():
    use_existing_auth = os.path.exists(AUTH_FILE)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            storage_state=AUTH_FILE if use_existing_auth else None,
        )
        page = await context.new_page()

        # 注册 popup 处理器
        async def handle_popup(popup):
            print(f"  [POPUP] 关闭弹出页面: {popup.url}")
            await popup.close()
        page.on("popup", handle_popup)

        # ===== 登录检查 =====
        await ensure_login(context, page)

        # ===== 提取单张试卷 =====
        await extract_paper(page, TARGET_URL, OUTPUT_DIR)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
