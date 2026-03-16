class DPDACore:
    def __init__(self, transition_dict):
        """
        Инициализация ДМПА

        Args:
            transition_dict (dict):  Словарь переходов:
                - headers: кортежи (symbols, stack_pop) для tokenPairs
                - transitions: кортежи (next_state, stack_push)
        """
        self.dpda_stack = []  # Магазинная память для скобок
        self.stack = [] #  Стек для хранения лексем и кода
        self.buffer = "" # Буфер считываемой лексемы
        self.current_state = 0  # Текущее состояние автомата
        
        self.transition_dict = transition_dict

        # Извлекаем headers (варианты, куда можно пойти)
        self.headers = transition_dict['headers']
        # Извлекаем transition_table (сами инструкции для перехода)
        self.transition_table = transition_dict['transitions']

    def change_state(self, symbol):
        """
        Попытка перехода по таблице переходов ДМПА с текущим символом и состоянием стека

        Returns:
            int: 1 - успешный переход
                 0 - завершение работы (достигнуто состояние 99)
                -1 - ошибка (нет перехода, неверный символ и т.д.)
        """
        # Если автомат уже завершил работу: ничего не делаем
        if self.current_state == 99:
            return 0

        # Получаем вершину стека
        stack_is_empty = len(self.dpda_stack) == 0
        stack_top = None if stack_is_empty else self.dpda_stack[-1]

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
                    is_match = stack_is_empty  # '\0' - стек должен быть пуст
                else:
                    is_match = not stack_is_empty and stack_top == stack_pop

                if is_match:
                    candidate_pairs.append((idx, symbols, stack_pop))

        # Если нет кандидатов: сразу возвращаем -1
        if not candidate_pairs:
            print("Подходящего перехода не найдено")
            return -1

        # Для каждого кандидата проверяем переходы
        best_pair_idx = -1
        best_new_state = -1
        best_stack_action = '\0'
        best_header_symbols = ""
        best_header_stack_pop = '\0'

        for pair_idx, token_key, token_value in candidate_pairs:
            # Проверяем границы таблицы состояний
            if (self.current_state < 0 or
                    self.current_state >= len(self.transition_table) or
                    pair_idx < 0 or
                    pair_idx >= len(self.transition_table[0])):
                continue

            # Получаем переход из таблицы состояний
            candidate_new_state, candidate_stack_action = self.transition_table[self.current_state][pair_idx] if self.transition_table[self.current_state][pair_idx] else (-1, '\1')

            # Если нашли переход с состоянием не -1, сохраняем его
            if candidate_new_state != -1:
                best_pair_idx = pair_idx
                best_new_state = candidate_new_state
                best_stack_action = candidate_stack_action
                best_header_symbols = token_key
                best_header_stack_pop = token_value
                break  # Нашли подходящий переход

        # Если не нашли ни одного перехода с состоянием не -1
        if best_pair_idx == -1:
            print("Все возможные переходы ведут в состояние -1")
            return -1

        # Меняем стек согласно правилам
        if not stack_is_empty and best_header_stack_pop != '\1':
            # Если value не '\1' (игнорируем), делаем pop
            self.dpda_stack.pop()

        # Кладём новый символ в стек, если нужно
        if best_stack_action not in ('\0', '\1'):
            self.dpda_stack.append(best_stack_action)

        # Получаем новую вершину стека для вывода
        new_stack_top = None if not self.dpda_stack else self.dpda_stack[-1]

        print(f"Символ: {symbol}, Символ в стеке: {stack_top}")
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

    def reset(self):
        """Сброс автомата в начальное состояние"""
        self.dpda_stack = []
        self.current_state = 0
        self.is_ended = False

    def get_current_stack(self):
        """Получить текущее состояние стека"""
        return self.dpda_stack.copy()

    def new_buffer(self, symbol):
        "A1: Начало нового буфера"
        self.buffer = symbol

    def add_to_buffer(self, symbol):
        "A2: Добавление в буфер"
        self.buffer += symbol

    def move_buffer_to_stack(self):
        "A3: Поместить содержимое буфера в стек"
        self.stack.append(self.buffer)
        self.buffer = ""

    def stack_parse(self):
        "A4: Взятие данных для построения кода"
        op = self.dpda_stack.pop()
        Cr = self.stack.pop()
        Cl = self.stack.pop()
        self.stack.append(self.process_code(op,Cl,Cr))
    
    def finalize(self):
        "A5: Обработка в конце цепочки"
        self.move_buffer_to_stack() # A3
        self.stack_parse() # A4

    def process_code(op,Cl,Cr):
        "Построение кода"
        pass

    def cyclic_reduction(self, operator_a):
        "A6: Циклическое выполнение приоритетных операторов"
        self.move_buffer_to_stack() # A3
        operator_z = self.dpda_stack[-1]
        while (priotity_check(operator_z, operator_a)):
            self.stack_parse() # A4
            operator_z = self.dpda_stack[-1]
        
