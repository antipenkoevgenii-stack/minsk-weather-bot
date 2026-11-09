import telebot
import requests
from datetime import datetime, timedelta
import os

# ТВОЙ ТОКЕН ОТ BOTFATHER
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
       print("❌ ОШИБКА: Токен не найден! Проверь переменные окружения.")

# Координаты Минска
LAT = 53.9
LON = 27.5667

bot = telebot.TeleBot(TOKEN)


def get_weather_data():
    """Получает детальную погоду: сегодня, завтра, вчера"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)

    # URL для Open-Meteo API
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "windspeed_10m_max"],
        "hourly": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "wind_speed_10m",
            "wind_gusts_10m"
        ],
        "timezone": "Europe/Minsk"
    }

    # Получаем прогноз (сегодня + завтра)
    response = requests.get(url, params=params)
    forecast_data = response.json()

    # Получаем вчерашнюю погоду (архив)
    archive_url = "https://archive-api.open-meteo.com/v1/archive"
    archive_params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": yesterday.strftime("%Y-%m-%d"),
        "end_date": yesterday.strftime("%Y-%m-%d"),
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
    }

    archive_response = requests.get(archive_url, params=archive_params)
    archive_data = archive_response.json()

    return forecast_data, archive_data


def get_time_of_day(hour):
    """Определяет время суток"""
    if 6 <= hour < 12:
        return "утро"
    elif 12 <= hour < 18:
        return "день"
    elif 18 <= hour < 24:
        return "вечер"
    else:
        return "ночь"


def analyze_hourly_data(forecast_data, day_offset=0):
    """Анализирует почасовые данные и группирует по времени суток"""
    hourly = forecast_data['hourly']

    # Определяем индекс начала нужного дня
    start_index = day_offset * 24

    periods = {
        "утро": {"temp": [], "feels_like": [], "humidity": [], "wind": [], "gusts": []},
        "день": {"temp": [], "feels_like": [], "humidity": [], "wind": [], "gusts": []},
        "вечер": {"temp": [], "feels_like": [], "humidity": [], "wind": [], "gusts": []},
        "ночь": {"temp": [], "feels_like": [], "humidity": [], "wind": [], "gusts": []}
    }

    # Проходим по 24 часам нужного дня
    for i in range(24):
        idx = start_index + i
        if idx >= len(hourly['time']):
            break

        # Получаем час из временной метки
        time_str = hourly['time'][idx]
        hour = int(time_str.split('T')[1].split(':')[0])
        period = get_time_of_day(hour)

        periods[period]['temp'].append(hourly['temperature_2m'][idx])
        periods[period]['feels_like'].append(hourly['apparent_temperature'][idx])
        periods[period]['humidity'].append(hourly['relative_humidity_2m'][idx])
        periods[period]['wind'].append(hourly['wind_speed_10m'][idx])
        periods[period]['gusts'].append(hourly['wind_gusts_10m'][idx])

    return periods


def format_period_info(period_name, data):
    """Форматирует информацию о периоде времени"""
    if not data['temp']:
        return ""

    temp_min = min(data['temp'])
    temp_max = max(data['temp'])
    feels_min = min(data['feels_like'])
    feels_max = max(data['feels_like'])
    humidity_min = min(data['humidity'])
    humidity_max = max(data['humidity'])
    wind_min = min(data['wind'])
    wind_max = max(data['wind'])
    gust_min = min(data['gusts'])
    gust_max = max(data['gusts'])

    return f"""
