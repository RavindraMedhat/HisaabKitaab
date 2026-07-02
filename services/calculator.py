from collections import defaultdict


def simplify_debts(expenses: list) -> list:
    """
    Given a list of expenses, return the minimum transactions to settle all debts.
    Each expense: {"paid_by": uid, "amount": float, "split_among": [uid, ...]}
    Returns: [{"from": uid, "to": uid, "amount": float}, ...]
    """
    balance = defaultdict(float)

    for expense in expenses:
        paid_by = expense["paid_by"]
        amount = expense["amount"]
        members = expense["split_among"]
        share = amount / len(members)

        balance[paid_by] += amount
        for member in members:
            balance[member] -= share

    creditors = sorted([(amt, uid) for uid, amt in balance.items() if amt > 0.01], reverse=True)
    debtors = sorted([(abs(amt), uid) for uid, amt in balance.items() if amt < -0.01], reverse=True)

    transactions = []
    i, j = 0, 0

    while i < len(creditors) and j < len(debtors):
        credit_amt, creditor = creditors[i]
        debt_amt, debtor = debtors[j]

        settled = min(credit_amt, debt_amt)
        transactions.append({"from": debtor, "to": creditor, "amount": round(settled, 2)})

        creditors[i] = (credit_amt - settled, creditor)
        debtors[j] = (debt_amt - settled, debtor)

        if creditors[i][0] < 0.01:
            i += 1
        if debtors[j][0] < 0.01:
            j += 1

    return transactions
