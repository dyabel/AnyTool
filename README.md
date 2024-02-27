# AnyTool
![Static Badge](https://img.shields.io/badge/anytool-blue)
<a href='https://arxiv.org/abs/2402.04253'><img src='https://img.shields.io/badge/arXiv-2402.04253-b31b1b.svg'></a>  <a href='https://github.com/buaacyw/GaussianEditor/blob/master/LICENSE.txt'><img src='https://img.shields.io/badge/License-Apache-blue'></a>

This is the implementation of the paper [AnyTool: Self-Reflective, Hierarchical Agents for Large-Scale API Calls](https://arxiv.org/abs/2402.04253)
![Figure](https://media.discordapp.net/attachments/1202909094470492163/1202909161755648010/image.png?ex=65d865f5&is=65c5f0f5&hm=a399dda2c4b1c6caf17d3a0d29bc7dc9c504012ba7a4cc856283ce9dc9a3ebd5&=&format=webp&quality=lossless&width=781&height=601)

# 🔧 Installation
## ✅ Dependencies
Require Python 3.9+

## 🚀 Quick install 
```bash
pip install -r requirements.txt
```

# 🔆 Data Preparation
**ToolBench**

Refer to [ToolBench](https://github.com/OpenBMB/ToolBench).

**Prepare the API data**

You should prepare the ToolBench data first. Make sure you have the directory of data/toolenv/tools
```
python extract_api_details.py
python extract_category_tool_details.py
python extract_tool_database.py
```

**AnyToolBench**

Generation script
```
python data_generation_by_gpt4.py
```

We provide sample data in anytoolbench.json file.



# 🚗 Run AnyTool
Fill your OpenAI config and toolbench key into the config.py.

Run ToolBench
```
python anytool.py --output_dir result/test_instruction/G1_instruction --query_path data/test_instruction/G1_instruction.json --max_api_number 64
```
Run AnyToolBench
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
