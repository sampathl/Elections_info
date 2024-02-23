import pandas as pd
import inflect

# Initialize the inflect engine
p = inflect.engine()

def describe_party_affiliation(party_name):
    if party_name.lower() == 'independent':
        return "an Independent candidate"
    elif 'party' in party_name.lower():
        return f"a member of the {party_name}"
    else:
        return f"a member of the {party_name} Party"

def describe_criminal_cases(cases):
    try:
        num_cases = int(cases)
    except ValueError:
        return "with an unknown legal standing"
    if num_cases == 0:
        return "with no criminal cases on record"
    elif num_cases == 1:
        return "with 1 criminal case on record"
    else:
        return f"with {num_cases} criminal cases on record"

def describe_education(education_level):
    education_descriptions = {
        'Doctorate': "who holds a Doctorate degree",
        'Graduate': "a Graduate",
        'Post Graduate': "with a Post Graduate degree",
        '10th Pass': "who has completed secondary education (10th standard)",
        '12th Pass': "who has completed higher secondary education (12th standard)",
        'Graduate Professional': "a Graduate Professional",
        '5th Pass': "with primary education (5th standard)",
        '8th Pass': "who has completed middle school (8th standard)",
        'Others': "with other educational qualifications",
        'Illiterate': "who is illiterate",
        'Literate': "who is literate but with unspecified formal education",
        'Not Given': "with unspecified educational background"
    }
    return education_descriptions.get(education_level, "with an unspecified level of education")

def convert_to_words(amount_in_words, amount_numeric, amount_type):
    if amount_in_words and not amount_in_words.replace(' ', '').isdigit():
        amount_words = amount_in_words
    else:
        amount = int(amount_numeric.replace(',', ''))
        if amount == 0:
            return f"no {amount_type}"
        amount_words = p.number_to_words(amount)
    if 'crore' in amount_words.lower():
        unit = 'crore'
    elif 'lakh' in amount_words.lower() or 'lac' in amount_words.lower():
        unit = 'lakh'
    else:
        unit = ''
    if unit:
        amount_words = p.plural(unit, amount)
    if amount_type.lower() == 'assets':
        return f"assets valued at {amount_words}"
    elif amount_type.lower() == 'liabilities':
        return f"liabilities amounting to {amount_words}"
    else:
        return f"{amount_words}"

def process_candidate_data(row):
    text_parts = [
        describe_party_affiliation(row['party']),
        describe_criminal_cases(row['criminal_cases']),
        f"at the age of {row['age']}",
        describe_education(row['education']),
        convert_to_words(row['assets_in_words'], row['assets'], 'assets'),
        convert_to_words(row['liabilities_in_words'], row['liabilities'], 'liabilities')
    ]
    return f"{row['name']}, " + ", ".join(text_parts) + "."

def process_dataset(filename, output_filename):
    data = pd.read_csv(filename)
    summaries = [process_candidate_data(row) for index, row in data.iterrows()]

    with open(output_filename, 'w') as f:
        for summary in summaries:
            f.write(summary + '\n\n')

# Example usage
input_csv = 'path_to_your_file.csv'  # Update this to the path of your CSV file
output_txt = 'candidate_summaries.txt'
process_dataset(input_csv, output_txt)
