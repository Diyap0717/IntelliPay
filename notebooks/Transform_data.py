# Transform_to_excel_2.py  (refactored for import)
# single-file OCR -> CSV pipeline
# - Normalizes any "Name ... Number" pattern into Name=Number (same-line or next-line)
# - Handles Tips and Hrs sections
# - Keeps fuzzy-name canonicalization (merge Simrom -> Simran)
# - Writes CSV to "Resultant CSVs/output.csv"

import re
import os
import pandas as pd
from rapidfuzz import process, fuzz

# ============================================================
# 1) CONFIG / THRESHOLDS / ROSTER
# ============================================================
VALID_NAMES = ["Diya", "Simran", "Rahul", "Ritu", "Emily", "Reema", "Sameed", "Richita", "Maya", "Fam","Riddhi", "Samantha", "Zarin","Paulina"]
VALID_DAYS  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ROSTER_MATCH_THRESHOLD = 70   # map raw -> roster if score >= this
MERGE_MATCH_THRESHOLD  = 75   # merge remaining raw names into existing canonicals if similar

OUTPUT_FOLDER = "Resultant CSVs"
OUTPUT_FILENAME = "output_TestCase6.csv"

# ============================================================
# 2) UTILITIES
# ============================================================
def to_float_from_string(s: str) -> float:
    """Return first reasonable numeric substring as float, else 0.0.
       Accepts '.' or ',' as decimal separator."""
    if s is None:
        return 0.0
    s = str(s)
    # replace common OCR noise for decimal comma
    s = s.replace(",", ".")
    # find first float or integer
    m = re.search(r"[-+]?\d*\.\d+|[-+]?\d+", s)
    return float(m.group(0)) if m else 0.0

def normalize_name_text(name: str) -> str:
    """Lowercase + remove non-letter characters for stable comparison."""
    if not name:
        return ""
    return re.sub(r"[^a-z]", "", name.lower())

# precompute normalized roster mapping
ROSTER_NORM_MAP = { normalize_name_text(n): n for n in VALID_NAMES }
ROSTER_NORM_KEYS = list(ROSTER_NORM_MAP.keys())

def fuzzy_roster_match(raw_name: str, threshold=ROSTER_MATCH_THRESHOLD):
    """Try to map raw_name -> roster canonical using normalized fuzzy match."""
    if not raw_name:
        return None
    norm = normalize_name_text(raw_name)
    if norm in ROSTER_NORM_MAP:
        return ROSTER_NORM_MAP[norm]
    # fuzzy match against normalized keys
    match = process.extractOne(norm, ROSTER_NORM_KEYS, scorer=fuzz.ratio)
    if match and match[1] >= threshold:
        return ROSTER_NORM_MAP[match[0]]
    return None

# ============================================================
# 3) SECTION DETECTION (Tips / Hrs)
# ============================================================
def find_section_indices(lines):
    """Return (tips_idx, hrs_idx) of header lines in list of lines. -1 if not found."""
    tips_idx = -1
    hrs_idx  = -1
    for i, ln in enumerate(lines):
        token = re.sub(r"[^A-Za-z]", "", ln).lower()
        if token and process.extractOne(token, ["tips","tip"], scorer=fuzz.ratio)[1] >= 80:
            tips_idx = i
        if token and process.extractOne(token, ["hrs","hours","hrs","has","hus"], scorer=fuzz.ratio)[1] >= 75:
            hrs_idx = i
    return tips_idx, hrs_idx

