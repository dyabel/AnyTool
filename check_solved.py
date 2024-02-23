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
    parser.add_argument("--output_dir", type=str, default='', help="Path for the output file")
    parser.add_argument("--check_solvable", action='store_true', default=False, help="check solvable")
    parser.add_argument("--recheck_solved", action='store_true', default=False, help="check solvable")
    parser.add_argument("--include_unsolvable", action='store_true', default=False, help="whether skip unsolvable")
    parser.add_argument("--use_original_prompt", action='store_true', default=False, help="whether use original prompt")
    parser.add_argument("--model", type=str, default='32k', help="openai model name")
    parser.add_argument("--solver", type=str, default='dfs', help="solver")
    parser.add_argument("--leaf_tool_number", type=int, default=5, help="Maximum number of leaf tools")

    # 添加整数参数
    parser.add_argument("--max_api_number", type=int, default=64, help="Maximum number of API calls")
    parser.add_argument("--all_api_number", type=int, default=17000, help="Total number of API calls")
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
# output_dir = f'result1/generated_solve_given_api_solvable_multicat_complex_r1/stack_reassign_solve_results_turbo_r16'
if __name__ == '__main__':
    # reassign = False
    test_sets = ["G1_instruction", "G1_tool", "G1_category", "G2_instruction", "G2_category", "G3_instruction"]
    # test_sets = ["G1_tool", "G1_category", "G2_instruction", "G2_category", "G3_instruction"]
    # test_sets = ['custom_data']
    # test_sets = ['G1_instruction']
    # test_sets = [ "G1_category","G1_instruction", "G1_tool", "G2_instruction"]
    # test_sets = ['G2_instruction', 'G3_instruction']
    unsolvable_list = json.load(open("unsolvable.json", "r", encoding="utf-8"))
    # unsolvable_list = []
    pass_rate_list = []
    average_tokens_list = []
    for test_set in test_sets:
        total_tokens = 0
        # query_dir = f'data/test_instruction/{test_set}'
        # output_dir = f'result2/test_instruction/{test_set}'
        # output_dir = f'result0111/turbo/test_instruction/{test_set}_r1'
        # output_dir = f'data/reproduction_data/model_predictions/chatgpt_dfs/{test_set}'
        # output_dir = f'data/reproduction_data/model_predictions/toolllama_dfs/{test_set}'
        output_dir = f'data/reproduction_data/model_predictions/toolllama_dfs_retriever/{test_set}'
        # output_dir = f'data/reproduction_data/model_predictions/gpt-4-0613_dfs/{test_set}'
        # output_dir = f'data/reproduction_data/model_predictions/chatgpt_cot/{test_set}'
        # output_dir = f'data/reproduction_data/model_predictions/gpt-4-0613_cot/{test_set}'
        # 33.5&33.5&41.0&23.5&29.5&3.0 27.3
        # output_dir = f'result0111/32k/test_instruction/{test_set}_r1'
        # output_dir = f'result0111/32k/max32/test_instruction/{test_set}_r1'
        # output_dir = f'result_final/toolbench/{test_set}'
        # output_dir = f'result0126/toolbench/{test_set}'
        # output_dir = f'repos/toolbench_ori/{test_set}_filtered/gpt4_retriever_dfs'
        # output_dir = f'repos/toolbench_ori/{test_set}_filtered/toolllama_retriever_ada_dfs'
        # output_dir = f'data/reproduction_data/model_predictions/gpt-35-turbo_dfs/{test_set}'
        # output_dir = 'result_final/custom_data/gpt_dfs_retriever'
        # output_dir = 'result_final/custom_data/toolllama_dfs_retriever'
        # output_dir = 'result_final/custom_data/gpt4_gt_dfs'
        # output_dir = 'result0111/32k_aus/custom_data'
        if 'reproduction' in output_dir or 'ori' in output_dir:
            reassign = False
        else:
            reassign = True
        # reassign = False
        if reassign:
            test_ids = list(range(200))
        else:
            test_ids = json.load(open(f'data/test_query_ids/{test_set}.json', 'r', encoding='utf-8'))
        if 'cot' in output_dir:
            method = 'CoT@1'
        else:
            method = 'DFS_woFilter_w2'
        if not os.path.exists(output_dir):
            continue
        # evaluation_output_dir = f'result2/test_instruction/{test_set}/pass_rate_result_reeval_32k'
        # os.system(f'mv {evaluation_output_dir} {output_dir}')
        # evaluation_output_dir = f'result2/test_instruction/{test_set}/pass_rate_result_35'
        # evaluation_output_dir = f'{output_dir}/pass_rate_result_reeval_32k_3times_nounsure_aus_r1'
        # evaluation_output_dir = f'{output_dir}/pass_rate_result_reeval_32k_r1'
        # final
        evaluation_output_dir = f'{output_dir}/pass_rate_result_reeval_32k_3times'
        # evaluation_output_dir = f'{output_dir}/pass_rate_result_35'
        # evaluation_output_dir = f'{output_dir}/pass_rate_result_reeval_32k'
        # continue
        os.makedirs(evaluation_output_dir, exist_ok=True)
        # label_cnt = {}
        # answer_dict = {}
        if os.path.exists(f"{evaluation_output_dir}/label_cnt.json"):
            label_cnt = json.load(open(f"{evaluation_output_dir}/label_cnt.json", "r", encoding="utf-8"))
        else:
            label_cnt = {}
        future = []
        if os.path.exists(f"{evaluation_output_dir}/answer_dict.json"):
            answer_dict = json.load(open(f"{evaluation_output_dir}/answer_dict.json", "r", encoding="utf-8"))
        else:
            answer_dict = {}
        # result_data = json.load(open(f'data/reproduction_data/model_predictions/gpt-4-0613_dfs/{test_set}.json', 'r', encoding='utf-8'))
        referenced_examples = {}

        with ThreadPoolExecutor(args.max_eval_threads) as pool:
            for i in test_ids:
                # print(i)
                if reassign:
                    try:
                        # print(f'{output_dir}/{i}.json')
                        data = json.load(open(f'{output_dir}/{i}.json', 'r', encoding='utf-8'))
                    except:
                        continue
                    query_id = data['query_id']
                    if int(query_id) in unsolvable_list:
                        continue
                else:
                    query_id = i
                    if int(query_id) in unsolvable_list:
                        continue
                    if 'chatgpt' in output_dir and 'cot' not in output_dir:
                        data = json.load(open(f'{output_dir}/{i}_ChatGPT_{method}.json', 'r', encoding='utf-8'))
                    elif 'chatgpt' in output_dir:
                        data = json.load(open(f'{output_dir}/{i}_{method}.json', 'r', encoding='utf-8'))
                    else:
                        data = json.load(open(f'{output_dir}/{i}_{method}.json', 'r', encoding='utf-8'))
                        
                if not reassign:
                    total_tokens += data['answer_generation']['total_tokens'] 
                else:
                    if 'total_tokens' in data:
                        total_tokens += data['total_tokens']
                if str(query_id) in label_cnt:
                    continue
                if reassign:
                    # print(i)
                    if 'last_solve_time' not in data:
                        try:
                            data_dict = json.load(open(f'{output_dir}/{i}_DFS_woFilter_w2.json', 'r', encoding='utf-8'))
                        except:
                            continue
                    else:
                        last_solve_time = data['last_solve_time']
                        data_dict = json.load(open(f'{output_dir}/{i}_{last_solve_time}_DFS_woFilter_w2.json', 'r', encoding='utf-8'))
                else:
                    data_dict = data
                if not data_dict['answer_generation']['valid_data']:
                    answer_dict[i] = process_invalid_data(method,data_dict)
                else:
                    answer_dict[i] = process_valid_data(method,data_dict['answer_generation'])
                example = answer_dict[i]
                # query_id = i
                # example['available_tools'] = query_data[str(query_id)]['available_tools']
                referenced_examples[query_id] = example
                for _ in range(args.evaluate_times):
                    future.append(pool.submit(
                        compute_pass_rate,
                        query_id,
                        example,
                        'Solvable',
                        'Task solvable human label'
                    ))
            for thd in tqdm(as_completed(future),total=len(future),ncols=100):
                query_id, task_solvable, is_solved, machine_label, reason, not_hallucinate, tokens = thd.result()
                example = referenced_examples[query_id]
                query = example["query"]
                tool_names = []
                for tool_dict in example["available_tools"]:
                    tool_name = tool_dict["name"]
                    tool_names.append(tool_name)
                answer_steps, final_step = get_steps(example)
                if query_id not in label_cnt:
                    label_cnt[query_id] = {"passed":0, "failed":0, "unsure":0}
                if machine_label == "passed":
                    label_cnt[query_id]["passed"] += 1
                elif machine_label == "failed":
                    label_cnt[query_id]["failed"] += 1
                else:
                    label_cnt[query_id]["unsure"] += 1
                label_cnt[query_id]["query"] = query
                label_cnt[query_id]["task_solvable"] = str(task_solvable)
                label_cnt[query_id]["tool_names"] = tool_names
                label_cnt[query_id]["answer_steps"] = answer_steps
                label_cnt[query_id]["final_step"] = final_step
                label_cnt[query_id]["is_solved"] = str(is_solved)
                label_cnt[query_id]["reason"] = reason
                label_cnt[query_id]["not_hallucinate"] = not_hallucinate
                json.dump(label_cnt, open(f"{evaluation_output_dir}/label_cnt.json", "w"), ensure_ascii=False, indent=4)
            filename = f"{evaluation_output_dir}/label_cnt.csv"
            write_results(filename, 'result', label_cnt)
            pass_rate = 0
            total_num = 0
            print('#'*100)
            for query_id in label_cnt:
                if int(query_id) in unsolvable_list:
                    continue
                if label_cnt[query_id]["failed"] <= label_cnt[query_id]["passed"]:
                    pass_rate += 1
                # if label_cnt[query_id]["unsure"] > 0:
                #     print('unsure')
                total_num += 1
            pass_rate /= total_num
            pass_rate_list.append(pass_rate)
            average_tokens_list.append(total_tokens/total_num)
            print(f"Pass rate: {str(pass_rate)} total num {total_num} average tokens {total_tokens/total_num} {test_set}")
            json.dump(answer_dict, open(f"{evaluation_output_dir}/answer_dict.json", "w"), ensure_ascii=False, indent=4)
        print('&'.join([str(round(x*100,1)) for x in pass_rate_list]),round(np.mean(pass_rate_list)*100,1))
        print('&'.join([str(round(x,1)) for x in average_tokens_list]),round(np.mean(average_tokens_list),1))
    
    

