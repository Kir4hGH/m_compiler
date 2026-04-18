using System;
using System.IO;
using System.Text;
using static System.Formats.Asn1.AsnWriter;

// ----------- Примеры для теста -----------
// ---------------- Валидно ----------------
// x = a + b
// y = 5 * c
// result = 2.5 + 3.7
// expr = a + b * c
// expr = (a + b) * c
// deep = ((a + b) * (c + d)) + e
// opt = 10 + x
// opt2 = y * 5
// result_val = var_1 + var_2
// program = (a + 2.5) * (b + 3) + c * 4.0
// program = a + b * (2 + 5)
// const = 42.0
// x = (((a)))
// x = 1e5
// y = 2.5e3
// z = 3.14e-2
// a = 6.02E+23
// b = 10e0
// d = 0.5e2
// result = 1.23e4 + a * 5.0e-1
// zero_exp = 5e0
// big = 1e100
//
// --------------- Не валидно --------------
// x = a + +
// y = (a + b
// z = a ** b
// z = a - b
// 123 = a + b
// neg = -2.7e-3
// x = 1e
// y = 2.5e
// z = 3e+
// b = 1.2.3e4
// c = 1e2e3
// d = 1e-+5

namespace TAP_LAP_1
{
    class DMPACore
    {
        // Поля
        private Stack<char> dmpaStack;  // Магазинная память для скобок (проверка вложенности)
        private int currentState;       // Текущее состояние автомата
        private bool isEnded;           // Флаг завершения (достигнуто конечное состояние 99)

        // Конфигурация ДМПА
        private string alphabet;                        // Допустимые символы входного алфавита
        private Dictionary<string, char> tokenPairs;    // Столбцы таблицы переходов [цепочка подходящих символов, забрать из стека]
        private int[,] nextStateTable;                  // Таблица переходов: новое состояние
        private char[,] stackActionTable;               // Таблица: что положить в стек

        // Действия
        private SemanticAnalyzer? semantic;
        private int[,] actionTable;

        public bool IsEnded => isEnded;

        // Конструктор
        public DMPACore(string _alphabet, Dictionary<string, char> _tokenPairs, int[,] _nextStateTable, char[,] _stackActionTable, int[,] _actionTable, SemanticAnalyzer? _semantic = null)
        {
            dmpaStack = new Stack<char>();
            currentState = 0;
            isEnded = false;
            alphabet = _alphabet;
            tokenPairs = _tokenPairs;
            nextStateTable = _nextStateTable;
            stackActionTable = _stackActionTable;
            actionTable = _actionTable;
            semantic = _semantic;
        }

