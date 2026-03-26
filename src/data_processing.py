import re
import pandas as pd
import os

city_file_path = os.path.join(os.path.dirname(__file__), "staedte_osm.txt")
with open(city_file_path, "r", encoding="utf-8") as f:
    all_cities = set(f.read().splitlines())


def parse_study_subjects(dataframe: pd.DataFrame):
    if dataframe.empty:
        return "", [], []
        
    table_type = dataframe["uni"].iloc[0] if len(dataframe) > 0 and pd.notna(dataframe["uni"].iloc[0]) else ""

    cities = []
    subjects = []
    current_span = []
    
    for idx, entry in enumerate(dataframe["uni"].iloc[1:]):
        if bool(entry) and pd.notna(entry) and entry.strip() != "":
            cities.append(entry)
            if current_span:
                subjects.append(current_span)
                current_span = []
        
        subj = dataframe["subject"].iloc[idx + 1]
        if pd.notna(subj):
            current_span.append(subj)
        else:
            current_span.append("")

    if current_span:
        subjects.append(current_span)

    return table_type, cities, subjects


def process_city(original_city: str) -> tuple[str, str, bool]:
    if not isinstance(original_city, str):
        return "", "<UNKNOWN>", False
        
    city_name = original_city.strip()

    # Parse City name
    multi_word_prefixes = [
        r'^(Bad\s\w+)',               # Bad + next word
        r'^(St\.\s\w+)',              # St. + next word
        r'^(St\s\w+)',                # St + next word
        r'^(\w+\sam\s\w+)',           # Word + am + Word
        r'^(\w+\san\sder\s\w+)',      # Word + an der + Word
        r'^(\w+\sim\s\w+)',           # Word + im + Word
        r'^(\w+\s\/\s\w+)',           # Word / Word
    ]

    for pattern in multi_word_prefixes:
        match = re.search(pattern, city_name, flags=re.IGNORECASE)
        if match:
            processed_city = match.group(1).strip()

    processed_city = city_name.split(' ', 1)[0]

    city_confirmed = processed_city in all_cities

    # Parse university type

    university_type_map = {
        "U" : "Universität",
        "FH": "Fachhochschule",
        "HS": "Hochschule",
        "PH": "Pädagogische Hochschule",
        "TU": "Technische Universität",
        "TH": "Technische Hochschule",
        "FU": "Freie Universität",
        "KHS": "Kunsthochschule",
        "KMH": "Kunst-/Musikhochschule",
        "HfK": "Hochschule für Künste",
        "HfM": "Hochschule für Musik",
        "MHS": "Musikhochschule",
        "DH": "Duale Hochschule",
        "HAW": "Hochschule für Angewandte Wissenschaften",
        "BA": "Berufsakademie"
    }

    university_type_pattern = r'\(?[A-Z]([a-z]*\/?[A-Z][a-z]*)*\)?[\s,]'
    residual_string = city_name.replace(processed_city, "")
    match = re.search(university_type_pattern, residual_string)
    if match:
        university_type = match.group(1)
        if university_type in university_type_map:
            university_type = university_type_map[university_type] + f" ({university_type})"
    else:
        university_type = "<UNKNOWN>"

    return processed_city, university_type, city_confirmed
   

def process_subject(subject_str):
    if not isinstance(subject_str, str) or not subject_str:
        return ""

    match = re.search(
        r'(.*?)(?:,?\s*(?:Master|Bachelor|Diplom|Bsc|Msc|Of\sScience|Of\sEngineering|M\.Sc\.|B\.Sc\.|M\.Eng\.|B\.Eng\.|LL\.M\.|LL\.B\.|Magister|Promotion|Aufbaustudium|Zertifikatsstudium))',
        subject_str,
        re.IGNORECASE
    )

    if match:
        cleaned_subject = match.group(1).strip()
    else:
        cleaned_subject = subject_str.split(',', 1)[0].strip()

    if cleaned_subject and cleaned_subject[-1] in [',', ';', ':']:
        cleaned_subject = cleaned_subject[:-1].strip()

    return cleaned_subject
