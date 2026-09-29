import urllib.parse
import requests
import re
import html
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

logger = logging.getLogger("translator")

# In-memory translation cache for the run
_TRANS_CACHE: Dict[str, str] = {}

def translate_single_text(text: str, timeout: int = 5) -> str:
    if not text or not text.strip():
        return ""

    clean_text = text.strip()
    if clean_text in _TRANS_CACHE:
        return _TRANS_CACHE[clean_text]

    snippet = clean_text[:350]

    # Try MyMemory API
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(snippet)}&langpair=en|tr"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            trans = data.get("responseData", {}).get("translatedText")
            if trans and not trans.startswith("MYMEMORY WARNING"):
                res = html.unescape(trans).strip()
                _TRANS_CACHE[clean_text] = res
                return res
    except Exception as e:
        logger.debug("MyMemory translation failed: %s", e)

    # Fallback to original text
    _TRANS_CACHE[clean_text] = clean_text
    return clean_text

def translate_to_turkish(text: str) -> str:
    return translate_single_text(text)

def categorize_article(title: str, text: str = "") -> str:
    """
    Assigns a Turkish category based on water terminology keywords with regex word boundaries.
    """
    combined = (title + " " + (text or "")).lower()
    t_lower = (title or "").lower()

    # 1. Tarımsal Sulama
    if re.search(r'\b(irrigat\w*|drip|sprinkler|crop\w*|alfalfa|maize|agri\w*|farm\w*|sulama|tar[ıi]m)\b', t_lower) or \
       re.search(r'\b(irrigat\w*|drip|sprinkler|crop\w*|alfalfa|maize|agri\w*|farm\w*|sulama|tar[ıi]m)\b', combined):
        return "Tarımsal Sulama"

    # 2. İklim & Kuraklık
    if re.search(r'\b(drought\w*|climate|scarcity|cmip\d*|precipitat\w*|flood\w*|rainfall|kurakl[ıi]k|iklim|sel|ta[şs]k[ıi]n)\b', t_lower) or \
       re.search(r'\b(drought\w*|climate|scarcity|cmip\d*|precipitat\w*|flood\w*|rainfall|kurakl[ıi]k|iklim|sel|ta[şs]k[ıi]n)\b', combined):
        return "İklim & Kuraklık"

    # 3. Su Politikaları
    if re.search(r'\b(govern\w*|polic\w*|gender|rights|law|sdg\w*|institut\w*|y[öo]neti[şs]im|politika|haklar|mevzuat)\b', t_lower) or \
       re.search(r'\b(govern\w*|polic\w*|gender|rights|law|sdg\w*|institut\w*|y[öo]neti[şs]im|politika|haklar|mevzuat)\b', combined):
        return "Su Politikaları"

    # 4. Su Teknolojileri (and Arıtma / Kalite)
    if re.search(r'\b(leak\w*|pipe\w*|sensor\w*|cnn|lstm|algorithm\w*|digital\w*|forecast\w*|xai|tespit|yapay zeka|tech\w*|smart|treat\w*|contamin\w*|pollut\w*|wastewater|reuse|ar[ıi]tma)\b', t_lower) or \
       re.search(r'\b(leak\w*|pipe\w*|sensor\w*|cnn|lstm|algorithm\w*|digital\w*|forecast\w*|xai|tespit|yapay zeka|tech\w*|smart|treat\w*|contamin\w*|pollut\w*|wastewater|reuse|ar[ıi]tma)\b', combined):
        return "Su Teknolojileri"

    # 5. Su Kaynakları (fallback)
    return "Su Kaynakları"

def batch_translate_articles(items: List[Dict]) -> List[Dict]:
    """
    Translates titles and creates Turkish editorial summaries in parallel using a thread pool.
    """
    items_to_translate = [it for it in items if not it.get("title_tr")]
    if not items_to_translate:
        return items

    print(f"[*] {len(items_to_translate)} makale başlığı paralel olarak Türkçe'ye çevriliyor...")

    def do_translate(it):
        guid = it["guid"]
        title_en = it["title"]
        category = categorize_article(title_en, it.get("description", ""))
        
        # Translate title
        title_tr = translate_single_text(title_en)
        
        # Clean summary & translate
        clean_desc = re.sub(r'<[^>]+>', ' ', it.get("description", ""))
        clean_desc = " ".join(clean_desc.split())
        
        summary_tr = ""
        if clean_desc:
            # First 200 chars of summary
            summary_tr = translate_single_text(clean_desc[:220])
        if not summary_tr or summary_tr == clean_desc[:220]:
            summary_tr = f"{title_tr}. Bu araştırma {it.get('source_feed', 'ilgili akademik kaynak')} bünyesinde yayımlanmış olup su yönetimi ve teknik bulguları incelemektedir."

        return guid, title_tr, summary_tr, category

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(do_translate, it): it for it in items_to_translate}
        for future in as_completed(futures):
            try:
                guid, title_tr, summary_tr, category = future.result()
                for it in items:
                    if it["guid"] == guid:
                        it["title_tr"] = title_tr
                        it["summary_tr"] = summary_tr
                        it["category_tr"] = category
                        break
            except Exception as e:
                logger.error("Parallel translation error: %s", e)

    return items
