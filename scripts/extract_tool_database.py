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
                    print(root, file)
                    data = json.load(f)
                    try:
                        tool_name = data["tool_name"] if "tool_name" in data else data["name"]
                    except:
                        tool_name = os.path.basename(file).split(".")[0]
                    api_list = data["api_list"]
                    if api_list is None: continue
                    cnt += len(api_list)
                    # print([api['name'] for api in api_list])
                    # print({file:{ tool_name:{"api_list": [api['name'] for api in api_list]}}})
                    if tool_name not in tool_data[root.split('/')[-1]]:
                        tool_data[root.split('/')[-1]][tool_name] = {"api_list_names": [api['name'] for api in api_list]}
                    else:
                        tool_name += '_new'    
                        tool_data[root.split('/')[-1]][tool_name]['api_list_names'].extend([api['name'] for api in api_list])
    # print(tool_data)
    print(cnt)
    return tool_data
tool_data = extract_tool_data()
print(tool_data.keys())
json.dump(tool_data, open("tool_data.json", "w", encoding='utf-8'), indent=4)
