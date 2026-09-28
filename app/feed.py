import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
import email.utils
from typing import List, Dict, Any, Optional

def generate_rss_2_xml(
    feed_title: str,
    feed_description: str,
    feed_link: str,
    self_rss_url: str,
    items: List[Dict[str, Any]],
    language: str = "tr"
) -> str:
    """
    Generates standard, strictly valid RSS 2.0 XML with Atom & Media namespaces.
    """
    now = datetime.now(timezone.utc)
    last_build_date = email.utils.format_datetime(now)

    root = ET.Element("rss", {
        "version": "2.0",
        "xmlns:atom": "http://www.w3.org/2005/Atom",
        "xmlns:content": "http://purl.org/rss/1.0/modules/content/",
        "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        "xmlns:media": "http://search.yahoo.com/mrss/"
    })

    channel = ET.SubElement(root, "channel")

    title_el = ET.SubElement(channel, "title")
    title_el.text = feed_title

    link_el = ET.SubElement(channel, "link")
    link_el.text = feed_link

    desc_el = ET.SubElement(channel, "description")
    desc_el.text = feed_description

    if self_rss_url:
        ET.SubElement(channel, "atom:link", {
            "href": self_rss_url,
            "rel": "self",
            "type": "application/rss+xml"
        })

    lbd_el = ET.SubElement(channel, "lastBuildDate")
    lbd_el.text = last_build_date

    gen_el = ET.SubElement(channel, "generator")
    gen_el.text = "Inoreader-RSS-Bridge/1.0"

    lang_el = ET.SubElement(channel, "language")
    lang_el.text = language

    for item in items:
        item_el = ET.SubElement(channel, "item")

        it_title = ET.SubElement(item_el, "title")
        it_title.text = item.get("title", "")

        it_link = ET.SubElement(item_el, "link")
        it_link.text = item.get("link", "")

        it_guid = ET.SubElement(item_el, "guid", {"isPermaLink": "false"})
        it_guid.text = item.get("guid", item.get("link", ""))

        it_pub = ET.SubElement(item_el, "pubDate")
        it_pub.text = item.get("pub_date", last_build_date)

        author = item.get("author") or item.get("source_feed")
        if author:
            it_creator = ET.SubElement(item_el, "dc:creator")
            it_creator.text = author

        desc_content = item.get("description", "")
        if desc_content:
            it_desc = ET.SubElement(item_el, "description")
            it_desc.text = desc_content

            it_content = ET.SubElement(item_el, "content:encoded")
            it_content.text = desc_content

        img_url = item.get("image_url")
        if img_url:
            ET.SubElement(item_el, "enclosure", {
                "url": img_url,
                "type": "image/jpeg",
                "length": "0"
            })
            ET.SubElement(item_el, "media:content", {
                "url": img_url,
                "medium": "image"
            })

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def generate_atom_xml(
    feed_title: str,
    feed_description: str,
    feed_link: str,
    self_atom_url: str,
    items: List[Dict[str, Any]]
) -> str:
    """
    Generates standard Atom 1.0 XML.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    root = ET.Element("feed", {
        "xmlns": "http://www.w3.org/2005/Atom"
    })

    title_el = ET.SubElement(root, "title")
    title_el.text = feed_title

    sub_el = ET.SubElement(root, "subtitle")
    sub_el.text = feed_description

    id_el = ET.SubElement(root, "id")
    id_el.text = self_atom_url or feed_link

    updated_el = ET.SubElement(root, "updated")
    updated_el.text = now_iso

    ET.SubElement(root, "link", {
        "href": feed_link,
        "rel": "alternate"
    })

    if self_atom_url:
        ET.SubElement(root, "link", {
            "href": self_atom_url,
            "rel": "self",
            "type": "application/atom+xml"
        })

    for item in items:
        entry = ET.SubElement(root, "entry")

        e_title = ET.SubElement(entry, "title")
        e_title.text = item.get("title", "")

        ET.SubElement(entry, "link", {
            "href": item.get("link", ""),
            "rel": "alternate"
        })

        e_id = ET.SubElement(entry, "id")
        e_id.text = item.get("guid", item.get("link", ""))

        # ISO timestamp
        pub_ts = item.get("pub_date_ts", int(now.timestamp()))
        dt_pub = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
        iso_pub = dt_pub.strftime("%Y-%m-%dT%H:%M:%SZ")

        e_updated = ET.SubElement(entry, "updated")
        e_updated.text = iso_pub

        e_published = ET.SubElement(entry, "published")
        e_published.text = iso_pub

        author = item.get("author") or item.get("source_feed")
        if author:
            a_el = ET.SubElement(entry, "author")
            a_name = ET.SubElement(a_el, "name")
            a_name.text = author

        desc = item.get("description", "")
        if desc:
            e_summary = ET.SubElement(entry, "summary", {"type": "html"})
            e_summary.text = desc
            e_content = ET.SubElement(entry, "content", {"type": "html"})
            e_content.text = desc

    xml_str = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(xml_str)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def generate_json_feed(
    feed_title: str,
    feed_description: str,
    feed_link: str,
    self_json_url: str,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates JSON Feed v1.1.
    """
    json_items = []
    for item in items:
        pub_ts = item.get("pub_date_ts")
        if pub_ts:
            dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            date_published = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            date_published = None

        it_dict = {
            "id": item.get("guid", item.get("link", "")),
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "content_html": item.get("description", ""),
        }
        if date_published:
            it_dict["date_published"] = date_published
        if item.get("author"):
            it_dict["authors"] = [{"name": item["author"]}]
        if item.get("image_url"):
            it_dict["image"] = item["image_url"]

        json_items.append(it_dict)

    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": feed_title,
        "description": feed_description,
        "home_page_url": feed_link,
        "feed_url": self_json_url,
        "items": json_items
    }
