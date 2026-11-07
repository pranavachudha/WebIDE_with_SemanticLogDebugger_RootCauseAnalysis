def get_user_status(user_id):
    # This will trigger a KeyError
    db = {"admin": "active", "guest": "limited"}
    return db[user_id]

print("Attempting to fetch status for \"root\"...")
print(get_user_status("root"))
