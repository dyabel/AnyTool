import zipfile
import os
import json
from copy import deepcopy
# Extract the new zip file
# with zipfile.ZipFile(zip_file_path_small, 'r') as zip_ref:
#     zip_ref.extractall(extracted_folder_path_small)
extracted_folder_path_small = 'data/toolenv/tools'



# api_test_results = json.load(open('api_test_results_with_docs2.json', 'r', encoding='utf-8'))


# Walk through the extracted files and read the JSON data
detailed_data_small = {}  # Initialize an empty dictionary to store the extracted data
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
                if category not in detailed_data_small:
                    detailed_data_small[category] = {}
                if tool_name not in detailed_data_small[category]:
                    detailed_data_small[category][tool_name] = {"api_list": []}
                else:
                    tool_name += '_new'
                    raise ValueError('duplicate tool name')
                    detailed_data_small[category][tool_name] = {"api_list": []}
                for api in api_list:
                    cnt += 1
                    api_name = api.get('name', 'Unknown API')
                    # try:
                    #     if api_test_results[category][tool_name][api_name]["result"]['return_type'] == "inalive":
                    #         print('remove')
                    #         continue
                    # except:
                    #     print(category, tool_name, api_name)
                    #     pass
                    # if api_name in api_name_list:
                    #     raise Exception('duplicate api name')
                    api_name_list.append(api_name)
                    description = api.get('description', 'No description available.')
                    required_parameters = [param.get('name', 'Unknown Parameter') for param in api.get('required_parameters', [])]
                    optional_parameters = [param.get('name', 'Unknown Parameter') for param in api.get('optional_parameters', [])]
                    test_endpoint = api.get('test_endpoint', '') 
                    tool_description = json_data.get('tool_description', 'No description available.'),
                    # Organizing the data
                    # print(len(detailed_data_small[category][tool_name]['api_list']))
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
                    detailed_data_small[category][tool_name]["api_list"].append({
                        "name": api_name,
                        "description": description,
                        "required_parameters": required_parameters,
                        "optional_parameters": optional_parameters,
                        # "test_endpoint": test_endpoint
                    })
                # except Exception as e:
                    # Store the error message if we fail to process a file
                    # if category not in detailed_data_small:
                    #     detailed_data_small[category] = {}
                    # detailed_data_small[category][file] = {"error": str(e)}

# Verifying the structure of the detailed_data_small by displaying a sample
# sample_detailed_data_small = {
#     category: {
#         tool_name: detailed_data_small[category][tool_name] 
#         for tool_name in list(detailed_data_small[category].keys())[:1]
#     }
#     for category in list(detailed_data_small.keys())[:3]
# }
cnt = 0 
for category in detailed_data_small:
    for tool_name in detailed_data_small[category]:
        cnt += len(detailed_data_small[category][tool_name]['api_list'])
print('total api number:', cnt)

# json.dump(detailed_data_small, open('api_details_compressed.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
print(len(data_for_retrieval))
json.dump(data_for_retrieval, open('data_for_retrieval.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
json.dump(detailed_data_small, open('api_details.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
print(cnt)

