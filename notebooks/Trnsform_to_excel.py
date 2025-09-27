import re
import pandas as pd
import os



# # CLEAN CODE VERSION 3.0


# import re
# import pandas as pd

# raw_text = """
# Day: Satureday
# Date: 09/21/2028
# Shift: Evening
# Tips:
# Diya:
# $50.51
# Simran: $ 35.21
# Rahul: $100
# Hrs:
# Diya:
# 9.5
# Simrom: 7.6
# Rahul 10.3
# """

# def preprocess_text(ocr_text: str) -> str:
#     """Clean raw OCR text into a normalized format."""
#     # Merge broken lines like "Day:\nFriday"
#     text = re.sub(r"Day:\s*\n\s*([A-Za-z]+)", r"Day=\1", ocr_text)
#     text = re.sub(r"Shift:\s*\n\s*([A-Za-z]+)", r"Shift=\1", text)
#     text = re.sub(r"Date:\s*\n\s*([0-9/]+)", r"Date=\1", text)

#     # Normalize separators
#     text = re.sub(r"\s*[:=]\s*", "=", text)
#     text = re.sub(r"\$", "", text)

#     # Ensure block formatting
#     text = re.sub(r"Tips=\s*", "Tips:\n", text)
#     text = re.sub(r"Hrs=\s*", "Hrs:\n", text)

#     # Collapse multiple newlines
#     return re.sub(r"\n+", "\n", text).strip()


# def text_to_table(text: str) -> pd.DataFrame:
#     """Convert normalized text into structured DataFrame."""
#     day = re.search(r"Day=(\w+)", text).group(1)
#     shift_match = re.search(r"Shift=([^\n]+)", text)
#     shift = shift_match.group(1) if shift_match else ""
#     date_match = re.search(r"Date=([^\n]+)", text)
#     date = date_match.group(1) if date_match else ""

#     # Extract blocks
#     tips_block = re.findall(r"Tips:\s*([\s\S]*?)Hrs:", text)
#     hrs_block = re.findall(r"Hrs:\s*([\s\S]*)", text)

#     tips, hrs = {}, {}

#     if tips_block:
#         for line in tips_block[0].splitlines():
#             if "=" in line:
#                 name, val = line.split("=")
#                 tips[name.strip()] = float(val.strip())

#     if hrs_block:
#         for line in hrs_block[0].splitlines():
#             if "=" in line:
#                 name, val = line.split("=")
#                 hrs[name.strip()] = float(val.strip())

#     # Build rows
#     rows = []
#     for name in tips.keys() | hrs.keys():
#         tips_val = tips.get(name, 0)
#         hrs_val = hrs.get(name, 0)
#         total_val = tips_val * 0.11 + ((hrs_val * 11) * 0.92)

#         rows.append({
#             "Day": day,
#             "Date": date,
#             "Shift": shift,
#             "Name": name,
#             "Tips": tips_val,
#             "Hrs": hrs_val,
#             "Total": round(total_val, 2)
#         })

#     return pd.DataFrame(rows)


# # Run pipeline
# clean_text = preprocess_text(raw_text)
# df = text_to_table(clean_text)

# print(clean_text)
# print(df)

# # Save to CSV
# df.to_csv("Resultant CSVs\output_TestCase3.csv", index=False)


#   PREPROCESSING TEXT CODE VERSION 4.0

# Robust name-unification fix (paste this entire script and run)
import re
import os
import pandas as pd
from rapidfuzz import process, fuzz

# -------------------------
# CONFIG
# -------------------------
VALID_NAMES = ["Diya", "Simran", "Rahul", "Ritu", "Emily", "Reema", "Sameed", "Richita"]
VALID_DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# thresholds (tune if needed)
ROSTER_MATCH_THRESHOLD = 70   # match raw name -> roster
MERGE_MATCH_THRESHOLD  = 75   # merge remaining names into canonicals

DEBUG = False  # set True to print mapping debug info

