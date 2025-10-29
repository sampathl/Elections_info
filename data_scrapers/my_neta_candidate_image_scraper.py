"""Download profile images from MyNeta candidate pages.

The script expects MyNeta candidate URLs (e.g. ``https://www.myneta.info/Bihar2025/
candidate.php?candidate_id=149``). It renders each page with headless Chrome to
ensure any dynamic content is available, looks for the ``<img alt="profile image">``
element, and stores the referenced image locally. Saved filenames are derived
from the ``candidate_id`` query parameter so they stay stable across runs.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


PROFILE_IMG_XPATH = "//img[@alt='profile image' or translate(@alt, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='profile image']"


# ---------------------------- helper functions ---------------------------- #

def _create_driver() -> webdriver.Chrome:
    """Create a headless Chrome WebDriver instance."""

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except TypeError:
        # Fallback for older Selenium versions that expect the legacy signature.
        return webdriver.Chrome(
            executable_path=ChromeDriverManager().install(),
            chrome_options=options,
        )


def _load_urls(cli_urls: Iterable[str], list_file: Optional[str]) -> List[str]:
    """Merge URLs provided on the CLI with those from an optional file."""

    merged: List[str] = []

    def _add(url: str) -> None:
        url = url.strip()
        if url and url not in merged:
            merged.append(url)

    for url in cli_urls:
        _add(url)

    if list_file:
        file_path = Path(list_file).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"List file not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                _add(line)

    return merged


def _candidate_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    ids = qs.get("candidate_id")
    if not ids or not ids[0].strip():
        raise ValueError(f"Could not determine candidate_id from URL: {url}")
    return ids[0].strip()


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _wait_for_profile_image(
    driver: webdriver.Chrome,
    url: str,
    timeout: int,
    wait_after: int,
) -> BeautifulSoup:
    driver.set_page_load_timeout(timeout)
    driver.get(url)
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, PROFILE_IMG_XPATH)))
    time.sleep(wait_after)
    html = driver.page_source
    return BeautifulSoup(html, "html.parser")


def _extract_profile_image_src(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    # Try exact-case match first, fall back to case-insensitive search.
    img = soup.find("img", attrs={"alt": "profile image"})
    if not img:
        img = soup.find(
            "img",
            attrs={"alt": lambda value: isinstance(value, str) and value.lower() == "profile image"},
        )
    if not img or not img.get("src"):
        return None
    return urljoin(base_url, img["src"])


def _download_image(image_url: str, destination: Path) -> None:
    response = requests.get(image_url, stream=True, timeout=30)
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=8192):
            handle.write(chunk)


# ---------------------------------- CLI ---------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download profile images from MyNeta candidate pages."
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=[],
        help="Candidate page URLs to scrape.",
    )
    parser.add_argument(
        "--list-file",
        help="Optional file containing candidate URLs (one per line).",
    )
    parser.add_argument(
        "--out-dir",
        default="/Users/saml16/projects/Elections_info/static/Bihar/2025_data/candidate_static",
        help="Directory where downloaded images will be stored (default: candidate_images).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Max seconds to wait for page load (default: 45).",
    )
    parser.add_argument(
        "--wait-after",
        type=int,
        default=2,
        help="Extra seconds to wait after the image tag appears (default: 4).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing images if the file already exists.",
    )

    args = parser.parse_args()

    try:
        urls = _load_urls(args.urls, args.list_file)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    if not urls:
        parser.error("No candidate URLs provided. Use --urls or --list-file.")

    output_dir = Path(args.out_dir).expanduser()
    _ensure_directory(output_dir)

    driver = _create_driver()
    try:
        for url in urls:
            candidate_id = None
            try:
                candidate_id = _candidate_id_from_url(url)
                soup = _wait_for_profile_image(driver, url, args.timeout, args.wait_after)
                image_url = _extract_profile_image_src(soup, url)
                if not image_url:
                    print(f"No profile image found at {url}", file=sys.stderr)
                    continue

                extension = os.path.splitext(urlparse(image_url).path)[1] or ".jpg"
                destination = output_dir / f"{candidate_id}{extension}"

                if destination.exists() and not args.overwrite:
                    print(f"Skipping existing image: {destination}")
                    continue

                _download_image(image_url, destination)
                print(f"Saved {destination}")

            except Exception as exc:  # Capture all errors per URL and continue.
                if candidate_id:
                    print(f"Failed for candidate_id {candidate_id}: {exc}", file=sys.stderr)
                else:
                    print(f"Failed for URL {url}: {exc}", file=sys.stderr)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()

