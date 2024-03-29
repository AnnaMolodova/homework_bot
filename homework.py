import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import endpoint
import exceptions

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    filemode='w',
    format='%(asctime)s,%(levelname)s, %(message)s, %(funcName)s, %(lineno)s'
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream='sys.stbout')
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TELEGRAM_RETRY_TIME = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно отправлено в Telegram')
    except Exception:
        logger.error(f'Сообщение не отправилось: {message}')
        raise exceptions.SendMessageExeptinon


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_status = requests.get(
            endpoint.ENDPOINT, headers=HEADERS, params=params
        )
        if homework_status.status_code != HTTPStatus.OK:
            message_error = (
                f' ENDPOINT недоступен.'
                f' Ошибка: {homework_status.status_code}'
            )
            logger.error(message_error)
            raise exceptions.NoAccessToApiExeption(message_error)
        return homework_status.json()
    except json.JSONDecodeError:
        message_json = 'Ответ не преобразовался в JSON'
        logger.error(message_json)
        raise json.JSONDecodeError
    except Exception:
        message = 'Нет доступа к API'
        logger.error(message)
        raise exceptions.NoAccessToApiExeption(message)


def check_response(response):
    """Проверка API на корректность."""
    try:
        homework = response['homeworks']
    except KeyError:
        raise KeyError('Ключ homeworks не доступен')
    if not isinstance(response, dict):
        message = 'response должен быть словарем'
        logger.error(message)
        raise TypeError(message)
    if not isinstance(homework, list):
        message_error = 'homework должен быть списком'
        logger.error(message_error)
        raise TypeError(message_error)
    return homework


def parse_status(homework):
    """Извлекает из информации о домашней работе статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Статус работы не определен.'
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окруения."""
    logger.info('Проверка доступности переменных окружения')
    secret_key = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for key, value in secret_key.items():
        if value is None:
            logger.critical(
                f'Нет переменной окружения: {key}'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют важные переменные окружения')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    box_error = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get('current_date')
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != box_error:
                send_message(bot, message)
                box_error = message
                time.sleep(TELEGRAM_RETRY_TIME)
        else:
            logger.info('Сообщение отправлено')
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    main()