# -------------------------
# UTILITIES
# -------------------------
def to_float(s):
    if s is None: return 0.0
    s = str(s).strip()
    m = re.search(r"[-+]?\d*\.\d+|[-+]?\d+", s)
    return float(m.group(0)) if m else 0.0

def normalize_name_text(name: str) -> str:
    """Lowercase + remove non-letter characters for robust comparison."""
    if not name:
        return ""
    return re.sub(r"[^a-z]", "", name.lower())

# Precompute normalized roster mapping: norm -> canonical
ROSTER_NORM_MAP = { normalize_name_text(n): n for n in VALID_NAMES }
ROSTER_NORM_KEYS = list(ROSTER_NORM_MAP.keys())

def fuzzy_roster_match(name: str, threshold=ROSTER_MATCH_THRESHOLD):
    """Return canonical roster name if normalized fuzzy score >= threshold, else None."""
    if not name:
        return None
    norm = normalize_name_text(name)
    # If exact normalized key exists, return immediately
    if norm in ROSTER_NORM_MAP:
        return ROSTER_NORM_MAP[norm]
    # else run fuzzy on normalized keys
    if not ROSTER_NORM_KEYS:
        return None
    match = process.extractOne(norm, ROSTER_NORM_KEYS, scorer=fuzz.ratio)
    if match and match[1] >= threshold:
        return ROSTER_NORM_MAP[match[0]]
    return None

# -------------------------
# NAME UNIFICATION (robust)
# -------------------------
def unify_names(tips: dict, hrs: dict,
                roster_thresh=ROSTER_MATCH_THRESHOLD, merge_thresh=MERGE_MATCH_THRESHOLD):
    """
    1) Map raw names to roster canonical names where confident.
    2) For remaining names, try merging into mapped canonicals if similarity is high.
    3) If neither applies, treat name as its own canonical.
    Returns aggregated tips2, hrs2, and the mapping used.
    """
    all_names = list(dict.fromkeys(list(tips.keys()) + list(hrs.keys())))  # preserve order
    name_map = {}   # raw_name -> canonical_name

    # STEP A: map to roster where possible
    for raw in all_names:
        canon = fuzzy_roster_match(raw, threshold=roster_thresh)
        if canon:
            name_map[raw] = canon

    # STEP B: for remaining, try merging into existing canonicals (by similarity)
    existing_canonicals = set(name_map.values())
    for raw in all_names:
        if raw in name_map:
            continue
        norm_raw = normalize_name_text(raw)
        if existing_canonicals:
            # compare raw normalized name to normalized existing canonicals
            existing_norm_map = {normalize_name_text(c): c for c in existing_canonicals}
            best = process.extractOne(norm_raw, list(existing_norm_map.keys()), scorer=fuzz.ratio)
            if best and best[1] >= merge_thresh:
                name_map[raw] = existing_norm_map[best[0]]
                continue
        # else leave as its own canonical
        name_map[raw] = raw

    # STEP C: aggregate numeric values by canonical
    tips2 = {}
    for raw, val in tips.items():
        canon = name_map.get(raw, raw)
        tips2[canon] = tips2.get(canon, 0.0) + to_float(val)

    hrs2 = {}
    for raw, val in hrs.items():
        canon = name_map.get(raw, raw)
        hrs2[canon] = hrs2.get(canon, 0.0) + to_float(val)

    if DEBUG:
        print("RAW NAMES:", all_names)
        print("NAME MAP:")
        for k,v in name_map.items():
            print(f"  {k!r} -> {v!r}")
        print("AGGREGATED TIPS:", tips2)
        print("AGGREGATED HRS:", hrs2)

    return tips2, hrs2, name_map

