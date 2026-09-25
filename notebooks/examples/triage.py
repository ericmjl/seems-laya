"""A completely ordinary Python file that happens to use judgment syntax.

No special extension, no marker, no launcher: with seems-laya installed (and
its startup hook in this environment), a plain `python` can import and run
this file. Exact rules stay in Python; meaning goes to the local decision
model; the unsure band routes to a human.
"""
import seems

tickets = [
    {"amount": 950, "text": "Charged twice for March, I want my money back today."},
    {"amount": 40, "text": "The app crashes whenever I open settings."},
    {"amount": 1200, "text": "Your outage ate our launch. This is unacceptable."},
]

for t in tickets:
    if t["amount"] > 500 and t["text"] asks for a refund:
        queue = "manager"
    elif t["text"] sounds furious:
        queue = "manager"
    else:
        queue = "support"
    unsure:
        queue = "human review"
    print(f"${t['amount']:>5}  ->  {queue}")
