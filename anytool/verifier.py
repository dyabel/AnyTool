import openai
from openai_function_calling import FunctionInferer
import json
from anytool.prompt_template import *
from tenacity import retry, wait_random_exponential, stop_after_attempt
from concurrent.futures import ThreadPoolExecutor,as_completed
from openai_utils import call_gpt
import time
from termcolor import colored
from arguments import parse_args
from anytool.check_solved import compute_pass_rate, process_invalid_data, process_valid_data
import os
from tqdm import tqdm
import random
import importlib
args = parse_args()
output_dir = args.output_dir




def Finish(answer:str, reason:str=None):
    """Finish the conversation"""
    return answer, reason

def check_task_solvable(query):
    messages = [{
        "role": "system",
        "content": CHECK_SOLVABLE_PROMPT 
    },
        {"role": "user", 
        "content": f"Please check whether the following query is solvable: {query}. Begin!"}
        ]
    for i in range(5):
        # try:
        if True:
            t_s = time.time()
            response = call_gpt(
                            messages=messages,
                            functions=[solvable_finish_function]
                        )
            print(time.time() - t_s)
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls:
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    if function_name == 'Finish':
                        try:
                            solvable, reason = Finish(**json.loads(function_args))
                        except:
                            continue
                            # solvable, reason = Finish(json.loads(function_args))
                            
                    else:
                        continue
                    print(solvable, query, file=open('result/solvable.txt', 'a', encoding='utf-6'))
                    if solvable == 'Unsolvable' and reason is None:
                        messages.append({"role": "user", "content": 'You must give reason if the answer is Unsolvable'})
                    if reason is not None:
                        print(reason, file=open('result/solvable.txt', 'a', encoding='utf-8'))
                    else:
                        reason = ''
                    return solvable, reason
            else:
                print('Thought:', response.choices[0].message.content)
                continue
                # messages.append({"role": "assistant", "content": response.choices[0].message.get('content', '')})
        # except:
        #     pass
    print('No response from the model', file=open('result/solvable.txt', 'a', encoding='utf-8'))
    return 'No response', 'No response from the model'

def check_task_solvable_by_function(query, functions):
    # return 'Solvable', ''
    # print(functions)
    messages = [{
        "role": "system",
        "content": CHECK_SOLVABLE_BY_FUNCTION_PROMPT 
    },
        {"role": "user", 
        "content": f"Query: {query}.  Available_tools: {functions}. Begin!"}
        ]
    for i in range(5):
        # try:
        if True:
            t_s = time.time()
            response = call_gpt(
                            messages=messages,
                            functions=[solvable_finish_function]
                        )
            print(time.time() - t_s)
            tool_calls = response.choices[0].message.tool_calls
            print('Thought:', response.choices[0].message.content)
            if tool_calls:
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    if function_name.lower() == 'finish':
                        try:
                            solvable, reason = Finish(**json.loads(function_args))
                        except:
                            continue
                            # solvable, reason = Finish(json.loads(function_args))
                            
                    else:
                        continue
                    print(solvable, query, file=open('result/solvable.txt', 'a', encoding='utf-8'))
                    if solvable == 'Unsolvable' and reason is None:
                        messages.append({"role": "user", "content": 'You must give reason if the answer is Unsolvable'})
                    if reason is not None:
                        print(reason, file=open('result/solvable.txt', 'a', encoding='utf-8'))
                    else:
                        reason = ''
                    return solvable, reason, response.usage.total_tokens
            else:
                print('Thought:', response.choices[0].message.content)
                continue
                # messages.append({"role": "assistant", "content": response.choices[0].message.get('content', '')})
        # except:
        #     pass
    # print('No response from the model', file=open('result/solvable.txt', 'a', encoding='utf-8'))
    return 'Unsure', 'Connection to the assessing model timeout. You can call the check_current_api_suffucient function to check whether the current APIs is sufficient to solve the query.', response.usage.total_tokens

def check_task_solved(query, answer):
    messages = [{
        "role": "system",
        "content": CHECK_SOLVED_PROMPT 
    },
        {"role": "user", 
        "content": f"Please check whether the following answer solves the query. Query: {query}. Answer: {answer} Begin!"}
        ]
    print(colored('begin check solved', 'red'))
    for i in range(10):
        response = call_gpt(
                        messages=messages,
                        functions=[solve_finish_function]
                    )
        if isinstance(response, str):
            return 'Timeout', 'Timeout'
        tool_calls = response.choices[0].message.tool_calls
        print('Thought:', response.choices[0].message.content)
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                print(function_name, function_args)
                if function_name.lower() == 'finish':
                    solvable, reason = Finish(**json.loads(function_args))
                    print(solvable, query, file=open('result/solved.txt', 'a', encoding='utf-8'))
                    if solvable == 'Unsolved' and reason is None:
                        messages.append({"role": "user", "content": 'You must give reason if the answer is Unsolvable'})
                        continue
                    if reason is not None:
                        print(reason, file=open('result/solved.txt', 'a', encoding='utf-8'))
                    else:
                        reason = ''
                    return solvable, reason
                    
        else:
            # continue
            messages.append({"role": "assistant", "content": '' if response.choices[0].message.content is None else response.choices[0].message.content})
            messages.append({"role": "user", "content": "You must call the Finish function but you didn't"})
    print('No response from the model', file=open('result/solvable.txt', 'a', encoding='utf-8'))
    print('No response from the model')
    return 'No response', 'No response from the model'

