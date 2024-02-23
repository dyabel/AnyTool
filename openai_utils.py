import openai
from tenacity import retry, wait_random_exponential, stop_after_attempt
import time
import os
from datetime import datetime
import tiktoken
from copy import deepcopy
import json
from config import *
from arguments import parse_args
import importlib
from termcolor import colored
enc = tiktoken.encoding_for_model("gpt-4")
args = parse_args()
output_dir = args.output_dir
if api_type == "azure":
    from openai import AzureOpenAI as Client
else:
    from openai import OpenAI as Client
client = Client(
api_key=api_key,
api_version=api_version,
azure_endpoint = api_base
)
# turbo_client = Client(
# api_key=api_key,
# api_version=api_version,
# azure_endpoint = api_base
# )

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def call_gpt(messages, functions=None, **kwargs):
    if 'model' not in kwargs:
        kwargs['model'] = model_name
    messages_converted = messages
    for message in messages_converted:
        if "tool_calls" in message:
            message['function_call'] = message['tool_calls'][0]['function']
            message.pop('tool_calls')
        if "tool_call_id" in message:
            message.pop('tool_call_id')
            message['role'] = 'function'
    @retry(wait=wait_random_exponential(multiplier=10, max=50), stop=stop_after_attempt(5))
    def call_gpt_retry(messages, functions):
        ts = time.time()
        try:
            response = client.chat.completions.create(
                        seed=123,
                        messages=messages,
                        functions=functions,
                        **kwargs
                    )
        except openai.BadRequestError as e:
            # try:
            #     response = turbo_client.chat.completions.create(
            #             seed=123,
            #             model='gpt-4-turbo',
            #             messages=messages,
            #             functions=functions
            #         )
            # except Exception as e:
            #     raise e
            raise e
           
        except openai.RateLimitError as e:
            time.sleep(50)
            raise e
        except openai.InternalServerError as e:
            raise e
        except Exception as e:
            raise e
            
        t = time.time() - ts
        return response, t
    t_s = time.time()
    try:
        response, t_real = call_gpt_retry(messages_converted, functions)
        # json_content = response.choices[0].message.content
        t = time.time() - t_s
        print('minus:', t-t_real, file=open(os.path.join(output_dir, "time.txt"), "a"))
        # print(response.choices[0].message.function_call)
        if response.choices[0].finish_reason == 'function_call':
            response_json = json.loads(response.json())
            tool_call = {'arguments': response_json['choices'][0]['message']['function_call']['arguments'], 'name': response_json['choices'][0]['message']['function_call']['name']}
            response.choices[0].message.tool_calls = [dotdict({'id':'111', 'function':dotdict(tool_call)})]
        else:
            if model_name == 'gpt-4-turbo':
                response.choices[0].message.tool_calls = []
            # else:
                # response.choices[0].message['tool_calls'] = []
        if response.usage is None:
            token_cnt = len(enc.encode(str(functions))) + len(enc.encode(str(messages))) + len(enc.encode(str(response.choices[0].message.content)))
            response.usage = dotdict({'total_tokens': token_cnt})
        else:
            print(colored('tokens', 'blue'), colored(response.usage.total_tokens, 'blue'))
        return response
        
    except Exception as e:
        raise e
        t = time.time() - t_s
        print('minus:', t, file=open(os.path.join(output_dir, "time.txt"), "a"))
        return "openai error"

def call_gpt_no_func(messages):
    @retry(wait=wait_random_exponential(multiplier=60, max=100), stop=stop_after_attempt(10))
    def call_gpt_retry(messages):
        response = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                    )
        return response
    # try:
    return call_gpt_retry(messages)

#


def call_gpt_turbo(messages, functions):
    functions_new = []
    for function in functions:
        functions_new.append({
            "type": "function",
            "function": function
        })
    # time.sleep(1)
        
    @retry(wait=wait_random_exponential(multiplier=5, max=20), stop=stop_after_attempt(10))
    def call_gpt_retry(messages, functions):
        t_s = time.time()
        try:
            response = client.chat.completions.create(
                            model="gpt-4-turbo",
                            messages=messages,
                            seed=123,
                            # response_format={"type": "json_object"},
                            tools=functions,
                            # tool_choice="tool",  # auto is default, but we'll be explicit
                            tool_choice="auto",  # auto is default, but we'll be explicit

                        )
        except openai.BadRequestError as e:
            # raise e
            return "bad request", 0
        except openai.RateLimitError as e:
            time.sleep(50)
            raise e
        except openai.InternalServerError as e:
            return "internal server error", 0
        
        t = time.time() - t_s
        return response, t
    t_s = time.time()
    try:
    # if True:
        response, t_real = call_gpt_retry(messages, functions_new)
        t = time.time() - t_s
        print(f'{datetime.now()}', file=open(os.path.join(output_dir, "time.txt"), "a"))
        if not isinstance(response, str):
            print(response.usage.total_tokens, file=open(os.path.join(output_dir, "time.txt"), "a"))
        print('minus:', t-t_real, file=open(os.path.join(output_dir, "time.txt"), "a"))
        print('#'*100, '\n\n', messages, '\n\n', functions, '\n\n', response, file=open(os.path.join('output', "log.txt"), "a"))
        return response
    except Exception as e:
        raise e
        t = time.time() - t_s
        print('minus:', t, file=open(os.path.join(output_dir, "time.txt"), "a"))
        return "openai error"
# Example dummy function hard coded to return the same weather
# In production, this could be your backend API or an external API
def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    if "tokyo" in location.lower():
        return json.dumps({"location": "Tokyo", "temperature": "10", "unit": unit})
    elif "san francisco" in location.lower():
        return json.dumps({"location": "San Francisco", "temperature": "72", "unit": unit})
    elif "paris" in location.lower():
        return json.dumps({"location": "Paris", "temperature": "22", "unit": unit})
    else:
        return json.dumps({"location": location, "temperature": "unknown"})
if __name__ == "__main__":
    messages = [{"role": "user", "content": "What's the weather like in San Francisco, Tokyo, and Paris?"}]
    tools = [
            {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        "required": ["location"],
                    },
                },
        ]
    response = call_gpt(messages, tools)
    print(response)
