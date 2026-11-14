def expense_shares(e: dict) -> dict:
    """uid -> amount owed for this expense. Supports equal split or exact amounts."""
    amounts = e.get("split_amounts")
    if amounts:
        return {u: float(a) for u, a in amounts.items()}
    members = e.get("split_among", [])
    if not members:
        return {}
    share = float(e.get("amount", 0)) / len(members)
    return {u: share for u in members}
