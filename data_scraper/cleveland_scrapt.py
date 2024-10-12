#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   cleveland.py
@Time    :   2024/09/27 18:26:46
@Author  :   wbzhang
@Version :   1.0
@Desc    :   None
"""

from datetime import datetime
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)

from bs4 import BeautifulSoup
import json
import time

from data_scraper.scrapers.scraper import SpeechScraper
from utils.file_saver import json_dump

# 配置WebDriver
driver = webdriver.Chrome()

# 访问网站
url = "https://www.clevelandfed.org/collections/speeches"
driver.get(url)

try:
    # 设置时间范围为最早和最晚
    from_years_element = driver.find_element(By.ID, "fromYears")
    from_years_options = [
        int(option.text)
        for option in Select(from_years_element).options
        if option.text.isdigit()
    ]
    from_years_element.send_keys(str(min(from_years_options)))

    to_years_element = driver.find_element(By.ID, "toYears")
    to_years_options = [
        int(option.text)
        for option in Select(to_years_element).options
        if option and option.text.isdigit()
    ]
    to_years_element.send_keys(str(max(to_years_options)))
    # 点击搜寻按键
    search_button = driver.find_element(
        By.CSS_SELECTOR, "button.btn.btn-link[aria-label='Submit Filters']"
    )
    search_button.click()
    # 等待页面
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[@id='content']/div[3]/div[1]/search-results/div")
        )
    )
    time.sleep(3.0)
except Exception as e:
    print(f"Error setting date range: {e}")


# 主循环获取所有演讲信息
speeches = {}
while True:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    speech_items = soup.find_all("li", class_="result-item")

    for item in speech_items:
        # 提取日期
        date = item.find("div", class_="date-reference").text.split(" | ")[0].strip()
        year = int(date.split(".")[2])
        if year not in speeches:
            speeches[year] = []
        date = datetime.strptime(date, "%m.%d.%Y").strftime("%B %d, %Y")
        # 提取演讲者
        speaker = item.find("span", class_="author-name").text.strip()

        # 提取标题和链接
        title_link = item.find("a", href=True)
        title = title_link.text.strip()
        href = title_link["href"]

        # 提取描述
        description = (
            item.find("div", class_="page-description").find("p").text.strip()
            if item.find("div", class_="page-description")
            else ""
        )

        speeches[year].append(
            {
                "date": date,
                "speaker": speaker,
                "title": title,
                "href": f"https://www.clevelandfed.org{href}",
                "highlights": description,
                "content": "",  # 这里暂时不抓取具体内容
            }
        )

    # # Try to find and click the "Next" button
    try:
        next_button = driver.find_element(
            By.CSS_SELECTOR, "li.page-selector-item-next:not(.disabled) a"
        )
        driver.execute_script("arguments[0].click();", next_button)
        # 等待页面加载
        time.sleep(2.0)
        # WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.ID, "content"))
        # )
    except NoSuchElementException as e:
        print(f"Next button not found or disabled. Reached last page. {repr(e)}")
        break
    except TimeoutException as e:
        print(f"Next button not found or disabled. Reached last page. {repr(e)}")
        break
    except WebDriverException as e:
        print(f"Next button not found or disabled. Reached last page. {repr(e)}")
        break

    # try:
    #     next_button = driver.find_element(
    #         (
    #             By.CSS_SELECTOR,
    #             "li.page-selector-item-next:not(.disabled) a",
    #         )
    #     )
    #     next_button.click()
    #     WebDriverWait(driver, 10).until(
    #     EC.presence_of_element_located((By.ID, "content"))
    # )
    # except Exception as e:
    #     print(f"Clike next page failed. End of the page. {repr(e)}")
    #     break


# 将数据保存到JSON文件
with open("cleveland_speeches_infos.json", "w") as file:
    json.dump(speeches, file, indent=4)


# 关闭浏览器
driver.quit()
