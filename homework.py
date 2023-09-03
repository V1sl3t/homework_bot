import logging
import os
import sys
import time
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram.ext import Updater

from exeptions import StatusCodeisnot200

logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет наличие и доступность токинов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в телеграмм чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Выполнена отправка сообщения')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения {error}')


def get_api_answer(timestamp):
    """Делает запрос к API домашки и возращяет ответ формата JSON."""
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params={'from_date': timestamp}
                                )
        status_code = response.status_code
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise IndexError
    except Exception as error:
        logging.error(f'Ошибка при обработке ответа API: {error}')
        raise IndexError
    if status_code != 200:
        raise StatusCodeisnot200(f'Некоректный статус '
                                 f'ответа API:{status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        error_message = ('Ошибка: в овете приходит неожиданный тип данных')
        logging.error(error_message)
        raise TypeError(error_message)
    keys_list = {'homeworks': list,
                 'current_date': int}
    for key in keys_list:
        if key not in response:
            error_message = (f'Отсутствует ключ {key}')
            logging.error(error_message)
            raise KeyError(error_message)
        if not isinstance(response[key], keys_list[key]):
            error_message = ('Ошибка: в ответе приходит '
                             'иной тип данных для ключа "homeworks"')
            logging.error(error_message)
            raise TypeError(error_message)
    return True


def parse_status(homework):
    """Возращает подготовленную для отправки строку."""
    keys_list = ['homework_name', 'status']
    for key in keys_list:
        if key not in homework:
            raise KeyError(f'Отсутствует ключ {key}')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = ('Неожиданный статус домашней работы, '
                         'обнаруженный в ответе API')
        logging.error(error_message)
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    formatter = '%(asctime)s - %(levelname)s - %(message)s'
    logger.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if not check_tokens():
        logging.critical('Переменные окружения отсутсвуют')
        exit()
    logging.debug('Переменные окружения присутсвуют')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    updater = Updater(token=TELEGRAM_TOKEN)
    errors_list = []

    while True:
        try:
            response_api = get_api_answer(timestamp)
            check_response(response_api)
            homeworks = response_api['homeworks']
            for homework in homeworks:
                status_message = parse_status(homework)
                send_message(bot, status_message)
            current_date = response_api['current_date']
            timestamp = current_date if current_date else timestamp
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message not in errors_list:
                send_message(bot, message)
            errors_list.append(message)
        time.sleep(RETRY_PERIOD)
        updater.start_polling
        updater.idle


if __name__ == '__main__':
    main()
