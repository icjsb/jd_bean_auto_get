# -*- coding: utf-8 -*-
import sys
import time
import datetime
import pyocr
import pyocr.builders
import Image
from envelopes import Envelope
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

import settings


tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    sys.exit(1)
# The tools are returned in the recommended order of usage
tool = tools[0]

langs = tool.get_available_languages()
print("Available languages: %s" % ", ".join(langs))
lang = langs[0]

screen_path = 'screen.png'
code_path = 'code.png'
bean_path = 'bean.png'
code_box = (826, 182, 889, 207)

# 重要

envelope = Envelope(
    from_addr=(settings.email_user, u''),
    to_addr=(settings.email_user, u''),
    subject=u'京东领取京豆记录-{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()),
    text_body=u""
)
browser = webdriver.Firefox()
browser.implicitly_wait(10)


def crop_img(path, crop_path, box):
    """截图
    path: 图片地址
    crop_path: 剪贴地址
    box: 剪的坐标
    return: 无
    """
    im = Image.open(path)
    crop = im.crop(box)
    crop.save(crop_path)


def captcha_img_box():
    ele = browser.find_element_by_css_selector(
        '#captcha-img > img:nth-child(1)')
    return (ele.location['x'], ele.location['y'],
            ele.location['x'] + int(ele.get_attribute('width')),
            ele.location['y'] + int(ele.get_attribute('height')),
            )


def maybe_can_login():
    """
    返回验证码
    """
    while True:
        # http://selenium-python.readthedocs.org/waits.html
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#captcha-img"))
        )
        try:
            ele = browser.find_element_by_css_selector('#captcha-img')
            if not ele.is_displayed():
                print("captcha is hide!")
                return ""
            browser.get_screenshot_as_file(screen_path)
            crop_img(screen_path, code_path, captcha_img_box())
            code = tool.image_to_string(
                Image.open(code_path), lang=lang,
                builder=pyocr.builders.TextBuilder()
            )
            print(code)
            if len(code) == 4:
                return code
        except NoSuchElementException:
            return ""
        browser.refresh()


def try_login(username, pwd, code):
    print("尝试登录!")
    txt_username = browser.find_element_by_css_selector('.txt-username')
    txt_username.send_keys(username)
    txt_username.send_keys(Keys.RETURN)
    txt_pwd = browser.find_element_by_css_selector('.txt-password')
    txt_pwd.send_keys(pwd)
    txt_pwd.send_keys(Keys.RETURN)
    if code:
        txt_captcha = browser.find_element_by_css_selector('.txt-captcha')
        txt_captcha.send_keys(code)
        txt_captcha.send_keys(Keys.RETURN)
    browser.get_screenshot_as_file("/tmp/abb.png")
    browser.find_element_by_css_selector('.btn-login').click()
    time.sleep(10)
    print(browser.title)
    if u'\u767b\u5f55' not in browser.title:
        return True
    else:
        return False


def sign_and_getBeans():
    print("去拿豆豆!")
    url = 'http://ld.m.jd.com/userBeanHomePage/getLoginUserBean.action'
    browser.get(url)
    browser.find_element_by_css_selector('.state').click()
    browser.get_screenshot_as_file(bean_path)


def main():
    url = 'http://m.jd.com/'
    browser.get(url)
    browser.find_element_by_css_selector('.jd-search-icon-login').click()
    try:
        while True:
            code = maybe_can_login()
            # 尝试login
            if try_login(settings.username, settings.pwd, code):
                print("登录成功!")
                sign_and_getBeans()
                envelope.add_attachment(bean_path)
                envelope.send(settings.email_host,
                              login=settings.email_user,
                              password=settings.email_pwd,
                              tls=True)
                break
            else:
                print("登录失败,重试中!")

    finally:
        browser.quit()


if __name__ == '__main__':
    main()
