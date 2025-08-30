"""
MyNeta Bihar winners scraper (single render, no pagination) + Bye-Elections table
- Renders page in headless Chrome (Selenium)
- Extracts main winners table AND 'Bye-Elections' winners table
- Saves one CSV with Election_Type column (General / Bye-Elections)
- Downloads any icon images shown in Assets/Liabilities cells
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# -------------------------- Selenium rendering -------------------------- #

def _get_html_via_selenium(url: str, timeout: int = 45, wait_after: int = 6) -> str:
    """Render page with headless Chrome and return HTML."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        # Try Selenium 4 API
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except TypeError:
        # Fallback to Selenium 3 API
        driver = webdriver.Chrome(
            executable_path=ChromeDriverManager().install(),
            chrome_options=chrome_options,
        )

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        # Wait for a table whose first row contains Sno/Candidate/Constituency
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//table[.//tr[1][contains(normalize-space(.),'Sno') "
                "and (contains(normalize-space(.),'Candidate') or contains(normalize-space(.),'Constituency'))]]"
            ))
        )
        time.sleep(wait_after)  # let any late JS append icons/links
        return driver.page_source
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ----------------------- HTML → records (parsing) ----------------------- #

def _text(el: Optional[Tag]) -> str:
    return re.sub(r"\s+", " ", el.get_text(strip=True)) if el else ""

def _first_anchor_with_text(cell: Tag) -> Optional[Tag]:
    # Return the first anchor that has visible text (candidate name)
    for a in cell.find_all("a", href=True):
        if _text(a):
            return a
    return None

def _save_img_from_cell(cell: Tag, static_dir: str, base_url: str) -> str:
    """If cell contains an <img>, download it and return saved filename; else ''. """
    img = cell.find("img")
    if not img or not img.get("src"):
        return ""
    os.makedirs(static_dir, exist_ok=True)
    src = urljoin(base_url, img["src"])
    # Build a safe filename
    parsed = urlparse(src)
    fname = os.path.basename(parsed.path) or "icon.png"
    # Ensure uniqueness if repeated
    dst = os.path.join(static_dir, fname)
    stem, ext = os.path.splitext(dst)
    i = 1
    while os.path.exists(dst):
        dst = f"{stem}_{i}{ext}"
        i += 1
    try:
        r = requests.get(src, timeout=30)
        r.raise_for_status()
        with open(dst, "wb") as f:
            f.write(r.content)
        return os.path.basename(dst)
    except Exception:
        return ""  # non-fatal; leave blank

def _parse_winner_table_to_dicts(table: Tag, base_url: str, static_dir: str, election_type: str) -> List[Dict[str, str]]:
    """
    Parse the winners table (either General or Bye-Elections) into dict records.
    Expected columns:
      Sno | Candidate | Constituency | Party | Criminal Cases | Education | Total Assets | Liabilities
    Candidate cell: take the first anchor's text + href.
    Assets/Liabilities may be text OR an <img> icon — download if present.
    """
    records: List[Dict[str, str]] = []

    rows = table.find_all("tr")
    # Heuristically skip header rows (those with any <th> or that contain header keywords)
    data_rows = []
    for tr in rows:
        if tr.find("th"):
            continue
        txt = _text(tr)
        if not txt:
            continue
        # Require at least two <td>
        if len(tr.find_all("td")) < 3:
            continue
        data_rows.append(tr)

    for tr in data_rows:
        tds = tr.find_all("td")
        if len(tds) < 8:
            # Sometimes the table shows alt-rows; be conservative
            continue

        sno = _text(tds[0])

        # Candidate: first anchor with text
        cand_a = _first_anchor_with_text(tds[1]) or tds[1].find("a", href=True)
        if cand_a:
            candidate = _text(cand_a)
            candidate_link = urljoin(base_url, cand_a.get("href", ""))
        else:
            candidate = _text(tds[1])
            candidate_link = ""

        constituency = _text(tds[2])
        party = _text(tds[3])
        criminal_cases = _text(tds[4])
        education = _text(tds[5])

        # Total Assets: could be text or image icon
        assets_text = _text(tds[6])
        assets_img = _save_img_from_cell(tds[6], static_dir, base_url) if not assets_text else ""

        # Liabilities: text or image icon
        liabilities_text = _text(tds[7])
        liabilities_img = _save_img_from_cell(tds[7], static_dir, base_url) if not liabilities_text else ""

        records.append({
            "Election_Type": election_type,  # "General" or "Bye-Elections"
            "Sno": sno,
            "Candidate": candidate,
            "Candidate_Link": candidate_link,
            "Constituency": constituency,
            "Party": party,
            "Criminal_Cases": criminal_cases,
            "Education": education,
            "Total_Assets": assets_text,
            "Assets_Image": assets_img,
            "Liabilities": liabilities_text,
            "Liabilities_Image": liabilities_img,
        })
    return records

