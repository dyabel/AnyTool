import json
from copy import deepcopy
from autogen.retrieve_utils import TEXT_FORMATS
# from openai_function_calling import FunctionInferer
# import autogen
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
import random
import re
import os
from tqdm import tqdm
from openai_utils import call_gpt
from arguments import parse_args
from config import *
if api_type == "azure":
    from openai import AzureOpenAI as Client
else:
    from openai import OpenAI as Client
client = Client(
    api_version=api_version,
    api_key = api_key,
    azure_endpoint = api_base
)
def get_embedding(text, model="text-embedding-ada-002"):
    if isinstance(text, list):
        print(len(text))
        result = []
        for single_text in tqdm(text):
            result.append(client.embeddings.create(input = single_text.replace("\n", " "), model=model).data[0].embedding)
        return result
    text = text.replace("\n", " ")
    return client.embeddings.create(input = [text], model=model).data[0].embedding
args = parse_args()
output_dir = args.output_dir

# Load the extracted and restructured data from file
with open('tool_data.json', 'r', encoding='utf-8') as file:
    database = json.load(file)
api_details_dict = json.load(open('api_details.json', 'r', encoding='utf-8'))
category_tool_details_dict = json.load(open('category_tool_details.json', 'r', encoding='utf-8'))

sample_api_number = args.all_api_number
if sample_api_number == 1000:
    sampled_api_list = json.load(open('sampled_api_list1000.json', 'r', encoding='utf-8'))
elif sample_api_number == 5000:
    sampled_api_list = json.load(open('sampled_api_list5000.json', 'r', encoding='utf-8'))
elif sample_api_number == 10000:
    sampled_api_list = json.load(open('sampled_api_list10000.json', 'r', encoding='utf-8'))
else:
    sampled_api_list = []
print('database size ', sum([sum([len(database[category][tool_name]['api_list_names']) for tool_name in database[category].keys()]) for category in database.keys()]))
# """
if len(sampled_api_list) > 0:
    cnt = 0
    total_cnt = 0
    total_cnt1 = 0
    database_copy = deepcopy(database)
    for category in database_copy.keys():
        for tool_name, tool_data in database_copy[category].items():
            total_cnt += len(tool_data["api_list_names"])
            assert isinstance(tool_data['api_list_names'], list)
            for api in tool_data["api_list_names"]:
                total_cnt1 += 1
                try:
                    if category+tool_name+api not in sampled_api_list:
                        database[category][tool_name]["api_list_names"].remove(api)
                        for api_dict in api_details_dict[category][tool_name]["api_list"]:
                            if api_dict["name"] == api:
                                api_details_dict[category][tool_name]["api_list"].remove(api_dict)
                    else:
                        cnt += 1
                except:
                    pass
    print('total api number ', total_cnt, total_cnt1)
    print('total api number after filtering ', cnt)
# """
# """
# Define the query functions
def query_all_categories() -> list:
    """query all categories in the database"""

    return random.sample(list(database.keys()), len(database.keys()))

def get_tools_in_category(category_name: str=None) -> list:
    """query all tools in a specific category"""
    if category_name is None:
        return {'Error': 'Category name is required', 'response':''}
    if category_name not in database:
        return 'Illegal category name'
    return list(database[category_name].keys()) if category_name in database else None

def query_all_tools_in_all_categories() -> list:
    """query all tools in all categories"""
    return {category: list(tools.keys()) for category, tools in database.items()}

def get_apis_in_tool(category_name: str=None, tool_name: str=None) -> list:
    """query all apis in a specific tool"""
    if category_name is None:
        return {'Error': 'Category name is required', 'response':''}
    if category_name not in database:
        return 'Illegal category name'
    if tool_name not in database[category_name]:
        return 'Illegal tool name'
    return database[category_name][tool_name]['api_list_names']
