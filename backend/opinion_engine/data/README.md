# ECHO — Demographic Data Files

This directory contains region-scoped sociological configuration files used by the ECHO opinion dynamics engine.

## Directory Structure

```
data/
  india/
    religions.json   — Religious groups, dogma vectors, friction matrix (India, 4 groups)
    economics.json   — Economic classes, class anxiety, conditional religion matrix (India, Precariat model)
```

## Adding a New Region

1. Create a new subfolder: `data/<region_name>/`
2. Copy `india/religions.json` and `india/economics.json` into it.
3. Update all demographic weights, matrices, and group names to reflect the target region.
4. In `server.py`, change the `DATA_REGION` constant (or pass the region as a config parameter) to point to the new folder.

## Adding a New Economic Class Model

Edit `<region>/economics.json` only — no Python changes needed:
- Add/remove entries in `"classes"` array (keep IDs sequential from 0).
- Resize `"friction_matrix"` to match: must be `C × C` square.
- Resize `"religion_conditional_matrix"` to match: must be `C × R` where R = number of religions.

## Adding a New Religion

Edit `<region>/religions.json` only:
- Add a new entry to `"religions"` (keep IDs sequential from 0).
- Add a new row/column to `"friction_matrix"`.
- Add a new column to `"religion_conditional_matrix"` in `economics.json` (every row needs one extra value).
