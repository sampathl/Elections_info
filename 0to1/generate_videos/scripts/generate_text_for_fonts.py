import logging
import inflect
p = inflect.engine()

def text_for_criminal_cases(cases):
    try:
        num_cases = int(cases)
    except ValueError:
        return 'Unknown'
    if num_cases == 0:
        return '0 Criminal'
    else:
        return f'{num_cases} Criminal'

    
# function for assets,assets_in_words,liabilities,liabilities_in_words
def convert_money_to_text(amount_words, amount_numeric, amount_type):
    amount_type=str(amount_type)
    if amount_words and not str(amount_words).replace(' ', '').isdigit() and str(amount_words) != 'nan':
        amount_in_words = amount_words
    else:
        amount = int(amount_numeric.replace(',', ''))
        if amount == 0:
            return f'0'
        amount_words = p.number_to_words(amount)
        if 'crore' in amount_words.lower():
            unit = 'crore'
        elif 'lakh' in amount_words.lower() or 'lac' in amount_words.lower():
            unit = 'lakh'
        elif 'thou' in amount_words.lower() or 'thous' in amount_words.lower():
            unit = 'thousand'
        else:
            unit = ''
        if unit:
            amount_words = p.plural(unit, amount)
    if amount_type.lower() == 'assets':
        return f'{amount_in_words}'
    elif amount_type.lower() == 'liabilities':
        return f'{amount_in_words}'
    else:
        return f' '
    

def generate_candidate_video_text(row):
    # change this to a beter patter
    text_parts ={
        "name": str(row['name']),
        "party": str(row['party']),
        "age": str(row['age']),
        "constituency": str(row['constituency']),
        "education": str(row['education']),
        "criminal_cases": text_for_criminal_cases(row['criminal_cases']),
        "assets": convert_money_to_text(row['assets_in_words'], row['assets'], 'assets'),
        #check for nan in the data. 
        "liabilities": convert_money_to_text(row['liabilities_in_words'], row['liabilities'], 'liabilities'),
    }
    logging.debug(str(text_parts))
    return text_parts