        /// <summary>
        /// Попытка перехода по таблице переходов ДМПА с текущим символом и состоянием стека
        /// </summary>
        /// <returns>
        /// true если:
        ///        * символ в алфавите
        ///        * найдено правило в tokenPairs для текущего символа
        ///        * стек содержит ожидаемый символ (или пуст для открывающих символов)
        ///        * существует переход в таблице переходов
        /// </returns>
        public int ChangeState(char symbol)
        {
            // Если автомат уже завершил работу: ничего не делать
            if (isEnded)
                return 0;

            // Проверка корректности символа
            if (!alphabet.Contains(symbol))
            {
                Console.WriteLine("Нет такого символа в алфавите");
                return -1;
            }

            // Получение вершины стека
            char stackTop;
            // Если стек пустой: true
            bool stackIsEmpty = dmpaStack.Count == 0;

            if (stackIsEmpty)
                stackTop = '\0';              // Специальный символ для пустого стека
            else
                stackTop = dmpaStack.Peek();  // Верхний элемент стека

            // Поиск всех подходящих пар в tokenPairs
            var candidatePairs = new List<KeyValuePair<string, char>>();
            foreach (var pair in tokenPairs)
            {
                // Содержится ли символ в ключе tokenPairs
                if (pair.Key.Contains(symbol))           
                {
                    // Извлечение Value ('e', '+', '\0')
                    char tokenValue = pair.Value;

                    // Проверка условия для value
                    bool isMatch = false;
                    if (tokenValue == '\u0001')
                    {
                        isMatch = true;            // 'e' - игнорирования стека
                    }
                    else if (tokenValue == '\0')
                    {
                        isMatch = stackIsEmpty;    // '\0' - стек должен быть пуст
                    }
                    else
                    {
                        isMatch = !stackIsEmpty && stackTop == tokenValue; // Должен совпадать с вершиной
                    }

                    if (isMatch)
                    {
                        candidatePairs.Add(pair);
                    }
                }
            }

            // Если нет кандидатов - вернуть -1
            if (candidatePairs.Count == 0)
            {
                Console.WriteLine("Подходящего перехода не найдено");
                return -1;
            }

            // Для каждого кандидата проверка перехода
            KeyValuePair<string, char>? bestPair = null;
            int bestNewState = -1;
            char bestStackAction = '\0';
            int bestPairIndex = -1;

            foreach (var candidate in candidatePairs)
            {
                // Нахождение индекса пары в tokenPairs
                int pairIndex = -1;
                int currentIndex = 0;
                foreach (var pair in tokenPairs)
                {
                    if (pair.Key == candidate.Key && pair.Value == candidate.Value)
                    {
                        pairIndex = currentIndex;
                        break;
                    }
                    currentIndex++;
                }

                if (pairIndex == -1)
                    continue;

                // Проверка границы массивов
                if (currentState < 0 || currentState >= nextStateTable.GetLength(0) || // Количество строк (состояний)
                    pairIndex < 0 || pairIndex >= nextStateTable.GetLength(1))         // Количество столбцов (правил)
                    continue;

                // Получение перехода
                int candidateNewState = nextStateTable[currentState, pairIndex];
                char candidateStackAction = stackActionTable[currentState, pairIndex];

                // Если найден переход с состоянием не -1 - сохранить его
                if (candidateNewState != -1)
                {
                    bestPair = candidate;
                    bestNewState = candidateNewState;
                    bestStackAction = candidateStackAction;
                    bestPairIndex = pairIndex;
                    break;
                }
                // Если состояние -1 - продолжение поиска других вариантов
            }

            // Если не найдено ни одного перехода с состоянием не -1
            if (!bestPair.HasValue)
            {
                Console.WriteLine("Все возможные переходы ведут в состояние -1");
                return -1;
            }

            // Использование найденной лучшей пары
            var matchingPair = bestPair.Value;
            int newState = bestNewState;
            char charToPutInStack = bestStackAction;
            int gotpairIndex = bestPairIndex;

            // Вызов действия
            if (semantic != null && bestPair.HasValue)
            {
                int actionId = actionTable[currentState, gotpairIndex];

                switch (actionId)
                {
                    case 1: // Накопление символов в лексему
                        semantic.ActionAppendChar(symbol);
                        break;
                    case 2: // Обработка оператора с учётом приоритета
                        semantic.ActionOperator(symbol);
                        break;
                    case 3: // Обработка скобок
                        semantic.ActionParen(symbol);
                        break;
                    case 4: // Завершение лексемы + свёртка оставшихся операторов
                        semantic.Finalize();
                        break;
                }
            }

            // Меняем стек согласно правилам для matchingPair.Value
            if (!stackIsEmpty && matchingPair.Value != '\u0001')
            {
                // Если value не 'e' (игнорируем), делается pop
                dmpaStack.Pop();
            }

            // Кладём новый символ в стек, если нужно
            if (charToPutInStack != '\0' && charToPutInStack != '\u0001')
                dmpaStack.Push(charToPutInStack);

            Console.WriteLine($"\nСимвол: {symbol} , Символ в стеке: {stackTop}" +
                $"Состояние: {currentState} -> {newState}, \n" +
                $"Токен-пара: '{matchingPair.Key}'->'{matchingPair.Value}', " +
                $"Pop(): {(matchingPair.Value == '\0' ? "пустой"
                : (matchingPair.Value == '\u0001' ? "игнорировать" : $"забрать '{matchingPair.Value}'"))} " + 
                $"Push(): {(charToPutInStack == '\u0001' ? "игнорировать" : $"положить '{charToPutInStack}'")}");

