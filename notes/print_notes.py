        # 保存文件的文件名
        self.speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        )
        self.speeches_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_fed_speeches.json"
        )
        self.failed_speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
        )

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            dict: 按自然年整理的演讲内容
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        # 载入已存储的演讲信息
        if os.path.exists(self.speech_infos_filename):
            existed_speech_infos = json_load(self.speech_infos_filename)
        else:
            existed_speech_infos = {}
        speech_infos = self.extract_speech_infos(existed_speech_infos)

        # 提取已存储的演讲
        if os.path.exists(self.speeches_filename):
            existed_speeches = json_load(self.speeches_filename)
            # 查看已有的最新的演讲日期
            existed_lastest = get_latest_speech_date(existed_speeches)
        else:
            existed_speeches = {}
            existed_lastest = "Jan 01, 2006"

        # 提取演讲正文内容
        print(
            "==" * 20
            + f"Start extracting speech content of {self.__fed_name__} from {existed_lastest}"
            + "==" * 20
        )
        speeches = self.extract_speeches(
            speech_infos_by_year=speech_infos,
            existed_speeches=existed_speeches,
            start_date=existed_lastest,
        )
        print("==" * 20 + f"{self.__fed_name__} finished." + "==" * 20)
        return speeches