🌅 {period_name.capitalize()}:
🌡 Температура: {temp_min}°C ... {temp_max}°C
🤔 Ощущается как: {feels_min}°C ... {feels_max}°C
💧 Влажность: {humidity_min}% ... {humidity_max}%
💨 Ветер: {wind_min} ... {wind_max} км/ч
🌬 Порывы: {gust_min} ... {gust_max} км/ч"""


def get_clothing_advice(temp_max, temp_min, precipitation, wind_speed, humidity):
    """Генерирует совет по одежде"""
    advice = []

    # По температуре
    if temp_max <= -10:
        advice.append("🧥 Зимняя куртка, теплый свитер, термобелье")
    elif temp_max <= 0:
        advice.append("🧥 Зимняя куртка, свитер, шапка обязательна")
    elif temp_max <= 10:
        advice.append("🧥 Осенняя куртка, теплый свитер")
    elif temp_max <= 18:
        advice.append("🧥 Легкая куртка или ветровка")
    else:
        advice.append("👕 Легкая одежда, футболка")

    # По осадкам
    if precipitation > 0:
        advice.append("☔ Возьми зонт или непромокаемую одежду")

    # По ветру
    if wind_speed > 20:
        advice.append("💨 Сильный ветер — нужна непродуваемая одежда")

    # По влажности
    if humidity > 80:
        advice.append("💧 Высокая влажность — может быть душно")
    elif humidity < 30:
        advice.append("🏜 Низкая влажность — пей больше воды")

    return "\n".join(advice)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Приветственное сообщение"""
    welcome_text = """
👋 Привет! Я бот для просмотра погоды в Минске.

📍 Доступные команды:
/weather - Подробная погода на сегодня (утро/день/вечер/ночь)
/tomorrow - Подробная погода на завтра
/yesterday - Погода вчера
/advice - Что надеть сегодня
/help - Помощь
    """
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['weather'])
def send_weather(message):
    """Детальная погода на сегодня"""
    try:
        forecast_data, _ = get_weather_data()

        today = datetime.now()

        # Анализируем почасовые данные для сегодня
        periods = analyze_hourly_data(forecast_data, day_offset=0)

        text = f"🌤 Погода в Минске на сегодня ({today.strftime('%d.%m')}):\n"

        for period_name in ["утро", "день", "вечер", "ночь"]:
            period_info = format_period_info(period_name, periods[period_name])
            if period_info:
                text += period_info + "\n"

        bot.reply_to(message, text)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении погоды: {e}")


@bot.message_handler(commands=['tomorrow'])
def send_tomorrow(message):
    """Детальная погода на завтра"""
    try:
        forecast_data, _ = get_weather_data()

        tomorrow = datetime.now() + timedelta(days=1)

        # Анализируем почасовые данные для завтра
        periods = analyze_hourly_data(forecast_data, day_offset=1)

        text = f"🌤 Погода в Минске на завтра ({tomorrow.strftime('%d.%m')}):\n"

        for period_name in ["утро", "день", "вечер", "ночь"]:
            period_info = format_period_info(period_name, periods[period_name])
            if period_info:
                text += period_info + "\n"

        bot.reply_to(message, text)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении погоды: {e}")


@bot.message_handler(commands=['yesterday'])
def send_yesterday(message):
    """Погода вчера"""
    try:
        _, archive_data = get_weather_data()

        yesterday = datetime.now() - timedelta(days=1)

        yest_max = archive_data['daily']['temperature_2m_max'][0]
        yest_min = archive_data['daily']['temperature_2m_min'][0]
        yest_precip = archive_data['daily']['precipitation_sum'][0]

        text = f"""
📊 Погода вчера ({yesterday.strftime('%d.%m')}):

🌡 Температура: {yest_min}°C ... {yest_max}°C
🌧 Осадки: {yest_precip} мм
        """

        bot.reply_to(message, text)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении данных: {e}")


@bot.message_handler(commands=['advice'])
def send_advice(message):
    """Совет что надеть"""
    try:
        forecast_data, archive_data = get_weather_data()

        today_max = forecast_data['daily']['temperature_2m_max'][0]
        today_min = forecast_data['daily']['temperature_2m_min'][0]
        today_precip = forecast_data['daily']['precipitation_sum'][0]
        wind_speed = forecast_data['daily']['windspeed_10m_max'][0]

        # Получаем среднюю влажность за сегодня
        periods = analyze_hourly_data(forecast_data, day_offset=0)
        all_humidity = []
        for period_data in periods.values():
            all_humidity.extend(period_data['humidity'])
        avg_humidity = sum(all_humidity) / len(all_humidity) if all_humidity else 50

        advice = get_clothing_advice(today_max, today_min, today_precip, wind_speed, avg_humidity)

        text = f"""
👔 Что надеть сегодня в Минске:

{advice}

💡 Совет: Температура от {today_min}°C до {today_max}°C
💧 Средняя влажность: {avg_humidity:.0f}%
💨 Максимальный ветер: {wind_speed} км/ч
        """

        bot.reply_to(message, text)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


if __name__ == "__main__":
    print("🤖 Бот запущен...")
    bot.polling(none_stop=True)