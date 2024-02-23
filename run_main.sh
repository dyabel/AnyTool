#main 
python anytool.py --model aus --output_dir result/aus/test_instruction/G1_instruction_customrapidapi --query_path data/test_instruction/G1_instruction.json --max_api_number 64

python anytool.py --model aus --output_dir result/aus/test_instruction/G1_tool_customrapidapi --query_path data/test_instruction/G1_tool.json --max_api_number 64

 python anytool.py --model 32k --output_dir result/32k/test_instruction/G1_instruction_customrapidapi --query_path data/test_instruction/G1_instruction.json --max_api_number 64

proxychains4 python anytool.py --model aus --output_dir result/aus/test_instruction/G1_tool_customrapidapi_oriprompt_r1 --query_path data/test_instruction/G1_tool.json --max_api_number 64

proxychains4 python anytool.py --model aus --output_dir result/aus/test_instruction/G1_instruction_customrapidapi_oriprompt_r1 --query_path data/test_instruction/G1_instruction.json --max_api_number 64