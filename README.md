# AnyTool
![Static Badge](https://img.shields.io/badge/anytool-blue)
<a href='https://arxiv.org/abs/2402.04253'><img src='https://img.shields.io/badge/arXiv-2402.04253-b31b1b.svg'></a>  <a href='https://github.com/dyabel/AnyTool/blob/public/LICENSE'><img src='https://img.shields.io/badge/License-Apache-blue'></a>

This is the implementation of the paper [AnyTool: Self-Reflective, Hierarchical Agents for Large-Scale API Calls](https://arxiv.org/abs/2402.04253)
![Figure](./assets/anytool.png)

# 🔧 Installation
## ✅ Dependencies
Require Python 3.9+

## 🚀 Quick install 
```bash
pip install -r requirements.txt
```

# OpenAI GPT API config
Fill your  and toolbench key into the config.py (see config_example.py). 


# 🔆 Data Preparation
**ToolBench**

Refer to [ToolBench](https://github.com/OpenBMB/ToolBench).

**Prepare the API data**

You should prepare the ToolBench data first. Make sure you have the directory of data/toolenv/tools
```
python scripts/extract_api_details.py
python scripts/extract_category_tool_details.py
python scripts/extract_tool_database.py
```

**AnyToolBench**

Generation script
```
python scripts/data_generation_by_gpt4.py
```

We provide sample data in [anytoolbench.json]() file.



# 🚗 Run AnyTool
Fill your OpenAI GPT API config and toolbench key into the config.py (see config_example.py). 

Experiment on ToolBench
```
python anytool.py --output_dir result/test_instruction/G1_instruction --query_path data/test_instruction/G1_instruction.json --max_api_number 64
```
Experiment on AnyToolBench
```
python anytool.py --output_dir result/anytoolbench --query_path anytoolbench.json -max_api_number 64
```

# 👨‍🏫 Acknowledgement
This repo is built on [ToolBench](https://github.com/OpenBMB/ToolBench).

# 📑Citation
If you find this project is helpful for your research, consider citing our paper
```
@article{du2024anytool,
  title={AnyTool: Self-Reflective, Hierarchical Agents for Large-Scale API Calls},
  author={Du, Yu and Wei, Fangyun and Zhang, Hongyang},
  journal={arXiv preprint arXiv:2402.04253},
  year={2024}
}
```
