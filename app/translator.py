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

# Known domain titles and overrides for clean academic translation
KNOWN_TITLES = {
    "Editorial Board": "Yayın ve Editörler Kurulu",
    "Reviewers": "Hakem ve Değerlendirme Kurulu",
    "Table of Contents": "İçindekiler",
    "COP31 UNFCCC": "COP31 BM İklim Değişikliği Konferansı (UNFCCC)",
    "World Soil Day 2026": "2026 Dünya Toprak Günü",
    "Auszubildende starten in ihre berufliche Zukunft": "Stajyer ve Çıraklar Mesleki Geleceklerine Başlıyor",
}

def is_already_turkish(text: str) -> bool:
    """Checks if text already contains Turkish-specific characters or common Turkish words."""
    if not text:
        return False
    # Turkish-unique letters: ç, ğ, ı, ö, ş, ü, Ç, Ğ, İ, Ö, Ş, Ü
    if re.search(r'[çğıöşüÇĞİÖŞÜ]', text):
        return True
    # Common Turkish words with word boundaries
    turkish_words = (
        r'\b(ve|ile|için|olan|bir|bu|şu|o|da|de|su|sulama|tarım|kuraklık|iklim|taşkın|sel|arıtma|'
        r'şebeke|yönetimi|analizi|araştırması|üzerine|etkileri|harcıyor|dolar|milyar|milyon|haber|'
        r'bülteni|türkiye|baraj|havza|nehir|göl|yağış|sıcaklık|proje|bakanlığı|genel|müdürlüğü|dsi|'
        r'tarımsal|çevre|rapor|verileri|yılı|gün|ay|yıl|nasıl|neden|kadar|yeni|büyük|son|sonra|'
        r'önce|olarak|göre|karşı|tarafından|çalışma|dünya|küresel|tasarruf|toprak|ürün)\b'
    )
    if re.search(turkish_words, text.lower()):
        return True
    return False

def detect_language(text: str) -> str:
    """Detects if input is likely German ('de') or other language ('autodetect')."""
    if not text:
        return "autodetect"
    t_lower = text.lower()
    german_indicators = [
        r'\b(der|die|das|und|von|aus|für|zur|beim|eine|einer|eines|auf|mit|des|den|dem|im|ist|nicht|über|durch|nach|wird|sind|vor|bei|vom|zum|einen|einem|ihre|ihren|ihrer)\b',
        r'\b(steb|dwa|dvgw|kläranlage|abwasser|hochwasser|wasserversorger|düngegesetz|klärgas|fachmagazin|auszubildende)\b'
    ]
    for pattern in german_indicators:
        if re.search(pattern, t_lower):
            return "de"
    return "autodetect"

def is_valid_translation(trans_text: str) -> bool:
    """Verifies that the translated text is not an API warning or error message."""
    if not trans_text or not trans_text.strip():
        return False
    upper = trans_text.upper()
    if "PLEASE SELECT" in upper or "MYMEMORY WARNING" in upper or "INVALID" in upper or "QUOTA EXCEEDED" in upper:
        return False
    return True

def translate_single_text(text: str, timeout: int = 8) -> str:
    if not text or not text.strip():
        return ""

    clean_text = text.strip()

    # 1. Zaten Türkçe ise ASLA çeviri API'sine gönderme! Doğrudan döndür.
    if is_already_turkish(clean_text):
        _TRANS_CACHE[clean_text] = clean_text
        return clean_text

    if clean_text in _TRANS_CACHE:
        return _TRANS_CACHE[clean_text]

    if clean_text in KNOWN_TITLES:
        _TRANS_CACHE[clean_text] = KNOWN_TITLES[clean_text]
        return KNOWN_TITLES[clean_text]

    snippet = clean_text[:400]
    detected = detect_language(snippet)
    langpair = f"{detected}|tr"

    # Try MyMemory API with user email parameter for maximum quota and high speed
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(snippet)}&langpair={langpair}&de=mserman90@gmail.com"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            trans = data.get("responseData", {}).get("translatedText")
            if is_valid_translation(trans):
                res = html.unescape(trans).strip().strip('"\'')
                _TRANS_CACHE[clean_text] = res
                return res
    except Exception as e:
        logger.debug("MyMemory translation error: %s", e)

    # Fallback to explicit de|tr or en|tr if autodetect did not succeed
    if detected == "autodetect":
        for fallback_lang in ["en", "de"]:
            try:
                url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(snippet)}&langpair={fallback_lang}|tr&de=mserman90@gmail.com"
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    trans = data.get("responseData", {}).get("translatedText")
                    if is_valid_translation(trans):
                        res = html.unescape(trans).strip().strip('"\'')
                        _TRANS_CACHE[clean_text] = res
                        return res
            except Exception:
                pass

    # Hiçbir çeviri yapılamadıysa veya hata döndüyse orijinal metni koru
    _TRANS_CACHE[clean_text] = clean_text
    return clean_text

