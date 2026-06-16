"""Утилита: Расписание занятий с полным функционалом."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime, timedelta


class Lesson:
    """Модель занятия."""

    def __init__(self, id, name, day, start_time, end_time, lesson_type, room, status="scheduled"):
        self.id = id
        self.name = name
        self.day = day  # 0=Пн, 1=Вт, ..., 4=Пт
        self.start_time = start_time  # "HH:MM"
        self.end_time = end_time
        self.lesson_type = lesson_type  # "Лекция", "Практика", "Семинар", "Лабораторная"
        self.room = room
        self.status = status  # "scheduled", "completed", "cancelled"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "day": self.day,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "lesson_type": self.lesson_type,
            "room": self.room,
            "status": self.status
        }


class Storage:
    """Хранение данных в SQLite."""
    DB_FILE = "schedule.db"

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_FILE)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                day INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                lesson_type TEXT NOT NULL,
                room TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled'
            )
        """)
        self.conn.commit()

    def get_all_lessons(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM lessons ORDER BY day, start_time")
        rows = cursor.fetchall()
        return [Lesson(*row) for row in rows]

    def add_lesson(self, lesson):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO lessons (name, day, start_time, end_time, lesson_type, room, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
            lesson.name, lesson.day, lesson.start_time, lesson.end_time, lesson.lesson_type, lesson.room, lesson.status)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_lesson(self, lesson):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE lessons SET name=?, day=?, start_time=?, end_time=?, lesson_type=?, room=?, status=? WHERE id=?",
            (
            lesson.name, lesson.day, lesson.start_time, lesson.end_time, lesson.lesson_type, lesson.room, lesson.status,
            lesson.id)
        )
        self.conn.commit()

    def delete_lesson(self, lesson_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()


class ScheduleEngine:
    """Логика расписания."""
    DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    LESSON_TYPES = ["Лекция", "Практика", "Семинар", "Лабораторная"]

    @staticmethod
    def validate_time(start, end):
        """Проверка корректности времени."""
        try:
            s = datetime.strptime(start, "%H:%M")
            e = datetime.strptime(end, "%H:%M")
            if e <= s:
                return False, "Время конца должно быть позже времени начала"
            if (e - s).total_seconds() > 6 * 3600:
                return False, "Занятие не может длиться более 6 часов"
            return True, "OK"
        except ValueError:
            return False, "Неверный формат времени (должен быть ЧЧ:ММ)"

    @staticmethod
    def check_conflict(lessons, new_lesson, exclude_id=None):
        """Проверка пересечения с другими занятиями."""
        for lesson in lessons:
            if lesson.id == exclude_id:
                continue
            if lesson.day != new_lesson.day:
                continue
            if (new_lesson.start_time < lesson.end_time and
                    new_lesson.end_time > lesson.start_time):
                return False, f"Пересечение с '{lesson.name}' ({lesson.start_time}-{lesson.end_time})"
        return True, "OK"

    @staticmethod
    def get_next_lesson(lessons):
        """Получить следующее занятие."""
        now = datetime.now()
        current_day = now.weekday()
        current_time = now.strftime("%H:%M")

        # Ищем сегодня
        today_lessons = [l for l in lessons if l.day == current_day and l.start_time > current_time]
        if today_lessons:
            today_lessons.sort(key=lambda x: x.start_time)
            return today_lessons[0], 0

        # Ищем завтра и дальше
        for day_offset in range(1, 7):
            next_day = (current_day + day_offset) % 5  # Только будни
            day_lessons = [l for l in lessons if l.day == next_day]
            if day_lessons:
                day_lessons.sort(key=lambda x: x.start_time)
                return day_lessons[0], day_offset

        return None, -1

    @staticmethod
    def get_workload_stats(lessons):
        """Статистика нагрузки."""
        stats = {"total": len(lessons), "by_day": {}, "by_type": {}}

        for lesson in lessons:
            day_name = ScheduleEngine.DAYS[lesson.day] if lesson.day < 5 else "Другое"
            stats["by_day"][day_name] = stats["by_day"].get(day_name, 0) + 1

            ltype = lesson.lesson_type
            stats["by_type"][ltype] = stats["by_type"].get(ltype, 0) + 1

        return stats


class ScheduleManager(tk.Frame):
    """Главный виджет расписания."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg="white")
        self.storage = Storage()
        self.engine = ScheduleEngine()
        self.lessons = self.storage.get_all_lessons()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._setup_ui()
        self._refresh()
        self._start_timer()

    def _setup_ui(self):
        """Создать интерфейс."""
        # Заголовок
        title_frame = tk.Frame(self, bg="#3498db", height=60)
        title_frame.grid(row=0, column=0, sticky="ew")
        title_frame.grid_propagate(False)

        tk.Label(title_frame, text="📅 Расписание занятий",
                 font=("Arial", 20, "bold"), bg="#3498db", fg="white").pack(pady=15)

        # Таймер обратного отсчёта
        timer_frame = tk.Frame(self, bg="#f39c12", relief="ridge", bd=2)
        timer_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        self.timer_label = tk.Label(timer_frame, text="⏰ Следующее занятие: загрузка...",
                                    font=("Arial", 14, "bold"), bg="#f39c12", fg="white")
        self.timer_label.pack(pady=10)

        self.countdown_label = tk.Label(timer_frame, text="00:00:00",
                                        font=("Arial", 24, "bold"), bg="#f39c12", fg="white")
        self.countdown_label.pack()

        # Кнопки управления
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        tk.Button(btn_frame, text="➕ Добавить", command=self._add_lesson,
                  bg="#27ae60", fg="white", relief="flat", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📊 Нагрузка", command=self._show_workload,
                  bg="#9b59b6", fg="white", relief="flat", padx=20, pady=8).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🔄 Обновить", command=self._refresh,
                  bg="#3498db", fg="white", relief="flat", padx=20, pady=8).pack(side="left", padx=5)

        # Сетка расписания
        grid_frame = tk.Frame(self, bg="white")
        grid_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)

        # Заголовки дней
        header_frame = tk.Frame(grid_frame, bg="#ecf0f1")
        header_frame.grid(row=0, column=0, sticky="ew")

        tk.Label(header_frame, text="Время", bg="#ecf0f1", font=("Arial", 10, "bold"),
                 width=10).pack(side="left", padx=2)

        for day in self.engine.DAYS:
            tk.Label(header_frame, text=day[:3], bg="#ecf0f1", font=("Arial", 10, "bold"),
                     width=15).pack(side="left", padx=2)

        # Сетка
        self.grid_container = tk.Frame(grid_frame, bg="white")
        self.grid_container.grid(row=1, column=0, sticky="nsew")

    def _start_timer(self):
        """Запустить таймер обновления."""
        self._update_timer()
        self.after(1000, self._start_timer)  # Обновление каждую секунду

    def _update_timer(self):
        """Обновить обратный отсчёт."""
        next_lesson, day_offset = self.engine.get_next_lesson(self.lessons)

        if next_lesson is None:
            self.timer_label.configure(text="⏰ Нет запланированных занятий")
            self.countdown_label.configure(text="--:--:--")
            return

        now = datetime.now()
        target_day = now.date() + timedelta(days=day_offset)
        target_time = datetime.strptime(next_lesson.start_time, "%H:%M").time()
        target_dt = datetime.combine(target_day, target_time)

        delta = target_dt - now
        if delta.total_seconds() < 0:
            delta = timedelta(0)

        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)

        day_text = "сегодня" if day_offset == 0 else f"через {day_offset} дн."
        self.timer_label.configure(
            text=f"⏰ {next_lesson.name} ({next_lesson.room}) - {day_text} в {next_lesson.start_time}"
        )
        self.countdown_label.configure(
            text=f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        )

    def _refresh(self):
        """Обновить отображение."""
        self.lessons = self.storage.get_all_lessons()
        self._draw_grid()

    def _draw_grid(self):
        """Нарисовать сетку расписания."""
        for w in self.grid_container.winfo_children():
            w.destroy()

        # Временные слоты (8:00 - 20:00, шаг 1 час)
        time_slots = [f"{h:02d}:00" for h in range(8, 21)]

        for i, time_slot in enumerate(time_slots):
            row_frame = tk.Frame(self.grid_container, bg="white")
            row_frame.grid(row=i, column=0, sticky="ew", pady=1)

            # Время
            tk.Label(row_frame, text=time_slot, bg="white", font=("Arial", 9),
                     width=10).pack(side="left", padx=2)

            # Ячейки для дней
            for day in range(5):
                cell = tk.Frame(row_frame, bg="#ecf0f1", relief="ridge", bd=1,
                                width=100, height=40)
                cell.pack(side="left", padx=2, pady=1)
                cell.pack_propagate(False)

                # Найти занятие в этот слот
                for lesson in self.lessons:
                    if lesson.day == day and lesson.start_time <= time_slot < lesson.end_time:
                        self._fill_cell(cell, lesson)
                        break
                else:
                    # Пустая ячейка - клик для добавления
                    cell.bind("<Button-1>",
                              lambda e, d=day, t=time_slot: self._add_lesson(day=d, start=t))

    def _fill_cell(self, cell, lesson):
        """Заполнить ячейку занятием."""
        colors = {
            "Лекция": "#3498db",
            "Практика": "#27ae60",
            "Семинар": "#f39c12",
            "Лабораторная": "#e74c3c"
        }
        color = colors.get(lesson.lesson_type, "#95a5a6")

        cell.configure(bg=color)

        tk.Label(cell, text=lesson.name, bg=color, fg="white",
                 font=("Arial", 8, "bold")).pack(expand=True)
        tk.Label(cell, text=f"{lesson.room}", bg=color, fg="white",
                 font=("Arial", 7)).pack()

        # Клик для редактирования
        cell.bind("<Button-1>", lambda e: self._edit_lesson(lesson))
        cell.bind("<Button-3>", lambda e: self._delete_lesson(lesson))

    def _add_lesson(self, day=0, start="09:00"):
        """Добавить занятие."""
        dialog = LessonDialog(self, self.engine, self.lessons)
        if dialog.result:
            lesson = Lesson(
                None, dialog.result["name"], dialog.result["day"],
                dialog.result["start"], dialog.result["end"],
                dialog.result["type"], dialog.result["room"]
            )
            lesson.id = self.storage.add_lesson(lesson)
            self.lessons.append(lesson)
            self._refresh()
            messagebox.showinfo("Успех", "Занятие добавлено!")

    def _edit_lesson(self, lesson):
        """Редактировать занятие."""
        dialog = LessonDialog(self, self.engine, self.lessons, lesson)
        if dialog.result:
            lesson.name = dialog.result["name"]
            lesson.day = dialog.result["day"]
            lesson.start_time = dialog.result["start"]
            lesson.end_time = dialog.result["end"]
            lesson.lesson_type = dialog.result["type"]
            lesson.room = dialog.result["room"]
            self.storage.update_lesson(lesson)
            self._refresh()
            messagebox.showinfo("Успех", "Занятие обновлено!")

    def _delete_lesson(self, lesson):
        """Удалить занятие."""
        if messagebox.askyesno("Подтверждение", f"Удалить '{lesson.name}'?"):
            self.storage.delete_lesson(lesson.id)
            self._refresh()
            messagebox.showinfo("Успех", "Занятие удалено!")

    def _show_workload(self):
        """Показать статистику нагрузки."""
        stats = self.engine.get_workload_stats(self.lessons)

        window = tk.Toplevel(self)
        window.title("📊 Учебная нагрузка")
        window.geometry("600x500")

        tk.Label(window, text="📊 Статистика учебной нагрузки",
                 font=("Arial", 16, "bold")).pack(pady=10)

        # Всего занятий
        tk.Label(window, text=f"Всего занятий в неделю: {stats['total']}",
                 font=("Arial", 12)).pack(pady=5)

        # По дням
        days_frame = tk.LabelFrame(window, text="По дням недели",
                                   font=("Arial", 11, "bold"), relief="ridge", bd=2)
        days_frame.pack(fill="x", padx=20, pady=10)

        max_per_day = max(stats["by_day"].values()) if stats["by_day"] else 1

        for day in self.engine.DAYS:
            count = stats["by_day"].get(day, 0)
            bar_width = int((count / max_per_day) * 300) if max_per_day > 0 else 0

            row = tk.Frame(days_frame, bg="white")
            row.pack(fill="x", padx=10, pady=2)

            tk.Label(row, text=day, bg="white", width=12, anchor="w").pack(side="left")

            if count > 0:
                bar = tk.Frame(row, bg="#3498db", width=bar_width, height=20)
                bar.pack(side="left", padx=5)
                bar.pack_propagate(False)

            tk.Label(row, text=str(count), bg="white", font=("Arial", 10, "bold")).pack(side="left")

        # По типам
        types_frame = tk.LabelFrame(window, text="По типам занятий",
                                    font=("Arial", 11, "bold"), relief="ridge", bd=2)
        types_frame.pack(fill="x", padx=20, pady=10)

        colors = {"Лекция": "#3498db", "Практика": "#27ae60",
                  "Семинар": "#f39c12", "Лабораторная": "#e74c3c"}

        for ltype, count in stats["by_type"].items():
            row = tk.Frame(types_frame, bg="white")
            row.pack(fill="x", padx=10, pady=2)

            color = colors.get(ltype, "#95a5a6")
            tk.Label(row, text=ltype, bg="white", width=15, anchor="w").pack(side="left")

            bar = tk.Frame(row, bg=color, width=count * 30, height=20)
            bar.pack(side="left", padx=5)
            bar.pack_propagate(False)

            tk.Label(row, text=str(count), bg="white", font=("Arial", 10, "bold")).pack(side="left")

        tk.Button(window, text="Закрыть", command=window.destroy,
                  bg="#95a5a6", fg="white", relief="flat", padx=30, pady=10).pack(pady=20)


class LessonDialog(simpledialog.Dialog):
    """Диалог добавления/редактирования занятия."""

    def __init__(self, parent, engine, lessons, lesson=None):
        self.engine = engine
        self.lessons = lessons
        self.edit_lesson = lesson
        self.result = None
        super().__init__(parent, title="Редактировать занятие" if lesson else "Новое занятие")

    def body(self, master):
        tk.Label(master, text="Название:", font=("Arial", 11)).grid(row=0, sticky="w", pady=5)
        self.name_entry = tk.Entry(master, width=40, font=("Arial", 11))
        self.name_entry.grid(row=1, sticky="ew", pady=5)

        tk.Label(master, text="День недели:", font=("Arial", 11)).grid(row=2, sticky="w", pady=5)
        self.day_var = tk.IntVar(value=0)
        for i, day in enumerate(self.engine.DAYS):
            tk.Radiobutton(master, text=day, variable=self.day_var, value=i).grid(
                row=3, column=i, padx=2)

        tk.Label(master, text="Время начала:", font=("Arial", 11)).grid(row=4, sticky="w", pady=5)
        self.start_entry = tk.Entry(master, width=10, font=("Arial", 11))
        self.start_entry.grid(row=5, sticky="w", pady=5)
        self.start_entry.insert(0, "09:00")

        tk.Label(master, text="Время конца:", font=("Arial", 11)).grid(row=4, column=1, sticky="w", pady=5,
                                                                       padx=(20, 0))
        self.end_entry = tk.Entry(master, width=10, font=("Arial", 11))
        self.end_entry.grid(row=5, column=1, sticky="w", pady=5, padx=(20, 0))
        self.end_entry.insert(0, "10:30")

        tk.Label(master, text="Тип занятия:", font=("Arial", 11)).grid(row=6, sticky="w", pady=5)
        self.type_var = tk.StringVar(value="Лекция")
        type_combo = ttk.Combobox(master, textvariable=self.type_var,
                                  values=self.engine.LESSON_TYPES, state="readonly", width=35)
        type_combo.grid(row=7, sticky="ew", pady=5)

        tk.Label(master, text="Аудитория:", font=("Arial", 11)).grid(row=8, sticky="w", pady=5)
        self.room_entry = tk.Entry(master, width=40, font=("Arial", 11))
        self.room_entry.grid(row=9, sticky="ew", pady=5)

        # Заполнить если редактирование
        if self.edit_lesson:
            self.name_entry.insert(0, self.edit_lesson.name)
            self.day_var.set(self.edit_lesson.day)
            self.start_entry.delete(0, "end")
            self.start_entry.insert(0, self.edit_lesson.start_time)
            self.end_entry.delete(0, "end")
            self.end_entry.insert(0, self.edit_lesson.end_time)
            self.type_var.set(self.edit_lesson.lesson_type)
            self.room_entry.insert(0, self.edit_lesson.room)

        return self.name_entry

    def validate(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Введите название занятия")
            return False

        start = self.start_entry.get().strip()
        end = self.end_entry.get().strip()

        valid, msg = self.engine.validate_time(start, end)
        if not valid:
            messagebox.showerror("Ошибка", msg)
            return False

        # Проверка пересечений
        temp_lesson = type('obj', (object,), {
            'id': self.edit_lesson.id if self.edit_lesson else None,
            'day': self.day_var.get(),
            'start_time': start,
            'end_time': end
        })()

        valid, msg = self.engine.check_conflict(self.lessons, temp_lesson,
                                                self.edit_lesson.id if self.edit_lesson else None)
        if not valid:
            messagebox.showerror("Ошибка", msg)
            return False

        return True

    def apply(self):
        if not self.validate():
            return

        self.result = {
            "name": self.name_entry.get().strip(),
            "day": self.day_var.get(),
            "start": self.start_entry.get().strip(),
            "end": self.end_entry.get().strip(),
            "type": self.type_var.get(),
            "room": self.room_entry.get().strip()
        }