# def query_api_details(api_name):
#     if api_name in api_details_dict:
#         return api_details_dict[api_name]
#     return None
def get_api_details(category_name: str=None, tool_name: str=None, api_name: str=None) -> dict:
    """query the details of a specific api"""
    if category_name is None:
        return {'Error': 'Category name is required', 'response':''}
    if tool_name is None:
        return {'Error': 'Tool name is required', 'response':''}
    if api_name is None:
        return {'Error': 'API name is required', 'response':''}
    for category, tools in api_details_dict.items():
        if category != category_name:
            continue
        for tool, tool_data in tools.items():
            if tool != tool_name:
                continue
            for api in tool_data["api_list"]:
                if api["name"] == api_name:
                    return api
    return {}

def locate_api(api_name: str=None) -> dict:
    """query the details of a specific api"""
    for category, tools in api_details_dict.items():
        for tool, tool_data in tools.items():
            for api in tool_data["api_list"]:
                if api["name"] == api_name:
                    return {"category_name": category, "tool_name": tool, "api_name": api_name}
    return 'api not found'

def sample_apis(gt_apis, num=200):
    categories_origin = database.keys()
    sampled_categories = random.sample(categories_origin, 5)
    categories = []
    tools = []
    apis = []
    for api in gt_apis:
        if api['category_name'] not in categories:
            categories.append(api['category_name'])
        if api['tool_name'] not in tools:
            tools.append(api['tool_name'])
        if api['api_name'] not in apis:
            apis.append(api['api_name'])
    for cate in sampled_categories:
        if cate in categories:
            continue
        categories.append(cate)
        tools_origin = get_tools_in_category(cate)
        sampled_tools = random.sample(tools_origin, min(25, len(tools_origin)))
        tools.extend(sampled_tools)
        for tool in sampled_tools:
            apis_origin = get_apis_in_tool(cate, tool)
            if apis_origin is None:
                continue
            sampled_apis = random.sample(apis_origin, min(10, len(apis_origin)))
            apis.extend(sampled_apis)
    
    return categories, tools, apis
get_api_details_function = {
    'name': 'get_api_details',
    'description': 'get the details of a specific api',
    'parameters': {
        'type': 'object',
        'properties': {
            'category_name': {'type': 'string'}, 
            'tool_name': {'type': 'string'}, 
            'api_name': {'type': 'string'}
        },
        'required': ['category_name', 'tool_name', 'api_name']
    }
}

locate_api_function = {
    'name': 'locate_api',
    'description': 'locate a specific api in the database',
    'parameters': {
        'type': 'object',
        'properties': {
            'api_name': {"type": "string"}
        },
        'required': ['api_name']
    }
}

get_apis_in_tool_function = {
    'name': 'get_apis_in_tool',
    'description': 'query all apis in a specific tool',
    'parameters': {
        'type': 'object',
        'properties': {
            'category_name': {'type': 'string'}, 
            'tool_name': {'type': 'string'}
        },
        'required': ['category_name', 'tool_name']
    }
}

get_tools_in_category_function = {
    'name': 'get_tools_in_category',
    'description': 'get all tools in a specific category',
    'parameters': {
        'type': 'object',
        'properties': {
            'category_name': {'type': 'string'}
        },
        'required': ['category_name']
    }
}


get_tools_descriptions_function = {
    'name': 'get_tools_descriptions',
    'description': 'get the descriptions of some tools in a specific category. Require input to be list of tool names. You should query no more than 10 tools at a time.',
    'parameters': {
        'type': 'object',
        'properties': {
            'category_name':{'type':'string'}, 
            'tool_list': {
                'type': 'array', 
                'items': {'type': 'string'}
            }
        },
        'required': ['category_name', 'tool_list']
    }
}

retrieve_context_function = {
    'name': 'retrieve_context',
    'description': 'retrieve the context relevant to a specific query, the context must contain the search_string',
    'parameters': {
        'type': 'object',
        'properties': {
            'search_string': {'type': 'string'}
        },
        'required': ['search_string']
    }
}

