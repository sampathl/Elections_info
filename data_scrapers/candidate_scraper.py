"""
Scraper for individual MyNeta candidate pages using a headless browser.

This module uses Selenium to render the dynamic candidate profile page on
the ADR MyNeta website (e.g., ``https://www.myneta.info/bih2010/candidate.php?candidate_id=2140``)
and BeautifulSoup/Pandas to extract structured information.  Each
candidate page contains a top summary, several widgets and multiple
tables.  The scraper attempts to capture:

* Candidate summary: name, status (Winner/Runner/NA), constituency,
  party, relative (parent/spouse name) and age.
* High level summaries: number of criminal cases, total assets and
  liabilities, education category/details.
* Detailed tables:
    - Cases where accused and where convicted.
    - Movable assets (with columns for self, spouse and dependents).
    - Immovable assets (with similar columns).
    - Liabilities.

The script outputs a JSON representation of the scraped data and can
optionally save the detailed tables as CSV files.  Because the site
loads its content through JavaScript, you must install Selenium and
webdriver-manager.  See the ``requirements`` section below.

Usage example::

    python candidate_scraper.py --url https://www.myneta.info/bih2010/candidate.php?candidate_id=2140 \
        --out candidate_2140.json --static static_2140

Dependencies
------------
The script requires:

    pip install selenium webdriver-manager beautifulsoup4 pandas requests

Ensure that a recent version of Google Chrome or Chromium is installed
on your system so that webdriver-manager can download the correct
chromedriver.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
# We avoid depending on pandas.read_html here because optional
# dependencies like ``lxml`` may not be installed in the runtime
# environment.  Instead, we parse HTML tables with BeautifulSoup.
import pandas as pd  # still used for optional CSV writing
from bs4 import BeautifulSoup, Tag, Comment
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _init_driver(headless: bool = True) -> webdriver.Chrome:
    """Initialise a Chrome driver using webdriver-manager.

    Tries Selenium 4 syntax (service + options) and falls back to
    Selenium 3 syntax (executable_path + chrome_options) to support
    different environments.
    """
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    driver: Optional[webdriver.Chrome] = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except TypeError:
        # Fallback for older selenium versions
        driver = webdriver.Chrome(
            executable_path=ChromeDriverManager().install(),
            chrome_options=chrome_options,
        )
    return driver


def _get_page_html(url: str, timeout: int = 45, wait_after: int = 6) -> str:
    """Render a URL with Selenium and return page source.

    Parameters
    ----------
    url : str
        Full URL to load.
    timeout : int
        Maximum seconds to wait for the page to load and the basic content
        to appear.
    wait_after : int
        Additional seconds to wait after the initial load to allow
        JavaScript to append tables and widgets.

    Returns
    -------
    str
        The fully rendered HTML source.
    """
    driver = _init_driver()
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        # Wait for general markers of a candidate page: the candidate name
        # typically appears in a large header.  We wait for the <body>
        # because the page often renders quickly but tables load via JS.
        time.sleep(wait_after)
        html = driver.page_source
    finally:
        driver.quit()
    return html
    
    


def _parse_summary(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract candidate summary information from the soup.
    
    Attempts to locate candidate details from the structured w3-panel element,
    falling back to heuristic text parsing if the structured approach fails.
    
    Returns
    -------
    dict
        Candidate information including name, constituency, party, etc.
    """
    result = {
        "name": None,
        "constituency": None,
        "district": None,
        "party_name": None,
        "relative": None,
        "age": None,
        "voter_info": None,
        "self_profession": None,
        "spouse_profession": None
    }
    
    # Step 1: Find the HTML comment containing "Main Content"
    comment = soup.find(string=lambda s: isinstance(s, Comment) and "main content" in s.lower())
    if not comment:
        logger.debug(f"No 'Main Content' comment found")
        return result
    
    # Step 2: Find the next <div> element after the comment
    first_div_after = comment.find_next(lambda t: isinstance(t, Tag) and t.name == "div")
    if not first_div_after:
        logger.debug(f"No <div> found after 'Main Content' comment")
        return result
    
    # Step 3: Get direct child <div> elements
    child_divs = [child for child in first_div_after.children 
                  if isinstance(child, Tag) and child.name == "div"]

    # First, try to find direct child with class 'w3-half'
    w3_half_divs = []
    for child in child_divs:
        w3_half_divs.extend(child.find_all("div", class_="w3-half"))

    if not w3_half_divs:
        logger.debug(f"No direct 'w3-half' divs found, trying 'w3-twothird'")
        # If no direct w3-half found, look for grandchildren via w3-twothird
        w3_twothird_divs = soup.find_all("div", class_="w3-twothird")
        for twothird_div in w3_twothird_divs:
            w3_half_children = twothird_div.find_all("div", class_="w3-half")
            w3_half_divs.extend(w3_half_children)
    
    # Find the first 'w3-half' div that contains a child with class 'w3-panel'
    panel_child = next(
        (w3_half_div.find("div", class_="w3-panel") for w3_half_div in w3_half_divs if w3_half_div.find("div", class_="w3-panel")),
        None
    )
    
    if panel_child:
        # Extract name from h2 (ignore green font text)
        logger.debug(f"Found 'w3-panel' child in 'w3-half' divs, extracting candidate information")
        h2 = panel_child.find("h2")
        if h2:
            # Remove any green font elements
            for green_font in h2.find_all(style=lambda value: value and "color" in value.lower() and "green" in value.lower()):
                green_font.decompose()
            result["name"] = h2.get_text(strip=True).strip("(Winner)").strip("Winner")
            logger.debug(f"Extracted candidate name: {result['name']}")
        
        # Extract constituency and district from h5
        h5 = panel_child.find("h5")
        if h5:
            h5_text = h5.get_text(strip=True)
            # Pattern: "CONSTITUENCY (DISTRICT)"
            match = re.match(r"(.+?)\s*\((.+?)\)", h5_text)
            if match:
                result["constituency"] = match.group(1).strip()
                result["district"] = match.group(2).strip()
                logger.debug(f"Extracted constituency: {result['constituency']}, district: {result['district']}")

        # Extract information from divs
        divs = panel_child.find_all("div")
        for div in divs:
            div_text = div.get_text(strip=True)
            
            # Party information
            if "Party:" in div_text:
                party_match = re.search(r"Party:\s*(.+)", div_text)
                if party_match:
                    result["party_name"] = party_match.group(1).strip()
                    logger.debug(f"Extracted party name: {result['party_name']}")

            # Relative information (S/o|D/o|W/o)
            elif re.search(r"S/o\|D/o\|W/o:", div_text):
                relative_match = re.search(r"S/o\|D/o\|W/o:\s*(.+)", div_text)
                if relative_match:
                    result["relative"] = relative_match.group(1).strip()
                    logger.debug(f"Extracted relative information: {result['relative']}")

            # Age information
            elif "Age:" in div_text:
                age_match = re.search(r"Age:\s*(\d+)", div_text)
                if age_match:
                    result["age"] = age_match.group(1).strip()
                    logger.debug(f"Extracted age: {result['age']}")
            
            # Voter enrollment information
            elif "Name Enrolled as Voter in:" in div_text:
                voter_match = re.search(r"Name Enrolled as Voter in:\s*(.+)", div_text)
                if voter_match:
                    result["voter_info"] = voter_match.group(1).strip()
                    logger.debug(f"Extracted voter information: {result['voter_info']}")

        # Extract profession information from p tag
        p_tag = panel_child.find("p")
        if p_tag:
            p_html = str(p_tag)
            
            # Extract self profession
            self_prof_match = re.search(r"<b>Self Profession:</b>([^<]+?)(?:<br|</p)", p_html)
            if self_prof_match:
                result["self_profession"] = self_prof_match.group(1).strip()
                logger.debug(f"Extracted self profession: {result['self_profession']}")

            # Extract spouse profession
            spouse_prof_match = re.search(r"<b>Spouse Profession:</b>([^<]+?)(?:<br|</p)", p_html)
            if spouse_prof_match:
                result["spouse_profession"] = spouse_prof_match.group(1).strip()
                logger.debug(f"Extracted spouse profession: {result['spouse_profession']}")
        
        if any(result.values()):
            logger.info(f"Structured summary parsing succeeded")
            return result
        
    else: 
        logger.debug(f"No 'w3-panel' child found in 'w3-half' divs")
        logger.info(f"Structured summary parsing failed, falling back to heuristic text parsing")
        # Store fallback parsing results separately
        fallback_result = {
            "name": None,
            "constituency": None,
            "party_name": None,
            "relative": None,
            "age": None
        }
        
        lines: List[str] = []
        # Fallback: gather the first few paragraphs of the page
        header_candidates = soup.find_all("p")[:5]
        for p in header_candidates:
            text = p.get_text(strip=True)
            if text:
                lines.append(text)
                
        # Parse the lines heuristically
        for line in lines:
            # Candidate name line often has (Winner) or (Runner)
            if fallback_result["name"] is None and re.search(r"\(\w+\)", line):
                # e.g. "VIRENDRA SINGH (Winner)"
                name_part, status_part = line.rsplit("(", 1)
                fallback_result["name"] = name_part.strip()
                logger.debug(f"Extracted candidate name: {fallback_result['name']}")
                # Note: status_part is ignored as we don't track status in this version
                continue
                
            if fallback_result["constituency"] is None and re.match(r"^[A-Za-z].*\([A-Za-z ]+\)$", line):
                # e.g. "Wazirganj (GAYA)"
                fallback_result["constituency"] = line.strip()
                logger.debug(f"Extracted constituency: {fallback_result['constituency']}")
                continue
                
            if line.lower().startswith("party"):  # Party:BJP
                _, val = line.split(":", 1)
                fallback_result["party_name"] = val.strip()
                logger.debug(f"Extracted party name: {fallback_result['party_name']}")
                continue
                
            # S/o D/o W/o may appear with various prefixes (S/o, D/o, W/o, S/O/D/O/W/O)
            if any(prefix in line for prefix in ["S/o", "S/O", "S.O.", "Father", "Husband"]):
                # e.g. "S/o:D/o/W/o: LATE YUGESHWAR SINGH"
                fallback_result["relative"] = line.split(":")[-1].strip()
                logger.debug(f"Extracted relative information: {fallback_result['relative']}")
                continue
                
            if line.lower().startswith("age"):
                # e.g. "Age: 57"
                _, val = line.split(":", 1)
                fallback_result["age"] = val.strip()
                logger.debug(f"Extracted age: {fallback_result['age']}")
                continue
                
        # Fallbacks: if some fields are still missing, scan the entire page text
        full_text = soup.get_text(separator="|", strip=True)
        
        # Candidate name: look for UPPERCASE names followed by parentheses
        if fallback_result["name"] is None:
            m = re.search(r"([A-Z][A-Z .]+)\s*\(([^\)]+)\)", full_text)
            if m:
                fallback_result["name"] = m.group(1).strip()
                logger.debug(f"Extracted fallbacks candidate name: {fallback_result['name']}")

        # Party
        if fallback_result["party_name"] is None:
            m = re.search(r"Party\s*:?\s*([A-Za-z0-9 .&-]+)", full_text)
            if m:
                fallback_result["party_name"] = m.group(1).strip()
                logger.debug(f"Extracted fallbacks party name: {fallback_result['party_name']}")

        # Age
        if fallback_result["age"] is None:
            m = re.search(r"Age\s*:?\s*(\d+)", full_text)
            if m:
                fallback_result["age"] = m.group(1).strip()
                logger.debug(f"Extracted fallbacks age: {fallback_result['age']}")

        # Relative (S/O, D/O, W/O)
        if fallback_result["relative"] is None:
            # Pattern with pipes like "S/o|D/o|W/o: NAME"
            m = re.search(r"S/o\|D/o\|W/o\s*:?\s*([^|]+)", full_text)
            if m:
                fallback_result["relative"] = m.group(1).strip()
                logger.debug(f"Extracted fallbacks relative information: {fallback_result['relative']}")
            else:
                m = re.search(r"(?:S/o|S/O|D/o|D/O|W/o|W/O)\s*:?\s*([^|]+)", full_text)
                if m:
                    fallback_result["relative"] = m.group(1).strip()
                    logger.debug(f"Extracted fallbacks relative information: {fallback_result['relative']}")
                    
        # Constituency: look for words followed by parentheses with district names
        if fallback_result["constituency"] is None:
            # A constituency string often looks like "Wazirganj (GAYA)".  We look for a pattern
            m = re.search(r"([A-Za-z][A-Za-z .'-]+\s*\([A-Za-z .'-]+\))", full_text)
            if m:
                fallback_result["constituency"] = m.group(1).strip()
                logger.debug(f"Extracted fallbacks constituency: {fallback_result['constituency']}")

        # Add fallback results to main result object
        result["fallback"] = fallback_result
    return result


