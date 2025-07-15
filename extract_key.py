import json

# Load your downloaded Google service account key file
with open("Credential.json") as f:
    data = json.load(f)

# Format private key for TOML
formatted_key = 'private_key = """' + data["private_key"] + '"""'

# Print out the full TOML-compatible block
print("\nPaste this into .streamlit/secrets.toml:\n")
print("[GOOGLE_CREDS]")
for key, value in data.items():
    if key == "private_key":
        print(formatted_key)
    else:
        print(f'{key} = "{value}"')
