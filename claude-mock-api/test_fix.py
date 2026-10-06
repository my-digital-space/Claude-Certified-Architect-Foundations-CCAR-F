"""Quick scenario test for the fixed tool argument extraction."""
import sys, json
sys.path.insert(0, ".")
from app.services.tool_simulator import ToolUseSimulator

def schema(props, req):
    return {"type": "object", "properties": props, "required": req}

tools = [
    {"name": "get_product_price", "description": "Return the base price of a product.",
     "input_schema": schema({"product_name": {"type": "string"}}, ["product_name"])},
    {"name": "apply_discount", "description": "Apply a discount based on the customer type.",
     "input_schema": schema({"base_price": {"type": "number"}, "customer_type": {"type": "string"}},
                            ["base_price", "customer_type"])},
    {"name": "calculate_tax", "description": "Calculate tax on the discounted price.",
     "input_schema": schema({"price_after_discount": {"type": "number"}, "state": {"type": "string"}},
                            ["price_after_discount", "state"])},
]

sim = ToolUseSimulator(tools=tools)
query = "What is the final price of a laptop for a Gold customer in California?"
msgs = [{"role": "user", "content": query}]

for turn in range(5):
    r = sim.select_tools_to_call(msgs)
    if not r:
        print(f"Turn {turn+1}: FINAL ANSWER ->")
        print(sim.synthesize_final_response(msgs))
        break
    b = r[0]
    print(f"Turn {turn+1}: {b['name']} input={json.dumps(b['input'])}")
    if b["name"] == "get_product_price":
        res = "1000.0" if b["input"]["product_name"].lower() in ("laptop", "monitor", "keyboard") else "Error: Product not found."
    elif b["name"] == "apply_discount":
        res = str(b["input"]["base_price"] * 0.8)
    else:
        res = str(b["input"]["price_after_discount"] * 0.1)
    msgs.append({"role": "assistant", "content": [b]})
    msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": res}]})

# Regression: original weather scenario from the test suite
sim2 = ToolUseSimulator(tools=[
    {"name": "get_weather", "description": "Get the current weather for a given city",
     "input_schema": schema({"city": {"type": "string"}}, ["city"])},
])
msgs2 = [{"role": "user", "content": "What is the weather in Paris?"}]
b = sim2.select_tools_to_call(msgs2)[0]
print("Weather regression:", b["name"], b["input"])
assert b["input"]["city"] == "Paris", b["input"]
msgs2.append({"role": "assistant", "content": [b]})
msgs2.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"],
                                          "content": [{"type": "text", "text": "Sunny, 22C"}]}]})
assert not sim2.select_tools_to_call(msgs2)
print("end_turn regression: OK")
