import os
import random
import string
from aip import AipContentCensor

def fix_assets_path(path):
    full_path = os.path.join(os.path.dirname(__file__), "../../", path)
    print(full_path)
    return full_path


def response(data=None, errors=None, status=200):
    return {
        'data': data,
        'status': status,
        'errors': errors
    }


def rand(nums, rand_type):
    ret = ''
    choice_map = {
        'number': string.digits,
        'alpha': string.ascii_letters
    }
    rand_choice = choice_map.get(rand_type, '!@#$%^&*()' + string.digits + string.ascii_letters)
    for i in range(nums):
        rand = random.choice(rand_choice)
        ret += rand
    return ret

def baidu_aip_text(text):
    APP_ID = '33589128'
    API_KEY = 'GZspMROEcIUaQ7TkR5Ds3vON'
    SECRET_KEY = 'AxnE15b54Cost3TQFI6zVZ6xqx9NSQLm'
    client = AipContentCensor(APP_ID, API_KEY, SECRET_KEY)
    result = client.textCensorUserDefined(text)
    return result.get("conclusionType") == 1