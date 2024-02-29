#encoding:utf-8

import openai
import os
from typing import List, Dict, Any
import re
from tqdm import tqdm
import time
import requests
from termcolor import colored
import random
from anytool.api_database_function import *
from toolbench.inference.server import get_rapidapi_response
import tiktoken
from copy import deepcopy
from anytool.verifier import check_task_complete, check_task_solved
from anytool.prompt_template import FORMAT_INSTRUCTIONS_DATA_GENERATION
from openai_utils import call_gpt
enc = tiktoken.get_encoding("cl100k_base")
assert enc.decode(enc.encode("hello world")) == "hello world"
# To get the tokeniser corresponding to a specific model in the OpenAI API:
enc = tiktoken.encoding_for_model("gpt-4")
# enc = tiktoken.get_encoding("cl100k_base")
assert enc.decode(enc.encode("hello world")) == "hello world"
token_cnt = 0
error_list = ['Too many requests error...', 'Rate limit...', 'Unsubscribed', 'Unauthorized', 'not working error...', 'Quota','quota', 'Blocked', 'Rate limit', 'Unauthorized error']

import os
import json
from flask import Flask, jsonify, request

tool_root_dir = "data/toolenv/tools"

def standardize(string):
    res = re.compile("[^\\u4e00-\\u9fa5^a-z^A-Z^0-9^_]")
    string = res.sub("_", string)
    string = re.sub(r"(_)\1+","_", string).lower()
    while True:
        if len(string) == 0:
            return string
        if string[0] == "_":
            string = string[1:]
        else:
            break
    while True:
        if len(string) == 0:
            return string
        if string[-1] == "_":
            string = string[:-1]
        else:
            break
    if string[0].isdigit():
        string = "get_" + string
    return string

def fetch_api_json(api_list):
    api_list_new =[]
    index_list = []
    for k, item in enumerate(api_list):
        cate_name = item["category_name"]
        tool_name = standardize(item["tool_name"])
        api_name = change_name(standardize(item["api_name"]))
        tool_json = json.load(open(os.path.join(tool_root_dir, cate_name, tool_name + ".json"), "r"))
        append_flag = False
        api_dict_names = []
        for api_dict in tool_json["api_list"]:
            api_dict_names.append(api_dict["name"])
            pure_api_name = change_name(standardize(api_dict["name"]))
            if pure_api_name != api_name:
                continue
            api_json = {}
            api_json["category_name"] = cate_name
            api_json["api_name"] = api_dict["name"]
            api_json["api_description"] = api_dict["description"]
            api_json["required_parameters"] = api_dict["required_parameters"]
            api_json["optional_parameters"] = api_dict["optional_parameters"]
            api_json["tool_name"] = tool_json["tool_name"]
            api_list_new.append(api_json)
            index_list.append(k)
            append_flag = True
            break
        if not append_flag:
            print(api_name, api_dict_names)
    return api_list_new, index_list
    
def api_json_to_openai_json(api_json,standard_tool_name):
    description_max_length=256
    templete =     {
        "name": "",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "optional": [],
        }
    }
    
    map_type = {
        "NUMBER": "integer",
        "STRING": "string",
        "BOOLEAN": "boolean"
    }

    pure_api_name = change_name(standardize(api_json["api_name"]))
    templete["name"] = pure_api_name+ f"_for_{standard_tool_name}"
    templete["name"] = templete["name"][-64:]

    templete["description"] = f"This is the subfunction for tool \"{standard_tool_name}\", you can use this tool."
    
    if api_json["api_description"].strip() != "":
        tuncated_description = api_json['api_description'].strip().replace(api_json['api_name'],templete['name'])[:description_max_length]
        templete["description"] = templete["description"] + f"The description of this function is: \"{tuncated_description}\""
    if "required_parameters" in api_json.keys() and len(api_json["required_parameters"]) > 0:
        for para in api_json["required_parameters"]:
            name = standardize(para["name"])
            name = change_name(name)
            if para["type"] in map_type:
                param_type = map_type[para["type"]]
            else:
                param_type = "string"
            prompt = {
                "type":param_type,
                "description":para["description"][:description_max_length],
            }

            default_value = para['default']
            if len(str(default_value)) != 0:    
                prompt = {
                    "type":param_type,
                    "description":para["description"][:description_max_length],
                    "example_value": default_value
                }
            else:
                prompt = {
                    "type":param_type,
                    "description":para["description"][:description_max_length]
                }

            templete["parameters"]["properties"][name] = prompt
            templete["parameters"]["required"].append(name)
        for para in api_json["optional_parameters"]:
            name = standardize(para["name"])
            name = change_name(name)
            if para["type"] in map_type:
                param_type = map_type[para["type"]]
            else:
                param_type = "string"

            default_value = para['default']
            if len(str(default_value)) != 0:    
                prompt = {
                    "type":param_type,
                    "description":para["description"][:description_max_length],
                    "example_value": default_value
                }
            else:
                prompt = {
                    "type":param_type,
                    "description":para["description"][:description_max_length]
                }

            templete["parameters"]["properties"][name] = prompt
            templete["parameters"]["optional"].append(name)

    return templete, api_json["category_name"],  pure_api_name

