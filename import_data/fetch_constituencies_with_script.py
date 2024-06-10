from requests_html import AsyncHTMLSession
import asyncio
import pandas as pd
import time
from selenium import webdriver


fetched_constituencies_ids_file_path = '/Users/saml16/projects/Elections_info/static/lok_sabha_2024/constituency_list.csv'
static_path = '/Users/saml16/projects/Elections_info/static/lok_sabha_2024'
constituency_list_file_path = static_path + '/constituency_list.csv'
phase = '/phase_2'
constituency_folder_path = static_path + phase + '/constituency_html_dump/'
constituency_links_file_path = static_path + phase + '/constituency_links_list.csv'

failed = []

async def fetch_and_save_content(name, url, constituency_id):
   # Set up the webdriver
        driver = webdriver.Firefox()  # or webdriver.Chrome(), depending on your browser

        # Open the HTML file
        driver.get(url)

        # Save the page source
        page_source = driver.page_source

        # Write the page source to a new HTML file

        # Close the driver
        driver.quit()
        # Save the fully rendered HTML content to a file
        with open(name, 'w', encoding='utf-8') as f:
            f.write(page_source)
        
        driver.quit()
        print("Saved for id:", constituency_id)


async def fetch_constituency_html(constituency_ids, output_path):
    # Fetch already fetched constituency ids
    fetched_constituencies = pd.read_csv(fetched_constituencies_ids_file_path)
    fetched_constituencies_ids = set(fetched_constituencies['constituency_ids'])

    for constituency_id in constituency_ids:
        if int(constituency_id) not in fetched_constituencies_ids and int(constituency_id) != 0:
            url = "https://www.myneta.info/LokSabha2024/index.php?action=show_candidates&constituency_id=" + str(constituency_id)
            name = output_path + str(constituency_id) + ".html"

            await fetch_and_save_content(name, url, constituency_id)
            fetched_constituencies_ids.add(constituency_id)
            time.sleep(1)
            print("Done for id:", constituency_id)
            
        else:
            print("Skipping for fetched id:", constituency_id)

    pd.DataFrame(list(fetched_constituencies_ids), columns=['constituency_ids']).to_csv(fetched_constituencies_ids_file_path, index=False)

check = pd.read_csv(constituency_links_file_path)

loop = asyncio.get_event_loop()
loop.run_until_complete(fetch_constituency_html(check['constituency_id'], constituency_folder_path))
loop.close()
