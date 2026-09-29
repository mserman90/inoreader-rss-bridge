import html
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

def clean_html_tags(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', text)
    return " ".join(clean.split())

def generate_newspaper_portal_html(items: List[Dict[str, Any]], last_updated: str, rss_url: str, atom_url: str, json_url: str) -> str:
    today_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    
    # Sort items by date
    items_sorted = sorted(items, key=lambda x: x.get("pub_date_ts", 0), reverse=True)
    
    # Hero article (first item)
    hero_item = items_sorted[0] if items_sorted else None
    secondary_items = items_sorted[1:4] if len(items_sorted) > 1 else []
    remaining_items = items_sorted[4:] if len(items_sorted) > 4 else []

    # Fallback water images for articles without image
    default_water_images = [
        "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=800&q=80", # Agricultural field with water
        "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=800&q=80", # River / valley
        "https://images.unsplash.com/photo-1544717305-2782549b5136?w=800&q=80", # Water drop
        "https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=800&q=80", # Waves / reservoir
        "https://images.unsplash.com/photo-1574943320219-553eb213f72d?w=800&q=80", # Irrigation canal
    ]

    # JSON payload for modal dialogs
    import json
    portal_data = []
    for idx, it in enumerate(items_sorted):
        img = it.get("image_url") or default_water_images[idx % len(default_water_images)]
        title_tr = it.get("title_tr") or it.get("title")
        summary_tr = it.get("summary_tr") or clean_html_tags(it.get("description", ""))
        category = it.get("category_tr") or "Su Kaynakları"
        source = it.get("source_feed") or it.get("author") or "Bilimsel Araştırma"
        portal_data.append({
            "id": idx,
            "title_tr": title_tr,
            "title_en": it.get("title"),
            "summary_tr": summary_tr,
            "category": category,
            "source": source,
            "author": it.get("author", ""),
            "date": it.get("pub_date", ""),
            "link": it.get("link", ""),
            "image": img
        })

    json_portal_data = json.dumps(portal_data, ensure_ascii=False)

    # Secondary headline cards
    secondary_html = ""
    for it in portal_data[1:4]:
        secondary_html += f"""
        <div class="sub-headline-card" onclick="openArticleModal({it['id']})">
            <div class="sub-headline-img" style="background-image: url('{html.escape(it['image'])}');">
                <span class="news-badge">{html.escape(it['category'])}</span>
            </div>
            <div class="sub-headline-content">
                <span class="news-date">📅 {html.escape(it['date'][:16] if it.get('date') else today_str)}</span>
                <h4>{html.escape(it['title_tr'])}</h4>
                <p>{html.escape(it['summary_tr'][:120])}...</p>
            </div>
        </div>
        """

    # Grid article cards
    grid_html = ""
    for it in portal_data[4:]:
        grid_html += f"""
        <article class="news-grid-card" data-category="{html.escape(it['category'])}" data-title="{html.escape(it['title_tr'].lower())} {html.escape(it['title_en'].lower())}">
            <div class="card-img-wrap" style="background-image: url('{html.escape(it['image'])}');" onclick="openArticleModal({it['id']})">
                <span class="news-badge">{html.escape(it['category'])}</span>
            </div>
            <div class="card-body">
                <div class="card-meta">
                    <span>📅 {html.escape(it['date'][:16] if it.get('date') else today_str)}</span>
                    <span>🏛️ {html.escape(it['source'][:32])}</span>
                </div>
                <h3 class="card-title" onclick="openArticleModal({it['id']})">
                    {html.escape(it['title_tr'])}
                </h3>
                <h5 class="card-title-en">
                    Original: {html.escape(it['title_en'])}
                </h5>
                <p class="card-excerpt">
                    {html.escape(it['summary_tr'][:180])}...
                </p>
                <div class="card-action-bar">
                    <button class="btn-read-more" onclick="openArticleModal({it['id']})">Haberi Oku &rarr;</button>
                    <a href="{html.escape(it['link'])}" target="_blank" rel="noopener noreferrer" class="link-original" title="Orijinal Araştırma Sayfası">
                        🔗 Kaynak
                    </a>
                </div>
            </div>
        </article>
        """

    # Ticker titles
    ticker_items = "".join([f'<span class="ticker-item" onclick="openArticleModal({it["id"]})">🔥 {html.escape(it["title_tr"])}</span>' for it in portal_data[:8]])

    # Hero element
    hero_html = ""
    if portal_data:
        h = portal_data[0]
        hero_html = f"""
        <section class="main-headline-banner" onclick="openArticleModal(0)">
            <div class="hero-image-col" style="background-image: url('{html.escape(h['image'])}');">
                <div class="hero-image-overlay">
                    <span class="hero-category-tag">⭐ GÜNÜN MANŞETİ &bull; {html.escape(h['category'])}</span>
                </div>
            </div>
            <div class="hero-content-col">
                <div class="hero-meta">
                    <span>📅 {html.escape(h['date'])}</span> &bull; 
                    <span>🏛️ {html.escape(h['source'])}</span>
                </div>
                <h2 class="hero-title">{html.escape(h['title_tr'])}</h2>
                <h4 class="hero-title-en">Original: {html.escape(h['title_en'])}</h4>
                <p class="hero-summary">{html.escape(h['summary_tr'][:320])}...</p>
                <div class="hero-footer">
                    <button class="btn-hero-read">Tam Haberi ve Analizi Oku &rarr;</button>
                    <span class="hero-hint">ScienceDirect / ASCE Akademik Veritabanı Kaynağı</span>
                </div>
            </div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Su Haber Bülteni - Türkiye ve Dünya Su & Sulama Gazetesi</title>
    
    <!-- Meta tags for SEO & Feed Readers -->
    <meta name="description" content="Türkiye ve Dünya genelindeki su kaynakları, tarımsal sulama teknolojileri, hidroloji ve çevre araştırmalarından derlenen modern gazete temalı haber portalı.">
    <link rel="alternate" type="application/rss+xml" title="Su Haber Bülteni (RSS 2.0)" href="{rss_url}">
    <link rel="alternate" type="application/atom+xml" title="Su Haber Bülteni (Atom)" href="{atom_url}">
    <link rel="alternate" type="application/feed+json" title="Su Haber Bülteni (JSON)" href="{json_url}">

    <!-- Google Fonts for Editorial Newspaper Typography -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Merriweather:ital,wght@0,300;0,400;0,700;1,300;1,400&family=Public+Sans:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,600;0,800;0,900;1,400;1,700&display=swap" rel="stylesheet">

    <style>
        :root {{
            --paper-bg: #fdfdfc;
            --paper-card: #ffffff;
            --ink-black: #111827;
            --ink-dark: #1f2937;
            --ink-muted: #4b5563;
            --ink-light: #6b7280;
            --newspaper-navy: #0b2545;
            --newspaper-blue: #134074;
            --accent-red: #c1121f;
            --border-line: #d1d5db;
            --border-light: #e5e7eb;
            --border-double: 3px double #111827;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--paper-bg);
            color: var(--ink-black);
            font-family: 'Public Sans', -apple-system, sans-serif;
            line-height: 1.6;
        }}

        /* Top Info Bar */
        .top-masthead-bar {{
            background: #0b1a30;
            color: #d1d5db;
            font-size: 12px;
            padding: 7px 16px;
            border-bottom: 1px solid #1f2937;
        }}
        .top-bar-inner {{
            max-width: 1240px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .top-bar-left span, .top-bar-right span {{ margin-right: 14px; }}
        .rss-badge-link {{
            background: #e65100;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: bold;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}

        /* Newspaper Header / Masthead */
        .newspaper-header {{
            max-width: 1240px;
            margin: 0 auto;
            padding: 24px 16px 12px;
            text-align: center;
        }}
        .newspaper-motto {{
            font-family: 'Merriweather', serif;
            font-style: italic;
            font-size: 13px;
            color: var(--ink-muted);
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .newspaper-logo {{
            font-family: 'Playfair Display', 'Cinzel', serif;
            font-size: clamp(2.4rem, 6vw, 4.2rem);
            font-weight: 900;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: var(--newspaper-navy);
            margin: 4px 0;
            line-height: 1.1;
        }}
        .newspaper-sub-logo {{
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--newspaper-blue);
            margin-bottom: 16px;
        }}
        .masthead-divider {{
            border-top: 1px solid var(--ink-black);
            border-bottom: 3px solid var(--ink-black);
            height: 4px;
            margin: 12px 0 16px;
        }}

        /* Breaking News Ticker */
        .breaking-ticker-wrap {{
            max-width: 1240px;
            margin: 0 auto 16px;
            padding: 0 16px;
        }}
        .breaking-ticker {{
            display: flex;
            align-items: center;
            background: #fff;
            border: 1px solid var(--border-line);
            border-left: 5px solid var(--accent-red);
            border-radius: 4px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }}
        .ticker-label {{
            background: var(--accent-red);
            color: white;
            font-weight: 800;
            font-size: 11px;
            padding: 8px 14px;
            letter-spacing: 1px;
            white-space: nowrap;
        }}
        .ticker-marquee {{
            flex: 1;
            overflow: hidden;
            white-space: nowrap;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: 500;
        }}
        .ticker-item {{
            margin-right: 32px;
            cursor: pointer;
            color: var(--ink-dark);
            text-decoration: none;
        }}
        .ticker-item:hover {{ color: var(--accent-red); text-decoration: underline; }}

        /* Navigation Bar */
        .category-nav-bar {{
            max-width: 1240px;
            margin: 0 auto 24px;
            padding: 0 16px;
        }}
        .nav-inner {{
            background: white;
            border: 1px solid var(--border-line);
            border-radius: 6px;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .category-pills {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .cat-btn {{
            background: transparent;
            border: 1px solid transparent;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 600;
            color: var(--ink-dark);
            cursor: pointer;
            transition: all 0.15s;
        }}
        .cat-btn:hover, .cat-btn.active {{
            background: var(--newspaper-navy);
            color: white;
        }}
        .search-box {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .search-box input {{
            padding: 6px 12px;
            border: 1px solid var(--border-line);
            border-radius: 4px;
            font-size: 13px;
            width: 220px;
        }}

        /* Main Container */
        .portal-layout {{
            max-width: 1240px;
            margin: 0 auto;
            padding: 0 16px;
        }}

        /* Hero / Main Headline */
        .main-headline-banner {{
            display: grid;
            grid-template-columns: 1.15fr 1fr;
            background: white;
            border: 1px solid var(--border-line);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 28px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .main-headline-banner:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.09);
        }}
        .hero-image-col {{
            background-size: cover;
            background-position: center;
            min-height: 380px;
            position: relative;
        }}
        .hero-image-overlay {{
            position: absolute;
            bottom: 12px;
            left: 12px;
        }}
        .hero-category-tag {{
            background: var(--accent-red);
            color: white;
            font-size: 11px;
            font-weight: 800;
            padding: 5px 12px;
            border-radius: 3px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .hero-content-col {{
            padding: 32px 36px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .hero-meta {{
            font-size: 12px;
            color: var(--ink-light);
            margin-bottom: 12px;
            font-weight: 500;
        }}
        .hero-title {{
            font-family: 'Playfair Display', 'Merriweather', serif;
            font-size: clamp(1.4rem, 2.5vw, 2rem);
            font-weight: 800;
            line-height: 1.3;
            color: var(--ink-black);
            margin-bottom: 8px;
        }}
        .hero-title-en {{
            font-size: 12px;
            color: var(--ink-light);
            font-style: italic;
            margin-bottom: 16px;
        }}
        .hero-summary {{
            font-family: 'Merriweather', serif;
            font-size: 14.5px;
            color: var(--ink-dark);
            line-height: 1.65;
            margin-bottom: 24px;
        }}
        .hero-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            border-top: 1px solid var(--border-light);
            padding-top: 16px;
        }}
        .btn-hero-read {{
            background: var(--newspaper-navy);
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: 700;
            border-radius: 4px;
            cursor: pointer;
        }}
        .hero-hint {{
            font-size: 11.5px;
            color: var(--ink-light);
        }}

        /* Secondary Headlines Row */
        .sub-headlines-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 18px;
            margin-bottom: 36px;
        }}
        .sub-headline-card {{
            background: white;
            border: 1px solid var(--border-line);
            border-radius: 6px;
            overflow: hidden;
            display: flex;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        }}
        .sub-headline-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        }}
        .sub-headline-img {{
            width: 140px;
            min-width: 140px;
            background-size: cover;
            background-position: center;
            position: relative;
        }}
        .sub-headline-content {{
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .news-badge {{
            position: absolute;
            top: 8px;
            left: 8px;
            background: rgba(11, 37, 69, 0.9);
            color: white;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
        }}
        .news-date {{
            font-size: 11px;
            color: var(--ink-light);
            margin-bottom: 4px;
        }}
        .sub-headline-content h4 {{
            font-family: 'Merriweather', serif;
            font-size: 14px;
            font-weight: 700;
            line-height: 1.35;
            color: var(--ink-black);
            margin-bottom: 6px;
        }}
        .sub-headline-content p {{
            font-size: 12px;
            color: var(--ink-muted);
            line-height: 1.4;
        }}

        /* 2-Column Newspaper Section */
        .newspaper-columns {{
            display: grid;
            grid-template-columns: 2.3fr 1fr;
            gap: 28px;
        }}

        /* Section Headings */
        .section-headline {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2px solid var(--newspaper-navy);
            padding-bottom: 8px;
            margin-bottom: 20px;
        }}
        .section-headline h3 {{
            font-family: 'Playfair Display', serif;
            font-size: 1.35rem;
            color: var(--newspaper-navy);
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-headline span {{
            font-size: 12px;
            color: var(--ink-light);
        }}

        /* Article Cards Grid */
        .articles-news-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .news-grid-card {{
            background: white;
            border: 1px solid var(--border-line);
            border-radius: 6px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            transition: all 0.2s;
        }}
        .news-grid-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 18px rgba(0,0,0,0.07);
        }}
        .card-img-wrap {{
            height: 170px;
            background-size: cover;
            background-position: center;
            position: relative;
            cursor: pointer;
        }}
        .card-body {{
            padding: 16px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }}
        .card-meta {{
            font-size: 11px;
            color: var(--ink-light);
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .card-title {{
            font-family: 'Merriweather', serif;
            font-size: 15px;
            font-weight: 700;
            line-height: 1.4;
            color: var(--ink-black);
            margin-bottom: 4px;
            cursor: pointer;
        }}
        .card-title:hover {{
            color: var(--newspaper-blue);
        }}
        .card-title-en {{
            font-size: 11px;
            color: var(--ink-light);
            font-style: italic;
            margin-bottom: 10px;
            line-height: 1.3;
        }}
        .card-excerpt {{
            font-size: 12.5px;
            color: var(--ink-muted);
            line-height: 1.55;
            margin-bottom: 16px;
            flex-grow: 1;
        }}
        .card-action-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-light);
            padding-top: 10px;
            margin-top: auto;
        }}
        .btn-read-more {{
            background: none;
            border: none;
            color: var(--newspaper-blue);
            font-weight: 700;
            font-size: 12px;
            cursor: pointer;
            padding: 0;
        }}
        .btn-read-more:hover {{ text-decoration: underline; }}
        .link-original {{
            font-size: 11.5px;
            color: var(--ink-light);
            text-decoration: none;
        }}
        .link-original:hover {{ color: var(--ink-black); text-decoration: underline; }}

        /* Sidebar Cards */
        .sidebar-card {{
            background: white;
            border: 1px solid var(--border-line);
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        }}
        .sidebar-title {{
            font-family: 'Playfair Display', serif;
            font-size: 1.15rem;
            color: var(--newspaper-navy);
            border-bottom: 2px solid var(--newspaper-navy);
            padding-bottom: 6px;
            margin-bottom: 14px;
        }}
        .editorial-quote {{
            font-family: 'Merriweather', serif;
            font-size: 13.5px;
            font-style: italic;
            color: var(--ink-dark);
            border-left: 3px solid var(--newspaper-navy);
            padding-left: 12px;
            margin-bottom: 12px;
            line-height: 1.6;
        }}
        .editorial-author {{
            font-size: 12px;
            font-weight: 700;
            color: var(--ink-muted);
            text-align: right;
        }}

        /* Data stats infographic */
        .stat-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-light);
            font-size: 13px;
        }}
        .stat-value {{
            font-weight: 800;
            color: var(--newspaper-navy);
            font-size: 15px;
        }}

        /* RSS box in sidebar */
        .sidebar-rss-box {{
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 6px;
            padding: 16px;
            text-align: center;
        }}
        .rss-url-display {{
            background: white;
            border: 1px solid #86efac;
            padding: 6px 10px;
            font-family: monospace;
            font-size: 11px;
            border-radius: 4px;
            margin: 8px 0;
            word-break: break-all;
        }}
        .btn-copy-rss {{
            background: #16a34a;
            color: white;
            border: none;
            padding: 8px 14px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
        }}
        .btn-copy-rss:hover {{ background: #15803d; }}

        /* Modal / Article Reading Window */
        .modal-backdrop {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(11, 26, 48, 0.7);
            backdrop-filter: blur(4px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            padding: 20px;
        }}
        .modal-window {{
            background: #ffffff;
            width: 100%;
            max-width: 820px;
            max-height: 90vh;
            border-radius: 8px;
            overflow-y: auto;
            border: 1px solid var(--border-line);
            box-shadow: 0 20px 40px rgba(0,0,0,0.25);
            display: flex;
            flex-direction: column;
        }}
        .modal-header {{
            padding: 16px 24px;
            background: #f8fafc;
            border-bottom: 1px solid var(--border-line);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .modal-header span {{ font-weight: 700; font-size: 13px; color: var(--newspaper-navy); }}
        .btn-close-modal {{
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--ink-muted);
        }}
        .modal-body {{
            padding: 32px 36px;
        }}
        .modal-category-tag {{
            background: var(--newspaper-navy);
            color: white;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 3px;
            text-transform: uppercase;
            display: inline-block;
            margin-bottom: 12px;
        }}
        .modal-title-tr {{
            font-family: 'Playfair Display', serif;
            font-size: 1.85rem;
            font-weight: 800;
            line-height: 1.3;
            color: var(--ink-black);
            margin-bottom: 8px;
        }}
        .modal-title-en {{
            font-size: 13px;
            color: var(--ink-light);
            font-style: italic;
            margin-bottom: 18px;
        }}
        .modal-meta-bar {{
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--ink-muted);
            border-top: 1px solid var(--border-light);
            border-bottom: 1px solid var(--border-light);
            padding: 10px 0;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}
        .modal-img {{
            width: 100%;
            max-height: 380px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 24px;
        }}
        .modal-text {{
            font-family: 'Merriweather', serif;
            font-size: 15.5px;
            color: #262626;
            line-height: 1.8;
            margin-bottom: 30px;
        }}
        .modal-footer {{
            border-top: 1px solid var(--border-line);
            padding: 16px 24px;
            background: #f8fafc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .btn-doi-link {{
            background: var(--newspaper-navy);
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 700;
            font-size: 13px;
        }}
        .btn-doi-link:hover {{ background: var(--newspaper-blue); }}

        /* Footer */
        .newspaper-footer {{
            border-top: 3px solid var(--newspaper-navy);
            background: #0b1a30;
            color: #9ca3af;
            padding: 40px 16px;
            margin-top: 60px;
        }}
        .footer-inner {{
            max-width: 1240px;
            margin: 0 auto;
            text-align: center;
            font-size: 13px;
        }}
        .footer-inner h4 {{
            font-family: 'Playfair Display', serif;
            color: white;
            font-size: 1.4rem;
            margin-bottom: 8px;
        }}
        .footer-inner p {{ margin-bottom: 12px; }}

        /* Responsive */
        @media (max-width: 900px) {{
            .main-headline-banner {{ grid-template-columns: 1fr; }}
            .newspaper-columns {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>

    <!-- Top Bar -->
    <div class="top-masthead-bar">
        <div class="top-bar-inner">
            <div class="top-bar-left">
                <span>🗓️ {today_str}</span>
                <span>💧 Türkiye Su Stresi: %64.2</span>
                <span>📰 Günlük Bilimsel Bülten</span>
            </div>
            <div class="top-bar-right">
                <a href="{rss_url}" target="_blank" class="rss-badge-link">
                    📡 Sabit RSS Yayını (XML)
                </a>
            </div>
        </div>
    </div>

    <!-- Masthead -->
    <header class="newspaper-header">
        <div class="newspaper-motto">"Geleceğin dünyasında en stratejik güç sudur."</div>
        <h1 class="newspaper-logo">SU HABER BÜLTENİ</h1>
        <div class="newspaper-sub-logo">Türkiye ve Dünya Su, Sulama ve Çevre Araştırmaları Gazetesi</div>
        <div class="masthead-divider"></div>
    </header>

    <!-- Breaking News Ticker -->
    <div class="breaking-ticker-wrap">
        <div class="breaking-ticker">
            <div class="ticker-label">SON DAKİKA</div>
            <div class="ticker-marquee">
                {ticker_items}
            </div>
        </div>
    </div>

    <!-- Category Nav Bar -->
    <nav class="category-nav-bar">
        <div class="nav-inner">
            <div class="category-pills">
                <button class="cat-btn active" onclick="filterCategory('Tümü')">Tümü</button>
                <button class="cat-btn" onclick="filterCategory('Tarımsal Sulama')">🌾 Tarımsal Sulama</button>
                <button class="cat-btn" onclick="filterCategory('Su Teknolojileri')">🔬 Su Teknolojileri</button>
                <button class="cat-btn" onclick="filterCategory('Su Kaynakları')">💧 Su Kaynakları</button>
                <button class="cat-btn" onclick="filterCategory('İklim & Kuraklık')">🌍 İklim & Kuraklık</button>
                <button class="cat-btn" onclick="filterCategory('Su Politikaları')">⚖️ Su Politikaları</button>
            </div>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Başlıklarda ara..." onkeyup="filterSearch()">
            </div>
        </div>
    </nav>

    <!-- Main Layout -->
    <main class="portal-layout">
        
        <!-- Hero / Gunun Manseti -->
        {hero_html}

        <!-- Sub Headlines (Surmansetler) -->
        <section class="sub-headlines-grid">
            {secondary_html}
        </section>

        <!-- Columns Section -->
        <div class="newspaper-columns">
            
            <!-- Left Main Column: News Grid -->
            <div class="main-articles-col">
                <div class="section-headline">
                    <h3>🌊 Bilimsel Araştırmalar &amp; Son Raporlar</h3>
                    <span>Toplam <strong>{len(items)}</strong> makale</span>
                </div>
                
                <div class="articles-news-grid" id="newsGrid">
                    {grid_html}
                </div>
            </div>

            <!-- Right Sidebar: Editorial & Infographics -->
            <aside class="newspaper-sidebar">
                
                <!-- Editorial Box -->
                <div class="sidebar-card">
                    <h4 class="sidebar-title">Günün Başyazısı</h4>
                    <div class="editorial-quote">
                        "Tarımsal sulamada yapılacak her yüzde 10'luk verimlilik artışı, metropollerin yıllık içme suyu ihtiyacının tamamını karşılayabilecek ölçektedir. Akıllı sensörler ve damla sulama bir tercih değil, milli bir zorunluluktur."
                    </div>
                    <div class="editorial-author">&mdash; Su Haber Bülteni Editör Masası</div>
                </div>

                <!-- Water Stats Infographic -->
                <div class="sidebar-card">
                    <h4 class="sidebar-title">Rakamlarla Su Durumu</h4>
                    <div class="stat-row">
                        <span>Tarımsal Su Kullanım Payı</span>
                        <span class="stat-value">%73</span>
                    </div>
                    <div class="stat-row">
                        <span>Damla Sulamada Tasarruf</span>
                        <span class="stat-value">+%45</span>
                    </div>
                    <div class="stat-row">
                        <span>Kuraklık Tehdidi Altındaki Nüfus</span>
                        <span class="stat-value">2.3 Milyar</span>
                    </div>
                    <div class="stat-row">
                        <span>Yıllık Geri Dönüşüm Hedefi</span>
                        <span class="stat-value">%25 Artış</span>
                    </div>
                </div>

                <!-- Live RSS Subscription Card -->
                <div class="sidebar-card sidebar-rss-box">
                    <h4 style="color:#166534; font-size:15px; margin-bottom:6px;">📡 Sabit RSS Kaynağınız</h4>
                    <p style="font-size:12px; color:#14532d;">Feedly, Inoreader, Outlook veya istediğiniz okuyucuya doğrudan ekleyin:</p>
                    <div class="rss-url-display" id="sidebarRssUrl">{rss_url}</div>
                    <button class="btn-copy-rss" onclick="navigator.clipboard.writeText(document.getElementById('sidebarRssUrl').innerText); alert('Sabit RSS linki kopyalandı!');">
                        📋 RSS Linkini Kopyala
                    </button>
                    <div style="margin-top:10px; font-size:11px; color:#15803d;">
                        <a href="{atom_url}" target="_blank" style="color:#15803d; font-weight:bold;">Atom 1.0</a> &bull; 
                        <a href="{json_url}" target="_blank" style="color:#15803d; font-weight:bold;">JSON Feed</a>
                    </div>
                </div>

                <!-- Scientific Sources -->
                <div class="sidebar-card">
                    <h4 class="sidebar-title">Taranan Bilimsel Kaynaklar</h4>
                    <ul style="font-size:12px; color:var(--ink-muted); padding-left:18px; line-height:1.8;">
                        <li>ScienceDirect: Agricultural Water Management</li>
                        <li>ASCE: Journal of Water Resources Planning</li>
                        <li>IWMI: International Water Management Institute</li>
                        <li>Limnologica: Ecology of Inland Waters</li>
                        <li>Water Finance &amp; Management Bülteni</li>
                    </ul>
                </div>

            </aside>
        </div>

    </main>

    <!-- Reading Modal -->
    <div class="modal-backdrop" id="articleModal" onclick="closeArticleModal(event)">
        <div class="modal-window" onclick="event.stopPropagation()">
            <div class="modal-header">
                <span id="modalHeaderCategory">BİLİMSEL YAYIN &bull; SU HABER BÜLTENİ</span>
                <button class="btn-close-modal" onclick="closeArticleModal()">&times;</button>
            </div>
            <div class="modal-body">
                <span class="modal-category-tag" id="modalBadge">Kategori</span>
                <h2 class="modal-title-tr" id="modalTitleTr">Türkçe Başlık</h2>
                <h4 class="modal-title-en" id="modalTitleEn">Orijinal Başlık</h4>
                
                <div class="modal-meta-bar">
                    <span id="modalDate">📅 Tarih</span>
                    <span id="modalSource">🏛️ Kaynak</span>
                    <span id="modalAuthor">✍️ Yazar</span>
                </div>

                <img src="" id="modalImg" class="modal-img" alt="Haber Görseli">

                <div class="modal-text" id="modalContent">
                    Haber içeriği yükleniyor...
                </div>
            </div>
            <div class="modal-footer">
                <button class="cat-btn" onclick="window.print()">🖨️ Sayfayı Yazdır</button>
                <a href="#" id="modalDoiLink" target="_blank" rel="noopener noreferrer" class="btn-doi-link">
                    Orijinal Akademik Makaleyi Aç (DOI) &rarr;
                </a>
            </div>
        </div>
    </div>

    <!-- Newspaper Footer -->
    <footer class="newspaper-footer">
        <div class="footer-inner">
            <h4>SU HABER BÜLTENİ</h4>
            <p>Akademik araştırmalar, hakemli dergiler ve küresel su kurumlarından derlenen günlük dijital su gazetesi.</p>
            <p style="font-size:11.5px; opacity:0.75;">
                Otomasyon: GitHub Actions ile 30 dakikada bir güncellenir &bull; Son Güncelleme: {last_updated} &bull; Depo: mserman90/inoreader-rss-bridge
            </p>
        </div>
    </footer>

    <!-- Interactive Scripts -->
    <script>
        const articlesData = {json_portal_data};

        function openArticleModal(id) {{
            const it = articlesData.find(a => a.id === id);
            if (!it) return;

            document.getElementById('modalBadge').innerText = it.category;
            document.getElementById('modalHeaderCategory').innerText = it.category.toUpperCase() + ' &bull; SU HABER BÜLTENİ';
            document.getElementById('modalTitleTr').innerText = it.title_tr;
            document.getElementById('modalTitleEn').innerText = 'Orijinal: ' + it.title_en;
            document.getElementById('modalDate').innerText = '📅 ' + it.date;
            document.getElementById('modalSource').innerText = '🏛️ ' + it.source;
            document.getElementById('modalAuthor').innerText = it.author ? '✍️ ' + it.author : '✍️ Akademik Kurul';
            
            const imgEl = document.getElementById('modalImg');
            if (it.image) {{
                imgEl.src = it.image;
                imgEl.style.display = 'block';
            }} else {{
                imgEl.style.display = 'none';
            }}

            document.getElementById('modalContent').innerHTML = '<p>' + it.summary_tr.replace(/\\n/g, '</p><p>') + '</p>';
            document.getElementById('modalDoiLink').href = it.link;

            const modal = document.getElementById('articleModal');
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }}

        function closeArticleModal(e) {{
            const modal = document.getElementById('articleModal');
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeArticleModal();
        }});

        function filterCategory(cat) {{
            document.querySelectorAll('.cat-btn').forEach(btn => {{
                if (btn.innerText.includes(cat) || (cat === 'Tümü' && btn.innerText === 'Tümü')) {{
                    btn.classList.add('active');
                }} else {{
                    btn.classList.remove('active');
                }}
            }});

            const cards = document.querySelectorAll('.news-grid-card');
            cards.forEach(c => {{
                if (cat === 'Tümü' || c.getAttribute('data-category').includes(cat)) {{
                    c.style.display = '';
                }} else {{
                    c.style.display = 'none';
                }}
            }});
        }}

        function filterSearch() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.news-grid-card');
            cards.forEach(c => {{
                const title = c.getAttribute('data-title');
                if (title.indexOf(query) > -1) {{
                    c.style.display = '';
                }} else {{
                    c.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""