# ============================================================
# 4) PARSING RULE: NAME → NEAREST NUMBER (same or next line)
# ============================================================
def parse_name_number_pairs(lines):
    """
    Given a list of lines for a section, return dict {name: value}
    This follows the rule: whenever we encounter a name token, bind it to nearest numeric token
    (same line or following lines). Handles multiple pairs on same line.
    """
    pairs = {}
    pending_name = None

    for raw in lines:
        ln = raw.strip()

        if not ln:
            continue

        # Normalize common OCR punctuation that breaks parsing
        ln_clean = ln.replace(":", " ").replace("=", " ").replace("$", "").replace("!", "").strip()

        # 1) If line contains one or more explicit name=number patterns (or name number),
        #    extract all such pairs directly.
        kv_pairs = re.findall(r"([A-Za-z][A-Za-z\s']{0,30})\s*(?:[:=]|\b)\s*([0-9]+(?:[.,][0-9]+)?)", ln_clean)
        if kv_pairs:
            for name_raw, num_raw in kv_pairs:
                name = name_raw.strip()
                val = to_float_from_string(num_raw)
                pairs[name] = pairs.get(name, 0.0) + val
            pending_name = None
            continue

        # 2) If line contains both a name-like token and a stray numeric token separated by spaces
        #    e.g. "Rahul 10.3" or "Diya  50.51"
        tokens = ln_clean.split()
        # find all numeric tokens in line
        numeric_tokens = [t for t in tokens if re.search(r"\d", t)]
        name_tokens = [t for t in tokens if re.search(r"[A-Za-z]", t)]

        if name_tokens and numeric_tokens:
            # assume first name token + first numeric token is a pair
            name = name_tokens[0]
            val  = to_float_from_string(numeric_tokens[0])
            pairs[name] = pairs.get(name, 0.0) + val
            pending_name = None
            continue

        # 3) If line contains only a number (e.g. "$ 9.5" on its own line), attach to pending_name.
        only_number = re.fullmatch(r"[^\d\-+]*(?:[-+]?\d*\.\d+|[-+]?\d+)[^\d\-+]*", ln_clean)
        if only_number and pending_name:
            val = to_float_from_string(ln_clean)
            pairs[pending_name] = pairs.get(pending_name, 0.0) + val
            pending_name = None
            continue

        # 4) If line looks like a name-only line (e.g., "Maya" or "Diya:"), set pending_name.
        name_only = re.fullmatch(r"[A-Za-z][A-Za-z\s']{0,30}", ln_clean)
        if name_only:
            pending_name = ln_clean.strip()
            continue

        # 5) If nothing matched, try to salvage: if there's a numeric substring, and a word substring, bind them.
        word_match = re.search(r"([A-Za-z][A-Za-z\s']{0,30})", ln_clean)
        num_match  = re.search(r"([-+]?\d*\.\d+|[-+]?\d+)", ln_clean)
        if word_match and num_match:
            name = word_match.group(1).strip()
            val  = to_float_from_string(num_match.group(0))
            pairs[name] = pairs.get(name, 0.0) + val
            pending_name = None
            continue

        # otherwise ignore the line (noise)
        pending_name = None

    return pairs

# ============================================================
# 5) NAME UNIFICATION (fuzzy; maps similar raw names -> canonical)
# ============================================================
def unify_names(tips_raw: dict, hrs_raw: dict):
    """Map raw names to canonical roster names (if possible) and merge duplicates."""
    all_names = list(dict.fromkeys(list(tips_raw.keys()) + list(hrs_raw.keys())))
    name_map = {}

    # Step A: map to roster
    for raw in all_names:
        mapped = fuzzy_roster_match(raw)
        if mapped:
            name_map[raw] = mapped

    # Step B: for remaining, try merging into already-mapped canonicals
    canonicals = set(name_map.values())
    for raw in all_names:
        if raw in name_map:
            continue
        if canonicals:
            # compare normalized raw to normalized canonicals
            canon_norm_map = { normalize_name_text(c): c for c in canonicals }
            norm_raw = normalize_name_text(raw)
            best = process.extractOne(norm_raw, list(canon_norm_map.keys()), scorer=fuzz.ratio)
            if best and best[1] >= MERGE_MATCH_THRESHOLD:
                name_map[raw] = canon_norm_map[best[0]]
                continue
        # else keep raw as its own canonical
        name_map[raw] = raw

    # Aggregate values
    tips2 = {}
    for raw, val in tips_raw.items():
        canon = name_map.get(raw, raw)
        tips2[canon] = tips2.get(canon, 0.0) + to_float_from_string(val)

    hrs2 = {}
    for raw, val in hrs_raw.items():
        canon = name_map.get(raw, raw)
        hrs2[canon] = hrs2.get(canon, 0.0) + to_float_from_string(val)

    return tips2, hrs2, name_map

