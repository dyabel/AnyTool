# AnyTool
This is the implementation of the paper [AnyTool: Self-Reflective, Hierarchical Agents for Large-Scale API Calls](https://arxiv.org/abs/2402.04253)
![Figure](https://media.discordapp.net/attachments/1202909094470492163/1202909161755648010/image.png?ex=65d865f5&is=65c5f0f5&hm=a399dda2c4b1c6caf17d3a0d29bc7dc9c504012ba7a4cc856283ce9dc9a3ebd5&=&format=webp&quality=lossless&width=781&height=601)

# Installation
## Dependencies
Require Python 3.9+

Quick install 
```bash
pip install requirements.txt
```

# Data
**ToolBench**

Refer to [ToolBench](https://github.com/OpenBMB/ToolBench).

**AnyToolBench**

# AnyToolBench Generation
```
python data_generation_by_gpt4.py
```

We provide sample data in anytoolbench.json file.



# Run AnyTool
Fill your OpenAI config and toolbench key into the config.py.

Run ToolBench
```
python anytool.py --output_dir result/test_instruction/G1_instruction --query_path data/test_instruction/G1_instruction.json --max_api_number 64
```
Run AnyToolBench
```
python anytool.py --output_dir result/anytoolbench --query_path anytoolbench.json -max_api_number 64
```
# AnyToolBench Generation
```
python data_generation_by_gpt4.py
```
# Acknowledgement
This repo is built on [ToolBench](https://github.com/OpenBMB/ToolBench).

# Citation
If you find this project is helpful for your research, consider citing our paper
```
@article{du2024anytool,
  title={AnyTool: Self-Reflective, Hierarchical Agents for Large-Scale API Calls},
  author={Du, Yu and Wei, Fangyun and Zhang, Hongyang},
  journal={arXiv preprint arXiv:2402.04253},
  year={2024}
}
```
