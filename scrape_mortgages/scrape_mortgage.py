import pandas as pd
import requests

input_file = "mortgages.xlsx"
df_input = pd.read_excel(input_file)

results = []
base_url = "https://data.cityofnewyork.us/resource/636b-3b5g.json"


i = 0
for doc_id in df_input["DOCUMENT ID"]:
    i += 1
    params = {"document_id": doc_id}
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()

        # Logic to extract Party 1 (Grantor) and Party 2 (Grantee)
        party1 = next(
            (item.get("name") for item in data if item.get("party_type") == "1"), "N/A"
        )
        party2 = next(
            (item.get("name") for item in data if item.get("party_type") == "2"), "N/A"
        )
        address = data[0].get("address_1", "N/A") if data else "N/A"

        results.append(
            {
                "document_id": doc_id,
                "address_1": address,
                "party_type_1": party1,
                "party_type_2": party2,
            }
        )
    else:
        print(f"Failed to fetch data for {doc_id}")

# 3. Save to a new spreadsheet
df_output = pd.DataFrame(results)
df_output.to_excel("Mortgage_Results.xlsx", index=False)
print("Scraping complete. Results saved to 'Mortgage_Results.xlsx'.")
