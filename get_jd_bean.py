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


# 重要


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


class JDUser(object):
    screen_path = 'screen.png'
    code_path = 'code.png'
    bean_path = 'bean.png'
    sign_and_get_beans_url = 'http://ld.m.jd.com/userBeanHomePage/getLoginUserBean.action'
    base_url = 'http://m.jd.com/'

    def __init__(self, browser, user, pwd):
        self._browser = browser
        self._user = user
        self._pwd = pwd

    def captcha_img_box(self):
        ele = self._browser.find_element_by_css_selector(
            '#captcha-img > img:nth-child(1)')
        return (ele.location['x'], ele.location['y'],
                ele.location['x'] + int(ele.get_attribute('width')),
                ele.location['y'] + int(ele.get_attribute('height')),
                )

    def exactor_code(self):
        """
        返回验证码
        """
        # http://selenium-python.readthedocs.org/waits.html
        WebDriverWait(self._browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#captcha-img"))
        )
        try:
            ele = self._browser.find_element_by_css_selector('#captcha-img')
            if not ele.is_displayed():
                logger.info("captcha is hide!")
                return ""
            self._browser.get_screenshot_as_file(self.screen_path)
            crop_img(self.screen_path, self.code_path, self.captcha_img_box())
            code = tool.image_to_string(
                Image.open(self.code_path), lang=lang,
                builder=pyocr.builders.TextBuilder()
            )
            logger.info(u"计算验证码结果是{}".format(code))
            return code
        except NoSuchElementException:
            logger.info(u"没有验证码")
            return None

    def _login(self):
        logger.info("{}尝试登录!".format(self._user))
        txt_username = self._browser.find_element_by_css_selector(
            '.txt-username')
        txt_username.send_keys(self._user)
        txt_username.send_keys(Keys.RETURN)
        txt_pwd = self._browser.find_element_by_css_selector('.txt-password')
        txt_pwd.send_keys(self._pwd)
        txt_pwd.send_keys(Keys.RETURN)
        code = self.exactor_code()
        if code:
            if len(code) == 4:
                txt_captcha = self._browser.find_element_by_css_selector(
                    '.txt-captcha')
                txt_captcha.send_keys(code)
                txt_captcha.send_keys(Keys.RETURN)
            else:
                logger.info("验证码不正确")
                return False

        self._browser.get_screenshot_as_file(self.bean_path)
        self._browser.find_element_by_css_selector('.btn-login').click()
        try:
            ele = WebDriverWait(self._browser, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".err-msg")))
            logger.info(ele.text)
            return False
        except:
            logger.info(self._browser.title)
            if u'登录' not in self._browser.title:
                return True
            else:
                return False

    def login(self, trycount=10000):
        self._browser.get(self.base_url)
        self._browser.find_element_by_css_selector(
            '.jd-search-icon-login').click()
        for _ in range(trycount):
            if self._login():
                logger.info("{}登录成功！".format(self._user))
                return True
            else:
                logger.info("{}登录失败，重试中".format(self._user))
                self._browser.refresh()
        else:
            return False

    def logout(self):
        self._browser.get(self.base_url)
        self._browser.find_element_by_xpath('//footer/ul[1]/li[2]/a').click()
        logger.info("{}退出登录！".format(self._user))

    def sign_and_get_beans(self):
        logger.info("{}去拿豆豆!".format(self._user))
        self._browser.get(self.sign_and_get_beans_url)
        self._browser.find_element_by_css_selector('.state').click()
        self._browser.get_screenshot_as_file(self.bean_path)
        logger.info("{}拿豆豆成功!".format(self._user))
        self._browser.get(self.sign_and_get_beans_url)
        total_bean = float(
            self._browser.find_element_by_css_selector(
                '.my-bean > strong:nth-child(1)').text)
        return total_bean

    def __str__(self):
        return self._user


def main():
    browser = webdriver.Firefox()
    browser.implicitly_wait(10)
    try:
        text_body = ''
        for user, pwd in settings.users:
            user = JDUser(browser, user, pwd)
            if user.login():
                total_bean = user.sign_and_get_beans()
                text_body += '\n{}领取成功!当前京豆:{}'.format(user, total_bean)
                user.logout()
            else:
                text_body += '\n{}登录失败!'.format(user)

    except Exception:
        text_body = traceback.format_exc()
        logger.info(text_body)
    finally:
        envelope = Envelope(
            from_addr=(settings.email_user, u''),
            to_addr=(settings.email_user, u''),
            subject=u'京东领取京豆记录-{:%Y-%m-%d %H:%M:%S}'.format(
                datetime.datetime.now()),
            text_body=text_body
        )
        envelope.send(settings.email_host,
                      login=settings.email_user,
                      password=settings.email_pwd,
                      tls=True)
        logger.info("发送邮件成功!")
        browser.quit()

if __name__ == '__main__':
    main()
