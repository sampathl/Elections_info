# fetches data from myneta.info and saves it in a file using a list of constituency ids.
import ast
import time
import requests
import re
from bs4 import BeautifulSoup
import os 


path= '/Users/saml16/projects/Elections_info/static/'
constituency_path =path+"consituency_list.csv"
output_path = path+"constituency_candidates_dump/"

# Read the saved HTML file
constituency_id = []
with open(constituency_path, "r", encoding='utf-8') as file:
    constituency_id_string = file.read()

constituency_id = ast.literal_eval(constituency_id_string)


for id in constituency_id:
    r = requests.get("https://www.myneta.info/LokSabha2019/index.php?action=show_candidates&amp;constituency_id="+str(id))
    r.content
    soup = BeautifulSoup(r.content, 'html.parser')
    title = soup.find('title').text
    titles = title.split(":")
    if len(titles) > 1:
        title = titles[1]
    name = output_path+str(id)+"_"+str(title)+".html"
    with open( name, "w", encoding='utf-8') as file :
        file.write(str(soup.prettify()))
    time.sleep(20)
    print("Done for id: "+ str(id))