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

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

formatter = ('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


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
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        logging.debug('Переменные окружения присутсвуют')
        return True
    else:
        logging.critical('Переменные окружения отсутсвуют')
        exit()


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
    except Exception as error:
        logging.error(f'Ошибка при обработке ответа API: {error}')
    if status_code != 200:
        raise StatusCodeisnot200(f'Некоректный статус '
                                 f'ответа API:{status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        homeworks = response['homeworks']
        current_date = response['current_date']
    except KeyError:
        logging.error('Ошибка с отсутствием ключей в ответе')
    if not isinstance(homeworks, list):
        logging.error('Ошибка: в ответе приходит '
                      'иной тип данных для ключа "homeworks"')
        raise TypeError('Ошибка: в ответе приходит '
                        'иной тип данных для ключа "homeworks"')
    if not isinstance(current_date, int):
        logging.error('Ошибка: в ответе приходит '
                      'иной тип данных для ключа "current_date"')
        raise TypeError('Ошибка: в ответе приходит '
                        'иной тип данных для ключа "current_date"')
    return True


def parse_status(homework):
    """Возращает подготовленную для отправки строку."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name"')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
    else:
        logging.error('Неожиданный статус домашней работы, '
                      'обнаруженный в ответе API')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    formatter = ('%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    updater = Updater(token=TELEGRAM_TOKEN)

    while True:
        try:
            response_api = get_api_answer(timestamp)
            if check_response(response_api):
                homeworks = response_api['homeworks']
                if homeworks:
                    for homework in homeworks:
                        status_message = parse_status(homework)
                        send_message(bot, status_message)
                else:
                    send_message(bot, 'Cписок пуст')
                current_date = response_api['current_date']
                timestamp = current_date if current_date else timestamp
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        time.sleep(RETRY_PERIOD)
        updater.start_polling
        updater.idle


if __name__ == '__main__':
    main()