# For pipeline environment preparation
def get_white_list(tool_root_dir):
    # print(tool_root_dir)
    white_list_dir = os.path.join(tool_root_dir)
    white_list = {}
    for cate in tqdm(os.listdir(white_list_dir)):
        if not os.path.isdir(os.path.join(white_list_dir,cate)):
            continue
        for file in os.listdir(os.path.join(white_list_dir,cate)):
            if not file.endswith(".json"):
                continue
            standard_tool_name = file.split(".")[0]
            # print(standard_tool_name)
            with open(os.path.join(white_list_dir,cate,file)) as reader:
                js_data = json.load(reader)
            # print(js_data)
            try:
                origin_tool_name = js_data["tool_name"]
            except:
                print('#'*100)
                print('error:', 'js_data', js_data[0])

            white_list[standardize(origin_tool_name)] = {"description": js_data["tool_description"], "standard_tool_name": standard_tool_name}
    return white_list

def contain(candidate_list, white_list):
    output = []
    for cand in candidate_list:
        if cand not in white_list.keys():
            return False
        output.append(white_list[cand])
    return output


def Finish(answer: str):
    """finish the conversation, required answer to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
    return answer

functions = []
api_name_reflect = {}
api2origin = {}
tool_names = []
cate_names = []
white_list = get_white_list(tool_root_dir)
def add_apis(api_list):
    """add apis to the current available api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
    if isinstance(api_list, str):
        api_list = eval(api_list)
    if not isinstance(api_list, list) or any('category_name' not in ele or 'tool_name' not in ele or 'api_name' not in ele for ele in api_list):
        return 'illegal input, input should be list, each element in the list should have category_name, tool_name, api_name'
    if not all([isinstance(ele['category_name'],str) and isinstance(ele['tool_name'],str) and isinstance(ele['api_name'],str) for ele in api_list]):
        return 'illegal input, category_name, tool_name, api_name should be string'
    global raw_api_list
    origin_api_list = deepcopy(api_list)
    for api in api_list:
        api.update(get_api_details(api['category_name'], api['tool_name'], api['api_name']))
    api_list, indexs = fetch_api_json(api_list)
    origin_api_list = [origin_api_list[k] for k in indexs]
    raw_api_list.extend(origin_api_list)
    origin_tool_names = [standardize(cont["tool_name"]) for cont in api_list]
    tool_des = contain(origin_tool_names,white_list)
    tool_des = [[cont["standard_tool_name"], cont["description"]] for cont in tool_des]
    global functions, api_name_reflect, tool_names, cate_names, api2origin, call_cnt
    for k,api_json in enumerate(api_list):
        standard_tool_name = tool_des[k][0]
        openai_function_json, cate_name, pure_api_name = api_json_to_openai_json(api_json,standard_tool_name)
        functions.append(openai_function_json)

        api_name_reflect[openai_function_json["name"]] = pure_api_name
        api2origin[openai_function_json["name"]] = {'category_name': origin_api_list[k]['category_name'], 'tool_name': origin_api_list[k]['tool_name'], 'api_name': origin_api_list[k]['api_name']} 
        print(openai_function_json["name"])

        tool_names.append(standard_tool_name)
        cate_names.append(cate_name)
        call_cnt[openai_function_json["name"]] = 0
    return 'apis added successfully. The mapping from the standard api names to the original category_names, tool_names and  api_names is: ' + str(api2origin)

