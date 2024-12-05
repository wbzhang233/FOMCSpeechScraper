#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@File    :   fed_speech_scraper.py
@Time    :   2024/12/04 10:28:05
@Author  :   wbzhang 
@Version :   1.0
@Desc    :   FED演讲稿数据爬取运行
'''

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

if __name__ == "__main__":
    # 编排运行所有爬虫程序. 串行执行
    print(
        "="*50 + " Federal Reservel Speeches Scraper Starting... " + "="*50 + "\n"
    )
    for name, _scraper in SCRAPERS.items():
        scraper = _scraper()
        scraper.collect()
