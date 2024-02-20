import re
from bs4 import BeautifulSoup
import requests

# Make a request to the website
"""r = requests.get("https://www.myneta.info/LokSabha2019/")
r.content

# Use the 'html.parser' to parse the page
soup = BeautifulSoup(r.content, 'html.parser')

with open("static/LokSabha2019.html", "w", encoding='utf-8') as file:
    file.write(str(soup.prettify()))
"""
# Print the parsed data of html
#print(soup.prettify())
# Read the saved HTML file
html_data = ""
with open("static/LokSabha2019.html", "r", encoding='utf-8') as file:
    html_data = file.read()

# Process the HTML data
# Add your code here to extract the desired information from the HTML data
# For example, you can use BeautifulSoup to parse the HTML and extract specific elements

# Assuming 'html_doc' is your HTML document
soup = BeautifulSoup(html_data, 'html.parser')

# Use a regular expression to match ids with a certain pattern
pattern = re.compile('item_\\d+')

# Find all elements with an id that matches the pattern
matching_elements = [element for element in soup.find_all(id=pattern)]

id=[]
# Print the ids of the matching elements
for element in matching_elements:
    id.append(element['id'])
print(id)

with open('static/consituncy.html', 'w', encoding='utf-8') as file:
    file.write(str(matching_elements))

with open('static/consituncy_id.html', 'w', encoding='utf-8') as file:
    file.write(str(id))
