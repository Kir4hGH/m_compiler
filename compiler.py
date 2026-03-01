from dpda import DPDACore


class StringCompiler:
    def __init__(self, transition_dict):
        """
        Инициализация StringParser

        Args:
            transition_dict (dict): Объединенная таблица переходов ДМПА
        """

        self._transition_dict = transition_dict

    def compile(self, input_string):
        """
        Запуск анализа входной строки

        Args:
            input_string (str): Входная строка для анализа
        """
        # Проверка всей строки с помощью ДМПА
        if not self._validate_with_dmpa(input_string + '\0'):
            return "ДМПА не смог корректно завершить работу"

        result = ''

        # Генерация кода, если строка валидная (если ДМПА успешно закончил работу)
        try:
            generator = CodeGenerator(input_string)

            # Таблица имён
            result += CodeGenerator.print_name_table(generator.build_name_table())

            if input_string == '':
                return result


            # Неоптимизированный код
            code_unoptimized = generator.generate_unoptimized()
            result += "\n=== Неоптимизированный код ===\n"
            for line in code_unoptimized:
                result += line + '\n'

            # Оптимизированный код
            code_optimized = generator.generate_optimized()
            result += "\n=== Оптимизированный код ===\n"
            for line in code_optimized:
                result += line + '\n'

            return result

        except Exception as ex:
            print(f"Ошибка компиляции: {ex}")


    def _validate_with_dmpa(self, input_string) -> bool:
        """
        Проверка входной строки с помощью ДМПА

        Returns:
            bool: True если строка валидна, False в противном случае
        """
        core = DPDACore(self._transition_dict)
        i = 0

        while i < len(input_string):
            c = input_string[i]
            result = core.change_state(c)

            if result == -1:
                raise SyntaxError(f"Ошибка компиляции на символе '{c}' (позиция {i})")

            if result == 0 and core.is_ended:  # если завершилось
                break

            i += 1

        # ДМПА должен завершиться в состоянии 99
        return core.is_ended


