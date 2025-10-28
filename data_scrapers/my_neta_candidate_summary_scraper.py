"""Paginated scraper for MyNeta candidate summary listings.

The script renders each page with headless Chrome (via Selenium), walks the
pagination widget contained inside the center tag, and consolidates all rows
into a single CSV. Designed for listings such as:
https://www.myneta.info/Delhi2025/index.php?action=summary&subAction=candidates_analyzed&sort=candidate
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


CANDIDATE_TABLE_XPATH = (
    "//table[.//tr[.//th and contains(translate(normalize-space(.), "
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'candidate')]]"
)


def _strip_fragment(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except TypeError:
        return webdriver.Chrome(  # pragma: no cover - legacy Selenium branch
            executable_path=ChromeDriverManager().install(),
            chrome_options=options,
        )


def _load_html(
    driver: webdriver.Chrome,
    url: str,
    wait_xpath: Optional[str],
    timeout: int,
    wait_after: int,
) -> str:
    driver.set_page_load_timeout(timeout)
    driver.get(url)
    if wait_xpath:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, wait_xpath))
        )
    time.sleep(wait_after)
    return driver.page_source


def _text(node: Optional[Tag]) -> str:
    return node.get_text(strip=True).replace("\xa0", " ") if node else ""


def _first_anchor(cell: Tag) -> Optional[Tag]:
    for anchor in cell.find_all("a", href=True):
        if _text(anchor):
            return anchor
    return None


def _detect_table(soup: BeautifulSoup) -> Optional[Tag]:
    for table in soup.find_all("table"):
        header = table.find("tr")
        if not header:
            continue
        header_text = _text(header).lower()
        if "candidate" in header_text and ("constituency" in header_text or "total" in header_text):
            return table
    return None


def _extract_headers(table: Tag) -> List[str]:
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        if any(cell.name == "th" for cell in cells):
            headers = [_text(cell) or f"Column {idx + 1}" for idx, cell in enumerate(cells)]
            break
    else:  # pragma: no cover - unexpected layout fallback
        first_row = table.find("tr")
        headers = [
            _text(cell) or f"Column {idx + 1}" for idx, cell in enumerate(first_row.find_all("td"))
        ] if first_row else []

    final: List[str] = []
    seen: Dict[str, int] = {}
    for label in headers:
        if label in seen:
            seen[label] += 1
            final.append(f"{label} ({seen[label]})")
        else:
            seen[label] = 1
            final.append(label)
    return final


def _parse_table(table: Tag, page_url: str) -> Tuple[List[Dict[str, str]], List[str]]:
    headers = _extract_headers(table)
    records: List[Dict[str, str]] = []

    for row in table.find_all("tr"):
        if row.find("th"):
            continue
        if not _text(row):
            continue
        cells = row.find_all("td")
        if len(cells) < len(headers):
            continue

        record: Dict[str, str] = {}
        for idx, header in enumerate(headers):
            cell = cells[idx]
            value = _text(cell)
            record[header] = value

            if "candidate" in header.lower():
                anchor = _first_anchor(cell)
                if anchor:
                    record[f"{header} Link"] = urljoin(page_url, anchor.get("href", ""))

        records.append(record)

    fieldnames = headers.copy()
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    return records, fieldnames


def _candidate_identifier(record: Dict[str, str]) -> Optional[str]:
    for key, value in record.items():
        if not value:
            continue
        if "candidate" in key.lower() and not key.lower().endswith("link"):
            link_key = f"{key} Link"
            return record.get(link_key) or value
    return None


def _next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    center = soup.find("center")
    if not center:
        return None

    current_tag = None
    for bold in center.find_all("b"):
        if bold.get_text(strip=True).isdigit():
            current_tag = bold
            break

    if current_tag:
        for sibling in current_tag.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "a" and sibling.get("href"):
                return _strip_fragment(urljoin(current_url, sibling["href"]))

    for anchor in center.find_all("a", href=True):
        label = anchor.get_text(strip=True).lower()
        if label in {"next", ">"}:
            return _strip_fragment(urljoin(current_url, anchor["href"]))

    return None


def scrape_candidate_summary(
    start_url: str,
    timeout: int = 60,
    wait_after: int = 6,
    max_pages: Optional[int] = None,
) -> Tuple[List[Dict[str, str]], List[str]]:
    records: List[Dict[str, str]] = []
    field_order: List[str] = []
    visited: Set[str] = set()
    seen_candidates: Set[str] = set()

    driver = _create_driver()
    try:
        url = _strip_fragment(start_url)
        while url and url not in visited:
            visited.add(url)
            html = _load_html(driver, url, CANDIDATE_TABLE_XPATH, timeout, wait_after)
            soup = BeautifulSoup(html, "html.parser")
            table = _detect_table(soup)
            if not table:
                break

            page_records, page_fields = _parse_table(table, url)

            for record in page_records:
                identifier = _candidate_identifier(record)
                if identifier and identifier in seen_candidates:
                    continue
                if identifier:
                    seen_candidates.add(identifier)
                records.append(record)

            for field in page_fields:
                if field not in field_order:
                    field_order.append(field)

            if max_pages is not None and len(visited) >= max_pages:
                break

            url = _next_page_url(soup, url)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return records, field_order


def write_csv(records: List[Dict[str, str]], fieldnames: List[str], out_path: str) -> None:
    if not records:
        return
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key, "") for key in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape paginated MyNeta candidate summaries using a headless browser."
    )
    parser.add_argument(
        "url",
        help="Full URL to the first page of the candidate summary listing.",
    )
    parser.add_argument(
        "--out",
        default="candidate_summary.csv",
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Seconds to wait for the table to appear before giving up.",
    )
    parser.add_argument(
        "--wait-after",
        type=int,
        default=6,
        help="Extra seconds to wait after the table is detected (for late JS).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional limit on the number of pages to scrape (handy for tests).",
    )

    args = parser.parse_args()

    records, fieldnames = scrape_candidate_summary(
        args.url,
        timeout=args.timeout,
        wait_after=args.wait_after,
        max_pages=args.max_pages,
    )
    if not records:
        print("No rows scraped from the candidate summary listing.", file=sys.stderr)
        return

    write_csv(records, fieldnames, args.out)
    print(f"Saved {len(records)} rows to {args.out}")


if __name__ == "__main__":
    main()

