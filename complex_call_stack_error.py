def process_data_level_5(data):
    # Intentional error: dividing by zero
    total = sum(data)
    average = total / 0
    return average

def process_data_level_4(data):
    filtered_data = [x for x in data if x > 0]
    return process_data_level_5(filtered_data)

def process_data_level_3(data):
    normalized = [x * 10 for x in data]
    return process_data_level_4(normalized)

def process_data_level_2(data):
    cleaned = [x if x is not None else 0 for x in data]
    return process_data_level_3(cleaned)

def process_data_level_1(data):
    if not data:
        return 0
    return process_data_level_2(data)

def main():
    raw_input_data = [1, 2, None, 4, -1, 5]
    print("Starting data processing pipeline...")
    result = process_data_level_1(raw_input_data)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