            // Обновляем состояние
            currentState = newState;

            if (newState == 99)
            {
                isEnded = true;
                return 0;
            }

            return 1;
        }
    }

    class StringEvaluator
    {
        #region Объявление переменных
        private string _input;                           // Входной файл
        private string _alphabet;                        // Допустимые символы входного алфавита
        private Dictionary<string, char> _tokenPairs;    // Столбцы таблицы переходов [цепочка подходящих символов, забрать из стека]
        private int[,] _nextStateTable;                  // Таблица переходов: новое состояние
        private char[,] _stackActionTable;               // Таблица: что положить в стек
        private int[,] _actionTable;                     // Таблица действий
        #endregion

        /// <summary>
        /// Конструктор
        /// </summary>
        public StringEvaluator(string input)
        {
            _input = input;
        }

        /// <summary>
        /// Создание ядра
        /// </summary>
        private DMPACore CreateCore(SemanticAnalyzer? semantic = null)
        {
            return new DMPACore(
                _alphabet,
                _tokenPairs,
                _nextStateTable,
                _stackActionTable,
                _actionTable,
                semantic
            );
        }

        /// <summary>
        /// Старт из main
        /// </summary>
        public void StartReader(string alphabet, Dictionary<string, char> tokenPairs, int[,] nextStateTable, char[,] stackActionTable, int[,] actionTable)
        {
            #region Инициализация
            _alphabet = alphabet;
            _tokenPairs = tokenPairs;
            _nextStateTable = nextStateTable;
            _stackActionTable = stackActionTable;
            _actionTable = actionTable;
            #endregion

            // Создание семантического анализатора
            var semantic = new SemanticAnalyzer();
            DMPACore core = CreateCore(semantic);

            semantic.Reset();

            if (!ValidateWithDMPA(semantic))
            {
                return;
            }

            try
            {
                // Получение данных из семантического анализатора
                var symbolTable = semantic.GetSymbolTableList();         // Таблица имён
                var codeUnoptimized = semantic.GetGeneratedCode();       // Неоптимизированный код
                var codeOptimized = semantic.Optimize(codeUnoptimized);  // Оптимизированный код

                // Формирование полного отчёта
                var outputLines = new List<string>();

                // Таблица имён
                outputLines.Add("=== ТАБЛИЦА ИМЁН ===");
                outputLines.AddRange(symbolTable);
                outputLines.Add("");

                // Неоптимизированный код
                outputLines.Add("=== НЕОПТИМИЗИРОВАННЫЙ КОД ===");
                outputLines.AddRange(codeUnoptimized);
                outputLines.Add("");

                // Оптимизированный код
                outputLines.Add("=== ОПТИМИЗИРОВАННЫЙ КОД ===");
                outputLines.AddRange(codeOptimized);

                // Запись в output.txt
                File.WriteAllLines("output.txt", outputLines);
            }
            catch (Exception ex)
            {
                File.WriteAllText("output.txt", $"Ошибка генерации кода: {ex.Message}");
            }
        }

        /// <summary>
        /// Валидация ДМПА
        /// </summary>
        private bool ValidateWithDMPA(SemanticAnalyzer? semantic = null)
        {
            DMPACore core = CreateCore(semantic);

            int i = 0;
            while (i < _input.Length)
            {
                char c = _input[i];
                int result = core.ChangeState(c);
                if (result == -1)
                {
                    Console.WriteLine($"Ошибка на символе '{c}' (позиция {i})");
                    File.WriteAllText("output.txt", $"Ошибка на символе '{c}' (позиция {i})");
                    return false;
                }
                if (result == 0 && core.IsEnded)
                    break;
                i++;
            }

            // ДМПА должен завершиться в состоянии 99
            return core.IsEnded;
        }
    }

    public class SemanticAnalyzer
    {
        #region Объявление переменных
        public Dictionary<string, SymbolInfo> SymbolTable { get; } = new();   // Таблица символов
        private Stack<char> opStack = new();                                  // Стек операторов для shunting-yard
        private Stack<string> codeStack = new();                              // Стек для построения кода/AST
        private StringBuilder lexeme = new();                                 // Текущая лексема
        private string? assignmentLhs;                                        // Левая часть присваивания
        private int tempCounter = 0;                                          // Счётчик
        private bool expectingLhs = true;
        private bool lhsAssigned = false;
        public record SymbolInfo(SymbolType Type);                            // Переменная или константа
        public enum SymbolType                                                // Тип символа (Переменная или константа)
        { 
            Variable, 
            Constant 
        }
        #endregion

        /// <summary>
        /// Приоритет операторов
        /// </summary>
        private int Priority(char op) => op switch
        {
            '*' => 2,
            '+' => 1,
            '=' => 0,
            _ => -1
        };

        /// <summary>
        /// Проверка число ли это
        /// </summary>
        private static bool IsNumber(string s)
        {
            if (string.IsNullOrWhiteSpace(s)) 
                return false;
            bool hasDigit = false, hasDot = false, hasE = false;

            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (char.IsDigit(c)) 
                    hasDigit = true;
                else if (c == '.')
                {
                    if (hasDot || hasE) 
                        return false;

                    hasDot = true;
                }
                else if (c == 'e' || c == 'E')
                {
                    if (hasE) 
                        return false;

                    hasE = true;
                }
                else if (c == '+' || c == '-')
                {
                    // Знак разрешён только после e/E
                    if (i > 0 && (s[i - 1] == 'e' || s[i - 1] == 'E')) 
                        continue;

                    return false;
                }
                else 
                    return false;
            }
            return hasDigit;
        }

        /// <summary>
        /// Завершение лексемы (добавление в таблицу символов и стек кода)
        /// </summary>
        private void FinishLexeme()
        {
            if (lexeme.Length == 0) return;
            string token = lexeme.ToString();

            // Добавление в таблицу символов
            if (IsNumber(token))
                SymbolTable[token] = new(SymbolType.Constant);
            else
                SymbolTable[token] = new(SymbolType.Variable);

            // Добавление в стек кода
            if (expectingLhs && !lhsAssigned && !IsNumber(token))
            {
                assignmentLhs = token;
                lhsAssigned = true;
            }
            else
            {
                string prefix = IsNumber(token) ? "=" : "";
                codeStack.Push($"LOAD {prefix}{token}");
            }

            lexeme.Clear();

            if (expectingLhs)
                expectingLhs = false;
        }

        // ===================== Действия ===================== 

        /// <summary>
        /// Action 1: накопление символа в лексему
        /// </summary>
        public void ActionAppendChar(char c)
        {
            if (c != ' ' && c != '\t' && c != '\0')
                lexeme.Append(c);
        }

        /// <summary>
        /// Action 2: обработка оператора
        /// </summary>
        public void ActionOperator(char op)
        {
            FinishLexeme();

            if (op == '=')
                return;

            // Сворачивание операторов с высшим или равным приоритетом
            while (opStack.Count > 0 && Priority(opStack.Peek()) >= Priority(op))
            {
                FoldOperator(opStack.Pop());
            }
            opStack.Push(op);
        }

        /// <summary>
        /// Action 3: обработка скобок
        /// </summary>
        public void ActionParen(char c)
        {
            if (c == '(')
            {
                opStack.Push(c);
            }
            else if (c == ')')
            {
                FinishLexeme();
                while (opStack.Count > 0 && opStack.Peek() != '(')
                {
                    FoldOperator(opStack.Pop());
                }
                if (opStack.Count > 0) 
                    opStack.Pop();
            }
        }

        /// <summary>
        /// Свёртка одного оператора
        /// </summary>
        /// <param name="op"></param>
        private void FoldOperator(char op)
        {
            // Скобки не являются операторами
            if (op == '(' || op == ')')
                return;

            if (codeStack.Count < 2) 
                return;

            string right = codeStack.Pop();
            string left = codeStack.Pop();


            tempCounter++;
            string temp = $"${tempCounter}";
            string opcode = (op == '*' ? "MPY" : "ADD");

            string code = $"{right}; STORE {temp}; {left}; {opcode} {temp}";
            codeStack.Push(code);
        }

        /// <summary>
        /// Action 4: финализация
        /// </summary>
        public void Finalize()
        {
            FinishLexeme();

            // Сворачивание оставшихся операторов
            while (opStack.Count > 0)
            {
                char op = opStack.Pop();
                if (op == '=') continue;
                FoldOperator(op);
            }

            // Добавление STORE для присваивания
            if (!string.IsNullOrEmpty(assignmentLhs) && codeStack.Count > 0)
            {
                // Проверка - нет ли уже STORE в конце
                var lastItem = codeStack.Count > 0 ? codeStack.Peek() : "";
                if (!lastItem.EndsWith($"STORE {assignmentLhs}"))
                {
                    codeStack.Push($"STORE {assignmentLhs}");
                }
            }

            // Сброс для следующего выражения
            expectingLhs = true;
            lhsAssigned = false;
        }

        /// <summary>
        /// Получение сгенерированного кода
        /// </summary>
        public List<string> GetGeneratedCode()
        {
            var result = new List<string>();

            var items = codeStack.Reverse().ToList();

            foreach (var item in items)
            {
                if (!string.IsNullOrWhiteSpace(item))
                {
                    // Разбитие по ';' и добавление каждой инструкции отдельно
                    var instructions = item.Split(';', StringSplitOptions.RemoveEmptyEntries);
                    foreach (var instr in instructions)
                    {
                        var trimmed = instr.Trim();
                        if (!string.IsNullOrEmpty(trimmed))
                            result.Add(trimmed);
                    }
                }
            }
            return result;
        }

        /// <summary>
        /// Получение таблицы символов в нужном формате
        /// </summary>
        public List<string> GetSymbolTableList() => SymbolTable.Keys.OrderBy(k => SymbolTable[k].Type == SymbolType.Variable ? 0 : 1).ThenBy(k => k).ToList();

        /// <summary>
        /// Сброс счётчика при начале нового выражения
        /// </summary>
        public void Reset()
        {
            opStack.Clear();
            codeStack.Clear();
            lexeme.Clear();
            assignmentLhs = null;
            tempCounter = 0;
            expectingLhs = true;
            lhsAssigned = false;
        }

        /// <summary>
        /// Оптимизация сгенерированного кода (4 правила с методички)
        /// </summary>
        public List<string> Optimize(List<string> unoptimizedCode)
        {
            var code = new List<string>(unoptimizedCode);

            var tempToConstant = new Dictionary<string, string>();

            for (int i = 0; i < code.Count - 1; i++)
            {
                // Поиск шаблона: LOAD =const; STORE $temp
                if (code[i].StartsWith("LOAD =") && code[i + 1].StartsWith("STORE $"))
                {
                    string constant = code[i].Substring(5).Trim();
                    string temp = code[i + 1].Split(' ')[1];

                    if (!IsTempOverwritten(code, temp, i + 1))
                        tempToConstant[temp] = constant;
                }
            }

            // Применение оптимизаций
            var optimized = new List<string>();
            var skipNext = false;

            for (int i = 0; i < code.Count; i++)
            {
                if (skipNext)
                {
                    skipNext = false;
                    continue;
                }

                string line = code[i];

                // Правило 4 - пропуск LOAD =const; STORE $temp, если $temp подставлен
                if (line.StartsWith("LOAD =") && i + 1 < code.Count && code[i + 1].StartsWith("STORE $"))
                {
                    string temp = code[i + 1].Split(' ')[1];
                    if (tempToConstant.ContainsKey(temp))
                    {
                        skipNext = true;  // Пропустить и LOAD, и STORE
                        continue;
                    }
                }

                // Правило 3 - пропуск STORE $x; LOAD $x, если $x не используется после
                if (line.StartsWith("STORE $") && i + 1 < code.Count)
                {
                    string temp = line.Split(' ')[1];
                    string nextLine = code[i + 1];

                    if (nextLine == $"LOAD {temp}" && !IsTempUsedAfter(code, temp, i + 1))
                    {
                        skipNext = true;  // Пропустить STORE и LOAD
                        continue;
                    }
                }

                // Правило 4 - подстановка констант в операнды
                foreach (var kvp in tempToConstant)
                {
                    if (line.Contains($" {kvp.Key}") && !line.StartsWith($"STORE {kvp.Key}"))
                        line = line.Replace($" {kvp.Key}", $" {kvp.Value}");
                }

                // Правила 1 и 2 - коммутативность (константа справа)
                line = ApplyCommutativeOptimization(line);

                optimized.Add(line);
            }

            return optimized;
        }

        /// <summary>
        /// Проверка - перезаписывается ли $temp позже другим STORE
        /// </summary>
        private bool IsTempOverwritten(List<string> code, string temp, int startIndex)
        {
            for (int i = startIndex + 1; i < code.Count; i++)
            {
                if (code[i].StartsWith($"STORE {temp}"))
                    return true;  // Найдена перезапись — нельзя оптимизировать
            }
            return false;  // Не перезаписывается — можно оптимизировать
        }

        /// <summary>
        /// Проверка - используется ли $temp после позиции (кроме STORE)
        /// </summary>
        private bool IsTempUsedAfter(List<string> code, string temp, int startIndex)
        {
            for (int i = startIndex + 1; i < code.Count; i++)
            {
                string line = code[i];
                if (line.Contains($" {temp}") && !line.StartsWith($"STORE {temp}"))
                    return true;  // Используется как операнд
            }
            return false;
        }

        /// <summary>
        /// Правило 1 и 2 - коммутативность
        /// </summary>
        private string ApplyCommutativeOptimization(string line)
        {
            if (line.Contains(" ADD ") || line.Contains(" MPY "))
            {
                string[] parts = line.Split(new[] { "; " }, StringSplitOptions.None);
                if (parts.Length >= 2)
                {
                    string loadPart = parts[0].Trim();
                    string opPart = parts[1].Trim();

                    bool isAdd = opPart.StartsWith("ADD");
                    bool isMpy = opPart.StartsWith("MPY");

                    if ((isAdd || isMpy) && loadPart.StartsWith("LOAD "))
                    {
                        string loadOperand = loadPart.Substring(5).Trim();
                        string opOperand = opPart.Split(' ')[1];

                        // Если левый операнд — константа, меняется порядок
                        if (loadOperand.StartsWith("=") && !opOperand.StartsWith("="))
                        {
                            string opcode = isAdd ? "ADD" : "MPY";
                            return $"LOAD {opOperand}; {opcode} {loadOperand}";
                        }
                    }
                }
            }
            return line;
        }
    }

    internal class Program
    {
        /// <summary>
        /// Входной файл
        /// </summary>
        public static string input { get; private set; }

        /// <summary>
        /// Входной файл
        /// </summary>
        public static string alphabetString = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789\t \0+-*()=.";

        /// <summary>
        /// Столбцы таблицы переходов[цепочка подходящих символов, забрать из стека]
        /// </summary>
        public static readonly Dictionary<string, char> tokenPairs = new Dictionary<string, char>
        {
            { " \t\n\r", '\u0001' },
            { "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_", '\u0001' },
            { "0123456789", '\u0001' },
            { "=", '\u0001' },
            { ".", '\u0001' },
            { "eE", '\u0001' },
            { "+-", '\u0001' },
            { "(", '\u0001' },
            { ")", '+' },
            { "+*", '\u0001' },
            { "\0", '\0' }
        };

        /// <summary>
        /// Таблицы переходов: (новое состояние, положить в стек), получив текущее состояние и столбец перехода
        /// </summary>
        public static int[,] nextStateTable = new int[11, 11]
        {
                // ' '  a-z  0-9   =   .    eE   +-   (    )    +*  HALT
                {   0,   1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  99 },//q0
                {   3,   1,   1,   2,  -1,  -1,  -1,  -1,  -1,  -1,  -1 },//q1
                {   2,   4,   5,  -1,  -1,  -1,  -1,  2,   -1,  -1,  -1 },//q2
                {   3,  -1,  -1,   2,  -1,  -1,  -1,  -1,  -1,  -1,  -1 },//q3
                {  10,   4,   4,  -1,  -1,  -1,  -1,  -1,  10,   2,  99 },//q4
                {  10,  -1,   5,  -1,   6,   7,  -1,  -1,  10,   2,  99 },//q5
                {  10,  -1,   6,  -1,  -1,   7,  -1,  -1,  10,   2,  99 },//q6
                {  -1,  -1,   9,  -1,  -1,  -1,   8,  -1,  -1,  -1,  -1 },//q7
                {  -1,  -1,   9,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1 },//q8
                {  10,  -1,   9,  -1,  -1,  -1,  -1,  -1,  10,   2,  99 },//q9
                {  10,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  10,   2,  99 } //q10
        };

        /// <summary>
        /// Таблицы переходов: (новое состояние, положить в стек), получив текущее состояние и столбец перехода
        /// </summary>
        /// \u0001 - это e
        public static char[,] stackActionTable =
        {
                //   ' '       a-z       0-9        =         .        eE         +-        (        )         +*      HALT
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\0'},
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' },
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001',   '+',    '\u0001', '\u0001', '\u0001'},
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' },
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\0'},
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\0'},
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\0'},
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' },
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' },
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' },
                { '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001', '\u0001' }
        };

        /// <summary>
        /// Таблица семантических действий: [состояние, индекс токена] = action_id
        /// </summary>
        /// 0 = ничего
        /// 1 = накопление символов в лексему
        /// 2 = обработка оператора с учётом приоритета
        /// 3 = обработка скобок
        /// 4 = завершение лексемы + свёртка оставшихся операторов
        public static int[,] actionTable = new int[11, 11]
        {
            //    ' '  a-z  0-9   =    .    eE   +-   (    )    +*  HALT
            { 0,   1,   1,   0,   0,   0,   0,   3,   0,   0,   4 },//q0
            { 0,   1,   1,   2,   0,   0,   0,   0,   0,   0,   0 },//q1
            { 0,   1,   1,   2,   1,   1,   1,   3,   3,   2,   4 },//q2
            { 0,   0,   0,   2,   0,   0,   0,   0,   0,   0,   0 },//q3
            { 0,   1,   1,   2,   0,   0,   0,   0,   3,   2,   4 },//q4
            { 0,   0,   1,   2,   1,   1,   0,   0,   3,   2,   4 },//q5
            { 0,   0,   1,   2,   0,   1,   0,   0,   3,   2,   4 },//q6
            { 0,   0,   1,   0,   0,   0,   1,   0,   0,   0,   0 },//q7
            { 0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0 },//q8
            { 0,   0,   1,   2,   0,   0,   0,   0,   3,   2,   4 },//q9
            { 0,   0,   0,   2,   0,   0,   0,   0,   3,   2,   4 } //q10
        };

        /// <summary>
        /// Запись из входного файла
        /// </summary>
        private static void RecordInput()
        {
            try
            {
                input = File.ReadAllText("input.txt").Trim() + "\0";
            }
            catch
            {
                File.WriteAllText("output.txt", "Ошибка: не найден файл input.txt");
                return;
            }
        }

        /// <summary>
        /// Main
        /// </summary>
        static void Main()
        {
            RecordInput();

            StringEvaluator stringEvaluator = new StringEvaluator(input);
            stringEvaluator.StartReader(alphabetString, tokenPairs, nextStateTable, stackActionTable, actionTable);
        }
    }
}