import logging
import inflect
p = inflect.engine()

# function for Name
def describe_name(name):
    name=str(name)
    return f' Candidate name: <prosody rate="slow">{name}</prosody><mark name="name"/>'

# function for party
def describe_party_affiliation(party_abb, party_name):
    party_name=str(party_name if len(party_name) > len(party_abb) else party_abb)
    if party_abb in party_name:
        party_name = party_name.replace('('+party_abb+')',"")
    
    if party_name.lower() == 'independent':
        return ', is an Independent candidate <mark name="party"/>'
    elif 'party' in party_name.lower():
        return f', is a member of the {party_name} <mark name="party"/>'  
    else:
        return f', is a member of the {party_name} party <mark name="party"/>'

def describe_constituency(constituency):
    constituency=str(constituency)
    return f', is contesting for {constituency} seat<mark name="constituency"/>'
    
# function for age
def describe_age(age):
    age=str(age)
    return f', at the age of {age}<mark name="age"/>'


# function for education 
def describe_education(education_level):
    
    education_level=str(education_level)
    education_descriptions = {
        'Doctorate': ', holds a Doctorate degree<mark name="education"/>',
        'Graduate': ', holds a Graduate degree<mark name="education"/>',
        'Post Graduate': ', holds a Post Graduate degree <mark name="education"/>',
        '10th Pass': ', has completed secondary education<mark name="education"/>',
        '12th Pass': ', has completed higher secondary education<mark name="education"/>',
        'Graduate Professional': ', is a Graduate Professional<mark name="education"/>',
        '5th Pass': ', with primary education<mark name="education"/>',
        '8th Pass': ', has completed middle school<mark name="education"/>',
        'Others': ', has other educational qualifications<mark name="education"/>',
        'Illiterate': ', is illiterate<mark name="age"/>',
        'Literate': ',  is literate but with unspecified formal education<mark name="education"/>',
        'Not Given': ', has unspecified educational background<mark name="education"/>'
    }
    return education_descriptions.get(education_level, ' <mark name="education"/>')



# function for criminal_cases 
def describe_criminal_cases(cases):

    try:
        num_cases = int(cases)
    except ValueError:
        return ', with an unknown legal standing<mark name="criminal_cases"/> '
    if num_cases == 0:
        return ', with no criminal cases on record<mark name="criminal_cases"/>'
    elif num_cases == 1:
        return ', with 1 criminal case on record<mark name="criminal_cases"/>'
    else:
        return f', <google:style name="apologetic">with {num_cases} criminal cases on record</google:style><mark name="criminal_cases"/>'

    

# function for assets,assets_in_words,liabilities,liabilities_in_words
def convert_money_to_words(amount_words, amount_numeric, amount_type):
    # none, NAN and 0 checks 
    amount_type=str(amount_type)
    if amount_words and not str(amount_words).replace(' ', '').isdigit() and str(amount_words) != 'nan':
        amount_in_words = amount_words
    else:
        amount = int(amount_numeric.replace(',', ''))
        if amount == 0:
            return f', no declared {amount_type} <mark name="{amount_type}"/>'
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
        return f', declared assets valued at {amount_in_words} <mark name="{amount_type}"/>'
    elif amount_type.lower() == 'liabilities':
        return f', declared liabilities amounting to {amount_in_words} <mark name="{amount_type}"/>'
    else:
        return f', declared {amount_in_words} of {amount_type} <mark name="{amount_type}"/>'


def generate_candidate_audio_strings(row):
    # change this to a beter patter
    
    text_parts ={
        "name": describe_name(row['name']),
        "party": describe_party_affiliation(row['party'],row['party_name']),
        "age": describe_age(row['age']),
        "constituency": describe_constituency(row['constituency']),
        "education": describe_education(row['education']),
        "criminal_cases": describe_criminal_cases(row['criminal_cases']),
        "assets": convert_money_to_words(row['assets_in_words'], row['assets'], 'assets'),
        #check for nan in the data. 
        "liabilities": convert_money_to_words(row['liabilities_in_words'], row['liabilities'], 'liabilities'),
    }
    
    logging.debug(str(text_parts))
    return text_parts

