import zipfile
import os
import json
from copy import deepcopy
extracted_folder_path_small = 'data/toolenv/tools'

# Walk through the extracted files and read the JSON data
detailed_data = {}  # Initialize an empty dictionary to store the extracted data
cnt = 0
api_name_list = []
data_for_retrieval = []
for root, dirs, files in os.walk(extracted_folder_path_small):
    for file in files:
        # Ensure we are only processing .json files
        if file.endswith(".json"):
            file_path = os.path.join(root, file)
            # Extract the category name from the file path
            print(file_path)
            category = file_path.split('/')[-2]
            with open(file_path, 'r', encoding='utf-8') as json_file:
                # try:
                json_data = json.load(json_file)
                if 'name' in json_data:
                    tool_name = json_data['name']
                else:
                    tool_name = json_data['tool_name']
                api_list = json_data.get('api_list', [])
                # Extract necessary data for each API and organize it in the dictionary
                if category not in detailed_data:
                    detailed_data[category] = {}
                if tool_name not in detailed_data[category]:
                    detailed_data[category][tool_name] = {"api_list": []}
                else:
                    tool_name += '_new'
                    raise ValueError('duplicate tool name')
                    detailed_data[category][tool_name] = {"api_list": []}
                for api in api_list:
                    cnt += 1
                    api_name = api.get('name', 'Unknown API')
                    api_name_list.append(api_name)
                    description = api.get('description', 'No description available.')
                    required_parameters = [param.get('name', 'Unknown Parameter') for param in api.get('required_parameters', [])]
                    optional_parameters = [param.get('name', 'Unknown Parameter') for param in api.get('optional_parameters', [])]
                    test_endpoint = api.get('test_endpoint', '') 
                    tool_description = json_data.get('tool_description', 'No description available.'),
                    # Organizing the data
                    if tool_description is not None:
                        tool_description = tool_description[:100]
                    if description is not None:
                        description = description[:100]
                    data_for_retrieval.append({
                        "category_name": category,
                        "tool_name": tool_name,
                        "api_name": api_name,
                        "tool_description": tool_description,
                        "api_description": description,
                        "required_parameters": required_parameters,
                        "optional_parameters": optional_parameters,
                    })
                    detailed_data[category][tool_name]["api_list"].append({
                        "name": api_name,
                        "description": description,
                        "required_parameters": required_parameters,
                        "optional_parameters": optional_parameters,
                        # "test_endpoint": test_endpoint
                    })
cnt = 0 
for category in detailed_data:
    for tool_name in detailed_data[category]:
        cnt += len(detailed_data[category][tool_name]['api_list'])
print('total api number:', cnt)

# json.dump(detailed_data, open('api_details_compressed.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
# print(len(data_for_retrieval))
# json.dump(data_for_retrieval, open('data_for_retrieval.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
json.dump(detailed_data, open('api_details.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
print(cnt)