def remove_apis(api_list):
    """remove apis from the current available api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
    if isinstance(api_list, str):
        api_list = eval(api_list)
    global raw_api_list
    if not isinstance(api_list, list) or any('category_name' not in ele or 'tool_name' not in ele or 'api_name' not in ele for ele in api_list):
        return 'illegal input, input should be list, each element in the list should have category_name, tool_name, api_name'
    if not all([isinstance(ele['category_name'],str) and isinstance(ele['tool_name'],str) and isinstance(ele['api_name'],str) for ele in api_list]):
        return 'illegal input, category_name, tool_name, api_name should be string'
    origin_api_list = deepcopy(api_list)
    for api in api_list:
        api.update(get_api_details(api['category_name'], api['tool_name'], api['api_name']))
    api_list, indexs = fetch_api_json(api_list)
    origin_api_list = [origin_api_list[k] for k in indexs]
    origin_tool_names = [standardize(cont["tool_name"]) for cont in api_list]
    tool_des = contain(origin_tool_names,white_list)
    tool_des = [[cont["standard_tool_name"], cont["description"]] for cont in tool_des]
    global functions, api_name_reflect, tool_names, cate_names, api2origin, call_cnt
    for k,api_json in enumerate(api_list):
        standard_tool_name = tool_des[k][0]
        openai_function_json, cate_name, pure_api_name = api_json_to_openai_json(api_json,standard_tool_name)
        # print(openai_function_json)
        functions.remove(openai_function_json)

        api_name_reflect.pop(openai_function_json["name"])
        api2origin.pop(openai_function_json["name"])

        tool_names.remove(standard_tool_name)
        cate_names.remove(cate_name)
        call_cnt.pop(openai_function_json["name"])

    
    for api in origin_api_list:
        for ele in raw_api_list:
            if ele['category_name'] == api['category_name'] and ele['tool_name'] == api['tool_name'] and ele['api_name'] == api['api_name']:
                raw_api_list.remove(ele)
                break
    return 'apis removed successfully. The mapping from the standard api names to the original category_names, tool_names and  api_names is: ' + str(api2origin)

# Define the API endpoints
def get_categories():
    return jsonify(query_all_categories(database))

def get_current_weather(location: str, unit: str = "fahrenheit") -> str:
    """Get the current weather and return a summary."""
    return f"It is currently sunny in {location} and 75 degrees {unit}."


def get_tomorrows_weather(location: str, unit: str = "fahrenheit") -> str:
    """Get the weather for tomorrow and return a summary."""
    return f"Tomorrow it will be rainy in {location} and 60 degrees {unit}."

# Infer the function definitions.

api_mapping = {
    "query_all_categories": query_all_categories,
    "get_tools_in_category": get_tools_in_category,
    "get_apis_in_tool": get_apis_in_tool,
    # "Finish": Finish,
    "get_api_details": get_api_details,
    "get_tools_descriptions": get_tools_descriptions,
    "add_apis_into_api_pool": add_apis,
    "remove_apis": remove_apis,
}

call_cnt = {}

def standardize_category(category):
    save_category = category.replace(" ", "_").replace(",", "_").replace("/", "_")
    while " " in save_category or "," in save_category:
        save_category = save_category.replace(" ", "_").replace(",", "_")
    save_category = save_category.replace("__", "_")
    return save_category


def change_name(name):
    change_list = ["from", "class", "return", "false", "true", "id", "and"]
    if name in change_list:
        name = "is_" + name
    return name

def contain(candidate_list, white_list):
    output = []
    for cand in candidate_list:
        if cand not in white_list.keys():
            return False
        output.append(white_list[cand])
    return output

class CoT_Runner(object):
    def __init__(self):
        self.toolbench_key = 'VvZd8bIZV2Lu6wz63hAp1oVwIFRgpniyJrHG6bVU3zzOIAC3wC'
        self.service_url = "http://8.218.239.54:8080/rapidapi"
        self.max_observation_length = 1024
        self.observ_compress_method = 'truncate'
        self.CALL_MAX_TIME = 3
        self.task_description = f'''You should use functions to help handle the real time user querys. Remember:
1.ALWAYS call \"Finish\" function at the end of the task. And the final answer should contain enough information to show to the user,If you can't handle the task, or you find that function calls always fail(the function is not valid now), use function Finish->give_up_and_restart.
2.Do not use origin tool names, use only subfunctions' names.
\n'''
        try:
            self.rapidapi_key_list = json.load('rapidapi_key_list.json')
        except:
            self.rapidapi_key_list = []
        self.use_rapidapi_key = True
        self.api_customization = True
#         unduplicated_reflection = {}
#         for standardize_tool_name, tool_des in tool_des:
#             unduplicated_reflection[standardize_tool_name] = tool_des

#         for k,(standardize_tool_name, tool_des) in enumerate(unduplicated_reflection.items()):
#             striped = tool_des[:512].replace('\n','').strip()
#             if striped == "":
#                 striped = "None"
#             self.task_description += f"{k+1}.{standardize_tool_name}: {striped}\n"



    def call_api(self, action_name="", action_input=""):
        """Need to return an observation string and status code:
            0 means normal response
            1 means there is no corresponding api name
            2 means there is an error in the input
            3 represents the end of the generation and the final answer appears
            4 means that the model decides to pruning by itself
            5 represents api call timeout
            6 for 404
            7 means not subscribed
            8 represents unauthorized
            9 represents too many requests
            10 stands for rate limit
            11 message contains "error" field
            12 error sending request
        """
        global call_cnt
        if action_name in api_mapping:
            try:
            # if True:
                result = api_mapping[action_name](**json.loads(action_input))
            except Exception as e:
                # raise e
                result = 'input format error'
            return result, 2
        if action_name == "Finish":
            if len(call_cnt) > 0 and min(call_cnt.values()) == 0:
                function_never_called = []
                for function_name in call_cnt:
                    if call_cnt[function_name] == 0:
                        function_never_called.append(function_name)
                return json.dumps({"error": f"{function_never_called} have not been called. You should call them at least once before formulating the final query", "response": ""}), 15
                # return json.dumps({"error": "You should call the each new added function at least once before formulating the final query", "response": ""}), 15
            if len(functions) == 7:
                return json.dumps({"error": "There must be apis successfully added using the add_apis_into_api_pool function, and you should formulate your query based on the found apis", "response": ""}), 15
                
            try:
                json_data = json.loads(action_input,strict=False)
            except:
                json_data = {}
            if 'query' not in json_data:
                return json.dumps({"error": "You should formulate a query", "response": ""}), 15
            if 'answer' not in json_data:
                return json.dumps({"error": "You should formulate an answer", "response": ""}), 15
            if 'plan' not in json_data:
                return json.dumps({"error": "You should formulate a plan", "response": ""}), 15
            # solvable, reason = check_task_complete(json_data['query'], functions[5:])
            solved, reason = check_task_solved(json_data['query'], json_data['answer'])
            if solved != 'Solved':
                return json.dumps({"error": f"The query is not solved by the answer. The reason is: {reason}", "response": ""}), 15
            # if solvable == 'Incomplete':
                # return json.dumps({"error": f"The query has incomplete inforamtion. The reason is: {reason}", "response": ""}), 15
            return json_data, 3
                
        else:
            for k, function in enumerate(functions):
                if function["name"].endswith(action_name):
                    assert function["name"] in call_cnt, (function["name"], call_cnt)
                    call_cnt[function["name"]] += 1
                    pure_api_name = api_name_reflect[function["name"]]
                    payload = {
                        "category": cate_names[k],
                        "tool_name": tool_names[k],
                        "api_name": pure_api_name,
                        "tool_input": action_input,
                        "strip": self.observ_compress_method,
                        "toolbench_key": self.toolbench_key
                    }
                    # if self.process_id == 0:
                    if True:
                        print(colored(f"query to {cate_names[k]}-->{tool_names[k]}-->{action_name}",color="yellow"))
                    if True:
                        time.sleep(2) # rate limit: 30 per minute
                        headers = {"toolbench_key": self.toolbench_key}
                        try:
                            response = requests.post(self.service_url, json=payload, headers=headers, timeout=15)
                        except:
                            # return json.dumps({"error": action_name, "response": ""}), 13
                            os.makedirs('output', exist_ok=True)
                            return json.dumps({"error": "connection timeout", "response": ""}), 13
                        if response.status_code != 200:
                            return json.dumps({"error": f"request invalid, data error. status_code={response.status_code}", "response": ""}), 12
                        try:
                            response = response.json()
                        except:
                            print(response)
                            return json.dumps({"error": f"request invalid, data error", "response": ""}), 15
                    cnt = 0
                    while any([word in response["error"] for word in error_list]):
                        if cnt < len(self.rapidapi_key_list):
                            # if self.use_rapidapi_key or self.api_customization:
                            print(f'use rapidapi key {cnt}', file=open('output/rapidapi_key_usage.txt','a'))
                            print(colored(f'use rapidapi key {cnt}', 'red'))
                            payload["rapidapi_key"] = self.rapidapi_key_list[cnt]
                            response = get_rapidapi_response(payload, api_customization=self.api_customization)
                            print(response['error'], file=open('output/rapidapi_key_usage.txt','a'))
                            cnt += 1    
                        else:
                            break

# 12 error sending request
                    if response["error"] == "API not working error...":
                        status_code = 6
                    elif response["error"] == "Unauthorized error...":
                        status_code = 7
                    elif response["error"] == "Unsubscribed error...":
                        status_code = 8
                    elif response["error"] == "Too many requests error...":
                        status_code = 9
                    elif response["error"] == "Rate limit per minute error...":
                        print("Reach api calling limit per minute, sleeping...")
                        time.sleep(10)
                        status_code = 10
                    elif response["error"] == "Message error...":
                        status_code = 11
                    else:
                        status_code = 0
                    return json.dumps(response), status_code
                    # except Exception as e:
                    #     return json.dumps({"error": f"Timeout error...{e}", "response": ""}), 5
            return json.dumps({"error": f"No such function name: {action_name}", "response": ""}), 1

    def run(self):
        messages = [
                    {'role':'system',
                     'content': 'You are QueryGPT, a helpful assistant who can strictly follow my instructions to generate diverse real queries'},
                    #  'The query should be related to the category {random.sample(query_all_categories(), random.randint(2, 3))}
                    ]
         
        messages.append({'role':'user', 
                     'content': FORMAT_INSTRUCTIONS_DATA_GENERATION.replace('{generated_queries}', str(generated_query_list[-5:])).replace('{categories}', str(random.sample(query_all_categories(), 49)))})
        i = 0
        while i < 30:
            print('#'*100)
            print(len(functions), len(raw_api_list))
            # assert len(functions) == len(raw_api_list) + 7, (len(functions), len(raw_api_list))
            response = call_gpt(
                messages,
                functions
            )
            if response == 'bad request':
                pass
                # messages = messages_old
            elif isinstance(response, str):
                continue
            # messages_old = deepcopy(messages)
            i = i + 1
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            print(response.choices[0].finish_reason)
            if tool_calls:
                messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                }
                )
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
            
                    function_call_result, status_code = self.call_api(function_name, function_args)
                    if function_name == 'get_api_details':
                        function_call_result = str(function_call_result)
                    print('Thought:', response.choices[0].message.content)
                    print('function call:', function_name, function_args)
                    print('function response:', function_call_result)
                    messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": str(function_call_result),
                            })
                    if function_name == 'Finish' and status_code != 15:
                        return function_call_result, messages
            else:
                messages.append({'role': "assistant",
                    'content': response.choices[0].message.content})
                print('Thought:', response.choices[0].message.content)
        return 'Exceed_max_iterations', messages    
            
generated_query_list = ['What is the current weather in Seattle, and what is the weather forecast for the next five days?']       
    
def generate_return_api_main():
    data = {}
    global functions, tool_names, cate_names, generated_query_list, raw_api_list, call_cnt
    while True:
        raw_api_list = []
        call_cnt = {}
        functions = [
                    get_tools_in_category_function,
                    get_apis_in_tool_function,
                    get_api_details_function,
                    get_tools_descriptions_function,
                    add_apis_into_api_pool_function,
                     remove_apis_function,
                     ]

        finish_func = {
            "name": "Finish",
            "description": "If you believe that you have obtained a query that can answered by the api database, please call this function to provide the query, the corresponding answer and the plan of using the functions to answer the query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":{"type":"string"},
                    "answer":{"type":"string"},
                    "plan":{"type":"string"},
                },
                "required": ["query", "answer", 'plan']
            }
            }
    
        functions.append(finish_func)
        cate_names = ['' for func in functions]
        tool_names = ['' for func in functions]

        runner = CoT_Runner()
        result, messages = runner.run()
        if isinstance(result, str):
            continue
        data['result'] = result
        if 'openai' in result: 
            return result, messages, raw_api_list
        if not any([word in result['answer'].lower() for word in exclusion_words]):
            return result, messages, raw_api_list

import time
if __name__ == '__main__':
    exclusion_words = ["sorry", "apologize", "apology", "unfortunately", "couldn't"]
    output_path = args.output_path
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs('output', exist_ok=True)
    generated_query_list = []
    query_data = []
    query = ''
    answer = ''
    for i in range(1000):
        t_s = time.time()
        print('#' * 100)
        print('Generate the data', i)

        data = {}
        try:
            while True:
                result, generate_messages, api_list = generate_return_api_main()
                if isinstance(result, dict):
                    query = result['query']
                    answer = result['answer']
                    plan = result['plan']
                    print(query)
                else:
                    continue
                break
        except Exception as e:
            raise e
            continue

      
        # for message in generate_messages:
        #     if message['role'] == 'assistant':
        #         if 'tool_calls' in message:
        #             message['tool_calls'] = [tool_call.json() for tool_call in message['tool_calls']]
        data['generate_messages'] = generate_messages
        generated_query_list.append(query)

        query_data.append({
            'query': query,
            'final_answer': answer,
            'gt_api_list': api_list,
            'query_id': str(2000000+i)
        })
        json.dump(query_data, open(output_path, 'w'), indent=4)