class CodeGenerator:
    """
    Класс генерации кода типа Ассемблер
    Публичные методы:
        * generate_unoptimized(expression) - Генерация неоптимизированного кода
        * generate_optimized(expression) - Генерация оптимизированного кода
    """

    def __init__(self, expression):
        """
        Инициализация CodeGenerator

        Args:
            expression (str): Арифметическое выражение для генерации кода
        """
        # Удаляем пробелы и завершающие нулевые символы
        self.input = (expression.replace(" ", "")
                      .replace("\0", "")
                      .replace("\r", "")
                      .replace("\n", ""))

        self.pos = 0
        self._optimized_context = False  # Флаг для отслеживания контекста

    def generate_unoptimized(self):
        """
        Генерация НЕОПТИМИЗИРОВАННОГО кода (без перестановки операндов)

        Returns:
            list: Список строк сгенерированного кода
        """
        self.pos = 0  # сбрасываем позицию
        self._optimized_context = False

        var_name = self._parse_identifier()
        if self.pos >= len(self.input) or self.input[self.pos] != '=':
            raise Exception("Ожидался символ '='")
        self.pos += 1

        code, _ = self._parse_expression_unoptimized()  # результат выражения — в сумматоре

        lines = [line.strip() for line in code.split(';') if line.strip()]
        lines.append(f"STORE {var_name}")
        return lines

    def generate_optimized(self):
        """
        Генерация ОПТИМИЗИРОВАННОГО кода (с перестановкой операндов)

        Returns:
            list: Список строк сгенерированного кода
        """
        self.pos = 0  # сбрасываем позицию
        self._optimized_context = True

        var_name = self._parse_identifier()
        if self.pos >= len(self.input) or self.input[self.pos] != '=':
            raise Exception("Ожидался символ '='")
        self.pos += 1

        code, _ = self._parse_expression_optimized()  # с оптимизацией перестановки

        lines = [line.strip() for line in code.split(';') if line.strip()]
        lines.append(f"STORE {var_name}")

        # Применяем дополнительную оптимизацию
        return self._optimize(lines)

    def _parse_expression_unoptimized(self):
        """
        Парсинг выражения БЕЗ оптимизационной перестановки

        Returns:
            tuple: (код, уровень)
        """
        left_code, left_level = self._parse_term_unoptimized()

        if self.pos < len(self.input) and self.input[self.pos] == '+':
            self.pos += 1
            right_code, right_level = self._parse_expression_unoptimized()

            current_level = 1 + max(left_level, right_level)

            # сначала ПРАВЫЙ операнд, потом ЛЕВЫЙ
            left_value = left_code[5:] if left_code.startswith("LOAD ") else left_code
            new_code = f"{right_code}; STORE ${current_level}; LOAD {left_value}; ADD ${current_level}"
            return new_code, current_level

        return left_code, left_level

    def _parse_term_unoptimized(self):
        """
        Парсинг терма БЕЗ оптимизационной перестановки

        Returns:
            tuple: (код, уровень)
        """
        left_code, left_level = self._parse_factor()

        if self.pos < len(self.input) and self.input[self.pos] == '*':
            self.pos += 1
            right_code, right_level = self._parse_term_unoptimized()

            current_level = 1 + max(left_level, right_level)

            left_value = left_code[5:] if left_code.startswith("LOAD ") else left_code
            new_code = f"{right_code}; STORE ${current_level}; LOAD {left_value}; MPY ${current_level}"
            return new_code, current_level

        return left_code, left_level

    def _parse_expression_optimized(self):
        """
        Парсинг выражения С оптимизационной перестановкой

        Returns:
            tuple: (код, уровень)
        """
        left_code, left_level = self._parse_term_optimized()

        if self.pos < len(self.input) and self.input[self.pos] in '+':
            self.pos += 1
            right_code, right_level = self._parse_expression_optimized()

            current_level = 1 + max(left_level, right_level)

            # Определяем, какой операнд сделать "основным" (который будет в STORE)
            if self._is_constant_code(right_code):
                primary_code = left_code  # переменная
                secondary_code = right_code  # константа
            elif self._is_constant_code(left_code):
                primary_code = right_code  # переменная
                secondary_code = left_code  # константа
            else:
                # Оба не константы - оставляем как есть
                primary_code = left_code
                secondary_code = right_code

            # Генерируем: secondary (константа) сохраняется, primary загружается, затем ADD secondary
            new_code = f"{secondary_code}; STORE ${current_level}; {primary_code}; ADD ${current_level}"
            return new_code, current_level

        return left_code, left_level

    def _parse_term_optimized(self):
        """
        Парсинг терма С оптимизационной перестановкой

        Returns:
            tuple: (код, уровень)
        """
        left_code, left_level = self._parse_factor()

        if self.pos < len(self.input) and self.input[self.pos] == '*':
            self.pos += 1
            right_code, right_level = self._parse_term_optimized()

            current_level = 1 + max(left_level, right_level)

            # Проверяем, является ли левая часть переменной, а правая - константой
            # Если да, то переставляем для оптимизации (коммутативность *)
            if self._is_constant_code(left_code) and self._is_variable_code(right_code):
                new_code = f"{left_code}; STORE ${current_level}; {right_code}; MPY ${current_level}"
                return new_code, current_level
            else:
                new_code = f"{right_code}; STORE ${current_level}; {left_code}; MPY ${current_level}"
                return new_code, current_level

        return left_code, left_level

    def _parse_factor(self):
        """
        Парсинг фактора (переменная, число или выражение в скобках)

        Returns:
            tuple: (код, уровень)
        """
        if self.pos >= len(self.input):
            raise Exception("Неожиданный конец")

        if self.input[self.pos] == '(':
            self.pos += 1  # '('
            # Для скобок используем тот же подход - оптимизированный или неоптимизированный
            if self._optimized_context:
                result, level = self._parse_expression_optimized()
            else:
                result, level = self._parse_expression_unoptimized()

            if self.pos >= len(self.input) or self.input[self.pos] != ')':
                raise Exception("Ожидалась ')'")
            self.pos += 1  # ')'
            return result, level
        elif self.input[self.pos].isalpha() or self.input[self.pos] == '_':
            ident = self._parse_identifier()
            return f"LOAD {ident}", 0
        elif self.input[self.pos].isdigit():
            number = self._parse_number()
            return f"LOAD ={number}", 0
        else:
            raise Exception(f"Недопустимый символ: {self.input[self.pos]}")

    def _is_constant_code(self, code):
        """
        Проверяет, является ли код загрузкой константы

        Args:
            code (str): Код для проверки

        Returns:
            bool: True если код загружает константу
        """
        return code.startswith("LOAD =")

    def _is_variable_code(self, code):
        """
        Проверяет, является ли код загрузкой переменной

        Args:
            code (str): Код для проверки

        Returns:
            bool: True если код загружает переменную (не константу)
        """
        return code.startswith("LOAD ") and not code.startswith("LOAD =")

    def _parse_identifier(self):
        """
        Парсинг идентификатора (имени переменной)

        Returns:
            str: Идентификатор
        """
        start = self.pos
        while (self.pos < len(self.input) and
               (self.input[self.pos].isalnum() or self.input[self.pos] == '_')):
            self.pos += 1

        if start == self.pos:
            raise Exception("Ожидался идентификатор")

        return self.input[start:self.pos]

    def _parse_number(self):
        """
        Парсинг числа (целое, дробное, с экспонентой)

        Returns:
            str: Число в строковом формате
        """
        start = self.pos

        # Целая часть
        while self.pos < len(self.input) and self.input[self.pos].isdigit():
            self.pos += 1

        # Дробная часть
        if self.pos < len(self.input) and self.input[self.pos] == '.':
            self.pos += 1
            while self.pos < len(self.input) and self.input[self.pos].isdigit():
                self.pos += 1

        # Экспоненциальная часть: e или E
        if self.pos < len(self.input) and self.input[self.pos].lower() == '\1':
            self.pos += 1  # '\1' или 'E'

            # Опциональный знак
            if self.pos < len(self.input) and (self.input[self.pos] == '+' or self.input[self.pos] == '-'):
                self.pos += 1

            # Обязательные цифры после e
            if self.pos >= len(self.input) or not self.input[self.pos].isdigit():
                raise Exception("Ожидались цифры после '\1' или 'E'")

            while self.pos < len(self.input) and self.input[self.pos].isdigit():
                self.pos += 1

        return self.input[start:self.pos]

    def _optimize(self, code_lines):
        """
        Дополнительная оптимизация сгенерированного кода

        Args:
            code_lines (list): Список строк кода для оптимизации

        Returns:
            list: Оптимизированный список строк кода
        """
        # Сначала найдем все STORE и их позиции
        store_positions = {}
        temp_values = {}  # $1 -> LOAD =5

        for i, line in enumerate(code_lines):
            if line.startswith("STORE $"):  # STORE $1
                temp_var = line.split(' ')[1]
                store_positions[temp_var] = i

                # Найдем соответствующий LOAD перед STORE
                if i > 0 and code_lines[i - 1].startswith("LOAD "):
                    temp_values[temp_var] = code_lines[i - 1][5:].strip()

        # Подсчитаем использование каждой временной переменной
        usage_count = {}
        for temp_var in store_positions.keys():
            usage_count[temp_var] = 0
            for i, line in enumerate(code_lines):
                if i != store_positions[temp_var] and f" {temp_var}" in line:
                    usage_count[temp_var] += 1

        # Применяем оптимизацию
        optimized = []
        replacements = {}

        i = 0
        while i < len(code_lines):
            line = code_lines[i]

            # Проверяем шаблон: LOAD =const; STORE $k;
            if (line.startswith("LOAD =") and i + 1 < len(code_lines) and
                    code_lines[i + 1].startswith("STORE $")):

                temp_var = code_lines[i + 1].split(' ')[1]

                # Если временная переменная используется ровно 1 раз и её значение - константа
                if (usage_count.get(temp_var) == 1 and
                        temp_values.get(temp_var, '').startswith('=')):
                    replacements[temp_var] = line[5:].strip()  # "=5"
                    i += 1  # пропустить STORE
                    i += 1  # перейти к следующей итерации
                    continue

            # Также обрабатываем случаи как в (2+5) где STORE не сразу после LOAD
            if line.startswith("STORE $"):
                temp_var = line.split(' ')[1]
                # Проверяем, является ли значение константой и используется ли 1 раз
                if (usage_count.get(temp_var) == 1 and
                        temp_values.get(temp_var, '').startswith('=')):
                    # Пропускаем STORE, замена будет применена ниже
                    i += 1
                    continue
                else:
                    optimized.append(line)
            else:
                # Применяем замены
                new_line = line
                for rep_var, rep_value in replacements.items():
                    new_line = new_line.replace(f" {rep_var}", f" {rep_value}")
                optimized.append(new_line)

            i += 1

        return optimized

    def build_name_table(self):
        """
        Строит таблицу имен с проверкой уникальности идентификаторов.

        Returns:
            list: Таблица имен с уникальными идентификаторами
        """
        # Удаляем лишние пробелы по краям
        expr = self.input.strip()

        # Заменяем все операторы и скобки на пробелы
        for char in '=+-*/()':
            expr = expr.replace(char, ' ')

        # Сплитим по пробелам (учитываем множественные пробелы)
        tokens = expr.split()

        # Строим таблицу
        name_table = []
        seen_identifiers = set()  # Множество для отслеживания уже добавленных идентификаторов
        item_counter = 1  # Счетчик для нумерации элементов

        for token in tokens:
            # Проверяем, что токен не пустой
            if not token:
                continue

            # Определяем тип
            if token[0].isalpha() or token[0] == '_':
                info = "Переменная с плавающей точкой"
            elif all(c.isdigit() or c in '.-+eE' for c in token):
                info = "Константа с плавающей точкой"
            else:
                # Неизвестный тип, пропускаем
                continue

            # Проверяем уникальность идентификатора
            if token in seen_identifiers:
                # Если идентификатор уже есть, не добавляем его снова
                continue

            # Добавляем в множество просмотренных
            seen_identifiers.add(token)

            # Добавляем в таблицу
            name_table.append({
                'Номер': item_counter,
                'Идентификатор': token,
                'Информация': info
            })
            item_counter += 1

        return name_table

    # Таблица в текстовом виде
    @staticmethod
    def print_name_table(name_table):
        if not name_table:
            print("Таблица имен пуста")
            return

        # Определяем максимальные длины для красивого вывода
        max_num_len = max(len(str(item['Номер'])) for item in name_table)
        max_id_len = max(len(item['Идентификатор']) for item in name_table)
        max_info_len = max(len(item['Информация']) for item in name_table)

        # Заголовки
        num_header = "№"
        id_header = "Идентификатор"
        info_header = "Информация"

        # Корректируем максимальные длины под заголовки
        max_num_len = max(max_num_len, len(num_header))
        max_id_len = max(max_id_len, len(id_header))
        max_info_len = max(max_info_len, len(info_header))

        result = ''
        # Выводим заголовок
        result += f"{num_header:^{max_num_len}} | {id_header:^{max_id_len}} | {info_header:^{max_info_len}}\n"
        result += "-" * (max_num_len + max_id_len + max_info_len + 6) + '\n'

        # Заносим данные
        for item in name_table:
            result += \
                f"{item['Номер']:^{max_num_len}} | {item['Идентификатор']:^{max_id_len}} | {item['Информация']:^{max_info_len}}\n"

        return result