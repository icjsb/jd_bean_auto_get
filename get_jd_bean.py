# -*- coding: utf-8 -*-
import sys
import time
import datetime
import logging
from logging import handlers
import traceback
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


LOG_FILE = 'get_jd_bean.log'

handler = handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=1024 * 1024, backupCount=5)
fmt = '%(asctime)s - %(filename)s:%(lineno)s - %(name)s - %(message)s'

formatter = logging.Formatter(fmt)
handler.setFormatter(formatter)

logger = logging.getLogger('main')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


tools = pyocr.get_available_tools()
if len(tools) == 0:
    logging.info("No OCR tool found")
    sys.exit(1)
# The tools are returned in the recommended order of usage
tool = tools[0]

langs = tool.get_available_languages()
logging.info("Available languages: %s" % ", ".join(langs))
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


def exactor_code():
    """
    返回验证码
    """
    # http://selenium-python.readthedocs.org/waits.html
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#captcha-img"))
    )
    try:
        ele = browser.find_element_by_css_selector('#captcha-img')
        if not ele.is_displayed():
            logger.info("captcha is hide!")
            return ""
        browser.get_screenshot_as_file(screen_path)
        crop_img(screen_path, code_path, captcha_img_box())
        code = tool.image_to_string(
            Image.open(code_path), lang=lang,
            builder=pyocr.builders.TextBuilder()
        )
        logger.info(u"计算验证码结果是{}".format(code))
        return code
    except NoSuchElementException:
        logger.info(u"没有验证码")
        return None


def try_login(username, pwd, code):
    logger.info("尝试登录!")
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
    browser.get_screenshot_as_file(bean_path)
    browser.find_element_by_css_selector('.btn-login').click()
    try:
        ele = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".err-msg")))
        logger.info(ele.text)
        return False
    except:
        logger.info(browser.title)
        if u'登录' not in browser.title:
            return True
        else:
            return False


def sign_and_getBeans():
    logger.info("去拿豆豆!")
    url = 'http://ld.m.jd.com/userBeanHomePage/getLoginUserBean.action'
    browser.get(url)
    browser.find_element_by_css_selector('.state').click()
    browser.get_screenshot_as_file(bean_path)
    logger.info("拿豆豆成功!")


def main():
    url = 'http://m.jd.com/'
    browser.get(url)
    browser.find_element_by_css_selector('.jd-search-icon-login').click()
    try:
        while True:
            code = exactor_code()
            # 尝试login
            if code is None or len(code) == 4:
                if try_login(settings.username, settings.pwd, code):
                    logger.info("登录成功!")
                    sign_and_getBeans()
                    envelope.add_attachment(bean_path)
                    envelope.send(settings.email_host,
                                  login=settings.email_user,
                                  password=settings.email_pwd,
                                  tls=True)
                    logger.info("发送邮件成功!")
                    break
                else:
                    logger.info("登录失败,重试中!")
            else:
                logger.info("提取验证码失败!")
            browser.refresh()

    except Exception:
        logger.debug(traceback.format_exc())
    finally:
        browser.quit()


if __name__ == '__main__':
    main()
