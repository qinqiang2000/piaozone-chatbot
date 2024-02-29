# 知识库集成中心

## 1. 项目介绍

本项目用于将发票云内部的语雀知识与LLM、IM、金蝶社区等系统打通，具体流程如下：
![](https://cdn.nlark.com/yuque/0/2023/jpeg/22742461/1703663222819-9ec4b434-698e-46a8-a7f6-c1c3c3c6caf3.jpeg)

- 流程的核心是知识集成中心，它负责串联知识的来源地和知识输出地、串联IM的问题和AI模型的回答
- 流程有三类：数据同步、问答或搜索、逆向反馈三类流程
  - 数据同步：由知识库后台定时从语雀同步到指定的地方；语雀内容由知识库负责人进行维护
  - 问答、搜索：用户可通过云之家或其他IM的进行问答；也可以直接到各知识库进行搜索
  - 逆向反馈：知识集成中心将无法回答的问题反馈给知识库负责人，后者依此优化知识库
  
  
  
  已完成：
  
  > 1. 云之家群聊的正向流程
  > 
  > 2. 语雀文档的同步,包括基于云之家传入文本 “sync gpt” 的同步以及基于语雀更新消息通知的同步

## 2. 配置
### 2.1 云之家群配置
- 在群中启用一个“通知”机器人，获取yzjtoken
- 在该群启用一个“对话型”机器人，将项目地址填入其接受地址，并将上面token填入，例如：{项目运行地址}/chat?yzj_token=***
### 2.2 语雀、云之家群、GPT Assistant的关系配置
在config.yml中配置语雀知识库、云之家群、GPT Assistant的关系，参考如下：

```yaml
dn5ehb: # 语雀知识库的唯一标识
  乐企:  # 语雀分的名字；我们以分组为单位进行AI知识库的管理
    gptAssistantId: "asst_G5t60WEtbD9ygU5n2Ol727N6"
    yzj_token:  # 云之家的群token(云之家的通知token，支持配多个)
      - "d29fe265a9594811881e86b7e3d8a1e7"
      - "123"
```

在.env中配置相关key

```editorconfig
# openai
OPENAI_API_KEY=sk-***

# azure
AZURE_OPENAI_API_KEY=***
AZURE_OPENAI_ENDPOINT="https://kdtest.openai.azure.com/"
...
```

安装依赖

```shell
pip install -r requirements.txt
```

运行

```shell
python src/app.py
```

> 环境要求：python3.10+
