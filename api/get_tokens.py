from tgtg import TgtgClient

email = input("TGTG email: ")

client = TgtgClient(email=email)
creds = client.get_credentials()

print("ACCESS_TOKEN =", creds["access_token"])
print("REFRESH_TOKEN =", creds["refresh_token"])
print("USER_ID =", creds["user_id"])