import re
query = "What is the weather in Paris?"
w = "paris"
m = re.search(rf"\b{re.escape(w)}\b", query, re.IGNORECASE)
print("match:", repr(m.group(0)) if m else None)
m2 = re.search(rf"\b{re.escape('California')}\b", "in California?", re.IGNORECASE)
print("match2:", repr(m2.group(0)) if m2 else None)
w3 = re.findall(r"\b[a-zA-Z]+\b", "in California?")
print("words:", w3)