def check_solved_toolbench(output_path, query_id, task_solvable=None, solvable_task_reason=None):
    print('begin check solved')
    data_dict = json.load(open(output_path, 'r', encoding='utf-8'))
    method = 'DFS_woFilter_w2'
    if not data_dict['answer_generation']['valid_data']:
        example = process_invalid_data(method,data_dict)
    else:
        example = process_valid_data(method,data_dict['answer_generation'])
    # example['available_tools'] = query_data[str(ori_query_id)]['available_tools']
    future = []
    answer_dict = {'passed':0, 'failed':0}
    with ThreadPoolExecutor(32) as pool:
        print(task_solvable, solvable_task_reason, file=open(os.path.join(output_dir, 'solvable.txt'), 'a', encoding='utf-8'))
        for _ in range(3):
            future.append(pool.submit(
                compute_pass_rate,
                query_id,
                example,
                task_solvable,
                solvable_task_reason
            ))
    reason_list = []
    total_tokens = 0
    for thd in tqdm(as_completed(future),total=len(future),ncols=100):
        query_id, task_solvable, is_solved, machine_label, reason, not_hallucinate, tokens = thd.result()
        total_tokens += tokens
        if machine_label == 'passed':
            answer_dict['passed'] += 1
        else:
            answer_dict['failed'] += 1
        reason_list.append(reason)
            
    if answer_dict['passed'] >= answer_dict['failed']:
        return 'Solved', random.sample(reason_list, 1)[0], total_tokens
    else:
        reason = random.sample(reason_list, 1)[0]
        return 'Unsolved', reason, total_tokens
    
    

def check_task_complete(query, functions):
    messages = [{
        "role": "system",
        "content": CHECK_COMPLETE_PROMPT 
    },
        {"role": "user", 
        "content": f"Please check whether the following query has the complete information for calling the functions : {query}. And the functions is {functions}. Begin!"}
        ]
    for i in range(5):
        response = call_gpt(
                        messages=messages,
                        functions=[finish_function]
                    )
        tool_calls = response.choices[0].message.tool_calls
        print('Thought:', response.choices[0].message.content)
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                if function_name == 'Finish':
                    solvable, reason = Finish(**json.loads(function_args))
                    print(solvable, query, file=open('result/complete.txt', 'a', encoding='utf-8'))
                    if solvable == 'Incomplete' and reason is None:
                        messages.append({"role": "user", "content": 'You must give reason if the answer is Incomplete'})
                    if reason is not None:
                        print(reason, file=open('result/complete.txt', 'a', encoding='utf-8'))
                    else:
                        reason = ''
                    return solvable, reason
        else:
            messages.append({"role": "assistant", "content": '' if response.choices[0].message.content is None else response.choices[0].message.content})
            messages.append({"role": "user", "content": "You must call the Finish function but you didn't"})
    return 'No response', 'No response from the model'

# finish_function = FunctionInferer.infer_from_function_reference(Finish)
finish_function = {
                "name": "Finish",
                "description": "Finish the conversation with the answer, the answer should be in [Complete, Incomplete]. If the answer is Incomplete, please provide the reason.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer":{"type":"string"},
                        "reason":{"type":"string",
                                  "description":"You must have this if answer==Incomplete."}
                    },
                    "required": ["answer"]
                }
                }

solvable_finish_function = {
                "name": "Finish",
                "description": "Finish the conversation with the answer, the answer should be in [Solvable, Unsolvable, Unsure]. If the answer is Unsolvable or Unsure, please provide the reason.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer":{"type":"string"},
                        "reason":{"type":"string",
                                  "description":"You must have this if answer==Unsolvable or answer==Unsure."}
                    },
                    "required": ["answer"]
                }
                }


solve_finish_function = {
                "name": "Finish",
                "description": "Finish the conversation with the answer, the answer should be in [Solved, Unsolved]. If the answer is 'Unsolved', please provide the reason.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer":{"type":"string"},
                        "reason":{"type":"string",
                                  "description":"You must have this if answer==Unsolved."}
                    },
                    "required": ["answer"]
                }
                }
if __name__ == "__main__":
    result_path = 'data/reproduction_data/model_predictions_converted/gpt-4-0613_dfs/G1_category.json'
    output_path = 'result2/test_instruction/check_solved/G1_category.txt'
    test_ids = list(json.load(open('data/test_query_ids/G1_category.json', 'r', encoding='utf-8')).keys())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    data_dict = json.load(open(result_path, 'r', encoding='utf-8'))
    success_cnt = 0
    total_cnt = 0
    check_solved_dict = {}
    for query_id, example in data_dict.items():
        if query_id not in test_ids:
            continue
        total_cnt += 1
        query = example['query']
        answer = example['answer']['final_answer']
        check_solved, reason = check_task_solved(query, answer)
        print(check_solved, reason)
        if check_solved == 'Solved':
            success_cnt += 1
        print(success_cnt, total_cnt, file=open(output_path, 'a', encoding='utf-8'))
        check_solved_dict[query_id] = check_solved
        json.dump(check_solved_dict, open('result2/test_instruction/check_solved/G1_category.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
