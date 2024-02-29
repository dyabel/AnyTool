from anytool.api_database_function import *
import json
import os
from anytool.prompt_template import *
from anytool.verifier import check_task_solvable_by_function, check_task_solvable, check_solved_toolbench, check_task_complete
from termcolor import colored
from openai_utils import call_gpt
import threading
from threading import Thread, Semaphore
import time
import numpy as np
from arguments import parse_args
args = parse_args()
output_dir = args.output_dir
raise_error = False
max_api_number = args.max_api_number
sem = Semaphore(16)  # 允许同时运行的最大线程数为16
class DoNothingContextManager:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

leaf_tool_number = args.leaf_tool_number

multi_thread = True
if multi_thread:
    counter_lock = threading.Lock()
else:
    counter_lock = DoNothingContextManager()
    
def Finish():
    """Finish the conversation"""
    return 'finished'
def remove_apis(api_list):
    """remove apis from the current available api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
    print(colored(f'removing apis: {api_list}', 'red'))
    if len(api_list) == 0:
        return 'empty api list'
    if isinstance(api_list, str):
        api_list = eval(api_list)
    if not isinstance(api_list, list) or any('category_name' not in ele or 'tool_name' not in ele or 'api_name' not in ele for ele in api_list):
        return 'illegal input, input should be list, each element in the list should have category_name, tool_name, api_name'
    if not all([isinstance(ele['category_name'],str) and isinstance(ele['tool_name'],str) and isinstance(ele['api_name'],str) for ele in api_list]):
        return 'illegal input, category_name, tool_name, api_name should be string'
    origin_api_list = deepcopy(api_list)
    # for api in origin_api_list:
    #     self.api_list.remove(api)
    global global_api_list, global_api_list_detailed
    for api in api_list:
        # api.update(get_api_details(api['category_name'], api['tool_name'], api['api_name']))
        tool_details = get_tool_description(api['category_name'], api['tool_name'])
        api_details = get_api_details(**api)
        api['tool_description'] = tool_details['tool_description'] if isinstance(tool_details, dict) else ''
        api['api_description'] = api_details['description'] if 'description' in api_details else ''
        try:
            with counter_lock:
                if api in global_api_list:
                    global_api_list.remove(api)
        except:
            pass

    for api in origin_api_list:
        for ele in global_api_list:
            if ele['category_name'] == api['category_name'] and ele['tool_name'] == api['tool_name'] and ele['api_name'] == api['api_name']:
                with counter_lock:
                    global_api_list.remove(ele)
                break
    return f'APIs removed successfully. Current API number: {len(global_api_list)}. Max API number: {max_api_number}'


class Agent(object):
    def __init__(self) -> None:
        self.failed_reason = None
        self.messages = []
        self.depth = 0
        self.index = 0
        self.finish_search = False
        self.sub_agents = []

def check_if_request_solvable():
    global stop, status, total_tokens, call_cnt
    if stop:
        return 'Current APIs already sufficient to solve the query.'
    t_s = time.time()
    solvable, reason, tokens = check_task_solvable_by_function(query, global_api_list_detailed)
    total_tokens += tokens
    call_cnt += 1

    print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
    if solvable != 'Unsolvable':
        with counter_lock:
            stop = True
            status = 'The current API list can solve the query.'
        return f'Current API number: {len(global_api_list)}. Max API number: {max_api_number}'
    else:
        with counter_lock:
            status = f'The current API list cannot solve the query due to the following reason: {reason}'
        if len(global_api_list) >= max_api_number:
            with counter_lock:
                stop = True
        return f'Current API number: {len(global_api_list)}. Max API number: {max_api_number}. The current API list cannot solve the query due to the following reason: {reason}'

class Category_Agent(Agent):
    def __init__(self, query, category=None) -> None:
        super().__init__()
        self.category = category
        self.tools = get_tools_in_category(self.category)
        self.query = query
        self.info = f'category: {self.category} assigned'
        self.api_mapping = {
                "query_all_categories": query_all_categories,
                "retrieve_context": retrieve_context,
                "Finish": Finish,
                "get_tools_descriptions": get_tools_descriptions,
                "create_agent_tool_level": self.create_agent_tool_level,
                }
        self.functions = [
            get_tools_descriptions_function,
            finish_function
        ]
        self.tools = get_tools_in_category(self.category)
    
   
    def resume_search(self):
        """Assign a category to an agent"""
        global call_cnt, total_tokens, stop, error_flag 
        if stop or total_tokens > 200000: 
            self.finish_search = True
            if multi_thread:
                sem.release()
            return f'category: {self.category} assigned'
        print(colored(f'assigning category: {self.category}', 'green'))
        if len(self.tools) <= leaf_tool_number:
            self.finish_search = True
            return f'category: {self.category} assigned'
        if self.failed_reason is not None:
            self.messages.append({"role": "user", "content": REFIND_TOOL_PROMPT.replace('{failed_reason}', str(self.failed_reason))})
            self.failed_reason = None
        for i in range(20):
            if stop or total_tokens > 200000:
                if multi_thread:
                    sem.release()
                return f'category: {self.category} assigned'
            t_s = time.time()
            try:
                response = call_gpt(
                                messages=self.messages,
                                functions=self.functions
                            )
            except:
                error_flag = True
                stop = True
                continue
            with counter_lock:
                total_tokens += response.usage.total_tokens
                call_cnt += 1
            print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            if isinstance(response, str):
                continue
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls is not None:
                print('tool call number', len(tool_calls))
            # print('message', response.choices[0].message)
            if tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                })
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    print('function call:', function_name, function_args)
                    if function_name == 'get_tools_in_category':
                        self.query_tools_call = True
                    if function_name.lower() == 'finish':
                        print(colored(f'category: {self.category} assigned', 'green'))
                        print(colored('category finish search', 'green'))
                        self.messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": 'Finished',
                            })
                        self.finish_search = True
                        if multi_thread:
                            sem.release()
                            return f'category: {self.category} assigned.'
                        else:
                            return f'category: {self.category} assigned. The status of current found apis is: {status}'
                    elif function_name not in self.api_mapping:
                        function_name = 'hullucinating_function_name'
                        tool_call.function.name = function_name
                        function_call_result = "Function name error"
                        self.messages.append(
                            {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_call_result),
                            }
                        )
                    else:
                        try:
                            function_call_result = self.api_mapping[function_name](**json.loads(function_args))
                            if function_name in ['get_apis_in_tool'] and isinstance(function_call_result, str) and 'Illegal tool' in function_call_result:
                                function_call_result = f'Illegal tool. The tool should be in the tool list {self.tools}'
                        except Exception as e:
                            print(e, function_name, function_args, file=open(f'{output_dir}/error.txt', 'a', encoding='utf-8'))
                            if raise_error:
                                raise e
                            function_call_result = 'input format error'
                        self.messages.append(
                            {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_call_result),
                            })
                 
                    print('function response:', function_call_result)
            else:
                # continue
                self.messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                })
                self.messages.append({'role': "user",
                                 'content': 'At each step,  you should call a function to actually excute your step.'})
        print(colored(f'category: {self.category} assigned', 'green'))
        self.finish_search = True
        if multi_thread:
            sem.release()
            return f'category: {self.category} assigned.'
        else:
            return f'category: {self.category} assigned. The status of current found apis is: {status}' 
      
    def category_search(self):
        """Assign a category to an agent"""
        print(colored(f'assigning category: {self.category}', 'green'))
        self.tools = get_tools_in_category(self.category)
        if len(self.tools) > leaf_tool_number:
            self.functions.append(create_agent_tool_level_function)
            self.messages = [{
                "role": "system",
                "content": CATEGORY_AGENT_PROMPT.replace('{category}', self.category)},
                {"role": "user",
                 "content": f"Task description: {self.query}. All the tools: {self.tools}. Begin!"}]
        else:
            function_call_result = self.create_agent_tool_level(self.category, self.tools)
            return f'category: {self.category} assigned'
        global total_tokens, call_cnt, stop, error_flag
        for i in range(20):
            if stop or total_tokens > 200000:
                if multi_thread:
                    sem.release()
                return f'category: {self.category} assigned'
            t_s = time.time()
            try:
                response = call_gpt(
                                messages=self.messages,
                                functions=self.functions
                            )
            except:
                error_flag = True
                stop = True
                continue
            print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            if isinstance(response, str):
                continue
            with counter_lock:
                total_tokens += response.usage.total_tokens
                call_cnt += 1
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls is not None:
                print('tool call number', len(tool_calls))
            if tool_calls:
                self.messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                }
                )
                for tool_call in tool_calls:
                        
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    print('function call:', function_name, function_args)
                    if function_name.lower() == 'finish':
                        print(colored(f'category: {self.category} assigned', 'green'))
                        print(colored('category finish search', 'green'))
                        self.messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": 'Finished',
                            })
                        self.finish_search = True
                        if multi_thread:
                            sem.release()
                            return f'category: {self.category} assigned.'
                        else:
                            return f'category: {self.category} assigned. The status of current found apis is: {status}'
                    elif function_name not in self.api_mapping:
                        function_name = 'hullucinating_function_name'
                        tool_call.function.name = function_name
                        function_call_result = "Function name error"
                    else:
                        if function_name == "create_agent_tool_level":
                            print(colored('create_agent_tool_level', 'green')) 
                        try:
                        # if True:
                            function_call_result = self.api_mapping[function_name](**json.loads(function_args))
                            if function_name in ['get_apis_in_tool'] and isinstance(function_call_result, str) and 'Illegal tool' in function_call_result:
                                function_call_result = f'Illegal tool. The tool should be in the tool list {self.tools}'
                        except Exception as e:
                            print(e, function_name, function_args, file=open(f'{output_dir}/error.txt', 'a', encoding='utf-8'))
                            if raise_error:
                                raise e
                            function_call_result = 'input format error'
                    self.messages.append(
                        {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(function_call_result),
                        })
                 
                    print('function response:', function_call_result)
            else:
                self.messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                })
                self.messages.append({'role': "user",
                                 'content': 'At each step,  you should call a function to actually excute your step.'})
        print(colored(f'category: {self.category} assigned', 'green'))
        self.finish_search = True
        if multi_thread:
            sem.release()
            return f'category: {self.category} assigned.'
        else:
            return f'category: {self.category} assigned. The status of current found apis is: {status}'
    
    def create_agent_tool_level(self, category: str, tools):
        """Assign a subset of tools in a category to a agent"""
        if isinstance(tools, str):
            tools = eval(tools)
        illegal_tools = []
        for tool in tools:
            if tool not in self.tools:
                illegal_tools.append(tool)
        if len(illegal_tools) > 0:
            print(colored(f'Illegal tools: {illegal_tools} in category: {category} assigned', 'red'))
            return f'Illegal tools: {illegal_tools} in category: {category} assigned'
        if len(tools) > leaf_tool_number:
            return f'Tool number should not exceed the max tool number of {leaf_tool_number}. Please assign again'
        global tree
        with counter_lock:
            tree[category][str(tools)] = {}
        global agents, index
        with counter_lock:
            agents.append(Tool_Agent(self.query, category, tools))
            agents[-1].depth = self.depth + 1
            index += 1
            agents[-1].index = index
        self.sub_agents.append(agents[-1])
        # yield from agents[-1].tool_search()
        global threads
        if multi_thread:
            thread = threading.Thread(target=agents[-1].tool_search)
            sem.acquire()
            thread.start()
            with counter_lock:
                threads.append(thread)
        else:
            agents[-1].tool_search()
        if multi_thread:
            return f'tools {tools} assigned.'
        else:
            return f'tools {tools} assigned. The status of current found apis is: {status}'
    
class Tool_Agent(Agent):
    def __init__(self, query, category=None, tools=None) -> None:
        super().__init__()
        self.category = category
        if isinstance(tools, str):
            tools = eval(tools)
        self.tools = tools
        self.functions = [finish_function]
        self.query = query
        if isinstance(tools, str):
            tools = eval(tools)
        if len(tools) > leaf_tool_number:
            return f"you should assign less than {leaf_tool_number} tools each time"
        else:
            self.functions.extend([
                # get_api_details_function,
                # get_apis_in_tool_function,
                # get_tool_details_function,
                check_if_request_solvable_function,
                # remove_apis_function,
                add_apis_into_api_pool_function,
            ])
            tools_info = query_all_tool_info(category, tools)
            self.messages = [{
                "role": "system",
                "content": TOOL_AGENT_PROMPT.replace('{category}', str(category)).replace('{tools}', str(tools))},
                {"role": "user",
                 "content": f"Task description: {self.query} All the tool description and the contained api_list as a dict: {tools_info}. Begin!"}]
            
        self.api_mapping = {
                "query_all_categories": query_all_categories,
                "get_tools_in_category": get_tools_in_category,
                # "get_apis_in_tool": get_apis_in_tool,
                "Finish": Finish,
                # "get_api_details": get_api_details,
                "create_agent_tool_level": self.create_agent_tool_level,
                "add_apis_into_api_pool": self.add_apis_into_api_pool,
                "check_if_request_solvable": check_if_request_solvable,
                # "remove_apis": self.remove_apis,
                }
        
    def remove_apis(self, api_list):
        """remove apis from the current available api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
        print(colored(f'removing apis: {api_list}', 'red'))
        if isinstance(api_list, str):
            api_list = eval(api_list)
        if not isinstance(api_list, list) or any('category_name' not in ele or 'tool_name' not in ele or 'api_name' not in ele for ele in api_list):
            return 'illegal input, input should be list, each element in the list should have category_name, tool_name, api_name'
        if not all([isinstance(ele['category_name'],str) and isinstance(ele['tool_name'],str) and isinstance(ele['api_name'],str) for ele in api_list]):
            return 'illegal input, category_name, tool_name, api_name should be string'
        origin_api_list = deepcopy(api_list)
        global global_api_list, global_api_list_detailed
        for api in api_list:
            tool_details = get_tool_description(self.category, api['tool_name'])
            api_details = get_api_details(**api)
            api['tool_description'] = tool_details['tool_description'] if isinstance(tool_details, dict) else ''
            api['api_description'] = api_details['description'] if 'description' in api_details else ''
            try:
                with counter_lock:
                    if api in global_api_list:
                        global_api_list.remove(api)
            except:
                pass

        for api in origin_api_list:
            for ele in global_api_list:
                if ele['category_name'] == api['category_name'] and ele['tool_name'] == api['tool_name'] and ele['api_name'] == api['api_name']:
                    with counter_lock:
                        global_api_list.remove(ele)
                    break
        return f'apis removed successfully. Current api number: {len(global_api_list)}. Max api number: {max_api_number}'
    
    
    def create_agent_tool_level(self, category: str, tools):
        """Assign a subset of tools in a category to a agent"""
        if isinstance(tools, str):
            tools = eval(tools)
        illegal_tools = []
        for tool in tools:
            if tool not in self.tools:
                illegal_tools.append(tool)
        if len(illegal_tools) > 0:
            print(colored(f'Illegal tools: {illegal_tools} in category: {category} assigned', 'red'))    
            return f'Illegal tools: {illegal_tools} in category: {category} assigned'
        global tree
        with counter_lock:
            tree[category][str(tools)] = {}
        global agents, index
        with counter_lock:
            agents.append(Tool_Agent(self.query, category, tools))
            agents[-1].depth = self.depth + 1
            index += 1
            agents[-1].index = index
        self.sub_agents.append(agents[-1])
        # generator = agents[-1].tool_search()
        global threads
        if multi_thread:
            thread = threading.Thread(target=agents[-1].tool_search)
            sem.acquire()
            thread.start()
            with counter_lock:
                threads.append(thread)
        else:
            agents[-1].tool_search()
        if multi_thread:
            return f'tools {tools} assigned.'
        else:
            return f'tools {tools} assigned. The status of current found apis is: {status}'
    
    def add_apis_into_api_pool(self, api_list):
        """add apis to the current available api list. required input to be list of dictionaries describing with the keys category_name, tool_name, api_name"""
        print(colored(f'adding apis: {api_list}', 'red'))
        global global_api_list, global_api_list_detailed, stop, status
        if len(global_api_list) + len(api_list) > max_api_number:
            return f'API number exceeds the max API number of {max_api_number}, current API number: {len(global_api_list)}, number of APIs to be added: {len(api_list)}. Please reduce the APIs to be added.'
        if isinstance(api_list, str):
            api_list = eval(api_list)
        # if len(api_list) > 2:
            # return 'too many apis to add, please add less than 2 apis each time'
        if not isinstance(api_list, list) or any('category_name' not in ele or 'tool_name' not in ele or 'api_name' not in ele for ele in api_list):
            return 'illegal input, input should be list, each element in the list should have category_name, tool_name, api_name'
        if not all([isinstance(ele['category_name'],str) and isinstance(ele['tool_name'],str) and isinstance(ele['api_name'],str) for ele in api_list]):
            return 'illegal input, category_name, tool_name, api_name should be string'
        # with counter_lock:
        #     for api in deepcopy(api_list):
        #         with counter_lock:
        #             if api not in global_api_list:
        #                 global_api_list.append(api)
        # if stop:
        #     return 'adding apis failed. Current apis already sufficient to solve the query. Please add again later.'
        # with counter_lock:
        for api in api_list:
            tool_details = get_tool_description(self.category, api['tool_name'])
            if tool_details == 'tool name not found':
                continue
            if api not in global_api_list:
                global_api_list.append(deepcopy(api))
            api_details = get_api_details(**api)
            api['tool_description'] = tool_details['tool_description'] if isinstance(tool_details, dict) else ''
            api['api_description'] = api_details['description'] if 'description' in api_details else ''
            if api not in global_api_list_detailed:
                global_api_list_detailed.append(api)
        if not stop:
            t_s = time.time()
            solvable, reason, tokens = check_task_solvable_by_function(self.query, global_api_list_detailed)
            global total_tokens, call_cnt
            total_tokens += tokens
            call_cnt += 1


            print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            if solvable != 'Unsolvable':
                stop = True
                status = 'The current api list can solve the query.'
                return f'APIs added. Current API number: {len(global_api_list)}. Max API number: {max_api_number}'
                # return 'apis added. The current api list can solve the query. If you think you have finished, call the Finish function.'
            else:
                status = f'The current API list cannot solve the query due to the following reason: {reason}'
                if len(global_api_list) >= max_api_number:
                    stop = True
                # return f'apis added. Current api number: {len(global_api_list)}. Max api number: {max_api_number}'
                return f'APIs added. Current API number: {len(global_api_list)}. Max API number: {max_api_number}.'
                # return f'apis added. Current api number: {len(global_api_list)}. Max api number: {max_api_number}. The current api list cannot solve the query due to the following reason: {reason} Please find apis more purposely.'
        return f'APIs added. Current API number: {len(global_api_list)}. Max API number: {max_api_number}'
        
    def resume_search(self):
        if stop or total_tokens > 200000: 
            self.finish_search = True
            if multi_thread:
                sem.release()
            print(f'tools {self.tools} assigned')
            return f'tools {self.tools} assigned'
        # self.functions.append(remove_apis_function)
        if self.failed_reason is not None:
            if len(self.tools) > leaf_tool_number:
                self.messages.append({"role": "user", "content": REFIND_TOOL_PROMPT.replace('{failed_reason}', str(self.failed_reason))})
            else:
                self.messages.append({"role": "user", "content": REFIND_API_PROMPT.replace('{failed_reason}', str(self.failed_reason))})
            self.failed_reason = None
        return self.tool_search()
    
    def tool_search(self):
        global stop, total_tokens, call_cnt, error_flag
        print(colored(f'assigning tools: {self.tools} in category: {self.category}', 'blue'))
        for i in range(20):
            if stop or total_tokens > 200000:
                print('#'*100)
                print(colored('stop', 'red'))
                if multi_thread:
                    sem.release()
                return f'tools {self.tools} assigned'
            t_s = time.time()
            try:
                response = call_gpt(
                                messages=self.messages,
                                functions=self.functions
                            )
            except:
                error_flag = True
                stop = True
                continue
            print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            if isinstance(response, str):
                continue
            with counter_lock:
                total_tokens += response.usage.total_tokens
                call_cnt += 1
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls is not None:
                print('tool call number', len(tool_calls))
            if tool_calls:
                # self.messages.append(response.choices[0].message)
                self.messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                }
                )
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    print('function call:', function_name, function_args)
            
                    if function_name.lower() == 'finish':
                        self.messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": 'Finished',
                            })
                        print(f'tools {self.tools} assigned')
                        print(colored('tool finish search', 'green'))
                        self.finish_search = True
                        if multi_thread:
                            sem.release()
                            return f'tools {self.tools} assigned'
                        else:
                            return f'tools {self.tools} assigned. The status of current found apis is: {status}'
                    if function_name not in self.api_mapping:
                        function_name = 'hullucinating_function_name'
                        tool_call.function.name = function_name
                        function_call_result = "Function name error"
                    elif function_name == 'add_apis_into_api_pool':
                        with counter_lock:
                            try:
                                function_call_result = self.api_mapping[function_name](**json.loads(function_args))
                            except Exception as e:
                                print(e, function_name, function_args, file=open(f'{output_dir}/error.txt', 'a', encoding='utf-8'))
                                if raise_error:
                                    raise e
                                function_call_result = 'input format error'
                    else:
                        try:
                            function_call_result = self.api_mapping[function_name](**json.loads(function_args))
                            if function_name in ['get_apis_in_tool'] and isinstance(function_call_result, str) and 'Illegal tool' in function_call_result:
                                function_call_result = f'Illegal tool. The tool should be in the tool list {self.tools}'
                        except Exception as e:
                            print(e, function_name, function_args, file=open(f'{output_dir}/error.txt', 'a', encoding='utf-8'))
                            if raise_error:
                                raise e
                            function_call_result = 'input format error'
                    self.messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_call_result),
                        })
                    print('function response:', function_call_result)
            else:
                # continue
                self.messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                })
                self.messages.append({'role': "user",
                                 'content': 'At each step,  you should call a function to actually excute your step.'})
        print(f'tools {self.tools} assigned')
        self.finish_search = True
        if multi_thread:
            sem.release()
            return f'tools {self.tools} assigned'
        else:
            return f'tools {self.tools} assigned. The status of current found apis is: {status}'
            