def _parse_asserts_and_education(soup: BeautifulSoup) -> Dict[str, Any]:
    """Parse summary widgets: criminal cases count, asset/liability totals and education.

    Looks for specific keywords in the page text.
    """
    result: Dict[str, Any] = {
        "criminal_cases_count": None,
        "total_assets": None,
        "total_liabilities": None,
        "education_category": None,
        "education_details": None,
        "assets_href": None,
        "assets_description": None,
        "liabilities_description": None,
    }

    # Search for h3 elements with specific text
    assets_h3 = soup.find('h3', string=lambda text: text and 'Assets & Liabilities' in text)
    education_h3 = soup.find('h3', string=lambda text: text and 'Educational Details' in text)
    
    if assets_h3:
        logger.debug("Found h3 with 'Assets & Liabilities':")

        # Get parent div
        parent_div = assets_h3.find_parent('div')
        if parent_div:

            # Extract href from <a> element containing h3
            a_element = parent_div.find('a')
            if a_element and a_element.get('href'):
                result["assets_href"] = a_element.get('href')
                logger.debug(f"Assets href: {result['assets_href']}")

            # Find table in parent div and extract Assets and Liabilities values
            table = parent_div.find('table')
            if table:
                # Look for tbody first, fallback to table if no tbody
                tbody = table.find('tbody')
                rows = tbody.find_all('tr') if tbody else table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # First td contains the category (Assets: or Liabilities:)
                        category_text = cells[0].get_text(strip=True)
                        # Second td contains the details with <b> and <span> elements
                        details_cell = cells[1]
                        
                        # Extract numeric value from <b> element
                        b_element = details_cell.find('b')
                        span_element = details_cell.find('span')
                        
                        if "Assets" in category_text:
                            # Extract numeric value from Rs format, handling decimal points
                            b_text = b_element.get_text(strip=True)
                            assets_match = re.search(r'Rs\.?\s*([\d,\.]+)', b_text)
                            if assets_match:
                                result["total_assets"] = assets_match.group(1).replace(",", "").strip()
                                logger.debug(f"Extracted Assets: {result['total_assets']}")
                            
                            # Extract descriptive text from span element
                            if span_element:
                                result["assets_description"] = span_element.get_text(strip=True).strip('~').strip('+')
                                logger.debug(f"ExtractedAssets description: {result['assets_description']}")

                        elif "Liabilities" in category_text:
                            # Extract numeric value from Rs format, handling decimal points
                            b_text = b_element.get_text(strip=True)
                            liabilities_match = re.search(r'Rs\.?\s*([\d,\.]+)', b_text)
                            if liabilities_match:
                                result["total_liabilities"] = liabilities_match.group(1).replace(",", "").strip()
                                logger.debug(f"Extracted Liabilities: {result['total_liabilities']}")

                            # Extract descriptive text from span element
                            if span_element:
                                result["liabilities_description"] = span_element.get_text(strip=True).strip('~').strip('+')
                                logger.debug(f"Extracted Liabilities description: {result['liabilities_description']}")
            else:
                logger.debug("No Assets and Liabilities table found in parent div")
    else:
        logger.debug("No h3 with 'Assets & Liabilities' found")

    if education_h3:
        logger.debug("Found h3 with 'Educational Details':")

        # Get parent div
        parent_div = education_h3.find_parent('div')
        if parent_div:
            # Extract education information from the structured div
            # Pattern: <h3>Educational Details</h3> <hr/> Category: Graduate <br/> Details...
            
            # Get the HTML content of the parent div
            parent_html = str(parent_div)
            
            # Extract category - look for "Category:" followed by text before <br/>
            category_match = re.search(r'Category:\s*([^<]+?)(?:\s*<br|$)', parent_html, re.IGNORECASE)
            if category_match:
                result["education_category"] = category_match.group(1).strip()
                logger.debug(f"Extracted Education category: {result['education_category']}")

            # Extract education details - look for text after <br/> tag
            br_match = re.search(r'<br\s*/?>\s*([^<]+)', parent_html, re.IGNORECASE)
            if br_match:
                result["education_details"] = br_match.group(1).strip()
                logger.debug(f"Extracted Education details: {result['education_details']}")

            # Alternative: try extracting from text content if HTML parsing doesn't work
            if not result["education_category"] or not result["education_details"]:
                logger.debug("Falling back to text content parsing for education details")
                text_content = parent_div.get_text(" ", strip=True)
                # Remove the h3 title from the beginning
                text_content = re.sub(r'^Educational Details\s*', '', text_content, flags=re.IGNORECASE)
                
                # Split on "Category:" to get the category and details
                parts = text_content.split("Category:", 1)
                if len(parts) > 1:
                    remaining_text = parts[1].strip()
                    
                    # Split the remaining text to separate category from details
                    # Category should be the first word/phrase, details come after
                    lines = remaining_text.split('\n') if '\n' in remaining_text else remaining_text.split(' ', 1)
                    
                    if lines:
                        if not result["education_category"]:
                            result["education_category"] = lines[0].strip()
                            logger.info(f"Extracted Fallback Education category: {result['education_category']}")

                        if len(lines) > 1 and not result["education_details"]:
                            result["education_details"] = ' '.join(lines[1:]).strip()
                            logger.info(f"Extracted Fallback Education details: {result['education_details']}")
        else:
            logger.info("No 'Educational Details' h3 element found")




    # Fallback parsing: only use if structured parsing didn't find the values
    text = soup.get_text(separator="|", strip=True)
   
    # Criminal cases: match variations like "Number of Criminal Cases", "Criminal Cases", or "No criminal cases"
    if not result["criminal_cases_count"]:
        # First check for "No criminal cases" pattern
        no_cases_match = re.search(r"No\s+criminal\s+cases?", text, re.I)
        if no_cases_match:
            result["criminal_cases_count"] = "0"
            logger.debug(f"Criminal cases count (fallback - no cases): {result['criminal_cases_count']}")
        else:
            # Then check for numeric criminal cases
            m = re.search(r"(?:Number\s+of\s+)?Criminal\s+Cases?\s*:?\s*(\d+)", text, re.I)
            if m:
                result["criminal_cases_count"] = m.group(1)
                logger.debug(f"Criminal cases count (fallback): {result['criminal_cases_count']}")
    


    # Fallback Assets and liabilites: match "Assets", "Total Assets" followed by Rs or ₹
    if not result["total_assets"]:
        m = re.search(r"Assets\s*(?:Total\s*)?:?\s*(?:Rs\.?|₹)\s*([\d,\.]+)", text, re.I)
        if m:
            num = m.group(1).replace(",", "").strip()
            result["total_assets"] = num
            logger.debug(f"Total assets (fallback): {result['total_assets']}")
    
    # Liabilities summary: match "Liabilities" with Rs or ₹
    if not result["total_liabilities"]:
        m = re.search(r"Liabilities\s*(?:Total\s*)?:?\s*(?:Rs\.?|₹)\s*([\d,\.]+)", text, re.I)
        if m:
            num = m.group(1).replace(",", "").strip()
            result["total_liabilities"] = num
            logger.debug(f"Total liabilities (fallback): {result['total_liabilities']}")
    
    # Education details: only use fallback if structured parsing didn't find both category and details
    if not result["education_category"] and not result["education_details"]:
        edu_section = soup.find(lambda tag: tag.name in ["div", "td"] and "Educational Details" in tag.get_text())
        if edu_section:
            # Extract text after "Educational Details"
            content = edu_section.get_text(" ", strip=True)
            parts = content.split("Category:")
            if len(parts) > 1:
                # e.g. "Category: Graduate B.A. From ..."
                cat_and_details = parts[1].strip()
                # Category ends at the first space; rest is details
                cat_parts = cat_and_details.split(" ", 1)
                if not result["education_category"]:
                    result["education_category"] = cat_parts[0].strip()
                    logger.debug(f"Education category (fallback): {result['education_category']}")
                if len(cat_parts) > 1 and not result["education_details"]:
                    result["education_details"] = cat_parts[1].strip()
                    logger.debug(f"Education details (fallback): {result['education_details']}")

    logger.debug(f"Education and assets parsed")
    return result


