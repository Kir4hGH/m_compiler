class DPDACore:
    def __init__(self, transition_dict: dict, action_processor):
        """
        Инициализация ДМПА

        Args:
            transition_dict (dict):  Словарь переходов:
                - headers: кортежи (symbols, stack_pop) - варианты перехода
                - transitions: кортежи (next_state, stack_push, action) - инструкции перехода
            action_processor: Обработчик действий
        """
        self.transition_dict = transition_dict
        self.action_processor = action_processor

        self.dpda_stack = [] # Магазинная память
        self.current_state = 0 # Текущее состояние автомата
        self.is_ended = False

        # Извлекаем headers (варианты, куда можно пойти)
        self.headers = transition_dict['headers']
        # Извлекаем transition_table (сами инструкции для перехода)
        self.transition_table = transition_dict['transitions']

    def process_string(self, input_string, do_reset=False):
        """Проход по цепочке символов строки"""

        # Сброс ДМПА и процессора действий по требованию
        if do_reset:
            self.reset()
            self.action_processor.reset()

        i = 0
        try:
            while i <= len(input_string):
                # Попытка перехода с символом из цепочки
                if i < len(input_string):
                    match self._process_symbol(input_string[i]):
                        case 1:
                            i += 1
                            continue
                        case 0:
                            break
                # Попытка e-такта
                match self._process_symbol('\1'):
                    case 0:
                        break
                    case 1:
                        continue
                    case -1:
                        pos = min(i-1, len(input_string)-1)
                        raise SyntaxError(f"Ошибка компиляции на символе '{input_string[pos]}' (позиция {pos})")
        except Exception:
            pos = min(i - 1, len(input_string) - 1)
            raise SyntaxError(f"Ошибка компиляции на символе '{input_string[pos]}' (позиция {pos})")

    def _process_symbol(self, symbol) -> int:
        """
        Попытка перехода по таблице переходов ДМПА с текущим символом и состоянием стека

        Returns:
            int: 1 - успешный переход
                 0 - завершение работы (достигнуто состояние HALT=99)
                -1 - ошибка (нет перехода, неверный символ и т.д.)
        """

        # Если автомат уже завершил работу
        if self.is_ended:
            return 0

        transition = self._find_transition(symbol)
        if transition is None:
            return -1

        (stack_insert, stack_pop, dpda_action, new_state, header_symbols) = transition

        # Выполнение действия
        if dpda_action is not None:
            self.action_processor.do_action(self, dpda_action, stack_pop, symbol)

        # Выполнение stack_pop
        if not self.is_stack_empty() and stack_pop != '\1':
            # Если value не '\1' (игнорируем), делаем pop
            self.dpda_stack.pop()

        # Выполнение stack_insert
        if stack_insert not in ('\0', '\1'):
            self.dpda_stack.append(stack_insert)

        # Обновление состояния
        self.current_state = new_state

        # Проверка на нахождение в конечном состоянии
        if new_state == 99:
            self.is_ended = True
            return 0

        return 1

    def _find_transition(self, symbol) -> tuple|None :
        # Поиск подходящих пар
        candidate_pairs = []
        for idx, (symbols, stack_pop) in enumerate(self.headers):
            # Проверка перехода по символу
            if symbol in symbols:
                # Проверка условия для value
                is_match = False
                if stack_pop == '\1':
                    is_match = True  # '\1' - игнорируем стек
                elif stack_pop == '\0':
                    is_match = self.is_stack_empty()  # '\0' - стек должен быть пуст
                else:
                    is_match = not self.is_stack_empty() and self.get_stack_top() == stack_pop

                if is_match:
                    candidate_pairs.append((idx, symbols, stack_pop))

        # Если нет кандидатов: сразу возвращаем -1
        if not candidate_pairs:
            return None

        # Для каждого кандидата проверяем переходы
        best_pair_idx = -1
        best_new_state = -1
        best_stack_action = '\0'
        best_header_symbols = ""
        best_header_stack_pop = '\0'
        best_dpda_action = None

        for pair_idx, token_key, token_value in candidate_pairs:
            # Проверяем границы таблицы состояний
            if (self.current_state < 0 or
                    self.current_state >= len(self.transition_table) or
                    pair_idx < 0 or
                    pair_idx >= len(self.transition_table[0])):
                continue

            # Получаем переход из таблицы состояний
            candidate_transition = self.transition_table[self.current_state][pair_idx] \
                if self.transition_table[self.current_state][pair_idx] else (-1, '\1')

            (candidate_new_state, candidate_stack_action) = candidate_transition[0:2]
            candidate_action = candidate_transition[2] if len(candidate_transition) == 3 else None

            # Если нашли переход с состоянием не -1, сохраняем его
            if candidate_new_state != -1:
                best_pair_idx = pair_idx
                best_new_state = candidate_new_state
                best_stack_action = candidate_stack_action
                best_header_symbols = token_key
                best_header_stack_pop = token_value
                best_dpda_action = candidate_action
                break  # Нашли подходящий переход

        # Если не нашли ни одного перехода с состоянием не -1
        if best_pair_idx == -1:
            return None

        return best_stack_action, best_header_stack_pop, best_dpda_action, best_new_state, best_header_symbols

    def reset(self):
        """Сброс автомата в начальное состояние"""
        self.dpda_stack.clear()
        self.current_state = 0
        self.is_ended = False

    def get_stack_top(self):
        return None if self.is_stack_empty() else self.dpda_stack[-1]

    def is_stack_empty(self):
        return len(self.dpda_stack) == 0


