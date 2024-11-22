import aiohttp
import aiosqlite
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from aiogram import Router, F, html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from config import API_WEATHER_TOKEN
from states import WeatherStates
from keyboards import main_menu_keyboard

weather_router = Router()
db_connection = None

async def init_db():
    global db_connection
    if db_connection is None:
        db_connection = await aiosqlite.connect('requests.db')
        await create_tables()

async def create_tables():
    async with db_connection.cursor() as cursor:
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                request_time TEXT NOT NULL
            )
        """)
        await db_connection.commit()

async def log_weather_request(city: str, user_id: int):
    global db_connection
    await init_db()
    async with db_connection.cursor() as cursor:
        await cursor.execute(
            "INSERT INTO requests (user_id, city, request_time) VALUES (?, ?, ?)",
            (user_id, city, datetime.now().isoformat())
        )
        await db_connection.commit()

@weather_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(WeatherStates.city)
    await message.answer(
        text=''.join(['Здравствуй, ', message.from_user.first_name,
                      '!\nЯ Бот, который поможет тебе узнать погоду в любом городе планеты!',
                      '\nВ каком городе ты хочешь узнать погоду?'
                      ]),
        reply_markup=ReplyKeyboardRemove()
    )

@weather_router.message(Command('city'))
async def cmd_choose_city(message: Message, state: FSMContext) -> None:
    await state.set_state(WeatherStates.city)
    await message.answer(
        text='Выберите город, для которого хотите узнать погоду:',
        reply_markup=ReplyKeyboardRemove()
    )

@weather_router.message(WeatherStates.city)
async def process_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    await state.update_data(city=city)
    await state.set_state(WeatherStates.days)
    await message.answer(
        text='Отлично! Желаете узнать прогноз погоды на сегодняшний день или на неделю?',
        reply_markup=main_menu_keyboard()
    )

@weather_router.message(WeatherStates.days, F.text.casefold() == "погода сегодня")
async def get_today_weather(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city = data.get("city")
    weather_data = await fetch_weather(city)

    if weather_data:
        await message.answer(
            text=f"Погода в городе {html.quote(city)} сегодня:\n"
                 f"Температура: {weather_data['temp']}°C\n"
                 f"Описание: {weather_data['description']}\n"
                 f"Влажность: {weather_data['humidity']}%\n"
                 f"Скорость ветра: {weather_data['wind_speed']} м/с"
        )
        await log_weather_request(city, message.from_user.id)  # Запись запроса в базу данных
    else:
        await message.answer("Не удалось получить данные о погоде.")

    await state.clear()

@weather_router.message(WeatherStates.days, F.text.casefold() == "прогноз погоды")
async def get_forecast_weather(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    city = data.get("city")
    forecast_data = await fetch_forecast(city)

    if forecast_data:
        forecast_message = f"Прогноз погоды в городе {html.quote(city)} на неделю:\n"
        for day in forecast_data:
            forecast_message += (
                f"{day['date']}: Температура: {day['temp']}°C, "
                f"Описание: {day['description']}\n"
            )
        await message.answer(forecast_message)
        await log_weather_request(city, message.from_user.id)  # Запись запроса в базу данных
    else:
        await message.answer("Не удалось получить данные о прогнозе погоды.")

    await state.clear()

@weather_router.message(WeatherStates.days, F.text.casefold() == "выбрать город")
async def change_city(message: Message, state: FSMContext) -> None:
    await state.set_state(WeatherStates.city)
    await message.answer(
        text='Введите новый город:',
        reply_markup=ReplyKeyboardRemove()
    )

async def fetch_weather(city: str) -> Optional[dict[str, Any]]:
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&lang=ru&units=metric&APPID={API_WEATHER_TOKEN}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    "temp": data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"]
                }
            else:
                return None

async def fetch_forecast(city: str) -> Any:
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&lang=ru&units=metric&APPID={API_WEATHER_TOKEN}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                forecast = []
                today = datetime.now()
                forecast_dates = [today + timedelta(days=i) for i in range(7)]  # Текущая дата и следующие 6 дней

                # Инициализируем словарь для хранения данных по датам
                forecast_dict = {date.date(): [] for date in forecast_dates}

                # Сбор данных по датам
                for item in data['list']:
                    dt = datetime.fromisoformat(item["dt_txt"].replace("Z", "+00:00"))
                    if dt.date() in forecast_dict:
                        forecast_dict[dt.date()].append(item["main"]["temp"])

                # Формируем прогноз
                for date in forecast_dates:
                    temps = forecast_dict[date.date()]
                    if temps:
                        avg_temp = round(sum(temps) / len(temps), 2)
                        description = data['list'][0]["weather"][0]["description"]  # Берем первое описание
                        forecast.append({
                            "date": date.strftime("%d-%m-%Y"),
                            "temp": avg_temp,
                            "description": description,
                        })

                return forecast
            else:
                return None
