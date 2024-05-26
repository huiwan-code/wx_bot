import requests
import uuid
import hashlib
import json

from flask import request, abort, make_response,send_from_directory
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import (
    InvalidSignatureException,
    InvalidAppIdException,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import QianfanEmbeddingsEndpoint
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate,SystemMessagePromptTemplate,HumanMessagePromptTemplate

from wx_bot.handlers.base import BaseResource
from wx_bot.models import redis
from wx_bot import config

def get_embeddings_endpoint():
    # 使用bge-large-zh进行向量化处理
    return QianfanEmbeddingsEndpoint(model="bge-large-zh", qianfan_ak=config.QIANFAN_AK, qianfan_sk=config.QIANFAN_SK)

class WechatGptHandlerResource(BaseResource):
    def get(self):
        return send_from_directory('static', 'index.html')
    def post(self):
        cache_key = request.form.get("key", "")
        q_cache_key = cache_key + "#q"
        res_cache_key = cache_key + "#res"
        # 检查q是否存在redis
        if not redis.exists(q_cache_key):
            return make_response({"answer": "回答已过期"})
        question = redis.get(q_cache_key).decode('utf-8')
        current_res = redis.get(res_cache_key).decode('utf-8')
        if current_res == "":
            current_res = self.ask_gpt(question)
        redis.set(res_cache_key, current_res)
        return make_response(json.loads(current_res))
    
    def ask_gpt(self, question):
        chain = self.build_qa_chain()
        chain_response = chain({"query": question})
        # 找不到相关答案
        if chain_response.get("result", "NO_ANSWER") == "NO_ANSWER":
            return json.dumps({
                "answer": "公众号暂未有相关知识"
            })

        answer = chain_response.get("result", "")
        metadatas = []
        added_sources = []
        for source_document in chain_response.get("source_documents", []):
            # 过滤掉重复的来源
            if source_document.metadata.get("source") in added_sources:
                continue
            metadatas.append(source_document.metadata)
            added_sources.append(source_document.metadata.get("source"))
        return json.dumps({
            "answer": answer,
            "metadatas": metadatas
        })
    
    def build_qa_chain(self):
        llm = ChatOpenAI(model_name="gpt-3.5-turbo-0125", openai_api_base=config.OPENAI_API_BASE, openai_api_key=config.OPENAI_API_KEY)
        vectorstore = Chroma(persist_directory=config.DB_STORE_DIR, embedding_function=get_embeddings_endpoint())
        
        # 构建提示词模版
        system_template = """Use the following pieces of context to answer the user's question.
        the answer are output in MARKDOWN format
        If you cannot get the answer from the context, just RESPOND: NO_ANSWER, don't try to make up an answer.
        ----------------
        context:
        {context}
        ----------------"""
        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
        chat_prompt = ChatPromptTemplate.from_messages(messages)
        
        return RetrievalQA.from_chain_type(
            llm,
            # 设定搜索结果数量并限制相似度阈值
            retriever=vectorstore.as_retriever(search_type ="similarity_score_threshold", search_kwargs={"k": 3, "score_threshold": 0.7}),
            return_source_documents=True,
            chain_type_kwargs={"prompt": chat_prompt}
        )
        
        
class WechatHandlerResource(BaseResource):
    def handle_auto_reply(self, msg):
        content = msg.content.strip().lower()
        if not content.startswith('@gpt'):
            return create_reply('', msg)
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
            check_signature(config.WECHAT_TOKEN, signature, timestamp, nonce)
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

            crypto = WeChatCrypto(config.WECHAT_TOKEN, config.WECHAT_AES_KEY, '')
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
        try:
            check_signature(config.WECHAT_TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            abort(403)
        echo_str = request.args.get("echostr", "")
        response = make_response(echo_str)
        response.headers['content-type'] = 'text/plain'
        return response
    
    
class WechatArticlePostResource(BaseResource):
    def get(self):
        return send_from_directory('static', 'post_wechat_article.html')
    
    def post(self):
        article_url = request.get_json()['article_url']
        # 解析微信文章内容
        article_data = self.parse_article(article_url)
        
        if article_data is None:
            return make_response("文章拉取失败", 404)
        # 使用CharTextSplitter对内容进行分割 chunk_size = 1000; chunk_overlap = 300, 按句号分开
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=300,
            separators=['。','，', '']
        )
        docs = splitter.create_documents([article_data['content']], [{'title': article_data['title'], 'source': article_url}])
        
        # docs存入chroma向量数据库
        self.store_docs(docs)
        return make_response("文章添加成功")
    
    def parse_article(self, article_url):
        from bs4 import BeautifulSoup
        # 模拟头部，规避微信反爬策略
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = requests.get(article_url, headers=headers)
        # 文章获取失败
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # 获取文章标题
        title = soup.find('h1', class_='rich_media_title').get_text(strip=True)
        # 获取文章内容
        content = soup.find('div', class_='rich_media_content').get_text()
        article_data = {
            'title': title,
            'content': content
        }
        return article_data
    
    def store_docs(self, docs: list[Document]):
        # page_content+source生成一个doc_id，避免重复存储
        ids = []
        for doc in docs:
            doc_id = hashlib.md5(str(doc.page_content + doc.metadata['source']).encode('utf-8')).hexdigest()
            ids.append(doc_id)
        
        # 存入chroma向量数据库
        Chroma.from_documents(
            documents=docs,
            embedding=get_embeddings_endpoint(), 
            persist_directory=config.DB_STORE_DIR,
            ids=ids
        )
        