# -*- coding: utf-8 -*-
import os
import hashlib
import OpenSSL
import json
import urllib.parse

from Crypto.PublicKey import RSA

import rsa
import base64
import requests
import traceback


class AliPayCert():
    def __init__(self, info):
        # 应用公钥证书  注意此处是从支付宝下载的！ 【.crt】
        self._app_public_key_cert_string = info['a_app_public_key_cert_path']
        # 支付宝公钥证书
        self._alipay_public_key_cert_string = info['a_alipay_public_key_cert_path']
        # 支付宝根证书
        self._alipay_root_cert_string = info['a_alipay_root_cert_path']
        # 支付宝公钥
        self._alipay_public_key_string = self.load_alipay_public_key_string()

    def load_alipay_public_key_string(self):
        current_dir = os.path.dirname(__file__)
        with open(current_dir + self._alipay_public_key_cert_string) as f:
            cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
            return OpenSSL.crypto.dump_publickey(OpenSSL.crypto.FILETYPE_PEM, cert.get_pubkey()).decode("utf-8")

    def get_cert_sn(self, path):
        current_dir = os.path.dirname(__file__)
        with open(current_dir + path) as f:
            certContent = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
            certIssue = certContent.get_issuer()
            name = 'CN={},OU={},O={},C={}'.format(certIssue.CN, certIssue.OU, certIssue.O, certIssue.C)
            string = name + str(certContent.get_serial_number())
            m = hashlib.md5()
            m.update(bytes(string, encoding="utf8"))
            return m.hexdigest()

    def read_pem_cert_chain(self, path):
        certs = list()
        current_dir = os.path.dirname(__file__)
        with open(current_dir + path) as f:
            for c in f.read().split('\n\n'):
                cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, c)
                certs.append(cert)
            return certs

    def get_root_cert_sn(self, path):
        """
        """
        certs = self.read_pem_cert_chain(path)
        rootCertSN = None
        for cert in certs:
            try:
                sigAlg = cert.get_signature_algorithm()
            except ValueError:
                continue
            if b'rsaEncryption' in sigAlg or b'RSAEncryption' in sigAlg:
                certIssue = cert.get_issuer()
                name = 'CN={},OU={},O={},C={}'.format(certIssue.CN, certIssue.OU, certIssue.O, certIssue.C)
                string = name + str(cert.get_serial_number())
                m = hashlib.md5()
                m.update(bytes(string, encoding="utf8"))
                certSN = m.hexdigest()
                if not rootCertSN:
                    rootCertSN = certSN
                else:
                    rootCertSN = rootCertSN + '_' + certSN
        return rootCertSN

    @property
    def app_cert_sn(self):
        return self.get_cert_sn(self._app_public_key_cert_string)

    @property
    def alipay_root_cert_sn(self):
        return self.get_root_cert_sn(self._alipay_root_cert_string)

    def check_alipay(self, alipay_req_dict):
        try:
            sign = alipay_req_dict.pop('sign')  # 取出传过来的公钥
            alipay_req_dict.pop('sign_type')  # 去除传过来的sign_type

            params = sorted(alipay_req_dict.items(), key=lambda e: e[0], reverse=False)  # 取出字典元素按key的字母升序排序形成列表
            message = "&".join(u"{}={}".format(k, v) for k, v in params).encode()  # 将列表转为二进制参数字符串
            public_key = self._alipay_public_key_string
            sign = base64.b64decode(sign)
            # 验签支付宝密钥签名和证书签名都一样，只是证书签名下支付宝公钥需要解析证书得到
            return bool(rsa.verify(message, sign, rsa.PublicKey.load_pkcs1_openssl_pem(public_key)))

        except Exception:
            print('验签失败')

        return False

    # 验证是否是支付宝发来的通知
    def verifyURL(self, partner, notify_id):
        ALIPAY_REMOTE_ORIGIN_URL = 'https://mapi.alipay.com/gateway.do'
        # TODO
        if False:
            ALIPAY_REMOTE_ORIGIN_URL = 'https://mapi.alipaydev.com/gateway.do'
        payload = {'service': 'notify_verify', 'partner': partner, 'notify_id': notify_id}
        r = requests.get(ALIPAY_REMOTE_ORIGIN_URL, params=payload)
        result = r.text
        if result.upper() == "TRUE":
            return True
        return False

    # 验证响应示例中的sign值是否为蚂蚁金服所提供。
    def check_sign(self, response_str, sign, apistr):
        sign = base64.b64decode(sign)
        checkcontent = response_str.split('"' + apistr + '":')[1]
        checkcontent = checkcontent.split('"}')[0] + '"}'
        return bool(rsa.verify(checkcontent.encode(), sign, rsa.PublicKey.load_pkcs1_openssl_pem(self._alipay_public_key_string)))