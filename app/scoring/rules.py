def overlap_ratio(needed: list[str], available: list[str]) -> float:
    if not needed or not available:
        return 0.0
    needed_set = {n.lower() for n in needed}
    available_set = {a.lower() for a in available}
    return len(needed_set & available_set) / len(needed_set)
