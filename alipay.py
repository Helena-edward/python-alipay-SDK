# -*- coding: utf-8 -*-

import simplejson as sjson
import requests

import datetime

import logging
import json
import traceback

from Crypto.PublicKey import RSA

from bottle import request, FormsDict

from alipay.aop.api.constant.CommonConstants import *
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient

from server.pay.alipayCert import AliPayCert
from server.pay.payService import PayService


class AliPay():
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s',
            filemode='a',
        )
        logger = logging.getLogger('')

         # 获取appid 密钥 证书路径等信息
        info = PayService.getPayUserInfo()
        if info is None:
            return
        self.cert = AliPayCert(info)

        """
        设置配置，包括支付宝网关地址、app_id、应用私钥、支付宝公钥等，其他配置值可以查看AlipayClientConfig的定义。
        """
        # TODO sandbox_debug
        # alipay_client_config = AlipayClientConfig(True)
        alipay_client_config = AlipayClientConfig(False)

        # 应用ID
        alipay_client_config.app_id = info['a_appid']
        alipay_client_config.app_private_key = info['a_app_private_key_string']
        alipay_client_config.alipay_public_key = self.cert._alipay_public_key_string

        self.config = alipay_client_config

        # 收款支付宝用户ID
        self.seller_id = info['a_mch_id']
        # 必须是外网能访问的 支付宝回调用
        # self.server_url = Cfg.LOCAL_SERVER_URL
        self.server_url = info['server_url']

        self.subject = info['a_order_title']
        self.body = info['prod_desp']

        """
        得到客户端对象。
        注意，一个alipay_client_config对象对应一个DefaultAlipayClient，定义DefaultAlipayClient对象后，alipay_client_config不得修改，如果想使用不同的配置，请定义不同的DefaultAlipayClient。
        logger参数用于打印日志，不传则不打印，建议传递。
        """
        self.client = DefaultAlipayClient(
            alipay_client_config=alipay_client_config, logger=logger)

    def alipay_trade_wap_pay(self):
        """
        手机网站支付
        系统接口示例：alipay.trade.wap.pay
        """
        
        from alipay.aop.api.domain.AlipayTradeWapPayModel import AlipayTradeWapPayModel
        from alipay.aop.api.request.AlipayTradeWapPayRequest import AlipayTradeWapPayRequest
        from alipay.aop.api.response.AlipayTradeWapPayResponse import AlipayTradeWapPayResponse

        rJson = sjson.loads(request.forms.getunicode('sendJson'))

        # 对照接口文档，构造请求对象
        model = AlipayTradeWapPayModel()
        model.subject = self.subject
        model.body = self.body
        model.out_trade_no = rJson['out_trade_no']

        model.timeout_express = "90m"
        model.total_amount = rJson['total_amount']
        # 用户付款中途退出返回商户网站的地址
        model.quit_url = self.server_url + "pay"
        model.product_code = "QUICK_WAP_WAY"
        model.seller_id = self.seller_id

        alirequest = AlipayTradeWapPayRequest(biz_model=model)
        # # 同步通知地址 非必须
        # alirequest.return_url = self.server_url
        # 异步通知地址 非必须 商户外网可以访问的异步地址
        alirequest.notify_url = self.server_url + "alipayTradeWapPayNotify"

        # 应用公钥证书 SN
        alirequest.app_cert_sn = self.cert.app_cert_sn
        # 支付宝根证书 SN
        alirequest.alipay_root_cert_sn = self.cert.alipay_root_cert_sn
        response_content = None
        try:
            response_content = self.client.page_execute(alirequest)
            
        except:
            print('pay error')

        return response_content

    def alipay_trade_wap_pay_notify(self):
        params = FormsDict(request.params).decode('utf-8')
        if request.method == 'POST':
            if not len(params) > 0:
                return
        # 验证签名 sign
        if self.cert.check_alipay(params):
            notify_id = params['notify_id']
            parter = params['seller_id']
            # 验证是否是支付宝发来的通知
            if self.cert.verifyURL(parter, notify_id):
                # 处理服务器端逻辑，更新数据库等

                    
                # 向支付宝返回成功接收并处理异步通知状态
                return 'success'
            else:
                return 'fail'
        else:
            return 'fail'

    
    def alipayTradeQuery(self):
        """
        统一收单线下交易查询
        系统接口示例：alipay.trade.query
        """
        from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
        from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
        # from alipay.aop.api.response.AlipayTradeQueryResponse import AlipayTradeQueryResponse

        rJson = sjson.loads(request.forms.getunicode('sendJson'))
        # 对照接口文档，构造请求对象
        model = AlipayTradeQueryModel()
        # 商户订单号
        model.out_trade_no = rJson['out_trade_no']
        
        alirequest = AlipayTradeQueryRequest(biz_model=model)
        # 应用公钥证书 SN
        alirequest.app_cert_sn = self.cert.app_cert_sn
        # 支付宝根证书 SN
        alirequest.alipay_root_cert_sn = self.cert.alipay_root_cert_sn

        response_content = None
        status = "OK"
        errmsg = ""
        result = ""
        try:
            response_str_encode = self.client.execute(alirequest)
            response_str = response_str_encode.decode(self.config.charset)
            response_content = sjson.loads(response_str)
            if not response_content:
                return sjson.dumps({"status": 'NG', 'errmsg': ' execute failed'})
            else:
                res = response_content['alipay_trade_query_response']
                # 验证签名    
                if self.cert.check_sign(response_str, response_content['sign'], 'alipay_trade_query_response'):
                    if 'sub_code' not in res or not res['sub_code']:
                        # 查询成功
						status = "OK"
                    else:
                        # 如果业务失败，则从错误码中可以得知错误情况，具体错误码信息可以查看接口文档
                        status = "NG"
                        errmsg = res['code'] + "," + res['msg'] + "," + res['sub_code'] + "," + res['sub_msg']
                else:
                    status = "NG"
                    errmsg = 'sign check failed'
        except:
            errmsg = traceback.format_exc()
        finally:        
            rtn = {"status": status, "result": result, 'errmsg': errmsg}
            return sjson.dumps(rtn)

    def alipayTradeRefund(self):
        
        """
        统一收单交易退款接口
        系统接口示例：alipay.trade.refund
        """
        from alipay.aop.api.domain.AlipayTradeRefundModel import AlipayTradeRefundModel
        from alipay.aop.api.request.AlipayTradeRefundRequest import AlipayTradeRefundRequest
        # from alipay.aop.api.response.AlipayTradeRefundResponse import AlipayTradeRefundResponse

        rJson = sjson.loads(request.forms.getunicode('sendJson'))
        # 对照接口文档，构造请求对象
        model = AlipayTradeRefundModel()
        # 商户订单号
        model.out_trade_no = rJson['out_trade_no']
        import random, string
        now = datetime.datetime.now()
        # 退款请求号 标识一次退款请求，同一笔交易多次退款需要保证唯一。
        model.out_request_no = now.strftime("%Y%m%d%H%M%S") + "%03d" % (now.microsecond // 1000) + ''.join(random.sample(string.ascii_letters + string.digits, 8))
                        
        # 支付宝交易号 和商户订单号不能同时为空
        model.trade_no = None
        # 退款的金额
        model.refund_amount = 0.01

        alirequest = AlipayTradeRefundRequest(biz_model=model)
        # 应用公钥证书 SN
        alirequest.app_cert_sn = self.cert.app_cert_sn
        # 支付宝根证书 SN
        alirequest.alipay_root_cert_sn = self.cert.alipay_root_cert_sn

        response_content = None
        try:
            response_str_encode = self.client.execute(alirequest)
            response_str = response_str_encode.decode(self.config.charset)
            response_content = sjson.loads(response_str)
            if not response_content:
                return sjson.dumps({"status": 'NG', 'errmsg': ' execute failed'})
            else:
                res = response_content['alipay_trade_refund_response']
                # 验证签名
                if self.cert.check_sign(response_str, response_content['sign'], 'alipay_trade_refund_response'):
                    if 'sub_code' not in res or not res['sub_code']:
                        # 如果业务成功，则通过respnse属性获取需要的值
                        # 更新交易状态
                        
                        rtn = {"status": 'OK'}
                    else:
                        # 如果业务失败，则从错误码中可以得知错误情况，具体错误码信息可以查看接口文档
                        rtn = {"status": 'NG', 'errmsg': res['code'] + "," + res['msg'] + "," + res['sub_code'] + "," + res['sub_msg']}
                    
                    return sjson.dumps(rtn)
                else:
                    return sjson.dumps({"status": 'NG', 'errmsg': 'sign check failed'})
        except:
            return sjson.dumps({"status": 'NG', 'errmsg': traceback.format_exc()})

    def alipayRefundTradeQuery(self):
        """
        统一收单交易退款查询
        系统接口示例：alipay.trade.fastpay.refund.query
        """
        from alipay.aop.api.domain.AlipayTradeFastpayRefundQueryModel import AlipayTradeFastpayRefundQueryModel
        from alipay.aop.api.request.AlipayTradeFastpayRefundQueryRequest import AlipayTradeFastpayRefundQueryRequest
        # from alipay.aop.api.response.AlipayTradeFastpayRefundQueryResponse import AlipayTradeFastpayRefundQueryResponse

        rJson = sjson.loads(request.forms.getunicode('sendJson'))
        # 对照接口文档，构造请求对象
        model = AlipayTradeFastpayRefundQueryModel()
        # 商户订单号
        model.out_trade_no = rJson['out_trade_no']

        # 退款请求号
        model.out_request_no = PayService.getRefundNo(model.out_trade_no)
        
        alirequest = AlipayTradeFastpayRefundQueryRequest(biz_model=model)
        # 应用公钥证书 SN
        alirequest.app_cert_sn = self.cert.app_cert_sn
        # 支付宝根证书 SN
        alirequest.alipay_root_cert_sn = self.cert.alipay_root_cert_sn

        response_content = None
        status = "OK"
        errmsg = ""
        result = ""
        try:
            response_str_encode = self.client.execute(alirequest)
            response_str = response_str_encode.decode(self.config.charset)
            response_content = sjson.loads(response_str)
            if not response_content:
                return sjson.dumps({"status": 'NG', 'errmsg': ' execute failed'})
            else:
                res = response_content['alipay_trade_fastpay_refund_query_response']
                # 验证签名    
                if self.cert.check_sign(response_str, response_content['sign'], 'alipay_trade_fastpay_refund_query_response'):
                    # 该接口的返回码10000，仅代表本次查询操作成功，不代表退款成功。
                    if 'code' in res and res['code'] == '10000':
                        # 官方文档-- 该接口返回了查询数据，且refund_status为空或为REFUND_SUCCESS，则代表退款成功
                        # 社区问答--统一收单交易退款查询是不会返回refund_status字段的，如果想要判断订单是否退款成功，需要根据退款的金额进行判断
                        status = "OK"

                    else:
                        # 如果业务失败，则从错误码中可以得知错误情况，具体错误码信息可以查看接口文档
                        status = "NG"
                        errmsg = res['code'] + "," + res['msg'] + "," + res['sub_code'] + "," + res['sub_msg']
                else:
                    status = "NG"
                    errmsg = 'sign check failed'
        except:
            errmsg = traceback.format_exc()
        finally:        
            rtn = {"status": status, "result": result, 'errmsg': errmsg}
            return sjson.dumps(rtn)