from sync.yq_reader import list_yuque_toc
import requests
import json


# 测试 /chat 接口
def test_chat():
    url = "http://localhost:9999/chat"
    headers = {"sessionId": "test_session_id"}
    data = {
        "type": 1,
        "robotId": "test_robot_id",
        "operatorName": "test_operator_name",
        "msgId": "test_msg_id",
        "operatorOpenid": "test_operator_openid",
        "content": "test_content",
        "time": 1632393600,
        "sessionId": "test_session_id"
    }
    params = {"yzj_token": "test_yzj_token"}
    response = requests.post(url, headers=headers, data=json.dumps(data), params=params)
    print(response.json())


# 测试sync gpt
def test_chat_syn_gpt():
    url = "http://localhost:9999/chat"
    headers = {"sessionId": "test_session_id"}
    data = {
        "type": 1,
        "robotId": "test_robot_id",
        "operatorName": "test_operator_name",
        "msgId": "test_msg_id",
        "operatorOpenid": "test_operator_openid",
        "content": "@乐企 sync gpt",
        "time": 1632393600,
        "sessionId": "test_session_id"
    }
    params = {"yzj_token": "d29fe265a9594811881e86b7e3d8a1e7"}
    response = requests.post(url, headers=headers, data=json.dumps(data), params=params)
    print(response.json())


# 测试 /convert-excel-into-mds 接口
def test_convert_excel_into_mds():
    url = "http://localhost:9999/convert-excel-into-mds"
    files = {'file': open('test.xlsx', 'rb')}
    response = requests.post(url, files=files)
    print(response.content)


# 执行测试
test_chat_syn_gpt()
# test_convert_excel_into_mds()