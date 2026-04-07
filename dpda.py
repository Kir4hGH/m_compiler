class DPDACore:
    def __init__(self, transition_dict):
        """
        Инициализация ДМПА

        Args:
            transition_dict (dict):  Словарь переходов:
                - headers: кортежи (symbols, stack_pop) для tokenPairs
                - transitions: кортежи (next_state, stack_push)
        """
        self.dpda_stack = [] # Магазинная память для скобок
        self.stack = [] # Стек для хранения лексем и кода
        self.buffer = "" # Буфер считываемой лексемы
        self.current_state = 0 # Текущее состояние автомата
        self.name_table = [] # Таблица имён
        self.memory_counter = 0
        self.is_ended = False

        self.transition_dict = transition_dict

        # Извлекаем headers (варианты, куда можно пойти)
        self.headers = transition_dict['headers']
        # Извлекаем transition_table (сами инструкции для перехода)
        self.transition_table = transition_dict['transitions']

    def process_string(self, input_string) -> tuple:
        """
        Проход по цепочке символов строки

        Returns:
            Кортеж, содержащий:
                - Таблицу имён
                - Неоптимизированный код
        """

        i = 0
        while i < len(input_string):
            c = input_string[i]
            result = self._process_symbol(c)

            if result == -1:
                raise SyntaxError(f"Ошибка компиляции на символе '{c}' (позиция {i})")

            if result == 0:  # если завершилось
                break

            i += 1

        code = self.stack
        return self.name_table, code

    def _process_symbol(self, symbol) -> int:

        """
        Попытка перехода по таблице переходов ДМПА с текущим символом и состоянием стека

        Returns:
            int: 1 - успешный переход
                 0 - завершение работы (достигнуто состояние 99)
                -1 - ошибка (нет перехода, неверный символ и т.д.)
        """
        # Если автомат уже завершил работу, ничего не делаем
        if self.current_state == 99:
            return 0

        (best_stack_action, best_header_stack_pop, best_dpda_action, best_new_state, best_header_symbols) \
            = self._find_transition(symbol)

        if best_dpda_action is not None:
            self._do_action(best_dpda_action, best_header_stack_pop, symbol)

        # Меняем стек согласно правилам
        if not self._is_stack_empty() and best_header_stack_pop != '\1':
            # Если value не '\1' (игнорируем), делаем pop
            self.dpda_stack.pop()

        # Кладём новый символ в стек, если нужно
        if best_stack_action not in ('\0', '\1'):
            self.dpda_stack.append(best_stack_action)

        # Получаем новую вершину стека для вывода
        new_stack_top = None if not self.dpda_stack else self.dpda_stack[-1]

        print(f"Символ: {symbol}, Символ в стеке: {self._get_stack_top()}")
        print(f"Состояние: {self.current_state} -> {best_new_state}")
        print(f"Переход: '{best_header_symbols}', '{best_header_stack_pop}'")

        pop_action = ""
        if best_header_stack_pop == '\0':
            pop_action = "пустой"
        elif best_header_stack_pop == '\1':
            pop_action = "игнорировать"
        else:
            pop_action = f"забрать '{best_header_stack_pop}'"

        push_action = ""
        if best_stack_action == '\1':
            push_action = "игнорировать"
        elif best_stack_action == '\0':
            push_action = "ничего не класть"
        else:
            push_action = f"положить '{best_stack_action}'"

        print(f"Pop(): {pop_action}, Push(): {push_action}")
        print(f"Новая вершина стека: {new_stack_top}\n")


        # Обновляем состояние
        self.current_state = best_new_state

        if best_new_state == 99:
            self.is_ended = True
            return 0

        return 1

    def _find_transition(self, symbol):
        # Ищем все подходящие пары
        candidate_pairs = []
        for idx, (symbols, stack_pop) in enumerate(self.headers):
            # Можно ли перейти по символу
            if symbol in symbols or symbols == '\1':
                # Проверяем условия для value
                is_match = False
                if stack_pop == '\1':
                    is_match = True  # '\1' - игнорируем стек
                elif stack_pop == '\0':
                    is_match = self._is_stack_empty()  # '\0' - стек должен быть пуст
                else:
                    is_match = not self._is_stack_empty() and self._get_stack_top() == stack_pop

                if is_match:
                    candidate_pairs.append((idx, symbols, stack_pop))

        # Если нет кандидатов: сразу возвращаем -1
        if not candidate_pairs:
            return -1

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
            candidate_action = candidate_transition[2] if candidate_transition.count == 3 else None

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
            return -1

        return best_stack_action, best_header_stack_pop, best_dpda_action, best_new_state, best_header_symbols

    def _do_action(self, dpda_action, header_stack_pop, symbol):
        # Выполнение действия
        match dpda_action:
            case 1:
                self._add_to_buffer(symbol)
            case 2:
                self._move_buffer_to_stack()
            case 3:
                self._stack_parse()
            case 4:
                self._finalize()
            case 5:
                self._cyclic_reduction(header_stack_pop)
            case _:
                raise NotImplementedError("Нет реализации для действия под номером" + dpda_action)

    def reset(self):
        """Сброс автомата в начальное состояние"""
        self.dpda_stack = []
        self.current_state = 0
        self.is_ended = False

    def get_current_stack(self):
        """Получить текущее состояние стека"""
        return self.dpda_stack.copy()

    def _is_stack_empty(self):
        return len(self.dpda_stack) == 0

    def _get_stack_top(self):
        return None if self._is_stack_empty() else self.dpda_stack[-1]

    """Действия"""

    def _add_to_buffer(self, symbol):
        "A1: Добавление в буфер"
        self.buffer += symbol

    def _move_buffer_to_stack(self):
        "A2: Поместить содержимое буфера в стек и в таблицу имён"
        self.stack.append(self.buffer)
        self.add_to_name_table(self.buffer)
        self.buffer = ""

    def _stack_parse(self):
        "A3: Взятие данных для построения кода"
        op = self.dpda_stack.pop()
        Cr = self.stack.pop()
        Cl = self.stack.pop()
        self.stack.append(self._process_code(op, Cl, Cr))
    
    def _finalize(self):
        "A4: Обработка в конце цепочки"
        self._move_buffer_to_stack() # A2
        self._stack_parse() # A3

    def _cyclic_reduction(self, operator_a):
        "A5: Циклическое выполнение приоритетных операторов"
        self._move_buffer_to_stack() # A2
        operator_z = self.dpda_stack[-1]
        while DPDACore.get_operator_priority(operator_z) >= DPDACore.get_operator_priority(operator_a):
            self._stack_parse() # A3
            operator_z = self.dpda_stack[-1]

    """Вспомогательные методы"""

    def _process_code(self, op, Cl, Cr):
        """Построение кода"""
        if op == "=":
            "добавить STORE Cr"
            Cl += f"\nSTORE {Cr}"
        else:
            match op:
                case "+":
                    code_op = "ADD"
                case "*":
                    code_op = "MPY"
                case _:
                    raise NotImplementedError(f"Нет реализации для действия \"{op}\"")

            "store load action"
            Cl += (f"\nSTORE {{{++self.memory_counter}}}"
                   f"\nLOAD {Cr}"
                   f"\n{code_op} {{{self.memory_counter}}}")

    @staticmethod
    def get_operator_priority(op):
        operators = "+*("
        return operators.index(op)

    def add_to_name_table(self, token):
        # Добавляем запись в таблицу имён
        self.name_table.append({
            'Номер': self.name_table.count,
            'Идентификатор': token,
            'Информация': "info"
        })