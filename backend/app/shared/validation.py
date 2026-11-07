"""Small input-cleaning helpers used by several features' schemas."""




def blank_to_none(v):
    v = (v or "").strip()
    return v or None


MAX_ORDER_LINES = 30