check_if_request_solvable_function = {
    'name': 'check_if_request_solvable',
    'description': 'check if the current apis are sufficient to solve the query',
    'parameters': {
        'type': 'object',
        'properties': {}
    }
}

add_apis_into_api_pool_function = {
    'name': 'add_apis_into_api_pool',
    'description': 'add apis to the final api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name',
    'parameters': {
        'type': 'object',
        'properties': {
            'api_list': {'type': 'null'}
        },
        'required': ['api_list']
    }
}

remove_apis_function = {'name': 'remove_apis', 'description': 'remove apis from the final api list. require input to be list of dictionaries describing with the keys category_name, tool_name, api_name', 'parameters': {'type': 'object', 'properties': {'api_list': {'type': 'null'}},'required': ['api_list']}}

def query_all_tool_info(category:str, tools: list) -> list:
    """query all tool info of a list of tools"""
    if tools is None:
        return {'Error': 'Tool list is required', 'response':''}
    if not isinstance(tools, list):
        return {'Error': 'Tools must be a list', 'response':''}
    res = {}
    all_tools = api_details_dict[category]
    
    for tool in tools:
        if tool not in all_tools:
            return {'Error': f'Tool name {tool} not found', 'response':''}
        res[tool] = all_tools[tool]
        res[tool]['description'] = category_tool_details_dict[category][tool]['tool_description']
    return res

def query_all_tool_info_in_category(cate):
    """query all category tool"""
    return category_tool_details_dict[cate]

def get_tool_description(category_name: str, tool_name: str) -> dict:
    """get the description of a specific tool"""
    if category_name not in category_tool_details_dict:
        return 'category name not found'
    if tool_name not in category_tool_details_dict[category_name]:
        return 'tool name not found'
    return category_tool_details_dict[category_name][tool_name]['tool_description']

def get_tools_descriptions(category_name: str, tool_list: str) -> dict:
    """query the details of a tool list"""
    if category_name not in category_tool_details_dict:
        return {'Error': 'category name not found', 'response':''}
    if not isinstance(tool_list, list):
        return {'Error': 'tool_list must be a list', 'response':''}
    if isinstance(tool_list, str):
        tool_list = eval(tool_list)
    for tool_name in tool_list:
        if tool_name not in category_tool_details_dict[category_name]:
            return f'tool name {tool_name} not found'
    return {tool_name: category_tool_details_dict[category_name][tool_name]['tool_description'] for tool_name in tool_list}

def get_response_example(api_name: str) -> str:
    """get the response example of a specific api"""
    api_details = get_api_details(api_name)
    if api_details is None:
        return 'api name not found'
    # return api_details['response_example']
split_function = lambda x: x.split("}")
# # 1. create an RetrieveAssistantAgent instance named "assistant"
# assistant = RetrieveAssistantAgent(
#     name="assistant", 
#     system_message="You are a helpful assistant. You should help the user find the relevant apis for their tasks. Return the category_name, tool_name and api_name exactly as in your context. Do not make up them",
#     llm_config={
#         # "request_timeout": 600,
#         "seed": 42,
#         "config_list": config_list,
#     },
# )
# config_list = autogen.config_list_from_json(
#     env_or_file="OAI_CONFIG_LIST",
#     file_location=".",
#     filter_dict={
#         "model": {
#             "gpt-4",
#             "gpt4",
#             "gpt-4-32k",
#             "gpt-4-turbo",
#             "gpt-4-32k-0314",
#             "gpt-35-turbo",
#             "gpt-3.5-turbo",
#         }
#     },
# )

# assert len(config_list) > 0
# print("models to use: ", [config_list[i]["model"] for i in range(len(config_list))])


#  Accepted file formats for that can be stored in 
# a vector database instance
from autogen.retrieve_utils import TEXT_FORMATS

print("Accepted file formats for `docs_path`:")
print(TEXT_FORMATS)


