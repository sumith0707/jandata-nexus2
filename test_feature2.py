from processing.schema_mapper import map_columns_with_gemini


headers = [
    "District",
    "Government Hospitals",
    "Beds",
    "Doctors",
    "Nurses",
]

sample_rows = [
    ["Bagalkot", "12", "450", "75", "120"],
    ["Bangalore Urban", "25", "1200", "210", "350"],
    ["Mysuru", "18", "800", "140", "250"],
]


mapping = map_columns_with_gemini(
    headers,
    sample_rows,
)


print("\n========== FEATURE 2 TEST ==========")
print("Entity column:", mapping["_entity_column"])
print("Entity type:", mapping["_entity_type"])
print("Entity confidence:", mapping["_entity_type_confidence"])
print("Domain:", mapping["_domain"])
print("Domain confidence:", mapping["_domain_confidence"])
print("====================================")