def translate_to_turkish(text: str) -> str:
    return translate_single_text(text)

def categorize_article(title: str, text: str = "") -> str:
    """
    Assigns a Turkish category based on water terminology keywords
    in Turkish, English, and German with regex word boundaries.
    """
    combined = (title + " " + (text or "")).lower()
    t_lower = (title or "").lower()

    # 1. Tarımsal Sulama
    sulama_pattern = r'\b(irrigat\w*|drip|sprinkler|crop\w*|alfalfa|maize|agri\w*|farm\w*|sulama|tar[ıi]m|bewässer\w*|landwirt\w*|acker|pflanz\w*|ernte|dünge\w*)\b'
    if re.search(sulama_pattern, t_lower) or re.search(sulama_pattern, combined):
        return "Tarımsal Sulama"

    # 2. İklim & Kuraklık
    iklim_pattern = r'\b(drought\w*|climate|scarcity|cmip\d*|precipitat\w*|flood\w*|rainfall|kurakl[ıi]k|iklim|sel|ta[şs]k[ıi]n|hochwasser\w*|dürre\w*|klima\w*|niederschlag\w*|regen|wetter)\b'
    if re.search(iklim_pattern, t_lower) or re.search(iklim_pattern, combined):
        return "İklim & Kuraklık"

    # 3. Su Politikaları
    politika_pattern = r'\b(govern\w*|polic\w*|gender|rights|law|sdg\w*|institut\w*|y[öo]neti[şs]im|politika|haklar|mevzuat|yasa|tüzük|hukuk|kanun|invest\w*|bundestag|förder\w*|verband|richtlinie|versorger|preis\w*)\b'
    if re.search(politika_pattern, t_lower) or re.search(politika_pattern, combined):
        return "Su Politikaları"

    # 4. Su Teknolojileri (and Arıtma / Kalite)
    teknoloji_pattern = r'\b(leak\w*|pipe\w*|sensor\w*|cnn|lstm|algorithm\w*|digital\w*|forecast\w*|xai|tespit|yapay zeka|tech\w*|smart|treat\w*|contamin\w*|pollut\w*|wastewater|reuse|ar[ıi]tma|teknoloji|klär\w*|abwasser\w*|reinigung\w*|speicher\w*|gasspeicher|rohr\w*|netzwerk)\b'
    if re.search(teknoloji_pattern, t_lower) or re.search(teknoloji_pattern, combined):
        return "Su Teknolojileri"

    # 5. Su Kaynakları (fallback)
    return "Su Kaynakları"

def extract_real_body_text(description_html: str) -> str:
    """
    Extracts actual narrative/summary sentences from article description,
    skipping metadata paragraphs like 'Kaynak:', 'Yazar:', 'Publication date:'.
    """
    if not description_html:
        return ""
    paras = re.findall(r'<p>(.*?)</p>', description_html, re.DOTALL)
    real_paras = []
    for p in paras:
        clean = re.sub(r'<[^>]+>', ' ', p).strip()
        if not clean:
            continue
        # Skip metadata lines
        if re.match(r'^(Kaynak:|Yazar|Publication date|Source:|Author|\s*Makaleyi Oku|Journal of\b)', clean, re.IGNORECASE):
            continue
        if len(clean) > 25:
            real_paras.append(clean)
    return " ".join(real_paras)