# ============================================================
# 6) DRIVER: normalize text -> parse pairs -> unify -> dataframe
# ============================================================
def pipeline_from_raw_text(raw_text: str) -> pd.DataFrame:
    # normalize line endings & strip extra whitespace
    txt = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"\t", " ", txt)
    # collapse repeated spaces but preserve single spaces (helps tokenization)
    txt = re.sub(r"[ \t]+", " ", txt)
    # split into clean lines
    lines = [ln.strip() for ln in txt.splitlines()]

    # find Tips and Hrs section indices
    tips_idx, hrs_idx = find_section_indices(lines)

    # define slices
    tips_lines = []
    hrs_lines  = []
    if tips_idx >= 0 and hrs_idx >= 0:
        if tips_idx < hrs_idx:
            # Tips come first
            tips_lines = lines[tips_idx+1:hrs_idx]
            hrs_lines  = lines[hrs_idx+1:]
        else:
            # Hrs come first
            hrs_lines  = lines[hrs_idx+1:tips_idx]
            tips_lines = lines[tips_idx+1:]
    elif tips_idx >= 0:
        tips_lines = lines[tips_idx+1:]
        hrs_lines  = []
    elif hrs_idx >= 0:
        hrs_lines  = lines[hrs_idx+1:]
        tips_lines = []
    else:
        # No headers, fallback
        tips_lines = lines
        hrs_lines  = []

    # parse name-number pairs per section using general rule
    tips_raw = parse_name_number_pairs(tips_lines)
    hrs_raw  = parse_name_number_pairs(hrs_lines)

    # unify similar names (fuzzy)
    tips2, hrs2, name_map = unify_names(tips_raw, hrs_raw)

    # metadata extraction (Day, Date, Shift) using simple regex search on whole text
    day_match   = re.search(r"Day[:=]?\s*([A-Za-z]+)", raw_text, flags=re.IGNORECASE)
    date_match  = re.search(r"Date[:=]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})", raw_text, flags=re.IGNORECASE)
    shift_match = re.search(r"Shift[:=]?\s*([A-Za-z]+)", raw_text, flags=re.IGNORECASE)

    day   = day_match.group(1).strip() if day_match else ""
    date  = date_match.group(1).strip() if date_match else ""
    shift = shift_match.group(1).strip() if shift_match else ""

    # build dataframe
    rows = []
    for name in sorted(set(list(tips2.keys()) + list(hrs2.keys()))):
        tips_val = round(tips2.get(name, 0.0), 2)
        hrs_val  = round(hrs2.get(name, 0.0), 2)
        ans = (hrs_val * 11) + (tips_val * 0.97)
        total_val = round(ans * 0.92, 2)
        rows.append({"Day": day, "Date": date, "Shift": shift,
                     "Name": name, "Tips": tips_val, "Hrs": hrs_val, "Total": total_val})

    df = pd.DataFrame(rows)
    return df

# ============================================================
# 7) SAVE / APPEND UTILITY (keeps original save behavior)
# ============================================================
def save_df_to_output(df: pd.DataFrame, output_folder: str = OUTPUT_FOLDER, output_filename: str = OUTPUT_FILENAME) -> str:
    """
    Save (append) a dataframe to the configured CSV output.
    Returns the final out_path string.
    """
    print(">>> save_df_to_output CALLED with rows:", len(df))   # ✅ Debug line
    ...

    os.makedirs(output_folder, exist_ok=True)
    out_path = os.path.join(output_folder, output_filename)

    # If file exists → append without header
    if os.path.exists(out_path):
        df.to_csv(out_path, mode="a", header=False, index=False)
    else:
        # If file doesn't exist → create new with header
        df.to_csv(out_path, mode="w", header=True, index=False)

    print("Appended results to:", out_path)
    return out_path

def update_excel_with_text(raw_text: str) -> str:
    """
    Convenience wrapper: run pipeline_from_raw_text on raw_text and append result to CSV.
    Returns out_path (the file that was appended/created).
    """
    df = pipeline_from_raw_text(raw_text)
    out_path = save_df_to_output(df)
    return out_path

# ============================================================
# 8) MAIN (example usage preserved but protected by __main__)
# ============================================================
if __name__ == "__main__":
    raw_text = """
   Day: Wednesday
Date: 07/09/2025
Shift: Evening
Tips:
Diya
$170.05
Zarin: $65.06
Hrs:
Diya: 8.3
Zasin: 7.6
    """

    df = pipeline_from_raw_text(raw_text)
    print(df)
    # save result (same behavior as before)
    out_path = save_df_to_output(df)
    print("Appended results to:", out_path)
