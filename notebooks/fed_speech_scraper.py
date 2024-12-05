#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   fed_speech_scraper.py
@Time    :   2024/12/04 10:28:05
@Author  :   wbzhang
@Version :   1.0
@Desc    :   FED演讲稿数据爬取运行
"""

import schedule
import time
from data_scraper.scrapers import (
    BOGSpeechScraper,
    BostonSpeechScraper,
    NewYorkSpeechScraper,
    PhiladelphiaSpeechScraper,
    ClevelandSpeechScraper,
    RichmondSpeechScraper,
    AtlantaSpeechScraper,
    ChicagoSpeechScraper,
    StLouisSpeechScraper,
    MinneapolisSpeechScraper,
    KansasCitySpeechScraper,
    DallasSpeechScraper,
    SanFranciscoSpeechScraper,
)

SCRAPERS = {
    "board": BOGSpeechScraper,
    "boston": BostonSpeechScraper,
    "newyork": NewYorkSpeechScraper,
    "philadelphia": PhiladelphiaSpeechScraper,
    "cleveland": ClevelandSpeechScraper,
    "richmond": RichmondSpeechScraper,
    "atlanta": AtlantaSpeechScraper,
    "chicago": ChicagoSpeechScraper,
    "stlouis": StLouisSpeechScraper,
    "minneapolis": MinneapolisSpeechScraper,
    "kansascity": KansasCitySpeechScraper,
    "dallas": DallasSpeechScraper,
    "sanfrancisco": SanFranciscoSpeechScraper,
    # "freser": FRESERScraper,
    # "fraserfrb": FRASERFRBSpeechScraper
}


def main():
    # 编排运行所有爬虫程序. 串行执行
    print(
        "=" * 50 + " Federal Reservel Speeches Scraper Starting... " + "=" * 50 + "\n"
    )
    for name, _scraper in SCRAPERS.items():
        scraper = _scraper()
        scraper.collect()
    return False


def job_scheduler():
    should_continue = True

    def scheduled_main():
        nonlocal should_continue
        result = main()
        if result is False:
            should_continue = False

    schedule.every().day.at("02:00").do(scheduled_main)
    while should_continue:
        print("Checking for scheduled tasks...")
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次是否有任务需要执行


if __name__ == "__main__":
    job_scheduler()
