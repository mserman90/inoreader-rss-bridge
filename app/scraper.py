import re
import html
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
import email.utils
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("inoreader_scraper")

def decode_cf_email(cf_hex: str) -> str:
    """Decodes Cloudflare obfuscated email addresses."""
    try:
        k = int(cf_hex[:2], 16)
        return "".join(chr(int(cf_hex[i:i+2], 16) ^ k) for i in range(2, len(cf_hex), 2))
    except Exception:
        return ""

def clean_cf_emails_in_soup(soup: BeautifulSoup):
    """Finds all Cloudflare email-protected tags and replaces them with clean email strings."""
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        email_str = decode_cf_email(tag["data-cfemail"])
        if email_str:
            tag.replace_with(email_str)

def parse_inoreader_date(date_str: str, base_time: Optional[datetime] = None) -> Tuple[datetime, int, str]:
    """
    Parses Inoreader relative or absolute short date strings.
    Returns: (datetime_utc, timestamp_int, rfc822_str)
    """
    if base_time is None:
        base_time = datetime.now(timezone.utc)
    elif base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    if not date_str:
        rfc = email.utils.format_datetime(base_time)
        return base_time, int(base_time.timestamp()), rfc

    s = date_str.strip()

    # Relative formats: 10s, 30m, 19h, 2d, 1w
    rel_match = re.match(r"^(\d+)\s*([smhdw])$", s, re.IGNORECASE)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit == 's':
            dt = base_time - timedelta(seconds=val)
        elif unit == 'm':
            dt = base_time - timedelta(minutes=val)
        elif unit == 'h':
            dt = base_time - timedelta(hours=val)
        elif unit == 'd':
            dt = base_time - timedelta(days=val)
        elif unit == 'w':
            dt = base_time - timedelta(weeks=val)
        else:
            dt = base_time
        rfc = email.utils.format_datetime(dt)
        return dt, int(dt.timestamp()), rfc

    if s.lower() in ("now", "just now", "şu anda"):
        rfc = email.utils.format_datetime(base_time)
        return base_time, int(base_time.timestamp()), rfc

    # Absolute formats with explicit year: "Sep 27, 2026", "27 Sep 2026"
    for fmt in ("%b %d, %Y", "%b %d %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            rfc = email.utils.format_datetime(dt)
            return dt, int(dt.timestamp()), rfc
        except ValueError:
            pass

    # Absolute formats without year: "Sep 27", "27 Sep"
    # To prevent Python 3.13 deprecation warnings, prepend year explicitly
    current_year = base_time.year
    for fmt, with_year_fmt in (("%b %d", "%Y %b %d"), ("%d %b", "%Y %d %b")):
        try:
            dt = datetime.strptime(f"{current_year} {s}", with_year_fmt).replace(tzinfo=timezone.utc)
            # If the calculated date is in the future compared to base_time + 1 day, it belongs to previous year
            if dt > base_time + timedelta(days=1):
                dt = dt.replace(year=current_year - 1)
            rfc = email.utils.format_datetime(dt)
            return dt, int(dt.timestamp()), rfc
        except ValueError:
            pass

    # Fallback to base_time
    rfc = email.utils.format_datetime(base_time)
    return base_time, int(base_time.timestamp()), rfc


def scrape_inoreader(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Scrapes the Inoreader stream HTML page and extracts feed metadata and articles.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    logger.info("Inoreader URL çekiliyor: %s", url)
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    # Inoreader returns UTF-8 HTML
    response.encoding = "utf-8"
    html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")
    clean_cf_emails_in_soup(soup)

    # Extract Feed Title & Header info
    header_el = soup.find("div", class_="header")
    feed_title = "SU - Inoreader"
    feed_subtitle = ""

    if header_el:
        htext = header_el.find("div", class_="header_text")
        if htext:
            # First text node is the title (e.g. "SU")
            feed_title = htext.contents[0].strip() if htext.contents else "SU"
            span = htext.find("span")
            if span:
                feed_subtitle = span.get_text(" ", strip=True)
    elif soup.title:
        feed_title = soup.title.get_text(strip=True)

    # Find articles container
    body_container = soup.find(id="snip_body") or soup.find("div", class_="body")
    if not body_container:
        body_container = soup.body

    items: List[Dict[str, Any]] = []
    base_time = datetime.now(timezone.utc)

    # Find article wrappers inside body container
    wrappers = body_container.find_all("div", class_="article_magazine_content_wraper")

    for art in wrappers:
        # Ignore body tag if it happens to have that class
        if art.name == "body":
            continue

        title_link_el = art.find("a", class_="article_magazine_title_link")
        if not title_link_el:
            # Might be picture wrapper or continuation div
            continue

        title = title_link_el.get_text(strip=True)
        link = title_link_el.get("href", "").strip()
        raw_id = title_link_el.get("id", "").strip()

        # Stable GUID
        if raw_id:
            guid = f"inoreader:{raw_id}"
        elif link:
            guid = link
        else:
            continue

        # Author & Source Feed
        author_el = art.find("div", class_="article_author")
        author_text = ""
        source_feed = ""
        if author_el:
            feed_link_el = author_el.find("a", class_="feed_link")
            if feed_link_el:
                source_feed = feed_link_el.get_text(strip=True)
                # Remove "via <feed_link>" from author text
                author_text = author_el.get_text(" ", strip=True)
            else:
                author_text = author_el.get_text(" ", strip=True)

        # Content / Summary
        content_el = art.find("div", class_="article_magazine_content")
        description_text = ""
        if content_el:
            description_text = content_el.get_text(" ", strip=True)

        # Date
        date_el = art.find("div", class_="article_date_short")
        raw_date_str = date_el.get_text(strip=True) if date_el else ""
        dt_val, pub_ts, pub_rfc = parse_inoreader_date(raw_date_str, base_time)

        # Image extraction
        image_url = ""
        pic_div = art.find("div", class_="article_magazine_picture")
        if pic_div:
            style = pic_div.get("style", "")
            img_match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style)
            if img_match:
                image_url = img_match.group(1).strip()
        if not image_url:
            img_tag = art.find("img")
            if img_tag and img_tag.get("src"):
                src = img_tag["src"]
                if not src.endswith("circle_icon_logo.svg"):
                    image_url = src

        if image_url:
            try:
                from app.image_enricher import unwrap_inoreader_camo
                unwrapped = unwrap_inoreader_camo(image_url)
                if unwrapped:
                    image_url = unwrapped
            except Exception:
                pass

        # Build clean HTML description for RSS readers
        desc_parts = []
        if image_url:
            desc_parts.append(f'<p><img src="{html.escape(image_url)}" alt="{html.escape(title)}" style="max-width:100%; border-radius:6px;" /></p>')
        if source_feed:
            desc_parts.append(f'<p><strong>Kaynak:</strong> {html.escape(source_feed)}</p>')
        if author_text:
            desc_parts.append(f'<p><strong>Yazar / Detay:</strong> {html.escape(author_text)}</p>')
        if description_text:
            desc_parts.append(f'<p>{html.escape(description_text)}</p>')
        desc_parts.append(f'<p><a href="{html.escape(link)}" target="_blank" rel="noopener noreferrer">Makaleyi Oku &rarr;</a></p>')

        full_html_description = "\n".join(desc_parts)

        items.append({
            "guid": guid,
            "title": title,
            "link": link,
            "author": author_text,
            "source_feed": source_feed,
            "description": full_html_description,
            "image_url": image_url,
            "pub_date": pub_rfc,
            "pub_date_ts": pub_ts,
            "raw_date_str": raw_date_str,
        })

    # Pagination link if present
    continuation_token = None
    cont_a = soup.find("div", class_="continuation_div")
    if cont_a and cont_a.find("a"):
        href = cont_a.find("a").get("href", "")
        c_match = re.search(r"[?&]c=([^&]+)", href)
        if c_match:
            continuation_token = c_match.group(1)

    return {
        "title": feed_title,
        "subtitle": feed_subtitle,
        "source_url": url,
        "items": items,
        "continuation_token": continuation_token,
        "fetched_at": base_time.isoformat(),
    }


def scrape_turkey_water_news(limit: int = 25) -> List[Dict[str, Any]]:
    """
    Fetches real-time Turkish water news from Google News RSS feed:
    DSİ projeleri, tarımsal sulama, baraj doluluk oranları, su yönetimi.
    """
    import xml.etree.ElementTree as ET
    url = "https://news.google.com/rss/search?q=tar%C4%B1msal+sulama+OR+baraj+doluluk+OR+DS%C4%B0+su+OR+%22su+y%C3%B6netimi%22+OR+%22su+verimlili%C4%9Fi%22&hl=tr&gl=TR&ceid=TR:tr"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
    }
    items: List[Dict[str, Any]] = []
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            now_dt = datetime.now(timezone.utc)
            for it in root.findall(".//item"):
                if len(items) >= limit:
                    break

                raw_title = it.find("title").text if it.find("title") is not None else ""
                link = it.find("link").text if it.find("link") is not None else ""
                pub_str = it.find("pubDate").text if it.find("pubDate") is not None else ""
                guid = it.find("guid").text if it.find("guid") is not None else link
                source_el = it.find("source")
                source_name = source_el.text if source_el is not None else "Türkiye Su Bülteni"

                # Filter out social media platforms
                combined_src = (link + " " + source_name).lower()
                if any(bad in combined_src for bad in ["instagram.com", "youtube.com", "tiktok.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "pinterest.com"]):
                    continue

                # Parse date
                pub_ts = int(now_dt.timestamp())
                pub_rfc = email.utils.format_datetime(now_dt)
                if pub_str:
                    try:
                        dt_parsed = email.utils.parsedate_to_datetime(pub_str)
                        pub_ts = int(dt_parsed.timestamp())
                        pub_rfc = email.utils.format_datetime(dt_parsed)
                    except Exception:
                        pass

                # Clean title (Google News appends "- SourceName" at the end)
                clean_title = raw_title
                if " - " in raw_title:
                    clean_title = raw_title.rsplit(" - ", 1)[0].strip()

                desc_el = it.find("description")
                raw_desc = desc_el.text if desc_el is not None else ""
                clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True) if raw_desc else clean_title

                items.append({
                    "guid": f"tr_water:{guid}",
                    "title": clean_title,
                    "title_tr": clean_title,
                    "link": link,
                    "author": source_name,
                    "source_feed": f"🇹🇷 {source_name}",
                    "description": clean_desc,
                    "summary_tr": clean_desc,
                    "category_tr": "Türkiye",
                    "is_turkey": 1,
                    "image_url": "",
                    "pub_date": pub_rfc,
                    "pub_date_ts": pub_ts,
                    "raw_date_str": pub_str,
                })
    except Exception as e:
        logger.warning("Turkey water news scrape failed: %s", e)

    return items
