import re

import polars as pl

# put regex here so its only compiled once
COLUMN_NAME_VALIDATOR_PATTERN = re.compile(r"[^a-zA-Z_./(/)/\-\\\d:]")

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    # This is limited. Currently looking for numbers starting
    # with a + or 0. Does not match decimals
    "phone": r"^(?:\+|0|\()[\d\s()+-]+$",
}

PII_PATTERN_EXPRESSIONS = [
    pl.col("value").cast(pl.Utf8).str.extract(pattern, 0).alias(f"match_{type}")
    for type, pattern in PII_PATTERNS.items()
]

# pii columns that are searched for when checking if sheets contain pii data
# keep these lowercase.
PII_COLUMN_NAMES = [
    # Names
    "first_name",
    "last_name",
    "middle_name",
    "full_name",
    "name",
    "participant_name",
    "respondent_name",
    "subject_name",
    "person_name",
    "given_name",
    "family_name",
    "primary_name",
    "secondary_name",
    "mother_name",
    "father_name",
    "guardian_name",
    "child_name",
    "nom",
    # Phone Numbers
    "phone",
    "phone_number",
    "phone_no",
    "telephone",
    "mobile",
    "mobile_number",
    "cell_phone",
    "contact_number",
    "home_phone",
    "work_phone",
    "emergency_contact_phone",
    "primary_phone",
    "secondary_phone",
    "whatsapp_number",
    "telegram_number",
    "contact",
    # Email Addresses
    "email",
    "email_address",
    "e_mail",
    "contact_email",
    "primary_email",
    "secondary_email",
    "personal_email",
    "work_email",
    # Physical Addresses
    "address",
    "street_address",
    "street",
    "house_number",
    "building_number",
    "apartment",
    "floor",
    "postal_address",
    "mailing_address",
    "residential_address",
    "current_address",
    "permanent_address",
    "previous_address",
    "home_address",
    "work_address",
    "neighbourhood",
    "voisinage",
    # 'unit'
    # City/Region/Country
    # 'city', 'town', 'village', 'municipality', 'district', 'county',
    # 'state', 'province', 'region', 'territory', 'zone', 'ward',
    # 'country', 'nation', 'country_code', 'iso_country_code',
    # 'postal_code', 'zip_code', 'postcode', 'postal_code_1', 'postal_code_2',
    # GPS Coordinates / Location
    "gps",
    "latitude",
    "longitude",
    "lat",
    "lng",
    "lon",
    "coordinates",
    "geo_coordinates",
    "gps_coordinates",
    "location",
    "geo_location",
    "geopoint",
    "_geopoint",
    "gps_location",
    "survey_location",
    "collection_point",
    "field_location",
    "site_location",
    "start_gps",
    "end_gps",
    "waypoint",
    "marker",
    "position",
    "geo",
    # KoboToolbox Specific Fields
    "_geopoint",  # '_start', '_end', '_submission_time', '_uuid',
    # '_xform_id_string', '_status', '_notes', '_index', '_total_media',
    # '_media_all_received', '_media_count', '_geolocation_accuracy',
    # '_geolocation_altitude', '_geolocation_precision',
    # Identification Numbers
    # 'id', 'identifier', 'identification_number', 'national_id',
    # 'ssn', 'social_security_number', 'tax_id', 'passport_number',
    # 'drivers_license', 'license_number', 'birth_certificate',
    # 'member_id', 'patient_id', 'student_id', 'employee_id',
    # 'case_id', 'reference_number', 'tracking_number',
    # Demographics (can be identifying in combination)
    "date_of_birth",
    "dob",
    "birth_date",  # 'age', 'gender', 'sex',
    # 'ethnicity', 'race', 'religion', 'marital_status', 'occupation',
    # 'employer', 'job_title', 'income', 'salary', 'household_size',
    # Other Personal Identifiers
    # 'biometric_data', 'fingerprint', 'face_recognition', 'dna_sample',
    # 'medical_record_number', 'insurance_number', 'policy_number',
    # 'account_number', 'bank_account', 'credit_card', 'iban',
    "ip_address",
    "device_id",
    "mac_address",
    "serial_number",
    "signature",
    # Others
    "audit",
]


def get_pii_columns() -> list[str]:
    """Expands the pii column list by readding items without _ characters.


    Returns:
        list[str]: _description_
    """
    existing_items = set(PII_COLUMN_NAMES)
    result = list(PII_COLUMN_NAMES)  # Start with a copy of the original list

    for item in PII_COLUMN_NAMES:
        if "_" in item:
            base_name = item.replace("_", "")

            if base_name not in existing_items:
                result.append(base_name)

    return result
