from collections import defaultdict


def calc_my_balance(expenses: list, settlements: list, my_uid: str) -> float:
    """Positive = owed to me. Negative = I owe."""
    balance = 0.0

    for e in expenses:
        amount = float(e.get("amount", 0))
        paid_by = e.get("paid_by", "")
        split_among = e.get("split_among", [])
        if not split_among:
            continue
        share = amount / len(split_among)
        if paid_by == my_uid:
            balance += amount - (share if my_uid in split_among else 0)
        elif my_uid in split_among:
            balance -= share

    for s in settlements:
        amt = float(s.get("amount", 0))
        if s.get("from_uid") == my_uid:
            balance += amt   # I paid → my debt reduces
        elif s.get("to_uid") == my_uid:
            balance -= amt   # Someone paid me → my credit reduces

    return round(balance, 2)


def simplify_debts(expenses: list, settlements: list | None = None) -> list:
    """Return minimum transactions to settle all debts.
    Returns: [{"from": uid, "to": uid, "amount": float}, ...]
    """
    balance: dict[str, float] = defaultdict(float)

    for e in expenses:
        paid_by = e.get("paid_by", "")
        amount = float(e.get("amount", 0))
        members = e.get("split_among", [])
        if not members or not paid_by:
            continue
        share = amount / len(members)
        balance[paid_by] += amount
        for m in members:
            balance[m] -= share

    for s in (settlements or []):
        amt = float(s.get("amount", 0))
        from_uid = s.get("from_uid", "")
        to_uid = s.get("to_uid", "")
        if from_uid and to_uid:
            balance[from_uid] += amt
            balance[to_uid] -= amt

    creditors = sorted(
        [(amt, uid) for uid, amt in balance.items() if amt > 0.005],
        reverse=True,
    )
    debtors = sorted(
        [(abs(amt), uid) for uid, amt in balance.items() if amt < -0.005],
        reverse=True,
    )

    transactions = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        credit_amt, creditor = creditors[i]
        debt_amt, debtor = debtors[j]
        settled = min(credit_amt, debt_amt)
        transactions.append({"from": debtor, "to": creditor, "amount": round(settled, 2)})
        creditors[i] = (credit_amt - settled, creditor)
        debtors[j] = (debt_amt - settled, debtor)
        if creditors[i][0] < 0.005:
            i += 1
        if debtors[j][0] < 0.005:
            j += 1

    return transactions
