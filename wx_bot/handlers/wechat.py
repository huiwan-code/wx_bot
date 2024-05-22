import requests
import uuid
from flask import request, abort, make_response,send_from_directory
from wechatpy import WeChatClient, parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import (
    InvalidSignatureException,
    InvalidAppIdException,
)

from wx_bot.handlers.base import BaseResource
from wx_bot.handlers import helper

from wx_bot.models import redis


from wx_bot import config

WECHAT_TOKEN = config.WECHAT_TOKEN
WECHAT_APPID = config.WECHAT_APPID
WECHAT_SECRET = config.WECHAT_SECRET
WECHAT_AES_KEY = config.WECHAT_AES_KEY

def init_app(app):
    wechat_appid = app.config.get('WECHAT_APPID', '')
    wechat_secret = app.config.get('WECHAT_SECRET', '')
    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.extensions['wechat_client'] = WeChatClient(wechat_appid, wechat_secret)

class WechatGptHandlerResource(BaseResource):
    def get(self):
        return send_from_directory('static', 'index.html')
    def post(self):
        cache_key = request.form.get("key", "")
        q_cache_key = cache_key + "#q"
        res_cache_key = cache_key + "#res"
        # 检查q是否存在redis
        if not redis.exists(q_cache_key):
            return make_response("回答已过期")
        prompt = redis.get(q_cache_key).decode('utf-8')
        current_res = redis.get(res_cache_key).decode('utf-8')
        if current_res == "":
            current_res = self.ask_gpt(prompt)
        redis.set(res_cache_key, current_res)
        return make_response(current_res)
    
    def ask_gpt(self, prompt):
        # 设置OpenAI API的身份验证密钥
        # openai_api_key = "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"
        # 使用第三方的key
        openai_api_key = 'sk-WV29GlBY9AYTluAqpBHPjJ4gTmakrePEZCzxzb1ZRl6z3C1e'
        # 定义API的请求URL
        #url = "https://api.openai.com/v1/completions"
        # url = "https://openai.huiwan.tech/proxy/api.openai.com/v1/completions"
        # 第三方的url
        url = "https://api.chatanywhere.cn/v1/completions"
        # 设置API请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_api_key}",
        }
        final_prompt = f"""
        回答双引号中的问题,结果以markdown格式输出。问题是:"{prompt}"
        """
        # 设置API请求正文
        data = {
            "model": "text-davinci-003",
            "prompt": final_prompt,
            "max_tokens": 2048,
            "temperature": 0.8,
        }

        # 发送API请求
        response = requests.post(url, headers=headers, json=data)

        # 解析API响应
        if response.status_code == 200:
            response_json = response.json()
            message = response_json["choices"][0]["text"].strip()
            # 对返回的数据进行审核
            if helper.baidu_aip_text(message):
                return message
            else:
                return "不该问的别乱问哦"
        else:
            print(response.json())
            return "哎呀，我没听清问题，你再问一下～"
class WechatHandlerResource(BaseResource):
    def handle_auto_reply(self, msg):
        content = msg.content.strip().lower()
        rsp_content = self.create_gpt_res(content)
        return create_reply(rsp_content, msg)
    
    def create_gpt_res(self, prompt):
        cache_key = str(uuid.uuid4())
        # 存储问题的key
        q_cache_key = cache_key + "#q"
        redis.set(q_cache_key, prompt)
        redis.expire(q_cache_key, 86400)
        # 存储答案的key, value留空
        res_cache_key = cache_key + "#res"
        redis.set(res_cache_key, "")
        redis.expire(res_cache_key, 86400)
        # 返回请求链接
        return '<a href="https://www.huiwan.tech/api/wechat/gpt?key={}">点击查看回复</a>'.format(cache_key)

    def post(self):
        signature = request.args.get("signature", "")
        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        encrypt_type = request.args.get("encrypt_type", "raw")
        msg_signature = request.args.get("msg_signature", "")
        
        try:
            check_signature(WECHAT_TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            abort(403)

        resp_xml = ""
        # 明文模式
        if encrypt_type == "raw":
            # plaintext mode
            msg = parse_message(request.data)
            if msg.type == "text":
                reply = self.handle_auto_reply(msg)
            resp_xml = reply.render()
        else:
            # 加密模式
            from wechatpy.crypto import WeChatCrypto

            crypto = WeChatCrypto(WECHAT_TOKEN, WECHAT_AES_KEY, WECHAT_APPID)
            try:
                msg = crypto.decrypt_message(request.data, msg_signature, timestamp, nonce)
            except (InvalidSignatureException, InvalidAppIdException):
                abort(403)
            else:
                msg = parse_message(msg)
                if msg.type == "text":
                    reply = self.handle_auto_reply(msg)
                resp_xml = crypto.encrypt_message(reply.render(), nonce, timestamp)
        response = make_response(resp_xml)
        response.headers['content-type'] = 'text/plain;charset=UTF-8'
        return response

    # 微信后台验证服务器使用
    def get(self):
        signature = request.args.get("signature", "")
        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        echo_str = request.args.get("echostr", "")
        response = make_response(echo_str)
        response.headers['content-type'] = 'text/plain'
        return response