split_function = lambda x: x.split("}")
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
embedding_function = get_embedding
ragproxyagent = RetrieveUserProxyAgent(
    name="ragproxyagent",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    retrieve_config={
        "task": "qa",
        "docs_path": "data_for_retrieval.json",
        "chunk_token_size": 1000,
        "model": model_name,
        # "client": chromadb.PersistentClient(path="/tmp/chromadb"),
        # "embedding_model": "text-embedding-ada-002",
        # "embedding_model": "all-mpnet-base-v2",
        "embedding_function": embedding_function,
        "get_or_create": True,  # set to True if you want to recreate the collection
        # "custom_split_function": split_function,
        "collection_name": "toolbench",
        "must_break_at_empty_line": False
    },
)
def summarize_context(query, context):
    messages = [{
        "role": "system",
        "content": """You are a helpful assistant. Given a task description, you should help the user find  the relevant APIs in the context. Each API consists of category_name, tool_name and api_name. Do not make up them. 
        You should call Finish function with the api list. Each element of the list is a dictionary with keys 'category_name', 'tool_name', 'api_name'. Remember, you must call Finish function at one step.""",
    },
        {"role": "user", 
        "content": f"Task description: {query}. Can you help me find the relevant category_names, tool_names, and api_names in following context: {context}"}
        ]
    functions = [finish_function]
    for i in range(5):
        response = call_gpt(
                        messages=messages,
                        functions=functions
                    )
        tool_calls = response.choices[0].message.tool_calls
        print('Thought:', response.choices[0].message.content)
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                if function_name.lower() == 'finish':
                    try:
                        api_list = json.loads(function_args)['api_list']
                        if api_list is None:
                            continue
                    except:
                        continue
                        
                else:
                    continue
                return api_list
        else:
            print('Thought:', response.choices[0].message.content)
            continue
    return []
# assistant.reset()
finish_function = {
    'name': 'Finish',
    'description': 'Finish with the api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name',
    'parameters': {
        'type': 'object',
        'properties': {
            'api_list': {'type': 'null'}
        },
        'required': ['api_list']
    }
}
def retrieve_context(query, search_string=None):
    """retrieve the context relevant to a specific query, the context must contain the search_string"""
    print('search_string:', search_string)
    # try:
    context = ragproxyagent.generate_init_message(problem=query,n_results=64, search_string=search_string)
    # except:
    #     return 'No context found'
    # if 'Context is' not in context:
    #     return 'No context found'
    return summarize_context(query, context.split('Context is')[1])

def is_iterator(obj):
    return hasattr(obj, '__iter__') and hasattr(obj, '__next__')

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
            # print('-'*100)
            # print(white_list_dir, cate, file)
            with open(os.path.join(white_list_dir,cate,file)) as reader:
                js_data = json.load(reader)
            # print(js_data)
            # print('#'*100)
            try:
                origin_tool_name = js_data["tool_name"]
            except:
                print('#'*100)
                print('error:', 'js_data', js_data[0])

            white_list[standardize(origin_tool_name)] = {"description": js_data["tool_description"], "standard_tool_name": standard_tool_name}
    return white_list

tool_root_dir = "data/toolenv/tools"
white_list = get_white_list(tool_root_dir)

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

exclusion_words = ["sorry", "apologize", "apology", "unfortunately", "couldn't", "could not", "can't", "cannot", 'unable', 'regret', 'not successfully']

if __name__ == "__main__":
    qa_problem = "I'm interested in buying NFTs and would like to know the order-related information. Could you provide me with the fee rate, base token, fee token, and lower limit using the GetOrderInfo API? Additionally, I would like to know the balance of a specific stark key and asset ID using the Balanceofstark_keyandasset_id API."
    print(retrieve_context(qa_problem))
    # print(retrieve_context(qa_problem, search_string="GetOrderInfo"))
    # print(get_apis_in_tool('Search', 'Amazon Search'))