class Main_Search_Agent(Agent):
    def __init__(self, query) -> None:
        super().__init__()
        self.categories = []
        self.query = query
        self.api_mapping = {
    "query_all_categories": query_all_categories,
    "get_tools_in_category": get_tools_in_category,
    "get_apis_in_tool": get_apis_in_tool,
    # "retrieve_context": retrieve_context,
    "Finish": Finish,
    "get_api_details": get_api_details,
    # "locate_api": locate_api,
    # "query_tool_details": query_tool_details,
    "get_tools_descriptions": get_tools_descriptions,
    "create_agent_category_level": self.create_agent_category_level,
    }
        self.functions = [
            # get_categories_function.to_json_schema(),
            # get_tools_in_category_function.to_json_schema(),
            # locate_api_function,
            get_tools_in_category_function,
            get_tools_descriptions_function,
            create_agent_category_level_function,
            # retrieve_context_function,
        ]
        self.functions.append(finish_function)
        
        self.messages = [{
            "role": "system",
            "content": META_AGENT_PROMPT.replace('{categories}', str(query_all_categories()))},
            {"role": "user",
             "content": f"Task description: {query}.\
             Please determine relevant categories and assign them use the create_agent_category_level function. Begin!"}]
        #  All the categories and the contained tools as a dictionary: {all_cates_all_tools}
            #  "content": f"Task description: {query}. All the categories as well as the contained tools and their descriptions: {category_tool_info}\
   
    def create_agent_category_level(self, category):
        """Assign a category to an agent"""
        # print(colored(f'assigning category: {category}', 'green'))
        global agents, tree, index
        if category in self.categories:
            print(colored(f'category: {category} already assigned', 'green'))
            return f'category: {category} already assigned'
        with counter_lock:
            tree[category] = {}
        if not isinstance(category, str):
            return f'Error: category: {category} is not str'
        if category not in query_all_categories():
            return f'category: {category} not in database'
        self.categories.append(category)
        with counter_lock:
            agents.append(Category_Agent(self.query, category))
            index += 1
            agents[-1].depth = self.depth + 1
            agents[-1].index = index
        self.sub_agents.append(agents[-1])
        if multi_thread:
            thread = threading.Thread(target=agents[-1].category_search)
            sem.acquire()
            thread.start()
            with counter_lock:
                threads.append(thread)
        else:
            agents[-1].category_search()
        if multi_thread:
            return f'category: {category} assigned.'
        else:
            return f'category: {category} assigned. The status of current found apis is: {status}'

    def resume_search(self):
        if stop or total_tokens > 200000: 
            self.finish_search = True
            if multi_thread:
                sem.release()
            return self.categories
        if self.failed_reason is not None:
            self.messages.append({"role": "user", "content": REFIND_CATEGORY_PROMPT.replace('{failed_reason}', str(self.failed_reason))})
            self.failed_reason = None
        return self.assign_main(self.query)
    
    def assign_main(self, query):
        global total_tokens, stop, error_flag, call_cnt
        for i in range(20):
            if stop or total_tokens > 200000:
                if multi_thread:
                    sem.release()
                return self.categories
            t_s = time.time()
            try:
                response = call_gpt(
                                messages=self.messages,
                                functions=self.functions
                            )
            except:
                error_flag = True
                stop = True
                continue
            print(time.time() - t_s, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            if isinstance(response, str):
                print(response)
                print('response is str')
                continue
            with counter_lock:
                total_tokens += response.usage.total_tokens
                call_cnt += 1
            print('#'*100)
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls is not None:
                print('tool call number', len(tool_calls))
            if tool_calls:
                self.messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                }
                )
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    if function_name.lower() == 'finish':
                        self.messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": 'Finished',
                            })
                        self.finish_search = True
                        print(colored('main finish search', 'green'))
                        if multi_thread:
                            sem.release()
                        return self.categories
                
                    if function_name not in self.api_mapping:
                        function_name = 'hullucinating_function_name'
                        tool_call.function.name = function_name
                        function_call_result = "Function name error"
                    else:
                        if function_name == "retrieve_context" and 'query' not in function_args:
                            function_call_result = self.api_mapping[function_name](query, **json.loads(function_args))
                        else:
                            try:
                                function_call_result = self.api_mapping[function_name](**json.loads(function_args))
                                if function_name in ['get_apis_in_tool'] and isinstance(function_call_result, str) and 'Illegal tool' in function_call_result:
                                    function_call_result = f'Illegal tool. The tool should be in the tool list {self.tools}'
                            except Exception as e:
                                print(e, function_name, function_args, file=open(f'{output_dir}/error.txt', 'a', encoding='utf-8'))
                                if raise_error:
                                    raise e
                                function_call_result = 'input format error'
                    self.messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": str(function_call_result),
                            }
                        )
                    print('function call:', function_name, function_args)
                    print('function response:', function_call_result)
            else:
                self.messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content if response.choices[0].message.content is not None else '',
                })
                self.messages.append({'role': "user",
                                 'content': 'At each step,  you should call a function to actually excute your step.'})
        self.finish_search = True
        if multi_thread:
            sem.release()
        return self.categories

