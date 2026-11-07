def calculate_ratio(a, b):
    # This function will trigger a ZeroDivisionError
    return a / b

def process_data(val):
    print(f"Processing value: {val}")
    return calculate_ratio(val, 0)

print("🚀 Semantic Debugger Demo Ready")
print("Running process_data(10)...")
process_data(10)
