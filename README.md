# python-alipay-SDK
Modify the official SDK to make it suitable for public key certificate mode
修改官方SDK使其适用于公钥证书模式

this is a demo of smartphone wap pay use alipay sdk

after install python alipay sdk , 
cause it does not support the form of public key certificate, 
and we use the fund related interface, 
we have to modify it to support public key certificate.

so let's begin.

# 1. add cert Paramete to request
   to use public key certificate,
   you must have three cert already.
   
   应用公钥证书 app_public_key_cert
   
   支付宝公钥证书 alipay_public_key_cert
   
   支付宝根证书 alipay_root_cert
   
   then add cert Paramete to alipay request
   
   request.app_cert_sn = self.cert.app_cert_sn

   request.alipay_root_cert_sn = self.cert.alipay_root_cert_sn
   
   you can get SN from alipayCert.py
   
# 2. modify alipay request
   Take mobile wap payment as an example
   
   from alipay.aop.api.request.AlipayTradeWapPayRequest import AlipayTradeWapPayRequest
   
   modify AlipayTradeWapPayRequest：__init__，property，get_params
    