create_agent_category_level_function = {
    'name': 'create_agent_category_level',
    'description': 'Assign a category to an agent',
    'parameters': {
        'type': 'object',
        'properties': {
            'category': {'type': 'string'}
        },
        'required': ['category']
    }
}

create_agent_tool_level_function = {
    'name': 'create_agent_tool_level',
    'description': 'Assign a subset of tools in a category to an agent',
    'parameters': {
        'type': 'object',
        'properties': {
            'category': {'type': 'string'}, 
            'tools': {
                'type': 'array', 
                'items': {'type': 'string'}
            }
        },
        'required': ['category', 'tools']
    }
}

 
    
finish_function = {
                "name": "Finish",
                "description": "If you think you have finished, call this function.",
                "parameters": {
                    "type": "object",
                    'properties': {
                }
                }
}
import time
from anytool.dfs_gt import solve_given_api_main
output_dir = args.output_dir
query_path = args.query_path
if __name__ == "__main__":
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs('output', exist_ok=True)
    success_cnt = 0
    pass_cnt = 0
    unsolvable_task_cnt = 0
    unsolvable_list = json.load(open('misc/unsolvable.json', 'r', encoding='utf-8'))
    total_cnt = 0
    query_data_all = json.load(open(query_path, 'r', encoding='utf-8'))
    for query_data in query_data_all:
        try:
            query_id = query_data['query_id']
            query = query_data['query']
            threads = []
            global_api_list = []
            global_api_list_detailed = []   
            call_cnt = 0
            total_tokens = 0
            solve_tokens = 0
            agents = []
            index = 0
            failed_reason = None
            stop = False
            error_flag = False
            status = ''
            solved = False
            check_solved = 'Unsolved'
            tree = {}
            result_list = []
            reason_list = []
            assign_results = {}
            assign_results['api_list'] = []
            assign_results['stop'] = []
            ts = time.time()
            resumed_agents = []
            print(query_id, query, file=open(f'{output_dir}/query.txt', 'a', encoding='utf-8'))
            if not args.include_unsolvable and int(query_id) in unsolvable_list:
                unsolvable_task_cnt += 1
                print(unsolvable_task_cnt)
                print('Unsolvable human', unsolvable_task_cnt, pass_cnt, success_cnt, total_cnt, file=open(f'{output_dir}/success_cnt.txt', 'a', encoding='utf-8'))
                continue
            total_cnt += 1
            task_solvable = 'Solvable'
            solvable_reason = 'Solvable checked by human'
            if os.path.exists(f'{output_dir}/{query_id}.json'):
                assign_results = json.load(open(f'{output_dir}/{query_id}.json', 'r', encoding='utf-8'))
                if 'last_solve_time' in assign_results:
                    solved = assign_results['solved']
                    check_solved = assign_results['check_solved']
                    last_solve_time = assign_results['last_solve_time']
                    if solved:
                        pass_cnt += 1
                    if args.recheck_solved:
                        check_solved, reason, _ = check_solved_toolbench(f'{output_dir}/{query_id}_{last_solve_time}_DFS_woFilter_w2.json', assign_results['query_id'])
                        assign_results['check_solved'] = check_solved
                        assign_results['reason'] = reason
                        json.dump(assign_results, open(f'{output_dir}/{query_id}.json', 'w', encoding='utf-8'), indent=4)

                    api_list = assign_results['api_list'][-1]
                    api2origin = json.load(open(f'{output_dir}/{query_id}_{last_solve_time}_DFS_woFilter_w2.json', 'r', encoding='utf-8'))['api2origin']
                    if check_solved == 'Solved' and len(api_list) <= max_api_number:
                        success_cnt += 1
                    print(query_id, check_solved, unsolvable_task_cnt, success_cnt, total_cnt, success_cnt/total_cnt)
                    if assign_results['result'] != 'Timeout':
                        continue
                # continue
            print(f'query: {query}')
            flag = False
            try:
                runner = Main_Search_Agent(query)
                agents.append(runner)
                if multi_thread:
                    thread = threading.Thread(target=runner.assign_main, args=(query,))
                    sem.acquire()
                    thread.start()
                    threads.append(thread)
                else:
                    iter_func = runner.assign_main(query)
                messages = None
                cnt = 0
                solve_data = {}
                if multi_thread:
                    while True:
                        thread_num = len(threads)
                        has_thread_alive = False
                        for thread in threads:
                            if thread.is_alive():
                                has_thread_alive = True
                                thread.join()
                        if not has_thread_alive:
                            break
                        if error_flag: raise Exception('GPT Call Error')
                    threads = []
                # refind
                check_solved = ''
                max_depth = max([agent.depth for agent in agents])  
                while not all([agent.finish_search for agent in agents]) or not flag:
                    if check_solved == 'Solved':
                        break
                    max_depth = max([agent.depth for agent in agents])  
                    depth = max_depth
                    while all([agent.finish_search for agent in agents if agent.depth == depth]) and depth >= 0:
                        depth -= 1
                    if depth < 0 and flag:
                        break
                    agents_to_resume = [agent for agent in agents if not agent.finish_search and agent.depth == depth]
                    if total_tokens > 200000 and flag:
                        solved = False
                        check_solved = 'Timeout'
                        solve_data = {'result': 'Timeout'}
                        break
                    cnt += 1
                    failed_reason = None
                    print(len(global_api_list), file=open(f'{output_dir}/api_list_len.txt', 'a', encoding='utf-8'))
                    print(global_api_list, file=open(f'{output_dir}/api_list.txt', 'a', encoding='utf-8'))
                    print('#'*100)
                    assign_results['api_list'].append(deepcopy(global_api_list))
                    if stop or not flag or all([agent.finish_search for agent in agents]) and len(global_api_list) > 0:
                        flag = True
                        last_solve_time = cnt
                        t_s = time.time()
                        selected_api_list = deepcopy(global_api_list)

                        solved, solve_data = solve_given_api_main(query, selected_api_list, f'{query_id}_{cnt}', messages)

                        print('solve time:', time.time() - t_s, 'api number:', len(global_api_list),file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
                        result_list.append(deepcopy(solve_data['result']))
                        print(solve_data['result'], solved)
                        if not solved or any([word in solve_data['result']['final_answer'] for word in exclusion_words]):
                            check_solved = 'Unsolved'
                            reason = solve_data['result']
                        else:
                            check_solved, reason, tokens = check_solved_toolbench(f'{output_dir}/{query_id}_{last_solve_time}_DFS_woFilter_w2.json', query_id, task_solvable, solvable_reason)
                            total_tokens += tokens
                        print(colored((check_solved, reason), 'red'))
                        failed_reason = reason
                        dfs_data = json.load(open(f'{output_dir}/{query_id}_{last_solve_time}_DFS_woFilter_w2.json', 'r', encoding='utf-8'))
                        total_tokens += dfs_data['answer_generation']['total_tokens']
                        solve_tokens += dfs_data['answer_generation']['total_tokens']
                        if check_solved == 'Solved':
                            break
                        try:
                            messages = dfs_data['answer_generation']['train_messages'][-1]
                        except:
                            messages = None
                        api_list_to_prune = []
                        for standardized_api_name, origin_api in dfs_data['api2origin'].items():
                            if standardized_api_name in str(failed_reason):
                                if origin_api in global_api_list:
                                    api_list_to_prune.append(origin_api)
                        print(colored(api_list_to_prune, 'red'))
                        print(len(api_list_to_prune))
                        remove_apis(api_list_to_prune)
                        if len(global_api_list) >= max_api_number:
                            break
                        # print(api_list_to_prune, file=open(f'{output_dir}/prune_api_list.txt', 'a', encoding='utf-8'))
                        stop = False
                    else:
                        assert status != 'The current api list can solve the query.'
                        failed_reason = status
                    reason_list.append(failed_reason)
                    print(colored('Refind Begin', 'red'))
                    print(colored(agents_to_resume, 'red'))
                    print([agent.finish_search for agent in agents_to_resume])


                    threads = []
                    resume_cnt = 0 
                    resumed_agents.append([(str(a), a.index) for a in agents_to_resume])
                    for agent in reversed(agents_to_resume):
                        if agent.finish_search: continue
                        resume_cnt += 1
                        agent.failed_reason = str(failed_reason)
                        print(colored(('resuming', agent, agent.depth), 'red'))
                        print(colored(('resuming', agent, agent.depth), 'red'), file=open(f'{output_dir}/resume.txt', 'a', encoding='utf-8'))
                        if multi_thread:
                            thread = threading.Thread(target=agent.resume_search)
                            sem.acquire()
                            thread.start()
                            threads.append(thread)
                        else:
                            agent.resume_search()
                    if multi_thread:
                        while True:
                            thread_num = len(threads)
                            for thread in threads:
                                if thread.is_alive():
                                    thread.join()
                            if thread_num == len(threads):
                                break
                            if error_flag: raise Exception('GPT Call Error')
                    if not stop:
                        check_if_request_solvable()
                        print(colored(f'status:{status}', 'red'))
                    assign_results['stop'].append(stop)
            except KeyboardInterrupt as e:
                continue

            assign_results['api_complete'] = flag

            find_messages = []
            for agent in agents:
                find_messages.append([str(agent), agent.depth, agent.messages])
            assign_results['tree'] = tree
            assign_results['max_depth'] = max_depth
            assign_results['query'] = query
            assign_results['find_messages'] = find_messages
            assign_results['status'] = status
            assign_results['solved'] = solved
            assign_results['query_id'] = query_id
            assign_results['finish_search'] = [agent.finish_search for agent in agents]
            assign_results['flag'] = flag
            if check_solved == 'Solved':
                success_cnt += 1
            else:
                print(output_dir, 'failed', file=open(f'{output_dir}/failed.txt', 'a', encoding='utf-8'))
            if solved:
                pass_cnt += 1
            assign_results['loop_times'] = cnt
            assign_results['last_solve_time'] = last_solve_time
            if 'messages' in solve_data:
                assign_results['solve_messages'] = solve_data['messages']
            def parse_tree(node, tree):
                tree[str(node)] = {}
                if not isinstance(node, Main_Search_Agent):
                    tree[str(node)]['category'] = node.category
                    tree[str(node)]['tools'] = len(node.tools)
                    tree[str(node)]['index'] = node.index
                tree[str(node)]['children'] = {}
                for agent in node.sub_agents:
                    tree[str(node)]['children'].update(parse_tree(agent, {}))
                return tree
            agent_tree = parse_tree(runner, {})
            tree_results = {}
            tree_results['agent_tree'] = agent_tree
            tree_results['resume_agents'] = resumed_agents  
            tree_results['result_list'] = result_list
            tree_results['reason_list'] = reason_list

            json.dump(tree_results, open(f'{output_dir}/{query_id}_agent_tree.json', 'w', encoding='utf-8'), indent=4)   
            assign_results['resume_agents'] = resumed_agents
            assign_results['result_list'] = result_list
            assign_results['reason'] = reason
            assign_results['reason_list'] = reason_list
            assign_results['call_cnt'] = call_cnt
            assign_results['total_tokens'] = total_tokens
            assign_results['solve_tokens'] = solve_tokens
            if 'result' in solve_data:
                assign_results['result'] = solve_data['result']
            assign_results['check_solved'] = check_solved
            json.dump(assign_results, open(f'{output_dir}/{query_id}.json', 'w', encoding='utf-8'), indent=4)
            print(check_solved, total_tokens, time.time() - ts, query_path, file=open(f'{output_dir}/time.txt', 'a', encoding='utf-8'))
            print(query_id, task_solvable, cnt, check_solved, unsolvable_task_cnt, pass_cnt, success_cnt, total_cnt, success_cnt/total_cnt,  file=open(f'{output_dir}/success_cnt.txt', 'a', encoding='utf-8'))
        except Exception as e:
            print(e)
            continue