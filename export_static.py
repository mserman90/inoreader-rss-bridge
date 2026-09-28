#!/usr/bin/env python3
"""
export_static.py
Inoreader akışını çekip 'dist/' dizinine statik rss.xml, atom.xml, feed.json ve index.html dosyaları üretir.
GitHub Pages, Cloudflare Pages, Netlify veya statik web sunucularında sıfır maliyetle çalıştırmak için idealdir.
"""

import os
import sys
import json
import html
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config
from app.storage import Storage
from app.scraper import scrape_inoreader
from app.feed import generate_rss_2_xml, generate_atom_xml, generate_json_feed

def generate_portal_html(feed_title: str, public_url: str, items: list, last_updated: str) -> str:
    rss_url = f"{public_url}/rss.xml"
    atom_url = f"{public_url}/atom.xml"
    json_url = f"{public_url}/feed.json"

    items_cards = []
    for it in items:
        img_tag = ""
        if it.get("image_url"):
            img_tag = f'<div class="card-img" style="background-image: url(\'{html.escape(it["image_url"])}\');"></div>'

        author_badge = f'<span class="badge badge-source">🏷️ {html.escape(it.get("source_feed") or it.get("author") or "Inoreader")}</span>'
        date_badge = f'<span class="badge badge-date">📅 {html.escape(it.get("pub_date", ""))}</span>'

        # Extract snippet from description
        desc_text = html.escape(it.get("description", ""))
        # Strip simple tags for snippet if needed
        import re
        clean_desc = re.sub(r'<[^>]+>', ' ', it.get("description", ""))
        clean_desc = " ".join(clean_desc.split())
        if len(clean_desc) > 280:
            clean_desc = clean_desc[:280] + "..."

        card_html = f"""
        <article class="article-card" data-title="{html.escape(it['title'].lower())}">
            {img_tag}
            <div class="card-body">
                <div class="card-meta">
                    {date_badge}
                    {author_badge}
                </div>
                <h3 class="card-title">
                    <a href="{html.escape(it['link'])}" target="_blank" rel="noopener noreferrer">
                        {html.escape(it['title'])}
                    </a>
                </h3>
                <p class="card-summary">{clean_desc}</p>
                <div class="card-footer">
                    <a href="{html.escape(it['link'])}" target="_blank" rel="noopener noreferrer" class="read-btn">
                        Kaynağa Git &rarr;
                    </a>
                </div>
            </div>
        </article>
        """
        items_cards.append(card_html)

    cards_joined = "\n".join(items_cards)

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(feed_title)} - Web Portalı ve RSS Yayını</title>
    <link rel="alternate" type="application/rss+xml" title="{html.escape(feed_title)} (RSS 2.0)" href="{rss_url}">
    <link rel="alternate" type="application/atom+xml" title="{html.escape(feed_title)} (Atom 1.0)" href="{atom_url}">
    <link rel="alternate" type="application/feed+json" title="{html.escape(feed_title)} (JSON Feed)" href="{json_url}">
    <style>
        :root {{
            --primary: #1e40af;
            --primary-hover: #1d4ed8;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text-main);
            line-height: 1.5;
            padding-bottom: 60px;
        }}
        .hero {{
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
            color: white;
            padding: 48px 24px;
            text-align: center;
            box-shadow: 0 4px 20px -2px rgba(30, 58, 138, 0.25);
        }}
        .hero-inner {{ max-width: 900px; margin: 0 auto; }}
        .hero h1 {{ font-size: 2.2rem; font-weight: 800; margin-bottom: 8px; }}
        .hero p {{ font-size: 1.05rem; opacity: 0.9; margin-bottom: 24px; }}
        .source-pill {{
            display: inline-flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(8px);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 13px;
            color: #ffffff;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .source-pill:hover {{ background: rgba(255, 255, 255, 0.25); }}
        .main-container {{
            max-width: 1040px;
            margin: -24px auto 0;
            padding: 0 16px;
        }}
        .feed-box {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border);
            margin-bottom: 32px;
        }}
        .feed-box-header {{
            font-weight: 700;
            font-size: 15px;
            margin-bottom: 12px;
            color: var(--primary);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .url-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .url-input {{
            flex: 1;
            min-width: 260px;
            padding: 10px 14px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 13px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #f1f5f9;
            color: #0f172a;
        }}
        .btn {{
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}
        .btn-primary {{ background: var(--primary); color: white; }}
        .btn-primary:hover {{ background: var(--primary-hover); }}
        .btn-outline {{
            background: #ffffff;
            color: var(--text-main);
            border: 1px solid var(--border);
        }}
        .btn-outline:hover {{ background: #f8fafc; }}
        .formats-bar {{
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: var(--text-muted);
            flex-wrap: wrap;
        }}
        .formats-bar a {{ color: var(--primary); text-decoration: none; font-weight: 600; }}
        .formats-bar a:hover {{ text-decoration: underline; }}
        .toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .search-input {{
            padding: 10px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 14px;
            width: 320px;
            max-width: 100%;
            background: white;
        }}
        .articles-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}
        .article-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .article-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.08);
        }}
        .card-img {{
            height: 170px;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            border-bottom: 1px solid var(--border);
        }}
        .card-body {{
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }}
        .card-meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}
        .badge {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 500;
        }}
        .badge-date {{ background: #f1f5f9; color: #475569; }}
        .badge-source {{ background: #eff6ff; color: #1d4ed8; }}
        .card-title {{
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.35;
            margin-bottom: 10px;
        }}
        .card-title a {{
            color: var(--text-main);
            text-decoration: none;
        }}
        .card-title a:hover {{ color: var(--primary); }}
        .card-summary {{
            font-size: 13.5px;
            color: var(--text-muted);
            line-height: 1.5;
            margin-bottom: 16px;
            flex-grow: 1;
        }}
        .card-footer {{
            border-top: 1px solid #f1f5f9;
            padding-top: 12px;
            margin-top: auto;
        }}
        .read-btn {{
            font-size: 13px;
            font-weight: 600;
            color: var(--primary);
            text-decoration: none;
            display: inline-block;
        }}
        .read-btn:hover {{ text-decoration: underline; }}
        footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <header class="hero">
        <div class="hero-inner">
            <h1>📡 {html.escape(feed_title)} Web Portalı</h1>
            <p>Inoreader canlı akışındaki makalelerin otomatik derlenmiş web portalı ve sabit RSS servisi.</p>
            <a href="{config.INOREADER_URL}" target="_blank" rel="noopener noreferrer" class="source-pill">
                🔗 Orijinal Inoreader Akışını Aç &rarr;
            </a>
        </div>
    </header>

    <main class="main-container">
        <!-- Feed Link Box -->
        <section class="feed-box">
            <div class="feed-box-header">
                <span>⚡ Sabit RSS 2.0 Bağlantınız (Okuyucunuza Ekleyin)</span>
                <span style="font-weight: normal; font-size: 12px; color: var(--text-muted);">
                    Otomatik Güncelleme: Her 30 dakikada bir
                </span>
            </div>
            <div class="url-row">
                <input type="text" readonly value="{rss_url}" class="url-input" id="rssUrl">
                <button class="btn btn-primary" onclick="navigator.clipboard.writeText(document.getElementById('rssUrl').value); alert('RSS linki panoya kopyalandı!');">
                    📋 Kopyala
                </button>
                <a href="{rss_url}" target="_blank" class="btn btn-outline">
                    Aç (XML)
                </a>
            </div>
            <div class="formats-bar">
                <span>Diğer Formatlar:</span>
                <a href="{atom_url}" target="_blank">Atom 1.0 Yayını</a>
                <a href="{json_url}" target="_blank">JSON Feed (v1.1)</a>
                <span style="margin-left: auto;">Toplam <strong>{len(items)}</strong> makale listeleniyor</span>
            </div>
        </section>

        <!-- Search Toolbar -->
        <div class="toolbar">
            <h2 style="font-size: 1.25rem; font-weight: 700;">Son Eklenen Makaleler</h2>
            <input type="text" id="searchInput" class="search-input" placeholder="🔍 Başlıklarda ara..." onkeyup="filterArticles()">
        </div>

        <!-- Articles Grid -->
        <section class="articles-grid" id="articlesGrid">
            {cards_joined}
        </section>
    </main>

    <footer>
        <p>Son Güncelleme: {last_updated} &bull; GitHub Actions &amp; Pages ile otomatik dağıtılmaktadır.</p>
    </footer>

    <script>
        function filterArticles() {{
            const filter = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.article-card');
            cards.forEach(card => {{
                const title = card.getAttribute('data-title');
                if (title.indexOf(filter) > -1) {{
                    card.style.display = "";
                }} else {{
                    card.style.display = "none";
                }}
            }});
        }}
    </script>
</body>
</html>"""

def main():
    dist_dir = Path(os.getenv("DIST_DIR", config.BASE_DIR / "dist"))
    dist_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Inoreader akışı çekiliyor: {config.INOREADER_URL}")
    data = scrape_inoreader(config.INOREADER_URL)
    print(f"[+] Çekilen öğe sayısı: {len(data['items'])}")

    storage = Storage(config.DB_PATH)
    new_count = storage.save_items(data["items"])
    storage.prune_items(config.MAX_STORED_ITEMS)
    print(f"[+] Veritabanına {new_count} yeni öğe eklendi. Toplam kayıt: {storage.count_items()}")

    items = storage.get_items(limit=100)
    feed_title = data.get("title", config.FEED_TITLE)
    public_url = config.PUBLIC_BASE_URL or "https://mserman90.github.io/inoreader-rss-bridge"
    rss_self = f"{public_url}/rss.xml"
    atom_self = f"{public_url}/atom.xml"
    json_self = f"{public_url}/feed.json"
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # Generate RSS 2.0
    rss_content = generate_rss_2_xml(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_rss_url=rss_self,
        items=items,
        language=config.FEED_LANGUAGE
    )
    (dist_dir / "rss.xml").write_text(rss_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'rss.xml'}")

    # Generate Atom 1.0
    atom_content = generate_atom_xml(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_atom_url=atom_self,
        items=items
    )
    (dist_dir / "atom.xml").write_text(atom_content, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'atom.xml'}")

    # Generate JSON Feed
    json_data = generate_json_feed(
        feed_title=feed_title,
        feed_description=config.FEED_DESCRIPTION,
        feed_link=config.INOREADER_URL,
        self_json_url=json_self,
        items=items
    )
    (dist_dir / "feed.json").write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'feed.json'}")

    # Generate Web Portal HTML in dist/index.html
    portal_html = generate_portal_html(feed_title, public_url, items, now_str)
    (dist_dir / "index.html").write_text(portal_html, encoding="utf-8")
    print(f"[+] Üretildi: {dist_dir / 'index.html'} (Zengin Web Portalı)")

    print("[*] Tüm statik dosyalar ve web portalı başarıyla oluşturuldu!")

if __name__ == "__main__":
    main()
