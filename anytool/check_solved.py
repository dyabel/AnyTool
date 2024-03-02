from toolbench.tooleval.eval_pass_rate import compute_pass_rate, write_results, get_steps, load_registered_automatic_evaluator
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import os
from tqdm import tqdm
import random
from toolbench.tooleval.evaluators.registered_cls.rtl import AnswerStatus, TaskStatus, AnswerPass
from toolbench.tooleval.convert_to_answer_format import process_invalid_data, process_valid_data
import numpy as np
abs_dir = os.path.split(__file__)[0]
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--save_path', type=str, default="", required=False, help='result save path')
    parser.add_argument('--reference_model', type=str, default="", required=False, help='model predictions path')
    parser.add_argument('--evaluator', type=str, default="tooleval_gpt-3.5-turbo_default", required=False, help='which evaluator to use.')
    parser.add_argument('--max_eval_threads', type=int, default=20, required=False, help='max threads nums')
    parser.add_argument('--evaluate_times', type=int, default=7, required=False, help='how many times to predict with the evaluator for each solution path.')
    parser.add_argument("--query_path", type=str, default='', help="Path to the query directory")
    parser.add_argument("--output_dir", type=str, default='./', help="Directory for the output file")
    parser.add_argument("--output_path", type=str, default='./tmp.json', help="Path for the output file")
    parser.add_argument("--check_solvable", action='store_true', default=False, help="check solvable")
    parser.add_argument("--recheck_solved", action='store_true', default=False, help="check solvable")
    parser.add_argument("--include_unsolvable", action='store_true', default=False, help="whether skip unsolvable")
    parser.add_argument("--use_original_prompt", action='store_true', default=False, help="whether use original prompt")
    parser.add_argument("--model", type=str, default='32k', help="openai model name")
    parser.add_argument("--solver", type=str, default='dfs', help="solver")
    parser.add_argument("--leaf_tool_number", type=int, default=5, help="Maximum number of leaf tools")

    # 添加整数参数
    parser.add_argument("--max_api_number", type=int, default=64, help="Maximum number of API calls")
    parser.add_argument("--all_api_number", type=int, default=16545, help="Total number of API calls")
    return parser.parse_args()
args = parse_args()
evaluators = [load_registered_automatic_evaluator(evaluator_name=args.evaluator, evaluators_cfg_path=os.path.join('toolbench/tooleval','evaluators')) for _ in range(args.max_eval_threads)]
def compute_pass_rate(query_id, example, task_solvable=None, task_solvable_reason=None):
    global evaluators
    evaluator = random.choice(evaluators)
    try:
        not_hallucinate = evaluator.check_has_hallucination(
        example['available_tools'],
        example['answer']
        )
    except:
        not_hallucinate = True
    final_step = ''
    answer_steps, final_step = get_steps(example)
    
    if "'name': 'Finish'" not in final_step:
        return query_id, TaskStatus.Solvable, AnswerStatus.Unsolved, "failed", "No answer", not_hallucinate, 0
    
    is_solved, is_solved_reason, tokens = evaluator.check_is_solved(
        {
            'query':example['query'],
            'available_tools':example['available_tools'],
        },
        example['answer'],
        return_reason=True
    )
    if is_solved == AnswerStatus.Solved:
        is_solved_flag = True
    elif is_solved == AnswerStatus.Unsolved:
        is_solved_flag = False
    else:
        is_solved_flag = False
        
    if task_solvable is None:
        task_solvable, task_solvable_reason, _ = evaluator.check_task_solvable(
        {
            'query':example['query'],
            'available_tools':example['available_tools'],
        },
        has_been_solved=is_solved_flag,
        return_reason=True
    )

    is_passed, _ = evaluator.is_passed(
        {
            'query':example['query'],
            'available_tools':example['available_tools'],
        },
        example['answer'],
        answer_status=is_solved,
        task_status=task_solvable
    )

    reason = f"Is solved: {is_solved_reason}\nTask solvable: {task_solvable_reason}"
    if is_passed == AnswerPass.Passed:
        label = "passed"
    elif is_passed == AnswerPass.Failed:
        label = "failed"
    else:
        # label = 'unsure'
        if random.random() < 0.5: # if unsure, random choose
            label = "passed"
        else:
            label = "failed"
    return query_id, task_solvable, is_solved, label, reason, not_hallucinate, tokens
