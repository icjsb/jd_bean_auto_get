# jd_bean_auto_get
自动领取京豆


## 安装要求
**python 2.7**

pyocr
selenium
tesseract
envelopes
PIL

## 使用

配置 settings.py

```

email_host = '***'
email_user = '***'
email_pwd = '***'

users = (
    ('***', '***'),
)


```

运行:
python get_jd_bean.py
