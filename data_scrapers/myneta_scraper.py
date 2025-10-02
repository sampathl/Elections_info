"""
Module to scrape winner tables from the Association for Democratic
Reforms (ADR) portal MyNeta for Bihar assembly elections.

The ADR site lists the winners of each assembly election year with
columns for serial number, candidate name, constituency, party,
criminal cases, education, total assets and liabilities.  Candidate
names in the table are hyperlinked to detailed candidate pages and
some asset/liability fields are represented with small icons instead
of text.  This script fetches the tables for a given year (for
example 2005, 2010, 2015 or 2020), extracts the data, downloads any
icon images and writes the results to a CSV file.

Usage example::

    python myneta_scraper.py 2005 --out winners_2005.csv --static static_2005

The script will iterate through all available pages for that election
year, save any images to the ``static_2005`` directory and produce a
CSV with columns:

    Sno, Candidate, Candidate_Link, Constituency, Party, Criminal_Case,
    Education, Total_Assets, Assets_Image, Liabilities, Liabilities_Image

Note
----
The ADR website occasionally denies requests from non‑browser user
agents.  This script sets a common browser ``User‑Agent`` header but
may still fail if the site employs additional protections.  In such
cases you may need to run the script from a network with proper
access or after obtaining permission from the site owner.

Copyright
---------
Released under the MIT license.  Use this script responsibly and
obtain permission from ADR (MyNeta.info) before using the data for
public or commercial projects.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


# Data structure to hold one winner row
@dataclass
class WinnerRecord:
    sno: str
    candidate: str
    candidate_link: str
    constituency: str
    party: str
    criminal_case: str
    education: str
    total_assets: str
    assets_image: Optional[str]
    liabilities: str
    liabilities_image: Optional[str]


def _extract_text_and_image(cell: Tag, base_url: str, static_dir: str, prefix: str) -> Tuple[str, Optional[str]]:
    """Extracts the textual content and optionally downloads an image from a table cell.

    Some MyNeta cells use small icons instead of textual content.  This helper
    function looks for an ``<img>`` tag inside the cell, downloads the image
    into ``static_dir`` if present and returns a tuple of (text, image_path).

    If there are multiple images in the cell, only the first one is saved.
    If no image is found, the cell's text is returned with ``image_path`` set
    to ``None``.

    Parameters
    ----------
    cell : bs4.Tag
        The ``<td>`` or ``<th>`` element to inspect.
    base_url : str
        The base URL of the page used to resolve relative image URLs.
    static_dir : str
        Directory where downloaded images will be saved.
    prefix : str
        A prefix used to construct unique filenames (e.g. f"{sno}_assets").

    Returns
    -------
    (text, image_path) : Tuple[str, Optional[str]]
        ``text`` is the textual representation of the cell and ``image_path``
        is the relative path to the downloaded image or ``None`` if no image
        was present.
    """
    # Initialise return values
    text = cell.get_text(separator=" ", strip=True)
    image_path: Optional[str] = None

    # Look for images in the cell
    img = cell.find("img") if isinstance(cell, Tag) else None
    if img and img.get("src"):
        src = img["src"]
        # Resolve relative URLs using the page's base URL
        img_url = urljoin(base_url, src)
        # Determine file extension (default to .png if none)
        ext = os.path.splitext(img_url)[1] or ".png"
        # Construct local filename
        filename = f"{prefix}{ext}"
        local_path = os.path.join(static_dir, filename)
        # Only download if the file does not already exist
        if not os.path.exists(local_path):
            try:
                r = requests.get(img_url, stream=True, timeout=20)
                r.raise_for_status()
            except Exception as e:
                # If the image cannot be downloaded, leave it unset and
                # preserve whatever text the cell had.
                sys.stderr.write(f"Failed to download image {img_url}: {e}\n")
            else:
                os.makedirs(static_dir, exist_ok=True)
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                image_path = local_path
                # When an image is present, the textual value often comes
                # from an adjacent cell or is represented elsewhere.  Clear
                # the text in favour of the image indicator if it is empty.
                if not text:
                    text = ""
        else:
            image_path = local_path
    return text, image_path


def _parse_winner_table(table: Tag, base_url: str, static_dir: str) -> List[WinnerRecord]:
    """Parses a winners table into a list of WinnerRecord objects.

    Parameters
    ----------
    table : bs4.Tag
        The ``<table>`` element containing winner rows.
    base_url : str
        Base URL of the page, used to resolve relative links.
    static_dir : str
        Directory where images should be saved.

    Returns
    -------
    List[WinnerRecord]
        Parsed records from the table.
    """
    winners: List[WinnerRecord] = []
    rows = table.find_all("tr")
    # Skip the header row (assumed to be the first row)
    for row in rows[1:]:
        cols = row.find_all(["td", "th"])
        # Skip rows that do not have enough columns
        if len(cols) < 8:
            continue
        # Extract each column
        sno = cols[0].get_text(strip=True)
        # Candidate cell may contain multiple anchors; pick the first one
        cand_cell = cols[1]
        candidate = cand_cell.get_text(strip=True)
        candidate_link = ""
        # Identify the first anchor whose text is non‑empty; ignore icons and translate links
        for a in cand_cell.find_all("a", href=True):
            link_text = a.get_text(strip=True)
            if link_text and not link_text.lower().startswith("translate"):
                candidate = link_text
                candidate_link = urljoin(base_url, a["href"])
                break
        constituency = cols[2].get_text(strip=True)
        party = cols[3].get_text(strip=True)
        criminal_case = cols[4].get_text(strip=True)
        education = cols[5].get_text(strip=True)
        # Handle assets and liabilities; they may contain images
        assets_text, assets_image = _extract_text_and_image(
            cols[6], base_url, static_dir, f"{sno}_assets"
        )
        liabilities_text, liabilities_image = _extract_text_and_image(
            cols[7], base_url, static_dir, f"{sno}_liabilities"
        )
        record = WinnerRecord(
            sno=sno,
            candidate=candidate,
            candidate_link=candidate_link,
            constituency=constituency,
            party=party,
            criminal_case=criminal_case,
            education=education,
            total_assets=assets_text,
            assets_image=os.path.basename(assets_image) if assets_image else "",
            liabilities=liabilities_text,
            liabilities_image=os.path.basename(liabilities_image) if liabilities_image else "",
        )
        winners.append(record)
    return winners


def scrape_winners(year: int, static_dir: str = "static") -> List[WinnerRecord]:
    """Scrapes the winners list for a given Bihar assembly election year.

    The ADR website paginates results; this function automatically follows
    pages until no further rows are returned.  Each page is parsed into
    ``WinnerRecord`` objects.

    Parameters
    ----------
    year : int
        The election year (e.g. 2005, 2010, 2015, 2020).
    static_dir : str
        Directory where downloaded images should be placed.

    Returns
    -------
    List[WinnerRecord]
        A list of records representing all winners for the given year.
    """
    base_url = f"https://www.myneta.info/bih{year}/index.php?action=show_winners&sort=default"
    print(f"Scraping winners from: {base_url}")
    session = requests.Session()
    # Set a common browser User‑Agent to reduce the chance of being blocked
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    all_records: List[WinnerRecord] = []
    page = 1
    while True:
        # Append page parameter for subsequent pages
        url = base_url if page == 1 else f"{base_url}&page={page}"
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            sys.stderr.write(f"Failed to fetch {url}: {e}\n")
            break
        soup = BeautifulSoup(response.text, "html.parser")
        # Look for the table by header text; find the first table containing the word 'Sno'
        #print(soup.prettify())
        tables = soup.find_all("table")
        target_table: Optional[Tag] = None
        for tbl in tables:
            header = tbl.find("tr")
            if header and "Sno" in header.get_text():
                target_table = tbl
                break
        if not target_table:
            # No table found; exit
            break
        records = _parse_winner_table(target_table, base_url, static_dir)
        if not records:
            # No rows on this page implies termination
            break
        all_records.extend(records)
        # Simple heuristic: if fewer than 25 records returned, last page
        if len(records) < 25:
            break
        page += 1
    return all_records


def write_csv(records: Iterable[WinnerRecord], out_path: str) -> None:
    """Writes a sequence of WinnerRecords to a CSV file.

    Parameters
    ----------
    records : iterable of WinnerRecord
        Records to write.
    out_path : str
        Path of the CSV file to create.
    """
    fieldnames = [
        "Sno",
        "Candidate",
        "Candidate_Link",
        "Constituency",
        "Party",
        "Criminal_Case",
        "Education",
        "Total_Assets",
        "Assets_Image",
        "Liabilities",
        "Liabilities_Image",
    ]
    with open(out_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "Sno": r.sno,
                    "Candidate": r.candidate,
                    "Candidate_Link": r.candidate_link,
                    "Constituency": r.constituency,
                    "Party": r.party,
                    "Criminal_Case": r.criminal_case,
                    "Education": r.education,
                    "Total_Assets": r.total_assets,
                    "Assets_Image": r.assets_image,
                    "Liabilities": r.liabilities,
                    "Liabilities_Image": r.liabilities_image,
                }
            )


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the script when executed from the command line."""
    parser = argparse.ArgumentParser(
        description=(
            "Scrape winner data from MyNeta.info for Bihar assembly elections "
            "and save it to a CSV file.  Optionally download any asset/" 
            "liability icons into a static directory."
        )
    )
    parser.add_argument(
        "year",
        type=int,
        help="Election year to scrape (e.g. 2005, 2010, 2015, 2020)",
    )
    parser.add_argument(
        "--out",
        default="winners.csv",
        help="Output CSV file (default: winners.csv)",
    )
    parser.add_argument(
        "--static",
        default="static",
        help="Directory to store downloaded images (default: static)",
    )
    args = parser.parse_args(argv)
    records = scrape_winners(args.year, static_dir=args.static)
    if not records:
        print(f"No records found for year {args.year}.", file=sys.stderr)
        return
    write_csv(records, args.out)
    print(f"Saved {len(records)} records to {args.out}.")
    if any(r.assets_image or r.liabilities_image for r in records):
        print(f"Images saved in directory: {args.static}")


if __name__ == "__main__":
    main()