def _download_image(src: str, static_dir: str) -> str:
    """Download an image from the given URL into static_dir and return the local filename.

    If the download fails, returns the empty string.
    """
    os.makedirs(static_dir, exist_ok=True)
    parsed = urlparse(src)
    fname = os.path.basename(parsed.path) or "icon.png"
    dst = os.path.join(static_dir, fname)
    stem, ext = os.path.splitext(dst)
    i = 1
    while os.path.exists(dst):
        dst = f"{stem}_{i}{ext}"
        i += 1
    try:
        resp = requests.get(src, timeout=20)
        resp.raise_for_status()
        with open(dst, "wb") as f:
            f.write(resp.content)
        return os.path.basename(dst)
    except Exception:
        return ""


def _parse_tables(soup: BeautifulSoup, base_url: str, static_dir: str) -> Dict[str, Any]:
    """Extract structured tables from the candidate page.

    This function parses all HTML tables on the candidate page using
    BeautifulSoup rather than relying on ``pandas.read_html``.  It
    classifies each table into one of five categories based on its
    headers or surrounding context and returns a dictionary with lists
    of row dictionaries.  For asset/liability cells containing only
    images, the associated images are downloaded into ``static_dir``
    and the filename stored.

    Returns
    -------
    dict
        Keys ``cases_accused``, ``cases_convicted``, ``movable_assets``,
        ``immovable_assets`` and ``liabilities`` map to lists of row
        dictionaries extracted from the corresponding tables.
    """
    tables_data: Dict[str, Any] = {
        "cases_accused": [],
        "cases_convicted": [],
        "movable_assets": [],
        "immovable_assets": [],
        "liabilities": [],
    }

    # Iterate through all table tags in the soup
    for table in soup.find_all("table"):
        # Extract rows
        rows = table.find_all("tr")
        if not rows:
            continue
        # Determine headers: first row's th/td texts
        header_cells = rows[0].find_all(["th", "td"])
        headers = [cell.get_text(strip=True) for cell in header_cells]
        if len(headers) < 2:
            continue  # skip trivial tables
        # Collect row dictionaries
        body_rows: List[Dict[str, str]] = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            values: List[str] = []
            for cell in cells:
                # If cell contains <img> and has no text, keep the HTML to handle images later
                if cell.find("img"):
                    # We'll store the raw HTML; images will be downloaded later
                    values.append(str(cell))
                else:
                    values.append(cell.get_text(strip=True))
            # pad values if row has fewer cells than headers
            while len(values) < len(headers):
                values.append("")
            row_dict = {headers[i]: values[i] for i in range(len(headers))}
            body_rows.append(row_dict)
        if not body_rows:
            continue
        # Classification logic: Determine which kind of table this is.
        header_text = " ".join(headers).lower()
        first_col_values = [row[headers[0]] for row in body_rows]
        # Identify cases tables by presence of 'ipc' or 'bns' in headers or first column
        if "ipc" in header_text or "bns" in header_text:
            # Determine accused vs convicted by heading above the table
            label = "cases_accused"
            heading = table.find_previous(lambda t: t.name in ["h2", "h3", "h4", "b"])
            if heading and "convicted" in heading.get_text().lower():
                label = "cases_convicted"
            tables_data[label].extend(body_rows)
            continue
        # Movable assets: look for cash/deposits or 'movable' in header
        if any(re.search(r"cash|deposit|motor|jewellery|bonds|movable", h, re.I) for h in headers):
            tables_data["movable_assets"].extend(body_rows)
            continue
        if any(re.search(r"cash|deposit|motor|jewellery|bonds|movable", val, re.I) for val in first_col_values):
            tables_data["movable_assets"].extend(body_rows)
            continue
        # Immovable assets: look for agricultural land, buildings, houses
        if any(re.search(r"agricultural|non agricultural|buildings|houses", h, re.I) for h in headers):
            tables_data["immovable_assets"].extend(body_rows)
            continue
        if any(re.search(r"agricultural|non agricultural|buildings|houses", val, re.I) for val in first_col_values):
            tables_data["immovable_assets"].extend(body_rows)
            continue
        # Liabilities: look for loans or tax categories in headers/first column
        if any(re.search(r"loan|income tax|sales tax|property tax|tax", h, re.I) for h in headers):
            tables_data["liabilities"].extend(body_rows)
            continue
        if any(re.search(r"loan|income tax|sales tax|property tax|tax", val, re.I) for val in first_col_values):
            tables_data["liabilities"].extend(body_rows)
            continue
        # If none of the above, skip table
        continue

    # Download images and replace HTML with filenames for assets/liabilities
    for key in ["movable_assets", "immovable_assets", "liabilities"]:
        for row in tables_data[key]:
            for col, val in list(row.items()):
                # If value contains an <img> tag, download it
                if isinstance(val, str) and "<img" in val:
                    try:
                        soup_val = BeautifulSoup(val, "html.parser")
                        img = soup_val.find("img")
                        if img and img.get("src"):
                            filename = _download_image(urljoin(base_url, img["src"]), static_dir)
                            row[col] = filename
                    except Exception:
                        row[col] = ""
                # If value is None (rare), normalise to empty string
                elif val is None:
                    row[col] = ""
    return tables_data


