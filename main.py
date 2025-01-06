import json
import os
import random
import re
import sys
import time
from hashlib import md5

import requests
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
                             QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget, QDialog)
from config import Ui_Dialog

appid = ''
appkey = ''
choices = {
    "中文": "zh",
    "英语": "en",
    "日语": "jp",
    "韩语": "kor",
    "法语": "fra",
    "俄语": "ru",
    "德语": "de",
    "繁体中文": "cht",
}

def translate_text(text, src, dest):
    # Set your own appid/appkey.
    global appid
    global appkey

    # For list of language codes, please refer to `https://api.fanyi.baidu.com/doc/21`
    from_lang = src
    to_lang = dest

    endpoint = 'http://api.fanyi.baidu.com'
    path = '/api/trans/vip/translate'
    url = endpoint + path

    query = text

    # Generate salt and sign
    def make_md5(s, encoding='utf-8'):
        return md5(s.encode(encoding)).hexdigest()

    salt = random.randint(32768, 65536)
    sign = make_md5(appid + query + str(salt) + appkey)

    # Build request
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'appid': appid, 'q': query, 'from': from_lang, 'to': to_lang, 'salt': salt, 'sign': sign}

    # Send request
    r = requests.post(url, params=payload, headers=headers)
    result = r.json()

    assert "trans_result" in result
    # Show response
    text = ''
    for item in result['trans_result']:
        text += item['dst'] + "\n"

    return text[:-1]


class TranslateThread(QThread):
    sinOut = pyqtSignal(str)
    src_lang = ''
    dest_lang = ''
    src_text = ''

    def run(self):
        content = self.src_text.split("\n")

        for line in content:
            match = re.match(r'\"(.*)\"\s*=\s*\"(.*)\";', line)
            if match:
                key, value = match.groups()
                try:
                    translated_value = translate_text(value, self.src_lang, self.dest_lang)
                    translated_line = f'"{key}" = "{translated_value}";\n'
                except AssertionError:
                    translated_line = line + "\n"
            else:
                translated_line = line + "\n"
            self.sinOut.emit(translated_line)
            time.sleep(1)  # 个人用户百度访问速度限制


class TranslatorApp(QWidget):
    def __init__(self):
        super().__init__()

        global appid
        global appkey
        global choices

        select = QMessageBox.No
        if os.path.exists(os.path.join(os.path.expanduser("~"), "baidu.txt")):
            with open(os.path.join(os.path.expanduser("~"), "baidu.txt"), 'r', encoding='utf-8') as f:
                try:
                    data = json.loads(f.read())
                    if data.get("appid", "") > "" and data.get("appkey", "") > "":
                        appid = data['appid']
                        appkey = data['appkey']
                    else:
                        select = QMessageBox.warning(None, "警告", "百度配置错误，请重新输入配置信息", QMessageBox.Ok | QMessageBox.No)
                    if "language" in data and len(list(data['language'].keys())) > 0:
                        choices = data['language']
                except json.JSONDecodeError:
                    select = QMessageBox.warning(None, "警告", "未读取到百度翻译配置", QMessageBox.Ok | QMessageBox.No)
        else:
            select = QMessageBox.warning(None, "警告", "未读取到百度翻译配置", QMessageBox.Ok | QMessageBox.No)
        if select == QMessageBox.Ok:
            self.config_baidu()

        self.setWindowTitle('文本翻译器')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # 源语言选择
        hbox1 = QHBoxLayout()
        self.src_lang_label = QLabel('源语言:')
        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItems(["自动检测"] + list(choices.keys()))  # 可以根据需要添加更多语言
        hbox1.addWidget(self.src_lang_label)
        hbox1.addWidget(self.src_lang_combo)
        conf_btn = QPushButton("配置")
        conf_btn.clicked.connect(self.config_baidu)
        hbox1.addWidget(conf_btn)
        layout.addLayout(hbox1)

        # 目标语言选择
        hbox2 = QHBoxLayout()
        self.dest_lang_label = QLabel('目标语言:')
        self.dest_lang_combo = QComboBox()
        self.dest_lang_combo.addItems(list(choices.keys()))  # 可以根据需要添加更多语言
        hbox2.addWidget(self.dest_lang_label)
        hbox2.addWidget(self.dest_lang_combo)
        # 翻译按钮
        self.translate_button = QPushButton('翻译')
        self.translate_button.clicked.connect(self.translate_text)
        hbox2.addWidget(self.translate_button)
        layout.addLayout(hbox2)

        hbox3 = QHBoxLayout()
        vbox1 = QVBoxLayout()
        # 源文本输入
        self.src_text_label = QLabel('源文本:')
        self.src_text_edit = QTextEdit()
        vbox1.addWidget(self.src_text_label)
        vbox1.addWidget(self.src_text_edit)
        hbox3.addLayout(vbox1)
        vbox2 = QVBoxLayout()
        # 译文显示
        self.dest_text_label = QLabel('译文:')
        self.dest_text_edit = QTextEdit()
        self.dest_text_edit.setReadOnly(True)
        vbox2.addWidget(self.dest_text_label)
        vbox2.addWidget(self.dest_text_edit)
        hbox3.addLayout(vbox2)
        layout.addLayout(hbox3)

        self.setLayout(layout)

        self.thread = TranslateThread()
        self.thread.sinOut.connect(self.callback)

    def config_baidu(self):
        global appid
        global appkey
        global choices

        dialog = QDialog()
        ui = Ui_Dialog()
        ui.setupUi(dialog)
        ui.AppId.setText(appid)
        ui.AppKey.setText(appkey)
        ui.Language.setText(json.dumps(choices, ensure_ascii=False, indent=4))
        if dialog.exec_():
            appid = ui.AppId.text()
            appkey = ui.AppKey.text()
            choices = json.loads(ui.Language.toPlainText())
            self.src_lang_combo.clear()
            self.src_lang_combo.addItems(["自动检测"] + list(choices.keys()))
            self.dest_lang_combo.clear()
            self.dest_lang_combo.addItems(list(choices.keys()))
            with open(os.path.join(os.path.expanduser("~"), "baidu.txt"), 'w', encoding='utf-8') as f:
                f.write(json.dumps({"appid": appid, "appkey": appkey, "language": choices}))

    def translate_text(self):
        src_lang = self.src_lang_combo.currentText()
        if src_lang == '自动检测':
            src_lang = 'auto'
        else:
            src_lang = choices[src_lang]
        dest_lang = choices[self.dest_lang_combo.currentText()]
        src_text = self.src_text_edit.toPlainText()
        self.dest_text_edit.setPlainText("")

        if src_text:
            self.thread.src_lang = src_lang
            self.thread.dest_lang = dest_lang
            self.thread.src_text = src_text
            self.thread.start()
        else:
            QMessageBox.critical(None, "错误", "请先输入要翻译的文本。", QMessageBox.Ok)

    def callback(self, msg):
        self.dest_text_edit.setPlainText(self.dest_text_edit.toPlainText() + msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    translator_app = TranslatorApp()
    translator_app.show()
    sys.exit(app.exec_())
