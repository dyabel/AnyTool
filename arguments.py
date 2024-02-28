import argparse
def parse_args():
    # 创建 ArgumentParser 对象
    parser = argparse.ArgumentParser(description="Process paths and numbers.")

    # 添加字符串参数
    parser.add_argument("--query_path", type=str, default='', help="Path to the query data")
    parser.add_argument("--output_dir", type=str, default='./', help="Directory for the output file")
    parser.add_argument("--output_path", type=str, default='./tmp.json', help="Path for the output file")
    parser.add_argument("--model", type=str, default='32k', help="openai model name")
    parser.add_argument("--solver", type=str, default='dfs', help="solver")

    # 添加整数参数
    parser.add_argument("--max_api_number", type=int, default=64, help="Maximum number of API calls")
    parser.add_argument("--check_solvable", action='store_true', default=False, help="check solvable")
    parser.add_argument("--recheck_solved", action='store_true', default=False, help="check solvable")
    parser.add_argument("--include_unsolvable", action='store_true', default=False, help="whether skip unsolvable")
    parser.add_argument("--use_original_prompt", action='store_true', default=False, help="whether use original prompt")
    parser.add_argument("--leaf_tool_number", type=int, default=5, help="Maximum number of leaf tools")
    parser.add_argument("--all_api_number", type=int, default=16545, help="Total number of API calls")

    # 解析命令行参数
    args = parser.parse_args()

    # 使用参数
    print(f"Query Path: {args.query_path}")
    print(f"Output Path: {args.output_dir}")
    print(f"OpenAI Model: {args.model}")
    print(f"Maximum API Number: {args.max_api_number}")
    print(f"All API Number: {args.all_api_number}")
    return args