def scrape_candidate(
    url: str, static_dir: str = "static", timeout: int = 45, wait_after: int = 6
) -> Dict[str, Any]:
    """Scrape a single candidate page.

    Parameters
    ----------
    url : str
        Full URL to the candidate page.
    static_dir : str
        Directory where icons/images will be saved.
    timeout : int
        Maximum seconds to wait for page to load.
    wait_after : int
        Additional seconds to wait after page load.

    Returns
    -------
    dict
        A dictionary containing summary fields and lists for each table.
    """
    html = _get_page_html(url, timeout=timeout, wait_after=wait_after)
    logger.info(f"Fetched HTML")
    #logger.debug(f"Fetched HTML: {html[:1000]}...")  
    soup = BeautifulSoup(html, "html.parser")
    summary = _parse_summary(soup)
    logger.info(f"Fetched Summary")
    logger.debug(f" {summary}")
    
    widgets = _parse_asserts_and_education(soup)
    logger.info(f"Parsed Asserts and Education")
    logger.debug(f"{widgets}")
    
    tables = _parse_tables(soup, url, static_dir)
    logger.info(f"Parsed Tables")
    logger.debug(f"{tables}")
    
    data = {**summary, **widgets, **tables, "url": url}
    logger.info(f"Scraping complete for {url}")
    logger.debug(f"Final data: {data}")
    
    return data