# -------------------------
# PREPROCESS
# -------------------------
def preprocess_text(ocr_text: str) -> str:
    text = ocr_text
    text = re.sub(r"Day:\s*\n\s*([A-Za-z]+)", r"Day=\1", text, flags=re.IGNORECASE)
    text = re.sub(r"Shift:\s*\n\s*([A-Za-z]+)", r"Shift=\1", text, flags=re.IGNORECASE)
    text = re.sub(r"Date:\s*\n\s*([0-9/]{6,20})", r"Date=\1", text, flags=re.IGNORECASE)

    text = re.sub(r"\s*[:=]\s*", "=", text)
    text = re.sub(r"\$", "", text)

    # handle collapsed patterns like Tips=Diya=50.51 -> place under Tips block
    text = re.sub(r"(?i)Tips=([^=\n]+)=([\d.]+)", r"Tips:\n\1=\2", text)
    text = re.sub(r"(?i)Hrs=([^=\n]+)=([\d.]+)", r"Hrs:\n\1=\2", text)

    text = re.sub(r"(?i)Tips=\s*", "Tips:\n", text)
    text = re.sub(r"(?i)Hrs=\s*", "Hrs:\n", text)

    text = re.sub(r"\n+", "\n", text).strip()
    return text

# -------------------------
# PARSE -> DATAFRAME
# -------------------------
def text_to_table(text: str) -> pd.DataFrame:
    day = (re.search(r"Day=([^\n]+)", text, flags=re.IGNORECASE).group(1).strip()
           if re.search(r"Day=([^\n]+)", text, flags=re.IGNORECASE) else "")
    date = (re.search(r"Date=([^\n]+)", text, flags=re.IGNORECASE).group(1).strip()
           if re.search(r"Date=([^\n]+)", text, flags=re.IGNORECASE) else "")
    shift = (re.search(r"Shift=([^\n]+)", text, flags=re.IGNORECASE).group(1).strip()
            if re.search(r"Shift=([^\n]+)", text, flags=re.IGNORECASE) else "")

    tips_block = re.findall(r"(?i)Tips:\s*([\s\S]*?)Hrs:", text)
    hrs_block  = re.findall(r"(?i)Hrs:\s*([\s\S]*)", text)

    tips_raw = {}
    hrs_raw = {}

    if tips_block:
        # find all name=value pairs (multiple per line allowed)
        kvs = re.findall(r"([A-Za-z][A-Za-z\s]{0,30})\s*=\s*([0-9]+(?:\.[0-9]+)?)", tips_block[0])
        for name, val in kvs:
            tips_raw[name.strip()] = to_float(val)

    if hrs_block:
        kvs = re.findall(r"([A-Za-z][A-Za-z\s]{0,30})\s*=\s*([0-9]+(?:\.[0-9]+)?)", hrs_block[0])
        for name, val in kvs:
            hrs_raw[name.strip()] = to_float(val)

    # unify similar names -> mapping & aggregated dicts
    tips2, hrs2, name_map = unify_names(tips_raw, hrs_raw)

    rows = []
    for name in sorted(set(list(tips2.keys()) + list(hrs2.keys()))):
        tips_val = tips2.get(name, 0.0)
        hrs_val  = hrs2.get(name, 0.0)
        total_val = tips_val * 0.11 + ((hrs_val * 11) * 0.92)
        rows.append({
            "Day": day,
            "Date": date,
            "Shift": shift,
            "Name": name,
            "Tips": round(tips_val, 2),
            "Hrs": round(hrs_val, 2),
            "Total": round(total_val, 2)
        })
    return pd.DataFrame(rows)

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    raw_text = """
    Day: Satureday
    Date: 09/21/2028
    Shift: Evening
    Tips:
    Diya:
    $50.51
    Simran: $35.21
    Rahul: $100
    Hrs:
    Diya:
    9.5
    Simrom: 7.6
    Rahul 10.3
    """

    clean_text = preprocess_text(raw_text)
    df = text_to_table(clean_text)

    print(clean_text)
    print(df)

    output_folder = "Resultant CSVs"
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, "output_TestCase4.csv")
    df.to_csv(output_path, index=False)
    print("Saved:", output_path)
