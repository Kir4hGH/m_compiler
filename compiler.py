import dpda


class StringCompiler:
    def __init__(self, transition_dict):
        """
        Инициализация StringParser

        Args:
            transition_dict (dict): Объединенная таблица переходов ДМПА
        """

        self._transition_dict = transition_dict

    def compile(self, input_string) -> tuple:
        """
        Компиляция входной строки в код типа Ассемблер, используя ДМПА, и его оптимизация

        Args:
            input_string (str): Входная строка для анализа
        Returns:
            Кортеж, содержащий:
                - Таблицу имён
                - Неоптимизированный код
                - Оптимизированный код
        """

        processor = dpda.ActionProcessor()
        core = dpda.DPDACore(self._transition_dict, processor)

        # Проверка всей строки с помощью ДМПА
        core.process_string(input_string + '\0')
        return processor.get_result() # name_table, unoptimized_code, optimized_code

