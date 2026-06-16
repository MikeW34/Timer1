# ##Таймер с заметками(остаются сохранёнными, даже при выходе программы и их восстановление после открытия программы)
from tkinter import *
import winsound
from tkinter import ttk
from tkinter.messagebox import *
from datetime import *
import threading
import time
import json
import os

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def center_window(window, width, height):
    """Центрирует окно на экране"""
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# === КОНСТАНТЫ ДЛЯ НАСТРОЕК ===
class Config:
    WINDOW_WIDTH = 800
    WINDOW_HEIGHT = 650
    NOTIFICATION_CHECK_INTERVAL = 600  # 10 минут
    NOTIFICATION_DAYS_RANGE = (2, 3)
    BEEP_FREQUENCY = 1000
    BEEP_DURATION = 500
    TIMER_DATA_FILE = "timer_state.json"  # Файл для сохранения состояния таймера
    NOTES_DATA_FILE = "notes_data.json"   # Файл для сохранения заметок

    # Стандартные времена (в минутах)
    STANDARD_TIMES = [1, 5, 10, 15, 30, 45, 60, 90, 120]

    # Уровни сложности
    DIFFICULTY_LEVELS = ["Не важная", "Важная", "Очень Важная", "Совсем Важная"]

class TimerApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("Умный таймер со вкладками")

        # Состояние таймера
        self.time_remaining = 0
        self.is_timer_running = False
        self.timer_end_time = None  # Время окончания таймера

        # Состояние уведомлений
        self.notification_thread = None
        self.should_stop_notifications = False
        self.notified_note_ids = set()
        self.notes = []
        self.completed_notes = []  # Завершенные заметки
        self.failed_notes = []    # Просроченные заметки

        # Поток для фонового таймера
        self.timer_thread = None
        self.should_stop_timer = False

        self.setup_ui()
        self.start_notification_checker()
        self.load_timer_state()  # Загружаем состояние таймера при запуске
        self.load_notes_data()   # Загружаем заметки при запуске

    def setup_ui(self):
        """Настраивает весь пользовательский интерфейс"""
        center_window(self.root, Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)

        # Создаем вкладки
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.setup_timer_tab()
        self.setup_notes_tab()
        self.setup_completed_tab()
        self.setup_failed_tab()

        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_timer_tab(self):
        """Настраивает вкладку таймера с стандартными временами"""
        timer_frame = ttk.Frame(self.notebook)
        self.notebook.add(timer_frame, text="Таймер")

        # === СТАНДАРТНЫЕ ВРЕМЕНА ===
        standard_times_frame = LabelFrame(timer_frame, text="Быстрый выбор", padx=10, pady=10)
        standard_times_frame.pack(fill=X, padx=10, pady=10)

        # Создаем кнопки для стандартных времен
        buttons_frame = Frame(standard_times_frame)
        buttons_frame.pack()

        for i, minutes in enumerate(Config.STANDARD_TIMES):
            btn = Button(
                buttons_frame,
                text=f"{minutes} мин",
                command=lambda m=minutes: self.set_standard_time(m),
                width=8,
                height=2
            )
            btn.grid(row=i // 4, column=i % 4, padx=5, pady=5)

        # === РУЧНОЙ ВВОД ===
        manual_frame = LabelFrame(timer_frame, text="Ручной ввод", padx=10, pady=10)
        manual_frame.pack(fill=X, padx=10, pady=10)

        input_frame = Frame(manual_frame)
        input_frame.pack(pady=10)

        # Часы
        Label(input_frame, text="Часы:").grid(row=0, column=0, padx=5)
        self.hours_entry = Entry(input_frame, width=4)
        self.hours_entry.grid(row=1, column=0, padx=5)
        self.hours_entry.insert(0, "0")

        # Минуты
        Label(input_frame, text="Минуты:").grid(row=0, column=1, padx=5)
        self.minutes_entry = Entry(input_frame, width=4)
        self.minutes_entry.grid(row=1, column=1, padx=5)
        self.minutes_entry.insert(0, "0")

        # === ОТОБРАЖЕНИЕ ТАЙМЕРА ===
        self.timer_label = Label(timer_frame, text="00:00", font=("Arial", 40, "bold"))
        self.timer_label.pack(pady=20)

        # Информация о состоянии таймера
        self.timer_status_label = Label(timer_frame, text="Таймер остановлен", font=("Arial", 10))
        self.timer_status_label.pack()

        # === КНОПКИ УПРАВЛЕНИЯ ===
        button_frame = Frame(timer_frame)
        button_frame.pack(pady=20)

        self.start_button = Button(
            button_frame, text="Старт", command=self.start_timer,
            bg="lightgreen", width=12, height=2, font=("Arial", 12)
        )
        self.start_button.pack(side=LEFT, padx=10)

        self.pause_button = Button(
            button_frame, text="Пауза", command=self.pause_timer,
            bg="lightyellow", width=12, height=2, font=("Arial", 12), state=DISABLED
        )
        self.pause_button.pack(side=LEFT, padx=10)

        Button(
            button_frame, text="Сброс", command=self.reset_timer,
            bg="lightcoral", width=12, height=2, font=("Arial", 12)
        ).pack(side=LEFT, padx=10)

    def setup_notes_tab(self):
        """Настраивает вкладку заметок"""
        notes_frame = ttk.Frame(self.notebook)
        self.notebook.add(notes_frame, text="Заметки")

        # Поля ввода
        input_frame = ttk.Frame(notes_frame)
        input_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(input_frame, text="Задача:").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        self.task_entry = ttk.Entry(input_frame, width=30)
        self.task_entry.grid(row=0, column=1, padx=5, pady=5, sticky=W+E)

        ttk.Label(input_frame, text="Дата окончания:").grid(row=1, column=0, padx=5, pady=5, sticky=W)

        # Фрейм для поля даты и кнопки календаря
        date_input_frame = ttk.Frame(input_frame)
        date_input_frame.grid(row=1, column=1, padx=5, pady=5, sticky=W+E)

        self.date_entry = ttk.Entry(date_input_frame, width=18)
        self.date_entry.pack(side=LEFT, fill=X, expand=True)
        self.date_entry.insert(0, datetime.now().strftime("%d.%m.%Y %H:%M"))

        # Кнопка календаря
        self.calendar_btn = ttk.Button(date_input_frame, text="📅",
                                      command=self.open_calendar, width=3)
        self.calendar_btn.pack(side=RIGHT, padx=(5, 0))

        ttk.Label(input_frame, text="Формат: ДД.ММ.ГГГГ ЧЧ:ММ", font=("Arial", 8)).grid(
            row=1, column=2, padx=5, pady=5)
        self.create_tooltip(self.calendar_btn, "Открыть календарь для выбора даты и времени")

        # Уровень сложности
        ttk.Label(input_frame, text="Сложность:").grid(row=2, column=0, padx=5, pady=5, sticky=W)
        self.difficulty_var = StringVar(value=Config.DIFFICULTY_LEVELS[0])
        self.difficulty_combo = ttk.Combobox(input_frame, textvariable=self.difficulty_var,
                                           values=Config.DIFFICULTY_LEVELS, state="readonly", width=15)
        self.difficulty_combo.grid(row=2, column=1, padx=5, pady=5, sticky=W)

        # Прогресс
        ttk.Label(input_frame, text="Прогресс:").grid(row=3, column=0, padx=5, pady=5, sticky=W)
        self.progress_var = IntVar(value=0)
        self.progress_scale = ttk.Scale(input_frame, from_=0, to=100, variable=self.progress_var,
                                      orient=HORIZONTAL, length=200)
        self.progress_scale.grid(row=3, column=1, padx=5, pady=5, sticky=W+E)
        self.progress_label = ttk.Label(input_frame, text="0%")
        self.progress_label.grid(row=3, column=2, padx=5, pady=5)

        # Кнопки заметок
        button_frame = ttk.Frame(notes_frame)
        button_frame.pack(fill=X, padx=10, pady=5)

        ttk.Button(button_frame, text="Добавить заметку",
                  command=self.add_note).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Конвертировать в часы",
                  command=self.convert_to_hours).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Удалить заметку",
                  command=self.delete_note).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Добавить подзадачу",
                  command=self.add_subtask).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Отметить как выполненную",
                  command=self.mark_as_completed).pack(side=LEFT, padx=5)

        # Таблица заметок
        columns = ("№", "Задача", "Дата окончания", "Осталось времени", "Сложность", "Прогресс", "Подзадачи")
        self.notes_tree = ttk.Treeview(notes_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.notes_tree.heading(col, text=col)
            self.notes_tree.column(col, width=80)

        self.notes_tree.column("Задача", width=150)
        self.notes_tree.column("Дата окончания", width=120)
        self.notes_tree.column("Подзадачи", width=100)

        self.notes_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Фрейм для подзадач
        subtask_frame = LabelFrame(notes_frame, text="Подзадачи", padx=10, pady=10)
        subtask_frame.pack(fill=X, padx=10, pady=5)

        ttk.Label(subtask_frame, text="Подзадача:").pack(side=LEFT, padx=5)
        self.subtask_entry = ttk.Entry(subtask_frame, width=30)
        self.subtask_entry.pack(side=LEFT, padx=5)

        self.subtasks_listbox = Listbox(subtask_frame, height=4)
        self.subtasks_listbox.pack(side=LEFT, padx=5, fill=X, expand=True)

        # Привязываем обработчик выбора заметки
        self.notes_tree.bind("<<TreeviewSelect>>", self.on_note_select)

        # Настройка валидации даты
        vcmd = (self.root.register(self.validate_date), '%P')
        self.date_entry.config(validate="key", validatecommand=vcmd)
        # Привязываем проверку при потере фокуса
        self.date_entry.bind('<FocusOut>', self.validate_date_entry)

    def validate_date(self, new_text):
        """Валидация ввода даты в реальном времени"""
        if not new_text:
            return True

        # Разрешаем только цифры, точки, двоеточия и пробелы
        allowed_chars = set('0123456789. :')
        if all(c in allowed_chars for c in new_text):
            # Ограничиваем длину
            if len(new_text) <= 16:
                return True
        return False

    def open_calendar(self):
        """Открывает всплывающий календарь с выбором времени"""
        current_date = self.date_entry.get().strip()

        # Создаем попап календаря
        calendar = CalendarPopup(self.root, current_date)

        # Ждем закрытия календаря
        self.root.wait_window(calendar.top)

        # Получаем результат
        result = calendar.get_result()
        if result:
            self.date_entry.delete(0, END)
            self.date_entry.insert(0, result)

    def create_tooltip(self, widget, text):
        """Создает всплывающую подсказку"""
        tooltip = None

        def on_enter(event):
            nonlocal tooltip
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25

            tooltip = Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = Label(tooltip, text=text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Arial", 8, "normal"))
            label.pack()

        def on_leave(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def validate_date_entry(self, event=None):
        """Валидация введенной даты"""
        date_str = self.date_entry.get().strip()
        if date_str:
            try:
                datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                self.date_entry.config(foreground="black")
            except ValueError:
                self.date_entry.config(foreground="red")

    def setup_completed_tab(self):
        """Настраивает вкладку выполненных заметок"""
        completed_frame = ttk.Frame(self.notebook)
        self.notebook.add(completed_frame, text="Завершённые")

        columns = ("№", "Задача", "Дата создания", "Дата завершения", "Сложность")
        self.completed_tree = ttk.Treeview(completed_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.completed_tree.heading(col, text=col)
            self.completed_tree.column(col, width=100)

        self.completed_tree.column("Задача", width=200)

        self.completed_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Кнопки для управления выполненными заметками
        completed_buttons = ttk.Frame(completed_frame)
        completed_buttons.pack(fill=X, padx=10, pady=5)

        ttk.Button(completed_buttons, text="Удалить выполненную",
                  command=self.delete_completed).pack(side=LEFT, padx=5)
        ttk.Button(completed_buttons, text="Вернуть в активные",
                  command=self.restore_from_completed).pack(side=LEFT, padx=5)

    def setup_failed_tab(self):
        """Настраивает вкладку несделанных заметок"""
        failed_frame = ttk.Frame(self.notebook)
        self.notebook.add(failed_frame, text="Активные" "")

        columns = ("№", "Задача", "Дата создания", "Дата окончания", "Сложность", "Причина")
        self.failed_tree = ttk.Treeview(failed_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.failed_tree.heading(col, text=col)
            self.failed_tree.column(col, width=100)

        self.failed_tree.column("Задача", width=150)
        self.failed_tree.column("Причина", width=150)

        self.failed_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Кнопки для управления несделанными заметками
        failed_buttons = ttk.Frame(failed_frame)
        failed_buttons.pack(fill=X, padx=10, pady=5)

        ttk.Button(failed_buttons, text="Удалить несделанную",
                  command=self.delete_failed).pack(side=LEFT, padx=5)
        ttk.Button(failed_buttons, text="Вернуть в активные",
                  command=self.restore_from_failed).pack(side=LEFT, padx=5)

    def save_notes_data(self):
        """Сохраняет все заметки в файл"""
        try:
            notes_data = {
                "active_notes": self.serialize_notes(self.notes),
                "completed_notes": self.serialize_notes(self.completed_notes),
                "failed_notes": self.serialize_notes(self.failed_notes)
            }

            with open(Config.NOTES_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(notes_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Ошибка сохранения заметок: {e}")

    def load_notes_data(self):
        """Загружает заметки из файла при запуске"""
        try:
            if os.path.exists(Config.NOTES_DATA_FILE):
                with open(Config.NOTES_DATA_FILE, 'r', encoding='utf-8') as f:
                    notes_data = json.load(f)

                # Восстанавливаем заметки из JSON
                self.notes = self.deserialize_notes(notes_data.get("active_notes", []))
                self.completed_notes = self.deserialize_notes(notes_data.get("completed_notes", []))
                self.failed_notes = self.deserialize_notes(notes_data.get("failed_notes", []))

                # Обновляем интерфейс после загрузки
                self.update_notes_list()
                self.update_completed_list()
                self.update_failed_list()

        except Exception as e:
            print(f"Ошибка загрузки заметок: {e}")

    def serialize_notes(self, notes_list):
        """Конвертирует заметки в формат для JSON"""
        serialized = []
        for note in notes_list:
            serialized_note = note.copy()

            # Конвертируем datetime объекты в строки
            if "deadline" in serialized_note:
                serialized_note["deadline"] = serialized_note["deadline"].isoformat()
            if "created" in serialized_note:
                serialized_note["created"] = serialized_note["created"].isoformat()
            if "completed_date" in serialized_note:
                serialized_note["completed_date"] = serialized_note["completed_date"].isoformat()
            if "failed_date" in serialized_note:
                serialized_note["failed_date"] = serialized_note["failed_date"].isoformat()

            serialized.append(serialized_note)

        return serialized

    def deserialize_notes(self, notes_list):
        """Восстанавливает заметки из JSON формата"""
        deserialized = []
        for note in notes_list:
            deserialized_note = note.copy()

            # Восстанавливаем datetime объекты из строк
            if "deadline" in deserialized_note:
                deserialized_note["deadline"] = datetime.fromisoformat(deserialized_note["deadline"])
            if "created" in deserialized_note:
                deserialized_note["created"] = datetime.fromisoformat(deserialized_note["created"])
            if "completed_date" in deserialized_note:
                deserialized_note["completed_date"] = datetime.fromisoformat(deserialized_note["completed_date"])
            if "failed_date" in deserialized_note:
                deserialized_note["failed_date"] = datetime.fromisoformat(deserialized_note["failed_date"])

            deserialized.append(deserialized_note)

        return deserialized

    def on_note_select(self, event):
        """Обрабатывает выбор заметки в дереве"""
        selected = self.notes_tree.selection()
        if selected:
            item = self.notes_tree.item(selected[0])
            note_index = item['values'][0] - 1

            if 0 <= note_index < len(self.notes):
                note = self.notes[note_index]
                # Обновляем прогресс
                self.progress_var.set(note.get("progress", 0))
                self.progress_label.config(text=f"{note.get('progress', 0)}%")

                # Очищаем список подзадач
                self.subtasks_listbox.delete(0, END)

                # Загружаем подзадачи
                if "subtasks" in note:
                    for subtask in note["subtasks"]:
                        status = "✓" if subtask.get("completed", False) else "○"
                        self.subtasks_listbox.insert(END, f"{status} {subtask['text']}")

    def add_note(self):
        """Добавляет новую заметку"""
        task = self.task_entry.get().strip()
        date_str = self.date_entry.get().strip()

        if not task or not date_str:
            showwarning("Ошибка", "Введите задачу и дату")
            return

        try:
            deadline = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            now = datetime.now()

            if deadline <= now:
                response = askyesno("Подтверждение",
                                  "Дата уже прошла. Все равно создать задачу?")
                if not response:
                    return

            note = {
                "task": task,
                "deadline": deadline,
                "created": now,
                "difficulty": self.difficulty_var.get(),
                "progress": self.progress_var.get(),
                "subtasks": []
            }
            self.notes.append(note)
            self.update_notes_list()
            self.save_notes_data()  # Сохраняем после добавления

            self.task_entry.delete(0, END)
            self.date_entry.delete(0, END)
            self.date_entry.insert(0, datetime.now().strftime("%d.%m.%Y %H:%M"))
            self.progress_var.set(0)
            self.progress_label.config(text="0%")

        except ValueError:
            showwarning("Ошибка",
                   "Неверный формат даты!\nИспользуйте: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                   "Или нажмите 📅 для выбора даты и времени из календаря")

    def add_subtask(self):
        """Добавляет подзадачу к выбранной заметке"""
        selected = self.notes_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите заметку для добавления подзадачи")
            return

        subtask_text = self.subtask_entry.get().strip()
        if not subtask_text:
            showwarning("Ошибка", "Введите текст подзадачи")
            return

        item = self.notes_tree.item(selected[0])
        note_index = item['values'][0] - 1

        if 0 <= note_index < len(self.notes):
            note = self.notes[note_index]

            if "subtasks" not in note:
                note["subtasks"] = []

            note["subtasks"].append({
                "text": subtask_text,
                "completed": False
            })

            # Обновляем отображение
            self.update_notes_list()
            self.on_note_select(None)  # Обновляем список подзадач
            self.save_notes_data()  # Сохраняем после добавления подзадачи

            self.subtask_entry.delete(0, END)

    def mark_as_completed(self):
        """Отмечает выбранную заметку как выполненную"""
        selected = self.notes_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите заметку для отметки как выполненной")
            return

        item = self.notes_tree.item(selected[0])
        note_index = item['values'][0] - 1

        if 0 <= note_index < len(self.notes):
            note = self.notes[note_index]

            # Проверяем, все ли подзадачи выполнены
            all_subtasks_completed = True
            if "subtasks" in note and note["subtasks"]:
                for subtask in note["subtasks"]:
                    if not subtask.get("completed", False):
                        all_subtasks_completed = False
                        break

            if not all_subtasks_completed:
                response = askyesno("Подтверждение",
                                  "Не все подзадачи выполнены. Все равно отметить как выполненную?")
                if not response:
                    return

            # Перемещаем в выполненные
            completed_note = note.copy()
            completed_note["completed_date"] = datetime.now()
            self.completed_notes.append(completed_note)

            # Удаляем из активных
            self.notes.pop(note_index)

            # Обновляем отображение
            self.update_notes_list()
            self.update_completed_list()
            self.save_notes_data()  # Сохраняем после перемещения

            showinfo("Успех", "Заметка перемещена в выполненные")

    def update_notes_list(self):
        """Обновляет список заметок в интерфейсе"""
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)

        for index, note in enumerate(self.notes):
            deadline_str = note["deadline"].strftime("%d.%m.%Y %H:%M")
            time_left = note["deadline"] - datetime.now()

            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                time_left_str = f"{days}д {hours}ч {minutes}м"
            else:
                time_left_str = "Просрочено"
                # Автоматически перемещаем в несделанные при просрочке
                self.move_to_failed(note, "Просрочено")
                continue

            # Подсчитываем подзадачи
            subtask_info = "Нет"
            if "subtasks" in note and note["subtasks"]:
                completed = sum(1 for st in note["subtasks"] if st.get("completed", False))
                subtask_info = f"{completed}/{len(note['subtasks'])}"

            self.notes_tree.insert("", "end", values=(
                index + 1,
                note["task"],
                deadline_str,
                time_left_str,
                note.get("difficulty", "Не указана"),
                f"{note.get('progress', 0)}%",
                subtask_info
            ))

    def move_to_failed(self, note, reason):
        """Перемещает заметку в несделанные"""
        failed_note = note.copy()
        failed_note["failed_date"] = datetime.now()
        failed_note["reason"] = reason
        self.failed_notes.append(failed_note)

        # Удаляем из активных
        if note in self.notes:
            self.notes.remove(note)

        # Обновляем отображение
        self.update_failed_list()
        self.save_notes_data()  # Сохраняем после перемещения

    def update_completed_list(self):
        """Обновляет список выполненных заметок"""
        for item in self.completed_tree.get_children():
            self.completed_tree.delete(item)

        for index, note in enumerate(self.completed_notes):
            created_str = note["created"].strftime("%d.%m.%Y %H:%M")
            completed_str = note["completed_date"].strftime("%d.%m.%Y %H:%M")

            self.completed_tree.insert("", "end", values=(
                index + 1,
                note["task"],
                created_str,
                completed_str,
                note.get("difficulty", "Не указана")
            ))

    def update_failed_list(self):
        """Обновляет список несделанных заметок"""
        for item in self.failed_tree.get_children():
            self.failed_tree.delete(item)

        for index, note in enumerate(self.failed_notes):
            created_str = note["created"].strftime("%d.%m.%Y %H:%M")
            deadline_str = note["deadline"].strftime("%d.%m.%Y %H:%M")

            self.failed_tree.insert("", "end", values=(
                index + 1,
                note["task"],
                created_str,
                deadline_str,
                note.get("difficulty", "Не указана"),
                note.get("reason", "Не указана")
            ))

    def delete_completed(self):
        """Удаляет выбранную выполненную заметку"""
        selected = self.completed_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите выполненную заметку для удаления")
            return

        item = self.completed_tree.item(selected[0])
        note_index = item["values"][0] - 1

        if 0 <= note_index < len(self.completed_notes):
            self.completed_notes.pop(note_index)
            self.update_completed_list()
            self.save_notes_data()  # Сохраняем после удаления

    def delete_failed(self):
        """Удаляет выбранную несделанную заметку"""
        selected = self.failed_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите несделанную заметку для удаления")
            return

        item = self.failed_tree.item(selected[0])
        note_index = item["values"][0] - 1

        if 0 <= note_index < len(self.failed_notes):
            self.failed_notes.pop(note_index)
            self.update_failed_list()
            self.save_notes_data()  # Сохраняем после удаления

    def restore_from_completed(self):
        """Восстанавливает заметку из выполненных в активные"""
        selected = self.completed_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите выполненную заметку для восстановления")
            return

        item = self.completed_tree.item(selected[0])
        note_index = item["values"][0] - 1

        if 0 <= note_index < len(self.completed_notes):
            note = self.completed_notes[note_index].copy()
            # Удаляем служебные поля
            if "completed_date" in note:
                del note["completed_date"]

            # Устанавливаем новый дедлайн (например, +7 дней от текущей даты)
            note["deadline"] = datetime.now() + timedelta(days=7)

            self.notes.append(note)
            self.completed_notes.pop(note_index)

            self.update_notes_list()
            self.update_completed_list()
            self.save_notes_data()  # Сохраняем после восстановления

    def restore_from_failed(self):
        """Восстанавливает заметку из несделанных в активные"""
        selected = self.failed_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите несделанную заметку для восстановления")
            return

        item = self.failed_tree.item(selected[0])
        note_index = item["values"][0] - 1

        if 0 <= note_index < len(self.failed_notes):
            note = self.failed_notes[note_index].copy()
            # Удаляем служебные поля
            if "failed_date" in note:
                del note["failed_date"]
            if "reason" in note:
                del note["reason"]

            # Устанавливаем новый дедлайн (например, +7 дней от текущей даты)
            note["deadline"] = datetime.now() + timedelta(days=7)

            self.notes.append(note)
            self.failed_notes.pop(note_index)

            self.update_notes_list()
            self.update_failed_list()
            self.save_notes_data()  # Сохраняем после восстановления

    def auto_update_notes_list(self):
        """Автоматически обновляет список заметок каждую минуту"""
        self.update_notes_list()
        self.root.after(60000, self.auto_update_notes_list)

    def set_standard_time(self, minutes):
        """Устанавливает стандартное время в таймер"""
        hours = minutes // 60
        remaining_minutes = minutes % 60

        self.hours_entry.delete(0, END)
        self.minutes_entry.delete(0, END)
        self.hours_entry.insert(0, str(hours))
        self.minutes_entry.insert(0, str(remaining_minutes))

        # Показываем подсказку
        if hours > 0:
            time_str = f"{hours} ч {remaining_minutes} мин"
        else:
            time_str = f"{remaining_minutes} минут"

        self.timer_status_label.config(text=f"Установлено: {time_str}")

    def start_timer(self):
        """Запускает таймер (основной или фоновый)"""
        try:
            hours = int(self.hours_entry.get() or 0)
            minutes = int(self.minutes_entry.get() or 0)

            self.time_remaining = hours * 3600 + minutes * 60

            if self.time_remaining > 0:
                self.is_timer_running = True
                self.timer_end_time = datetime.now() + timedelta(seconds=self.time_remaining)

                self.start_button.config(state=DISABLED)
                self.pause_button.config(state=NORMAL)
                self.timer_label.config(fg="green")

                # Сохраняем состояние таймера
                self.save_timer_state()

                # Запускаем обновление интерфейса
                self.update_timer_display()

                # Показываем информацию
                end_time_str = self.timer_end_time.strftime("%H:%M:%S")
                self.timer_status_label.config(text=f"Таймер запущен до {end_time_str}")

            else:
                self.timer_status_label.config(text="Введите время больше 0")
        except ValueError:
            self.timer_status_label.config(text="Ошибка: введите числа")

    def pause_timer(self):
        """Ставит таймер на паузу"""
        if self.is_timer_running:
            self.is_timer_running = False
            self.pause_button.config(text="Продолжить", bg="lightblue")
            self.timer_status_label.config(text="Таймер на паузе")
        else:
            self.is_timer_running = True
            self.pause_button.config(text="Пауза", bg="lightyellow")
            self.timer_status_label.config(text="Таймер запущен")
            self.update_timer_display()

    def reset_timer(self):
        """Сбрасывает таймер"""
        self.is_timer_running = False
        self.time_remaining = 0
        self.timer_end_time = None

        self.timer_label.config(text="00:00", fg="black")
        self.start_button.config(state=NORMAL)
        self.pause_button.config(state=DISABLED, text="Пауза", bg="lightyellow")
        self.timer_status_label.config(text="Таймер остановлен")

        # Удаляем файл состояния
        self.clear_timer_state()

    def update_timer_display(self):
        """Обновляет отображение таймера в GUI"""
        if self.time_remaining > 0 and self.is_timer_running:
            # Пересчитываем оставшееся время на случай фоновой работы
            if self.timer_end_time:
                time_left = self.timer_end_time - datetime.now()
                self.time_remaining = max(0, int(time_left.total_seconds()))

            hours = self.time_remaining // 3600
            minutes = (self.time_remaining % 3600) // 60
            seconds = self.time_remaining % 60

            if hours > 0:
                self.timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

            # Меняем цвет при малом остатке времени
            if self.time_remaining <= 300:  # 5 минут
                self.timer_label.config(fg="red")
            elif self.time_remaining <= 600:  # 10 минут
                self.timer_label.config(fg="orange")

            self.root.after(1000, self.update_timer_display)
        elif self.time_remaining <= 0 and self.is_timer_running:
            # Таймер завершился
            self.timer_label.config(text="00:00", fg="blue")
            self.play_timer_sound()
            self.is_timer_running = False
            self.start_button.config(state=NORMAL)
            self.pause_button.config(state=DISABLED)
            self.timer_status_label.config(text="Время вышло!")

            # Показываем уведомление
            self.show_timer_notification()

            # Очищаем состояние
            self.clear_timer_state()

    def play_timer_sound(self):
        """Проигрывает звук окончания таймера"""
        try:
            for _ in range(5):  # Более настойчивый звук
                winsound.Beep(Config.BEEP_FREQUENCY, Config.BEEP_DURATION)
                time.sleep(0.3)
        except:
            print("ТАЙМЕР: Время вышло!")

    def show_timer_notification(self):
        """Показывает уведомление о завершении таймера"""
        showinfo("Таймер", "Время вышло! Таймер завершил свою работу.")

    # === МЕТОДЫ ДЛЯ ФОНОВОЙ РАБОТЫ ===

    def save_timer_state(self):
        """Сохраняет состояние таймера в файл"""
        if self.timer_end_time:
            timer_data = {
                "end_time": self.timer_end_time.isoformat(),
                "is_running": self.is_timer_running
            }

            try:
                with open(Config.TIMER_DATA_FILE, 'w') as f:
                    json.dump(timer_data, f)
            except Exception as e:
                print(f"Ошибка сохранения таймера: {e}")

    def load_timer_state(self):
        """Загружает состояние таймера из файла при запуске"""
        try:
            if os.path.exists(Config.TIMER_DATA_FILE):
                with open(Config.TIMER_DATA_FILE, 'r') as f:
                    timer_data = json.load(f)

                end_time = datetime.fromisoformat(timer_data["end_time"])
                now = datetime.now()

                if end_time > now and timer_data["is_running"]:
                    # Таймер все еще должен работать
                    self.timer_end_time = end_time
                    self.time_remaining = int((end_time - now).total_seconds())
                    self.is_timer_running = True

                    # Восстанавливаем интерфейс
                    self.start_button.config(state=DISABLED)
                    self.pause_button.config(state=NORMAL)
                    self.update_timer_display()

                    # Показываем сообщение
                    end_time_str = end_time.strftime("%H:%M:%S")
                    self.timer_status_label.config(
                        text=f"Таймер восстановлен! Завершится в {end_time_str}"
                    )

                    showinfo("Таймер",
                        f"Таймер был восстановлен! Завершится в {end_time_str}")

        except Exception as e:
            print(f"Ошибка загрузки таймера: {e}")

    def clear_timer_state(self):
        """Очищает сохраненное состояние таймера"""
        try:
            if os.path.exists(Config.TIMER_DATA_FILE):
                os.remove(Config.TIMER_DATA_FILE)
        except Exception as e:
            print(f"Ошибка очистки таймера: {e}")

    def on_closing(self):
        """Обрабатывает закрытие приложения"""
        if self.is_timer_running:
            response = askyesno(
                "Таймер работает",
                "Таймер все еще работает! Закрыть программу?\n"
                "Таймер продолжит работу в фоновом режиме и будет восстановлен при следующем запуске."
            )

            if response:
                # Сохраняем состояние и закрываем
                self.save_timer_state()
                self.save_notes_data()  # Сохраняем заметки при закрытии
                self.stop_notification_checker()
                self.root.destroy()
            else:
                # Отменяем закрытие
                return

        # Если таймер не работает, просто закрываем
        self.save_notes_data()  # Сохраняем заметки при закрытии
        self.stop_notification_checker()
        self.root.destroy()

    def convert_to_hours(self):
        """Конвертирует выбранную заметку в часы для таймера"""
        selected = self.notes_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите заметку")
            return

        item = self.notes_tree.item(selected[0])
        note_index = item['values'][0] - 1

        if 0 <= note_index < len(self.notes):
            note = self.notes[note_index]
            time_left = note["deadline"] - datetime.now()

            if time_left.total_seconds() > 0:
                total_hours = int(time_left.total_seconds() // 3600)
                total_minutes = int((time_left.total_seconds() % 3600) // 60)

                self.notebook.select(0)
                self.hours_entry.delete(0, END)
                self.minutes_entry.delete(0, END)
                self.hours_entry.insert(0, str(total_hours))
                self.minutes_entry.insert(0, str(total_minutes))

                self.timer_status_label.config(text="Время из заметки установлено в таймер")
            else:
                showwarning("Ошибка", "Время вышло")
        else:
            showwarning("Ошибка", "Неверная заметка!")

    def delete_note(self):
        """Удаляет выбранную заметку"""
        selected = self.notes_tree.selection()
        if not selected:
            showwarning("Ошибка", "Выберите заметку для удаления!")
            return

        item = self.notes_tree.item(selected[0])
        note_index = item["values"][0] - 1

        if 0 <= note_index < len(self.notes):
            if note_index in self.notified_note_ids:
                self.notified_note_ids.remove(note_index)

            self.notes.pop(note_index)
            self.update_notes_list()
            self.save_notes_data()  # Сохраняем после удаления

    def check_for_notifications(self):
        """Проверяет, нужно ли показать уведомления"""
        while not self.should_stop_notifications:
            now = datetime.now()
            notifications_to_show = []

            for note_id, note in enumerate(self.notes):
                if note_id in self.notified_note_ids:
                    continue

                time_left = note["deadline"] - now
                days_left = time_left.days

                min_days, max_days = Config.NOTIFICATION_DAYS_RANGE
                if min_days <= days_left <= max_days and time_left.total_seconds() > 0:
                    notifications_to_show.append((note_id, note, days_left))
                    self.notified_note_ids.add(note_id)

            if notifications_to_show:
                self.root.after(0, lambda: self.show_notifications(notifications_to_show))

            time.sleep(Config.NOTIFICATION_CHECK_INTERVAL)

    def show_notifications(self, notifications):
        """Показывает уведомления пользователю"""
        for note_id, note, days_left in notifications:
            message = (
                f"Напоминание о заметке!\n"
                f"Задача: {note['task']}\n"
                f"До окончания: {days_left} дней\n"
                f"Дата окончания: {note['deadline'].strftime('%d.%m.%Y %H:%M')}"
            )

            showinfo("Напоминание о заметке", message)

    def start_notification_checker(self):
        """Запускает фоновую проверку уведомлений"""
        self.should_stop_notifications = False
        self.notified_note_ids.clear()

        self.notification_thread = threading.Thread(
            target=self.check_for_notifications,
            daemon=True
        )
        self.notification_thread.start()

    def stop_notification_checker(self):
        """Останавливает проверку уведомлений"""
        self.should_stop_notifications = True

    def run(self):
        """Запускает приложение"""
        self.root.mainloop()

class CalendarPopup:
    def __init__(self, parent, initial_date=None):
        self.parent = parent
        self.result = None

        # Создаем окно календаря
        self.top = Toplevel(parent)
        self.top.title("Выберите дату и время")
        self.top.geometry("320x380")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        # Делаем окно модальным
        self.top.focus_set()

        # Центрируем окно
        self.center_window()

        # Устанавливаем начальную дату
        if initial_date:
            try:
                self.current_date = datetime.strptime(initial_date, "%d.%m.%Y %H:%M")
            except:
                self.current_date = datetime.now()
        else:
            self.current_date = datetime.now()

        self.setup_ui()

    def center_window(self):
        """Центрирует окно календаря"""
        self.top.update_idletasks()
        width = self.top.winfo_width()
        height = self.top.winfo_height()
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f'+{x}+{y}')

    def setup_ui(self):
        """Настраивает интерфейс календаря"""
        # Фрейм для навигации
        nav_frame = Frame(self.top, bg="white")
        nav_frame.pack(fill=X, padx=10, pady=10)

        # Кнопка предыдущего месяца
        self.prev_btn = Button(nav_frame, text="◀", command=self.prev_month,
                              width=3, font=("Arial", 10), bg="white")
        self.prev_btn.pack(side=LEFT)

        # Отображение текущего месяца и года
        self.month_label = Label(nav_frame, text="", font=("Arial", 12, "bold"), bg="white")
        self.month_label.pack(side=LEFT, expand=True, padx=10)

        # Кнопка следующего месяца
        self.next_btn = Button(nav_frame, text="▶", command=self.next_month,
                              width=3, font=("Arial", 10), bg="white")
        self.next_btn.pack(side=RIGHT)

        # Фрейм для дней недели
        days_frame = Frame(self.top, bg="white")
        days_frame.pack(fill=X, padx=10)

        # Заголовки дней недели
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for day in days:
            label = Label(days_frame, text=day, font=("Arial", 9, "bold"),
                         width=4, height=2, bg="lightgray")
            label.pack(side=LEFT, expand=True)

        # Фрейм для календаря
        self.calendar_frame = Frame(self.top, bg="white")
        self.calendar_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # === УЛУЧШЕННЫЙ ВВОД ВРЕМЕНИ С АВТОВЫДЕЛЕНИЕМ ===
        time_frame = LabelFrame(self.top, text="Время", padx=10, pady=10, font=("Arial", 10))
        time_frame.pack(fill=X, padx=10, pady=10)

        # Фрейм для ввода времени
        time_input_frame = Frame(time_frame)
        time_input_frame.pack(fill=X, pady=5)

        Label(time_input_frame, text="Часы:", font=("Arial", 9)).grid(row=0, column=0, padx=5)
        
        self.hours_var = StringVar(value=str(self.current_date.hour).zfill(2))
        self.hours_entry = Entry(time_input_frame, textvariable=self.hours_var, 
                                width=6, font=("Arial", 11, "bold"), justify="center",
                                relief="solid", bd=2, bg="#ffffe0", fg="black",
                                selectbackground="#4a86e8", selectforeground="white",
                                insertbackground="red", insertwidth=3,
                                highlightcolor="#4a86e8", highlightbackground="#4a86e8",
                                highlightthickness=2)
        self.hours_entry.grid(row=0, column=1, padx=5, ipady=3)
        
        # ОБРАБОТЧИКИ ДЛЯ ЧАСОВ
        def on_hours_click(e):
            self.hours_entry.focus_set()
            self.hours_entry.select_range(0, END)
            self.hours_entry.icursor(END)
        
        def on_hours_focusin(e):
            self.hours_entry.config(bg="#fffacd", relief="sunken", bd=3)
            # Не вызываем select_range здесь, чтобы не конфликтовать с кликом мыши
        
        def on_hours_focusout(e):
            self.hours_entry.config(bg="#ffffe0", relief="solid", bd=2)
        
        def on_hours_enter(e):
            if self.top.focus_get() != self.hours_entry:
                self.hours_entry.config(bg="#f0f8ff", relief="raised")
        
        def on_hours_leave(e):
            if self.top.focus_get() != self.hours_entry:
                self.hours_entry.config(bg="#ffffe0", relief="solid")
        
        # Привязываем обработчики
        self.hours_entry.bind("<Button-1>", on_hours_click)  # Левая кнопка мыши
        self.hours_entry.bind("<FocusIn>", on_hours_focusin)
        self.hours_entry.bind("<FocusOut>", on_hours_focusout)
        self.hours_entry.bind("<Enter>", on_hours_enter)
        self.hours_entry.bind("<Leave>", on_hours_leave)

        Label(time_input_frame, text=":", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=2)

        Label(time_input_frame, text="Минуты:", font=("Arial", 9)).grid(row=0, column=3, padx=5)
        
        self.minutes_var = StringVar(value=str(self.current_date.minute).zfill(2))
        self.minutes_entry = Entry(time_input_frame, textvariable=self.minutes_var,
                                  width=6, font=("Arial", 11, "bold"), justify="center",
                                  relief="solid", bd=2, bg="#ffffe0", fg="black",
                                  selectbackground="#4a86e8", selectforeground="white",
                                  insertbackground="red", insertwidth=3,
                                  highlightcolor="#4a86e8", highlightbackground="#4a86e8",
                                  highlightthickness=2)
        self.minutes_entry.grid(row=0, column=4, padx=5, ipady=3)
        
        # ОБРАБОТЧИКИ ДЛЯ МИНУТ
        def on_minutes_click(e):
            self.minutes_entry.focus_set()
            self.minutes_entry.select_range(0, END)
            self.minutes_entry.icursor(END)
        
        def on_minutes_focusin(e):
            self.minutes_entry.config(bg="#fffacd", relief="sunken", bd=3)
            # Не вызываем select_range здесь, чтобы не конфликтовать с кликом мыши
        
        def on_minutes_focusout(e):
            self.minutes_entry.config(bg="#ffffe0", relief="solid", bd=2)
        
        def on_minutes_enter(e):
            if self.top.focus_get() != self.minutes_entry:
                self.minutes_entry.config(bg="#f0f8ff", relief="raised")
        
        def on_minutes_leave(e):
            if self.top.focus_get() != self.minutes_entry:
                self.minutes_entry.config(bg="#ffffe0", relief="solid")
        
        # Привязываем обработчики
        self.minutes_entry.bind("<Button-1>", on_minutes_click)  # Левая кнопка мыши
        self.minutes_entry.bind("<FocusIn>", on_minutes_focusin)
        self.minutes_entry.bind("<FocusOut>", on_minutes_focusout)
        self.minutes_entry.bind("<Enter>", on_minutes_enter)
        self.minutes_entry.bind("<Leave>", on_minutes_leave)

        # Подсказка с улучшенным оформлением
        hint_label = Label(time_frame, text="Введите время (часы: 0-23, минуты: 0-59)", 
                          font=("Arial", 8), fg="gray", bg="white")
        hint_label.pack(pady=(5, 0))

        # Улучшенное отображение текущего выбранного времени
        self.time_display = Label(time_frame, text="", font=("Arial", 10, "bold"), 
                                 fg="blue", bg="white")
        self.time_display.pack(pady=5)
        self.update_time_display()

        # Кнопки действий
        button_frame = Frame(self.top, bg="white")
        button_frame.pack(fill=X, padx=10, pady=10)

        Button(button_frame, text="Отмена", command=self.cancel,
              width=10, height=2, bg="lightcoral", font=("Arial", 9, "bold")).pack(side=LEFT, padx=5)

        Button(button_frame, text="Сейчас", command=self.set_current_time,
              width=10, height=2, bg="lightblue", font=("Arial", 9, "bold")).pack(side=LEFT, padx=5)

        Button(button_frame, text="OK", command=self.ok,
              width=10, height=2, bg="lightgreen", font=("Arial", 9, "bold")).pack(side=RIGHT, padx=5)

        # Обновляем отображение календаря
        self.update_calendar()

        # Привязываем обработчики для обновления отображения
        self.hours_var.trace('w', self.on_time_change)
        self.minutes_var.trace('w', self.on_time_change)

        # Привязываем Enter к кнопке OK
        self.top.bind('<Return>', lambda e: self.ok())

        # Фокус на поле часов с автоматическим выделением
        self.hours_entry.focus_set()
        self.hours_entry.select_range(0, END)
        self.hours_entry.icursor(END)

        # Привязываем Tab для перехода между полями
        self.hours_entry.bind('<Tab>', lambda e: self.minutes_entry.focus_set())
        self.minutes_entry.bind('<Tab>', lambda e: self.ok())

        # Дополнительная привязка для автоматического выделения при любом клике
        self.hours_entry.bind('<FocusIn>', lambda e: self.top.after(10, lambda: self.hours_entry.select_range(0, END)))
        self.minutes_entry.bind('<FocusIn>', lambda e: self.top.after(10, lambda: self.minutes_entry.select_range(0, END)))

    def on_time_change(self, *args):
        """Обновляет отображение времени при изменении"""
        self.update_time_display()

    def update_time_display(self):
        """Обновляет отображение выбранного времени"""
        hours = self.hours_var.get()
        minutes = self.minutes_var.get()
        
        if hours and minutes:
            try:
                # Проверяем корректность времени
                h = int(hours) if hours else 0
                m = int(minutes) if minutes else 0
                
                if 0 <= h <= 23 and 0 <= m <= 59:
                    time_str = f"Выбрано время: {h:02d}:{m:02d}"
                    self.time_display.config(text=time_str, fg="green")
                else:
                    self.time_display.config(text="Некорректное время!", fg="red")
            except ValueError:
                self.time_display.config(text="Введите числа", fg="red")
        else:
            self.time_display.config(text="Введите время", fg="gray")

    def set_current_time(self):
        """Устанавливает текущее время"""
        now = datetime.now()
        self.hours_var.set(str(now.hour).zfill(2))
        self.minutes_var.set(str(now.minute).zfill(2))
        # После установки времени выделяем поле часов
        self.hours_entry.focus_set()
        self.hours_entry.select_range(0, END)

    def update_calendar(self):
        """Обновляет отображение календаря"""
        # Очищаем предыдущие кнопки
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Устанавливаем текст месяца и года
        month_names = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        month_name = month_names[self.current_date.month - 1]
        year = self.current_date.year
        self.month_label.config(text=f"{month_name} {year}")

        # Получаем первый день месяца и количество дней
        first_day = self.current_date.replace(day=1)
        days_in_month = (first_day.replace(month=first_day.month % 12 + 1, day=1) -
                        timedelta(days=1)).day

        # Определяем день недели первого дня (0-6, где 0 - понедельник)
        start_weekday = (first_day.weekday()) % 7

        # Создаем кнопки для дней
        row, col = 0, 0

        # Пустые кнопки для дней предыдущего месяца
        for _ in range(start_weekday):
            Label(self.calendar_frame, text="", width=4, height=2, bg="white").grid(
                row=row, column=col, padx=1, pady=1)
            col += 1

        # Кнопки для дней текущего месяца
        today = datetime.now().date()
        current_day = self.current_date.day

        for day in range(1, days_in_month + 1):
            btn = Button(self.calendar_frame, text=str(day), width=4, height=2,
                        command=lambda d=day: self.select_day(d),
                        font=("Arial", 9))

            # Выделяем текущий день
            if (self.current_date.year == today.year and
                self.current_date.month == today.month and
                day == today.day):
                btn.config(bg="lightblue", relief="sunken")

            # Выделяем выбранный день
            if day == current_day:
                btn.config(bg="lightgreen", relief="sunken")

            btn.grid(row=row, column=col, padx=1, pady=1)
            col += 1

            if col == 7:
                col = 0
                row += 1

    def select_day(self, day):
        """Выбирает день"""
        self.current_date = self.current_date.replace(day=day)
        self.update_calendar()

    def prev_month(self):
        """Переход к предыдущему месяцу"""
        if self.current_date.month == 1:
            self.current_date = self.current_date.replace(year=self.current_date.year-1, month=12)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month-1)
        self.update_calendar()

    def next_month(self):
        """Переход к следующему месяцу"""
        if self.current_date.month == 12:
            self.current_date = self.current_date.replace(year=self.current_date.year+1, month=1)
        else:
            self.current_date = self.current_date.replace(month=self.current_date.month+1)
        self.update_calendar()

    def ok(self):
        """Подтверждает выбор - ГЛАВНАЯ КНОПКА"""
        try:
            hours_str = self.hours_var.get()
            minutes_str = self.minutes_var.get()
            
            # Если поля пустые, используем 00
            hours = int(hours_str) if hours_str else 0
            minutes = int(minutes_str) if minutes_str else 0

            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                final_date = self.current_date.replace(hour=hours, minute=minutes, second=0)
                self.result = final_date.strftime("%d.%m.%Y %H:%M")
                self.top.destroy()
            else:
                showwarning("Ошибка", "Некорректное время! Часы: 0-23, Минуты: 0-59")
        except ValueError:
            showwarning("Ошибка", "Введите корректное время!")

    def cancel(self):
        """Отменяет выбор"""
        self.result = None
        self.top.destroy()

    def get_result(self):
        """Возвращает результат"""
        return self.result

# === ЗАПУСК ПРИЛОЖЕНИЯ ===
if __name__ == "__main__":
    app = TimerApp()
    app.run()
