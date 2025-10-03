import csv
import os
import re

from bs4 import BeautifulSoup

all={}

def fetch_assets(row):
    #print(row)
    candidate_info={}
    try:
        assets_list = row.get_text().replace(u'\xa0',' ').split("~")
        #print(assets_list)
        candidate_info['quantity'] = assets_list[0].replace('Rs','').strip()
        candidate_info['words'] = assets_list[1].replace('+','').strip()
        return candidate_info
    except:
        return {'quantity':0, 'words':0}


def extract_and_save(file_name):
    html_data = ""
    with open("static/constituency_candidates_dump/"+file_name+".html", "r", encoding='utf-8') as file:
        html_data = file.read()

    soup = BeautifulSoup(html_data, 'html.parser')
    tables= soup.find_all('table')
    candidate_list_table=tables[4]
    rows = candidate_list_table.find_all('tr')[1:]
    candidates = []

    # Extracting information from the table
    for count, row_ele in enumerate(rows):
        row = row_ele.find_all('td')
        print(count)
        candidate_info = {}
        candidate_info['serial_number'] = count
        name_link= row[1].find('a')
        candidate_info['name'] = name_link.text.strip()
        candidate_info['nem_candidate_id'] = name_link.get('href').split('=')[1]
        candidate_info['party'] = row[2].get_text().strip()
        candidate_info['criminal_cases'] = row[3].get_text().strip()
        candidate_info['education'] = row[4].get_text().strip()
        candidate_info['age'] = row[5].get_text().strip()
        
        assets_list = fetch_assets(row[6])
        candidate_info['assets'] = assets_list.get('quantity')
        candidate_info['assets_in_words'] = assets_list.get('words')

        liabilities_list = fetch_assets(row[7])
        candidate_info['liabilities'] = liabilities_list.get('quantity')
        candidate_info['liabilities_in_words'] = liabilities_list.get('words')

        candidates.append(candidate_info)

    all[file_name]=candidates    
    fieldnames = candidates[0].keys()

    # Write the list of dictionaries to a CSV file
    with open('static/constituency_candidates_dump/data/'+file_name+'.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)
    print("done")


# loop all the files in static/constituency_candidates_dump directory and call the extract_and_save function with the path and file name combines
for filename in os.listdir('static/constituency_candidates_dump'):
    if filename.endswith(".html"):
        file=filename.replace('.html','')
        print(filename, end=" ")
        extract_and_save(file)
    else:
        continue

