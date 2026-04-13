import re

def optimize_code(original_code, mode="textbook"):
    code = original_code

    # --- РЕГУЛЯРКИ ---

    # 1. По учебнику (меняет всё подряд)
    reg_textbook = r"(?:STORE\s+(\$\w+)\s+LOAD\s+\1)|(?:LOAD\s+(\w+)\s+(ADD|MPY)\s+(\$\w+))"

    # 2. Адекватная (разрешает перестановку ТОЛЬКО если оба операнда - временные ячейки $)
    # Или просто запрещает заменять LOAD временной переменной на LOAD константы/имени
    reg_sane = r"(?:STORE\s+(\$\w+)\s+LOAD\s+\1)|(?:LOAD\s+(\$\w+)\s+(ADD|MPY)\s+(\$\w+))"

    selected_reg = reg_textbook if mode == "textbook" else reg_sane

    def sub_func(m):
        if m.group(1):  # Правило 3 (STORE $1; LOAD $1) - всегда удаляем
            return ""
        # Правила 1-2 (Коммутативность)
        return f"LOAD {m.group(4)}\n{m.group(3)} {m.group(2)}"

    # Оптимизация 1-3
    for _ in range(3):
        code = re.sub(selected_reg, sub_func, code).strip()
        code = re.sub(r'\n\s*\n', '\n', code)

    # Правило 4 (выносим отдельно, так как оно глобальное)
    reg_4 = r"LOAD\s+(=[\d\.]+)\s+STORE\s+(\$\d+)(?=\s+LOAD)"
    m4 = re.search(reg_4, code)
    if m4:
        val, var = m4.group(1), m4.group(2)
        code = code.replace(f"LOAD {val}", "").replace(f"STORE {var}", "").replace(var, val)

    return re.sub(r'\n\s*\n', '\n', code).strip()

# --- ТЕСТ ---
raw_input = """
LOAD =0.98
STORE $2
LOAD TAX
STORE $1
LOAD PRICE
ADD $1
MPY $2
STORE COST
"""

print("--- 1. ВАРИАНТ ПО УЧЕБНИКУ (ADD PRICE) ---")
print(optimize_code(raw_input, mode="textbook"))

print("\n--- 2. АДЕКВАТНЫЙ ВАРИАНТ (БЕЗ НАРУШЕНИЯ ЛОГИКИ) ---")
print(optimize_code(raw_input, mode="sane"))