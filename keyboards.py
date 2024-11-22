from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard():
    kb_list = [
        [KeyboardButton(text="Погода сегодня"), KeyboardButton(text="Прогноз погоды")],
        [KeyboardButton(text="Аналитика погоды")]
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb_list,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder='Выбери вариант из меню :)'
    )
    return keyboard