def write_json(data: Dict[str, Any], out_path: str) -> None:
    """Write scraped data to a JSON file with UTF-8 encoding."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_tables(data: Dict[str, Any], out_dir: str) -> None:
    """Write the detailed tables to CSV files in ``out_dir``.

    Filenames are ``cases_accused.csv``, ``cases_convicted.csv``,
    ``movable_assets.csv``, ``immovable_assets.csv`` and ``liabilities.csv``.
    """
    os.makedirs(out_dir, exist_ok=True)
    for key in [
        "cases_accused",
        "cases_convicted",
        "movable_assets",
        "immovable_assets",
        "liabilities",
    ]:
        rows = data.get(key, [])
        if rows:
            # Determine field order by union of keys across all rows
            fieldnames = list({col for row in rows for col in row.keys()})
            with open(os.path.join(out_dir, f"{key}.csv"), "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)


def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('candidate_scraper.log'),
            #logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description=(
            "Scrape MyNeta candidate detail pages using Selenium and write to JSON/CSV."
        )
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Candidate profile URL (e.g. https://www.myneta.info/bih2010/candidate.php?candidate_id=2140)",
    )
    parser.add_argument(
        "--out",
        default="candidate.json",
        help="Output JSON file for summary and tables (default: candidate.json)",
    )
    parser.add_argument(
        "--static",
        default="static",
        help="Directory where downloaded images (icons) should be saved (default: static)",
    )
    parser.add_argument(
        "--tables-dir",
        default=None,
        help=(
            "If provided, write the detailed tables (cases, assets, liabilities) "
            "to separate CSV files in this directory."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Maximum seconds to wait for page load (default: 45)",
    )
    parser.add_argument(
        "--wait-after",
        type=int,
        default=6,
        help="Additional seconds after page load to wait for JS (default: 6)",
    )
    args = parser.parse_args()
    logger.debug(f"Starting scrape for URL: {args.url}")
    data = scrape_candidate(
        url=args.url,
        static_dir=args.static,
        timeout=args.timeout,
        wait_after=args.wait_after,
    )
    write_json(data, args.out)
    if args.tables_dir:
        write_tables(data, args.tables_dir)
    logger.info(f"Data written to {args.out} and tables to {args.tables_dir if args.tables_dir else 'N/A'}")

if __name__ == "__main__":
    main()