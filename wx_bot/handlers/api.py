from flask_restful import Api

from wx_bot.handlers.wechat import WechatHandlerResource,WechatGptHandlerResource, WechatArticlePostResource

api = Api()
api.add_resource(WechatGptHandlerResource, '/wechat/gpt', endpoint='wechat_gpt')
api.add_resource(WechatHandlerResource, '/wechat/callback', endpoint='wechat')
api.add_resource(WechatArticlePostResource, '/wechat/post-article', endpoint='post-article')

