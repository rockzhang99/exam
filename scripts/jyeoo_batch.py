"""
菁优网批量下载脚本 V3 — SQLite 版
用法:
  python jyeoo_batch.py --collect    收集所有学科的试卷链接到 batch.db
  python jyeoo_batch.py --download   下载（跳过已完成，失败可重试）
  python jyeoo_batch.py              先收集再下载
  python jyeoo_batch.py --status     查看各学科进度
  python jyeoo_batch.py --retry      重试所有失败的任务

数据库表 papers:
  subject | url(UNIQUE) | title | status | retry_count | error_msg | created_at | updated_at
  status: discovered / completed / failed
"""
import asyncio
import os
import sqlite3
import sys
from datetime import datetime
from playwright.async_api import async_playwright

from jyeoo_extractor import (
    sanitize_filename, extract_paper, ensure_login,
    AUTH_FILE, OUTPUT_DIR,
)

# ========== 配置 ==========
BATCH_OUTPUT = os.path.join(OUTPUT_DIR, "batch")
DB_FILE = os.path.join(BATCH_OUTPUT, "batch.db")

MIDDLE_SCHOOL_SUBJECTS = {
    "数学": "math", "物理": "physics", "化学": "chemistry",
    "生物": "biology", "地理": "geography", "语文": "chinese",
    "英语": "english", "道德与法治": "politics", "历史": "history",
    "科学": "science", "信息技术": "it",
}