class ActionProcessor:
    def __init__(self):
        """
        Класс обработки действий и построения кода
        """
        self.stack = []  # Стек для хранения лексем и кода
        self.buffer = ""  # Буфер считываемой лексемы
        self.name_table = {}  # Таблица имён
        self.memory_counter = 0

    def do_action(self, dpda: DPDACore,  dpda_action: int, header_stack_pop, symbol):
        """Выполнение действия"""
        match dpda_action:
            case 1:
                self.action_add_to_buffer(symbol)
            case 2:
                self.action_move_buffer_to_stack()
            case 3:
                self.action_stack_parse(dpda.dpda_stack)
            case 4:
                self.action_brackets_reduction(dpda)
            case 5:
                self.action_cyclic_reduction(symbol, dpda)
            case _:
                raise NotImplementedError(f"Нет реализации для действия под номером {dpda_action}.")

    def get_result(self) -> tuple:
        """Возврат обработанных данных"""
        code = ''
        optimized_code = ''
        if len(self.stack) != 0:
            code = self.stack.pop()["value"]
            optimized_code = self._optimize(code)
        return self.name_table, code, optimized_code

    def reset(self):
        self.stack.clear()
        self.name_table.clear()
        self.buffer = ""
        self.memory_counter = 0

    """Действия"""

    def action_add_to_buffer(self, symbol):
        """A1: Добавление в буфер"""
        self.buffer += symbol

    def action_move_buffer_to_stack(self):
        """A2: Поместить содержимое буфера в стек и в таблицу имён"""
        if self.buffer != '':
            if self._is_number(self.buffer):
                self.buffer = '=' + self.buffer
            self.stack.append(
                {'value': self.buffer,
                 'level': 0})
            self._add_to_name_table(self.buffer)
            self.buffer = ""

    def action_stack_parse(self, dpda_stack):
        """A3: Взятие данных для построения кода"""
        op = dpda_stack.pop()
        Cr = self.stack.pop()
        Cl = self.stack.pop()
        self.stack.append(self._process_code(op, Cl, Cr))

    def action_brackets_reduction(self, dpda):
        """A4: Обработка выражения в скобках"""
        self.action_move_buffer_to_stack() # A2
        while dpda.get_stack_top() != '(':
            self.action_stack_parse(dpda.dpda_stack) # A3
        dpda.dpda_stack.pop() # Удаление скобки из магазинной памяти

    def action_cyclic_reduction(self, operator_a, dpda):
        """A5: Циклическое выполнение приоритетных операторов"""
        self.action_move_buffer_to_stack() # A2
        operator_z = dpda.get_stack_top()
        while self._get_operator_priority(operator_z) >= self._get_operator_priority(operator_a):
            self.action_stack_parse(dpda.dpda_stack) # A3
            operator_z = dpda.get_stack_top()

    """Вспомогательные методы"""

    def _add_to_name_table(self, token):
        # Добавление записи в таблицу имён
        info = 'Константа с плавающей точкой' if token[0] == '=' else 'Переменная с плавающей точкой'
        if token not in self.name_table:
            self.name_table[token] = ({
                'Номер': len(self.name_table),
                'Информация': f"{info}"
            })

    def _process_code(self, op, Cl, Cr):
        """Построение кода"""
        new_level = max(Cr['level'], Cl['level']) + 1

        match op:
            case "=":
                code = (f"LOAD {Cr['value']}"
                        f"\nSTORE {Cl['value']}")
            case "+":
                code = (f"{Cr['value']}"
                        f"\nSTORE ${new_level}"
                        f"\nLOAD {Cl['value']}"
                        f"\nADD ${new_level}")
            case "*":
                code = (f"{Cr['value']}"
                        f"\nSTORE ${new_level}"
                        f"\nLOAD {Cl['value']}"
                        f"\nMPY ${new_level}")
            case _:
                raise NotImplementedError(f"Нет реализации для действия \"{op}\"")
        return {'value': code,
                'level': new_level}

    @staticmethod
    def _optimize(code: str) -> str:
        import re

        # Правила 1-3
        code = re.sub(r'\nSTORE (\$.*?)\nLOAD (=.*?)\n(ADD|MPY) \1', r'\n\3 \2', code)

        # Правило 4
        prev_len = -1
        while len(code) != prev_len:
            prev_len = len(code)
            code = re.sub(r'LOAD (=.*?)\nSTORE (\$.*?)\n((?:(?!\nSTORE \2)[^\n]*\n)*?)(ADD|MPY) \2',
                          r'\3\4 \1', code)

        return code

    @staticmethod
    def _is_number(value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _get_operator_priority(op):
        match op:
            case None:
                return -1
            case _:
                operators = "(\1\0=+*"
                return operators.index(op)
