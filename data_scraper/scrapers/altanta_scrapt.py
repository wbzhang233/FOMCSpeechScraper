from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time

from utils.file_saver import json_dump


def extract_speech_infos(driver, year):
    # 选择年份
    select_element = Select(driver.find_element(By.ID, "YearList"))
    select_element.select_by_value(str(year))

    # 点击筛选按钮
    filter_button = driver.find_element(
        By.XPATH,
        "/html/body/div[1]/article[2]/section/div[2]/div[2]/div[2]/div/div/div[1]/form/div/div[2]/input[1]",
    )
    filter_button.click()

    driver.implicitly_wait(2)
    time.sleep(2)
    # 等待加载完
    WebDriverWait(driver, 3).until(
        EC.presence_of_all_elements_located(
            (
                By.CLASS_NAME,
                "row.frba-content_router-date-linked-headline-Teaser-grouped",
            )
        )
    )

    # 获取页面源码
    page_source = driver.page_source

    soup = BeautifulSoup(page_source, "html.parser")
    speech_infos = []

    # 查找包含演讲信息的 div 元素
    speech_container = soup.find(
        "div", class_="row frba-content_router-date-linked-headline-Teaser-grouped"
    )

    # 包含这一年所有文章的元素
    foreach_item = speech_container.find("div", attrs={"data-bind": "foreach: items"})
    # 取出所有元素
    dates = foreach_item.find_all("div", class_="font-weight-bold")
    title_links = foreach_item.find_all("a")
    highlights = foreach_item.find_all("p")

    for i in range(len(dates)):
        speech_info = {
            "date": dates[i].text.strip(),
            "title": title_links[i].text.strip(),
            "href": title_links[i]["href"],
            "highlights": highlights[i].text.strip(),
        }
        speech_infos.append(speech_info)

    return speech_infos

    def extract_single_speech(driver, speech_info):
        try:
            driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "body > div.container > article:nth-child(2) > section > div.row > div.col-lg-11 > div.card.card-default.content-object-control.border-0 > div.card-block > div.main-content",
                    )
                )
            )

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            # 演讲内容元素
            speech_content = soup.find("div", class_="main-content")
            # 演讲人
            speaker_element = speech_content.find("p").find("strong")
            speaker = (
                speaker_element.text.split("\n")[0].strip() if speaker_element else ""
            )
            # highlights
            keypoints = speech_content.find("ul")
            highlights = "\n\n".join(
                [kp.text.strip() for kp in keypoints.find_all("li")]
            )
            # 剩下的兄弟节点才是正文内容
            content = [p.text.strip() for p in keypoints.find_next_siblings("p")]
            speech = {"speaker": speaker, "highlights": highlights, "content": content}
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {"speaker": "", "highlights": "", "content": ""}
        speech = speech.update(speech_info)
        return speech


def main():
    # 设置webdriver路径
    url = "https://www.atlantafed.org/news/speeches"

    # 初始化webdriver
    driver = webdriver.Chrome()
    driver.get(url)

    years = range(2023, 2021, -1)  # 指定要抓取的年份范围
    all_speeches = {}

    for year in years:
        print(f"Start scraping speeches of {year}...")
        speeches = extract_speech_infos(driver, year)
        all_speeches[year] = speeches
        json_dump(speeches, f"atlanta_fed_speeches_{year}.json")
        print(f"Fetched speeches for {year}")

    json_dump(all_speeches, "atlanta_fed_speeches.json")
    print("All speeches fetched and saved to atlanta_fed_speeches.json")
    driver.quit()


if __name__ == "__main__":
    main()
