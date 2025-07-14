import json

# Load the JSON key file
with open("service_account.json") as f:
    data = json.load(f)

# Get the private key in a format that TOML can accept
print('private_key = """' + data["private_key"] + '"""')