def get_db() -> sqlite3.Connection:
    os.makedirs(BATCH_OUTPUT, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            title TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'discovered',
            retry_count INTEGER DEFAULT 0,
            error_msg TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON papers(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subject ON papers(subject)")
    conn.commit()

    # 自动迁移旧 JSON 数据（仅首次）
    count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    if count == 0:
        _migrate_json_to_db(conn)
    return conn


def _migrate_json_to_db(conn):
    """从旧的 discovered_urls.json 和 progress.json 迁移到 SQLite"""
    import json
    discovered_file = os.path.join(BATCH_OUTPUT, "discovered_urls.json")
    progress_file = os.path.join(BATCH_OUTPUT, "progress.json")

    completed = set()
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                completed = set(json.load(f).get("completed_urls", []))
        except Exception:
            pass

    if os.path.exists(discovered_file):
        try:
            with open(discovered_file, "r", encoding="utf-8") as f:
                discovered = json.load(f)
            migrated = 0
            for subject_cn, papers in discovered.items():
                for p in papers:
                    status = "completed" if p["url"] in completed else "discovered"
                    conn.execute(
                        "INSERT OR IGNORE INTO papers (subject,url,title,status) VALUES (?,?,?,?)",
                        (subject_cn, p["url"], p.get("title", ""), status)
                    )
                    migrated += 1
            conn.commit()
            print(f"[MIGRATE] 已从 JSON 迁移 {migrated} 条到 SQLite")
        except Exception as e:
            print(f"[MIGRATE] 迁移失败: {e}")


# ========== 状态查询 ==========
def get_subject_stats(conn) -> dict:
    rows = conn.execute("""
        SELECT subject,
               COUNT(*) AS total,
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS done,
               SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
               SUM(CASE WHEN status='discovered' THEN 1 ELSE 0 END) AS pending
        FROM papers GROUP BY subject ORDER BY subject
    """).fetchall()
    return {r[0]: {"total": r[1], "done": r[2], "failed": r[3], "pending": r[4]} for r in rows}


def show_status(conn):
    stats = get_subject_stats(conn)
    grand_total = grand_done = grand_fail = grand_pend = 0
    print(f"{'学科':<10} {'总数':>6} {'已完成':>6} {'失败':>6} {'待下载':>6}")
    print("-" * 40)
    for subj in MIDDLE_SCHOOL_SUBJECTS:
        s = stats.get(subj, {"total": 0, "done": 0, "failed": 0, "pending": 0})
        print(f"{subj:<10} {s['total']:>6} {s['done']:>6} {s['failed']:>6} {s['pending']:>6}")
        grand_total += s['total']
        grand_done += s['done']
        grand_fail += s['failed']
        grand_pend += s['pending']
    print("-" * 40)
    print(f"{'合计':<10} {grand_total:>6} {grand_done:>6} {grand_fail:>6} {grand_pend:>6}")


# ========== Phase 1: 收集 ==========
async def collect_paper_urls(page, subject_cn: str, subject_code: str) -> list[dict]:
    list_url = f"https://www.jyeoo.com/{subject_code}/report/school"
    print(f"\n  [COLLECT] 访问 {list_url}")
    try:
        await page.goto(list_url, wait_until="networkidle", timeout=60000)
    except Exception:
        await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(4000)

    papers = []
    page_num = 1
    max_pages = 100

    while page_num <= max_pages:
        await page.wait_for_timeout(2000)

        paper_links = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const href = a.getAttribute('href');
                if (href && href.includes('/report/detail/')) {
                    const text = (a.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (text.length > 5 || a.querySelector('h3,h4,.title')) {
                        const t = a.querySelector('h3,h4,.title,.name,span');
                        results.push({
                            url: href.startsWith('http') ? href : 'https://www.jyeoo.com' + href,
                            title: t ? t.textContent.trim() : text
                        });
                    }
                }
            });
            if (!results.length) {
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.getAttribute('href');
                    if (href && href.includes('/report/detail/'))
                        results.push({ url: href.startsWith('http') ? href : 'https://www.jyeoo.com' + href, title: (a.textContent||'').trim()||'(未知)' });
                });
            }
            return results;
        }""")

        seen = {p["url"] for p in papers}
        new_papers = [p for p in paper_links if p["url"] not in seen]
        papers.extend(new_papers)
        print(f"    第{page_num}页: +{len(new_papers)} 个 (累计 {len(papers)})")

        if not new_papers and page_num > 1:
            break

        next_clicked = False
        for sel in ["a:has-text('下一页')", "button:has-text('下一页')", "li:has-text('下一页') a"]:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click(); next_clicked = True; break
            except Exception:
                continue
        if not next_clicked:
            for sel in [".ant-pagination-next:not(.ant-pagination-disabled)",
                        ".el-pagination button.btn-next:not(:disabled)",
                        "[class*='pagination'] [class*='next']:not([class*='disabled'])",
                        "li.next:not(.disabled) a"]:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click(); next_clicked = True; break
                except Exception:
                    continue
        if not next_clicked:
            for psel in [f".ant-pagination-item-{page_num+1}",
                         f"[class*='pagination'] li:has-text('{page_num+1}')"]:
                try:
                    btn = await page.query_selector(psel)
                    if btn:
                        await btn.click(); next_clicked = True; break
                except Exception:
                    continue
        if not next_clicked:
            print(f"    无法翻页，收集完毕")
            break
        page_num += 1
        await page.wait_for_timeout(3000)

    return papers


async def phase_collect(page, conn) -> int:
    """收集缺失学科的 URL，写入 SQLite"""
    print("=" * 60)
    print("PHASE: 收集试卷链接")
    print("=" * 60)

    collected = 0
    for subject_cn, subject_code in MIDDLE_SCHOOL_SUBJECTS.items():
        existing = conn.execute("SELECT COUNT(*) FROM papers WHERE subject=?", (subject_cn,)).fetchone()[0]
        if existing > 0:
            print(f"[{subject_cn}] 已有 {existing} 条，跳过")
            continue

        print(f"[{subject_cn}] 开始收集...")
        try:
            papers = await collect_paper_urls(page, subject_cn, subject_code)
            if papers:
                conn.executemany(
                    "INSERT OR IGNORE INTO papers (subject,url,title,status) VALUES (?,?,?,'discovered')",
                    [(subject_cn, p["url"], p["title"]) for p in papers]
                )
                conn.commit()
                print(f"  [{subject_cn}] 写入 {len(papers)} 条")
                collected += len(papers)
        except Exception as e:
            print(f"  [ERROR] {subject_cn}: {e}")

    total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    print(f"\n收集完毕: 数据库共 {total} 条\n")
    show_status(conn)
    return collected


# ========== Phase 2: 下载 ==========
async def phase_download(page, conn):
    print("=" * 60)
    print("PHASE: 下载试卷")
    print("=" * 60)

    for subject_cn in MIDDLE_SCHOOL_SUBJECTS:
        rows = conn.execute(
            "SELECT url,title FROM papers WHERE subject=? AND status!='completed' ORDER BY id",
            (subject_cn,)
        ).fetchall()
        if not rows:
            continue

        subject_output = os.path.join(BATCH_OUTPUT, subject_cn, "名校")
        os.makedirs(subject_output, exist_ok=True)

        total = len(rows)
        print(f"\n{'─' * 40}")
        print(f"[{subject_cn}] 待下载 {total} 个")

        for i, (url, title) in enumerate(rows):
            print(f"\n[{subject_cn}] ({i + 1}/{total}) {title[:70]}")
            try:
                result = await extract_paper(page, url, subject_output)
                if result:
                    conn.execute(
                        "UPDATE papers SET status='completed',updated_at=datetime('now','localtime') WHERE url=?",
                        (url,)
                    )
                    conn.commit()
                    print(f"  [OK]")
                else:
                    conn.execute(
                        "UPDATE papers SET status='failed',retry_count=retry_count+1,error_msg=?,updated_at=datetime('now','localtime') WHERE url=?",
                        ("提取返回空", url)
                    )
                    conn.commit()
                    print(f"  [FAIL] 提取返回空，下次重试")
            except Exception as e:
                err = str(e)[:200]
                conn.execute(
                    "UPDATE papers SET status='failed',retry_count=retry_count+1,error_msg=?,updated_at=datetime('now','localtime') WHERE url=?",
                    (err, url)
                )
                conn.commit()
                print(f"  [FAIL] {err[:80]}")

            await page.wait_for_timeout(1000)

    print("\n下载阶段完成")
    show_status(conn)


# ========== 重试失败 ==========
async def phase_retry(page, conn):
    rows = conn.execute(
        "SELECT url,title,subject FROM papers WHERE status='failed' ORDER BY subject,id"
    ).fetchall()
    if not rows:
        print("没有失败任务")
        return

    print(f"重试 {len(rows)} 个失败任务\n")
    for i, (url, title, subject) in enumerate(rows):
        subject_output = os.path.join(BATCH_OUTPUT, subject, "名校")
        os.makedirs(subject_output, exist_ok=True)
        print(f"\n[{i + 1}/{len(rows)}] [{subject}] {title[:70]}")
        try:
            result = await extract_paper(page, url, subject_output)
            if result:
                conn.execute("UPDATE papers SET status='completed',updated_at=datetime('now','localtime') WHERE url=?", (url,))
                conn.commit()
                print(f"  [OK]")
            else:
                conn.execute("UPDATE papers SET status='failed',retry_count=retry_count+1,updated_at=datetime('now','localtime') WHERE url=?", (url,))
                conn.commit()
                print(f"  [FAIL]")
        except Exception as e:
            conn.execute("UPDATE papers SET status='failed',retry_count=retry_count+1,error_msg=?,updated_at=datetime('now','localtime') WHERE url=?", (str(e)[:200], url))
            conn.commit()
            print(f"  [FAIL] {e}")


# ========== Main ==========
async def main():
    mode = "both"
    args = set(sys.argv[1:])
    if "--collect" in args: mode = "collect"
    elif "--download" in args: mode = "download"
    elif "--retry" in args: mode = "retry"
    elif "--status" in args:
        conn = get_db()
        show_status(conn)
        conn.close()
        return

    conn = get_db()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            storage_state=AUTH_FILE if os.path.exists(AUTH_FILE) else None,
        )
        page = await context.new_page()

        async def handle_popup(popup):
            print(f"  [POPUP] 关闭: {popup.url[:80]}")
            await popup.close()
        page.on("popup", handle_popup)

        await ensure_login(context, page)

        if mode == "collect":
            await phase_collect(page, conn)
        elif mode == "download":
            await phase_download(page, conn)
        elif mode == "retry":
            await phase_retry(page, conn)
        else:
            await phase_collect(page, conn)
            await phase_download(page, conn)

        await browser.close()

    show_status(conn)
    print(f"\n数据库: {DB_FILE}")
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
