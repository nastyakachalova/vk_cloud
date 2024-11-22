from aiogram.fsm.state import State, StatesGroup


class WeatherStates(StatesGroup):
    city = State()
    days = State()