def generate_turkish_editorial_summary(title_tr: str, category: str, source_feed: str, real_body_tr: str = "") -> str:
    """
    Generates a high-quality, informative Turkish news summary.
    If translated real body text exists, uses it; otherwise crafts a professional editorial summary.
    """
    if real_body_tr and len(real_body_tr) > 30 and not real_body_tr.lower().startswith("kaynak:"):
        return real_body_tr

    src = source_feed if source_feed else "akademik kaynak"
    
    if category == "Tarımsal Sulama":
        return f"{title_tr}. Bu bilimsel araştırma; tarımsal sulama verimliliği, su tasarruflu sulama sistemleri ve mahsul verimi üzerindeki etkileri kapsamlı saha ve modelleme analizleriyle incelemektedir. Detaylar {src} bünyesinde yayımlanmıştır."
    elif category == "Su Teknolojileri":
        return f"{title_tr}. Çalışma; su dağıtım şebekelerinde sızıntı tespiti, yapay zeka ve sensör algoritmaları, atık su arıtımı ve ileri su arıtma teknolojilerini konu almaktadır. Bulgular {src} bünyesinde yer almaktadır."
    elif category == "İklim & Kuraklık":
        return f"{title_tr}. Bu bilimsel araştırma; iklim değişikliğinin hidrolojik döngü üzerindeki etkilerini, kuraklık ve taşkın risklerini, iklim modelleri ve su güvenliği senaryolarını detaylandırmaktadır. Araştırma {src} kaynağından derlenmiştir."
    elif category == "Su Politikaları":
        return f"{title_tr}. Bu çalışma ve rapor; su kaynakları yönetişimi, su mevzuatı, sürdürülebilir kalkınma hedefleri ve kurumsal kapasite geliştirme stratejilerini ele almaktadır. Kaynak: {src}."
    else:  # Su Kaynakları
        return f"{title_tr}. Bu araştırma; su kaynaklarının sürdürülebilir yönetimi, nehir havzası planlaması ve hidrolojik dengelerin korunmasına yönelik teknik analizler ve bulgular içermektedir. Detaylar {src} yayınında yer almaktadır."

def needs_translation(it: Dict) -> bool:
    """Determines if an item requires translation or re-translation."""
    title = (it.get("title") or "").strip()
    title_tr = (it.get("title_tr") or "").strip()
    summary_tr = (it.get("summary_tr") or "").strip()
    
    # Bozuk / Hata mesajı içeren başlıklar kesinlikle düzeltilmeli
    if "PLEASE SELECT" in title_tr or "MYMEMORY" in title_tr or "PLEASE SELECT" in summary_tr:
        return True

    # Başlık zaten Türkçe ise asla çeviri servisine gönderilmemeli
    if is_already_turkish(title):
        if title_tr != title:
            return True
        if not summary_tr or summary_tr.lower().startswith("kaynak:"):
            return True
        return False
    
    if not title_tr:
        return True
    if title in KNOWN_TITLES and title_tr != KNOWN_TITLES[title]:
        return True
    if title_tr == title:
        # Check if title itself is foreign
        if not is_already_turkish(title):
            return True
    # If title_tr contains German words, re-translate
    if re.search(r'\b(der|die|das|und|aus|für|über|nach|beim|mit|von|des|den|dem|im|ist|wiedergewählt|schutzübung|auszubildende|berufliche|zukunft)\b', title_tr.lower()):
        return True
    # If summary_tr is missing or starts with metadata text
    if not summary_tr or summary_tr.lower().startswith("kaynak:"):
        return True
        
    return False

def batch_translate_articles(items: List[Dict]) -> List[Dict]:
    """
    Translates titles and creates Turkish editorial summaries in parallel using a thread pool.
    Re-translates any items that were previously untranslated or poorly formatted.
    """
    items_to_translate = [it for it in items if needs_translation(it)]
    if not items_to_translate:
        return items

    print(f"[*] {len(items_to_translate)} makale kontrol ediliyor ve derleniyor...")

    def do_translate(it):
        guid = it["guid"]
        title_orig = (it.get("title") or "").strip()
        source_feed = it.get("source_feed", "")
        
        # 1. Başlık zaten Türkçe ise doğrudan kullan, ASLA çevirme!
        if is_already_turkish(title_orig):
            title_tr = title_orig
        else:
            title_tr = translate_single_text(title_orig)
            if not is_valid_translation(title_tr):
                title_tr = title_orig
        
        # Categorize with both original and translated text
        category = categorize_article(title_orig + " " + title_tr, it.get("description", ""))

        # Check for real body content in description
        real_body = extract_real_body_text(it.get("description", ""))
        real_body_tr = ""
        if real_body:
            if is_already_turkish(real_body):
                real_body_tr = real_body
            else:
                real_body_tr = translate_single_text(real_body[:350])
                if not is_valid_translation(real_body_tr):
                    real_body_tr = real_body
        
        # Generate rich editorial summary
        summary_tr = generate_turkish_editorial_summary(title_tr, category, source_feed, real_body_tr)
        if not is_valid_translation(summary_tr):
            summary_tr = generate_turkish_editorial_summary(title_tr, category, source_feed, "")

        return guid, title_tr, summary_tr, category

    with ThreadPoolExecutor(max_workers=5) as executor:
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
