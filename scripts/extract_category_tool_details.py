import os
import json

def extract_tool_data():
    tool_data = {}
    cnt = 0
    for root, dirs, files in os.walk("data/toolenv/tools"):
        for file in files:
            if file.endswith(".json"):
                if root.split('/')[-1] not in tool_data:
                    tool_data[root.split('/')[-1]] = {}
                with open(os.path.join(root, file), "r") as f:
                    # print(root, file)
                    data = json.load(f)
                    try:
                        tool_name = data["tool_name"] if "tool_name" in data else data["name"]
                    except:
                        tool_name = os.path.basename(file).split(".")[0]
                    tool_description = data["tool_description"]

                    api_list = [api['name'] for api in data['api_list']]
                    # print({file:{ tool_name:{"api_list": [api['name'] for api in api_list]}}})
                    if tool_name not in tool_data[root.split('/')[-1]]:
                        tool_data[root.split('/')[-1]][tool_name] = {"tool_description": tool_description}
                    else:
                        tool_name += '_new'    
                        tool_data[root.split('/')[-1]][tool_name] = {"tool_description": tool_description}
    return tool_data
tool_data = extract_tool_data()
print(tool_data.keys())
json.dump(tool_data, open("category_tool_details.json", "w", encoding='utf-8'), indent=4)
# json.dump(tool_data, open("category_tool_details_add_nonfree.json", "w", encoding='utf-8'), indent=4)
