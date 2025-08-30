"""
Batch scraper for multiple MyNeta candidate pages.

This script builds on top of ``candidate_scraper.py`` to fetch and
consolidate information about several candidates into a single
Pandaspandas.DataFrame and output it as a CSV file.  It uses a
headless Selenium browser to render each candidate profile, extracts
summary fields (name, status, constituency, party, relative, age,
criminal cases count, total assets, total liabilities, education
category and details) and stores the full tables (cases, movable
assets, immovable assets, liabilities) as JSON strings in separate
columns.  Optionally the script will download any icons found in the
assets/liabilities tables into a static directory, as performed by
``candidate_scraper.py``.

Usage example::

    python batch_candidate_scraper.py \
        --urls https://www.myneta.info/bih2010/candidate.php?candidate_id=2140 \
        https://www.myneta.info/bih2010/candidate.php?candidate_id=2141 \
        --out-csv candidates.csv --static static_candidates

    # Or supply URLs via a file (one per line):
    python batch_candidate_scraper.py --list-file urls.txt --out-csv candidates.csv

Dependencies
------------
The script depends on ``selenium``, ``webdriver-manager``, ``beautifulsoup4``,
``pandas`` and ``requests``.  Install them via::

    pip install selenium webdriver-manager beautifulsoup4 pandas requests

Note: Running this scraper requires a copy of Google Chrome or
Chromium installed so that ``webdriver-manager`` can download the
appropriate ``chromedriver`` binary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from time import sleep
from typing import List

import pandas as pd

from candidate_scraper import scrape_candidate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_candidate_scraper.log'),
        #logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# Suppress WebDriver Manager logs
logging.getLogger('WDM').setLevel(logging.WARNING)


def load_urls(urls: List[str], list_file: str | None) -> List[str]:
    """Combine explicit URLs and URLs from a file into a single list.

    Parameters
    ----------
    urls : list[str]
        URLs passed directly on the command line.
    list_file : str or None
        Path to a text file containing one URL per line.

    Returns
    -------
    list[str]
        Combined and de-duplicated list of URLs.
    """
    result: List[str] = []
    # Add from command-line
    for u in urls:
        u = u.strip()
        if u and u not in result:
            result.append(u)
    # Add from file
    if list_file:
        if not os.path.isfile(list_file):
            raise FileNotFoundError(f"List file not found: {list_file}")
        with open(list_file, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and url not in result:
                    result.append(url)
    return result


def summarise_candidate(data: dict, url: str) -> dict:
    """Flatten candidate data into a row for the summary DataFrame.

    Extracts the high-level fields and serialises the nested tables
    (cases, assets, liabilities) as JSON strings.  Returns a dict
    representing a single row.

    Parameters
    ----------
    data : dict
        The dictionary returned by ``scrape_candidate``.
    url : str
        The original URL, stored for reference.

    Returns
    -------
    dict
        Flattened row with summary fields and JSON-encoded tables.
    """
    row = {
        "url": url,
        "name": data.get("name"),
        "status": data.get("status"),
        "constituency": data.get("constituency"),
        "party": data.get("party"),
        "relative": data.get("relative"),
        "age": data.get("age"),
        "criminal_cases_count": data.get("criminal_cases_count"),
        "total_assets": data.get("total_assets"),
        "total_liabilities": data.get("total_liabilities"),
        "education_category": data.get("education_category"),
        "education_details": data.get("education_details"),
    }
    # JSON encode tables; use ensure_ascii=False to preserve unicode, sort_keys for deterministic output
    row["cases_accused"] = json.dumps(data.get("cases_accused", []), ensure_ascii=False, sort_keys=True)
    row["cases_convicted"] = json.dumps(data.get("cases_convicted", []), ensure_ascii=False, sort_keys=True)
    row["movable_assets"] = json.dumps(data.get("movable_assets", []), ensure_ascii=False, sort_keys=True)
    row["immovable_assets"] = json.dumps(data.get("immovable_assets", []), ensure_ascii=False, sort_keys=True)
    row["liabilities"] = json.dumps(data.get("liabilities", []), ensure_ascii=False, sort_keys=True)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape multiple MyNeta candidate pages, consolidate summary data "
            "into a Pandas DataFrame and save it in a desired format (CSV, JSON, or pickle)."
        )
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=[],
        help=(
            "Candidate profile URLs to scrape (e.g. "
            "https://www.myneta.info/bih2010/candidate.php?candidate_id=2140). "
            "You can provide multiple URLs separated by spaces. Remember to quote each URL in zsh."
        ),
    )
    parser.add_argument(
        "--list-file",
        default=None,
        help=(
            "Path to a text file containing candidate profile URLs, one per line. "
            "URLs in this file are added to those provided by --urls."
        ),
    )
    parser.add_argument(
        "--out",
        default="candidates",
        help=(
            "Base name for the output file (without extension). "
            "If --format=csv, '.csv' will be appended; for json, '.json'; for pickle, '.pkl'."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "pickle"],
        default="csv",
        help="Output format: 'csv' (default), 'json' or 'pickle'."
    )
    parser.add_argument(
        "--static",
        default="static",
        help=(
            "Directory where downloaded images (icons) should be saved. "
            "This directory is passed to the underlying candidate scraper."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Maximum seconds to wait for each page load (default: 45)",
    )
    parser.add_argument(
        "--wait-after",
        type=int,
        default=6,
        help="Extra seconds to wait after page load for JS to complete (default: 6)",
    )
    args = parser.parse_args()

    # Combine all URLs
    try:
        urls = load_urls(args.urls, args.list_file)
    except FileNotFoundError as e:
        parser.error(str(e))
    if not urls:
        parser.error("You must specify at least one candidate URL via --urls or --list-file.")

    # Scrape each URL and build list of records
    records: List[dict] = []
    for url in urls:
        try:
            data = scrape_candidate(
                url=url,
                static_dir=args.static,
                timeout=args.timeout,
                wait_after=args.wait_after,
            )
            row = summarise_candidate(data, url)
            records.append(row)
            logger.info(f"Scraped: {url}")
            sleep(2)  # Be polite and avoid hammering the server
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
        

    if not records:
        logger.error("No data scraped; exiting without writing output.")
        return

    df = pd.DataFrame(records)
    # Determine output path and save accordingly
    base_path = args.out
    fmt = args.format
    if fmt == "csv":
        out_path = f"{base_path}.csv" if not base_path.lower().endswith(".csv") else base_path
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8")
    elif fmt == "json":
        out_path = f"{base_path}.json" if not base_path.lower().endswith(".json") else base_path
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        # Use 'records' orientation for a list of row dicts
        df.to_json(out_path, orient="records", force_ascii=False, indent=2)
    elif fmt == "pickle":
        out_path = f"{base_path}.pkl" if not base_path.lower().endswith(".pkl") else base_path
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        df.to_pickle(out_path)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
    logger.info(f"Saved consolidated data for {len(df)} candidates to {out_path}")


if __name__ == "__main__":
    main()