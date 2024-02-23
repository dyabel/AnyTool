import os
import json
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from tqdm import tqdm
import numpy as np
import argparse
import random
from evaluation import UserEvaluation,BaseToolMethod
from evaluators import load_registered_automatic_evaluator
from typing import List,Dict,Callable
import pandas as pd

abs_dir = os.path.split(__file__)[0]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default=os.path.join(abs_dir,'dataset','test.json'),help='where to store the method output.')
    parser.add_argument('--method',default='unknown',help='what the name of the method.')
    parser.add_argument('--ref_method',default='gpt-3.5-turbo_CoT',help='what the reference method is')
    parser.add_argument('--ref_output',default=os.path.join(abs_dir,'dataset','ref_sample.json'),help='where the reference answer stored')
    parser.add_argument('--evaluators_cfg_path',default=os.path.join(abs_dir,'evaluators'),help='where the evaluators config files are stored')
    parser.add_argument('--evaluator',default='tooleval_gpt-3.5-turbo_normalized',help='which evaluator to use')
    parser.add_argument('--max_eval_threads',default=1,type=int,help='how many threads to use for evaluation')
    parser.add_argument('--evalset',default='default_evalset',help='which the evaluation dataset to use')
    parser.add_argument('--eval_server_address',default='http://localhost:8000',help='the address of the evaluation server')
    parser.add_argument('--use_existed_output',default=False,action='store_true',help='whether to use the existed output')
    
    return parser.parse_args()
    

## !!define your method here !!
class SampleMethod(BaseToolMethod):
    def __init__(self):
        super().__init__()
    def forward(self,query:str,tools:List[Dict],tool_func:Callable)->Dict:
        return {}
    def convert_result_to_dict(self,result):
        return {
            'method': 'sample',
            'total_steps': 0,
            'final_answer': '',
            'answer_details': []
        }
def process_answer(answer: Dict):
    # answer['final_answer'] = answer['final_answer'][:1000]
    # answer['answer_details'] = answer['answer_details'][:3000]
    # answer.pop('method', None)
    return answer
if __name__=='__main__':
    args = parse_args()

    # exec_generating_method_outputs = True
    # if os.path.exists(args.output):
    #     print('Output file {} already exists!'.format(args.output))
    #     if args.use_existed_output:
    #         exec_generating_method_outputs = False
    #     else:
    #         print('Overwrite? (y/n)')
    #         exec_generating_method_outputs = input()=='y'
            
    # if exec_generating_method_outputs:
    #     ## change the SampleMethod to your method
    #     usereval = UserEvaluation(SampleMethod(),args.eval_server_address,args.evalset)
    #     print('Generating method outputs...')
    #     results = usereval.run()
    #     print('Saving method outputs...')
    #     with open(args.output,'w') as f:
    #         json.dump(results,f)
    # else:
    #     print('Use existed output.')
    results = json.load(open(args.output))
        
    print('Loading reference answer for evaluation...')
    try:
        output = json.load(open(args.output))
    except:
        raise Exception('Cannot load reference answer from {}\n Please Download before evaluation!'.format(args.ref_output))
    
    print('Loading automatic evaluators...')
    evaluators = [load_registered_automatic_evaluator(vars(args)) for _ in range(args.max_eval_threads)]
    
    def check_query_solved(qid,query, ans):
        global evaluators
        evaluator = random.choice(evaluators)
        is_solved = evaluator.check_solve_query(
            query,
            ans)
        return qid, is_solved

    
    print('Evaluating...')
    prefer_dict = {}
    with ThreadPoolExecutor(args.max_eval_threads) as pool:
        future = []
        solved = []
        data_list = []
        for qid in output.keys():
            try:
                results[qid]['answer'] = process_answer(results[qid]['answer'])
                future.append(pool.submit(
                    check_query_solved,
                    qid,
                    output[qid]['query'],
                    results[qid]['answer']['final_answer']
                ))
            except KeyError as e:
                print('Warning : Missing answer for query {} in answer file! '.format(e))

        for thd in tqdm(as_completed(future),total=len(future),ncols=100):
            qid, is_solved = thd.result()
            solved.append(is_solved)
        # print(ref_output[qid]['query'], file=open('output/check_solved.txt','a'))
        # print(results[qid]['answer'], file=open('output/check_solved.txt','a'))
            data = {'query':output[qid]['query'],
                'answer':results[qid]['answer']['final_answer'],
                'solved':is_solved,
                'qid':qid}
            data_list.append(data)
        print(np.mean(solved))
        file_name = args.output.split('/')[-1]
        prefix = os.path.dirname(args.output)
        json.dump(data_list, open(os.path.join(prefix, f'{file_name}_check_solved.json'),'w'), indent=4)

            
    
    # df = pd.DataFrame.from_dict([{
    #     'Method':args.method,
    #     'Win Rate':prefer.mean(),
    #     'Std Error':np.std(prefer)/np.sqrt(len(prefer))
    # }])
    # print('###### Leaderboard vs {} ######'.format(args.ref_method))
    # print(df)
    # save_file = os.path.join(abs_dir,'results',args.evalset,args.method)
    # os.makedirs(save_file,exist_ok=True)
    # df.to_csv(os.path.join(save_file,'win.csv'))