def _find_labeled_tables(soup: BeautifulSoup, year: int) -> List[tuple[Tag, str]]:
    """
    Find the General winners table and the Bye-Elections winners table.
    Returns: list of (table_tag, election_type)
    """
    sections: List[tuple[Tag, str]] = []

    # Strategy: find headings that contain the labels, then the next <table>
    heading_tags = soup.find_all(re.compile(r"^h[1-4]$", re.I))
    for h in heading_tags:
        title = _text(h)
        if not title:
            continue
        norm = title.lower()

        # General winners
        if f"list of winners in bihar {year}".lower() in norm and "bye" not in norm:
            nxt = h.find_next("table")
            if nxt:
                sections.append((nxt, "General"))

        # Bye-Elections winners
        if f"list of winners in bihar {year} bye-elections".lower() in norm or \
           f"list of winners in bihar {year} bye elections".lower() in norm:
            nxt = h.find_next("table")
            if nxt:
                sections.append((nxt, "Bye-Elections"))

    # Fallback: if headings not found, try the first table as General
    if not sections:
        first_tbl = soup.find("table")
        if first_tbl:
            sections.append((first_tbl, "General"))

    # Deduplicate (same table discovered twice through different headings)
    seen_ids = set()
    uniq: List[tuple[Tag, str]] = []
    for tbl, etype in sections:
        key = id(tbl)
        if key not in seen_ids:
            uniq.append((tbl, etype))
            seen_ids.add(key)
    return uniq


# ----------------------------- Main scraper ----------------------------- #

def scrape_winners_with_bye(year: int, static_dir: str = "static",
                             timeout: int = 60, wait_after: int = 8) -> List[Dict[str, str]]:
    base_url = f"https://www.myneta.info/bihar{year}/index.php?action=show_winners&sort=default"

    try:
        html = _get_html_via_selenium(base_url, timeout=timeout, wait_after=wait_after)
    except Exception as e:
        sys.stderr.write(f"Selenium failed to render {base_url}: {e}\n")
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables = _find_labeled_tables(soup, year)

    records: List[Dict[str, str]] = []
    for tbl, etype in tables:
        part = _parse_winner_table_to_dicts(tbl, base_url, static_dir, etype)
        records.extend(part)
    return records


def write_csv(records: List[Dict[str, str]], out_path: str) -> None:
    if not records:
        return
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fieldnames = [
        "Election_Type",
        "Sno",
        "Candidate",
        "Candidate_Link",
        "Constituency",
        "Party",
        "Criminal_Cases",
        "Education",
        "Total_Assets",
        "Assets_Image",
        "Liabilities",
        "Liabilities_Image",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in records:
            w.writerow(r)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Scrape MyNeta Bihar winners + Bye-Elections (single render, no pagination)."
    )
    p.add_argument("year", type=int, help="Election year (e.g., 2005, 2010, 2015, 2020)")
    p.add_argument("--out", default="winners.csv", help="Output CSV path")
    p.add_argument("--static", default="static", help="Directory to store downloaded images")
    p.add_argument("--timeout", type=int, default=60, help="Max seconds to wait for table to appear")
    p.add_argument("--wait-after", type=int, default=8, help="Extra seconds after table appears for JS to finish")
    args = p.parse_args()

    recs = scrape_winners_with_bye(args.year, static_dir=args.static,
                                   timeout=args.timeout, wait_after=args.wait_after)
    if not recs:
        print(f"No records found for year {args.year}.", file=sys.stderr)
        return

    write_csv(recs, args.out)
    print(f"Saved {len(recs)} rows to {args.out}. Images (if any) saved in: {args.static}")


if __name__ == "__main__":
    main()