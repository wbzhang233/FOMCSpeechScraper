from abc import abstractmethod
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC

FOMC_MEETING_PROMPT = """
下面这个网站是美联储FOMC的会议网址：https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
该网址的正文部分按照自然年用Panel控件发布了每年的美联储议息会议的公告，包括会议月份和日期、议息决议Statement和会议备忘录Minutes。其中Statement给出了PDF、HTML以及Implementation Note三个链接，Minutes则只给出了PDF和HTML链接以及发布时间。注意，有的决议可能不披露上述信息，则仅保存月份、日期和决议名称等信息。
我想要按照年份，爬取每一条议息决议数据，包括月份、日期、statement中HTML的网址和内容，以及会议备忘录minutes中的内容，每一条决议数据都存储为一个字典，最后按年份来保存所有数据为json文件。
记载每一条议息决议的字典应当包含如下键，含义如下：
year: 决议年份，为str类型，如2024
month: 决议月份，为str类型，如Feb
date: 决议日期，为str类型，如17-19


请帮我基于Python和Selenium开发代码实现上述功能。
"""


class SpeechScraper(object):
    URL: str = ""

    def __init__(self, url: str = None, **kwargs):
        options = kwargs.get("options", None)
        self.driver = webdriver.Chrome(options=options)
        url = self.URL if url is None else url
        if not url:
            raise ValueError("No url provided.")
        self.driver.get(url)

    @abstractmethod
    def extract_speech_infos(self):
        """抽取演讲的url信息

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `extract_speech_infos` not realized.")

    @abstractmethod
    def extract_speeches(self):
        """抽取演讲内容

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `extract_speeches` not realized.")
    
    @abstractmethod
    def collect(self):
        """收集演讲并保存

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `collect` not realized.")