"""
Клиент Moodle: скачивание PDF расписания из курса через гостевой доступ.
Вход как гость (username=guest, password=guest), поиск по папкам (mod/folder), загрузка PDF.
Токен не требуется.
"""
import os
import re
import tempfile
from typing import List, Optional, Tuple
from urllib.parse import urljoin, unquote

import aiohttp

from config import MOODLE_BASE_URL, MOODLE_COURSE_ID

BASE = MOODLE_BASE_URL.rstrip("/")


async def _guest_login(session: aiohttp.ClientSession) -> None:
    """
    Выполняет гостевой вход на Moodle через веб-форму.

    Алгоритм: GET страницы логина, извлечение logintoken из HTML, POST с username=guest,
    password=guest и logintoken; cookies сохраняются в переданной session.

    Args:
        session: Открытая aiohttp ClientSession с CookieJar.

    Raises:
        aiohttp.ClientError при сетевых ошибках.
    """
    async with session.get(f"{BASE}/login/index.php") as resp:
        html = await resp.text()
    token_m = re.search(r'name="logintoken"\s+value="([^"]+)"', html)
    logintoken = token_m.group(1) if token_m else ""
    payload = {
        "username": "guest",
        "password": "guest",
        "logintoken": logintoken,
        "anchor": "",
    }
    async with session.post(f"{BASE}/login/index.php", data=payload, allow_redirects=True):
        pass  # cookies сохраняются в jar


async def _get_guest_session() -> aiohttp.ClientSession:
    """
    Создаёт aiohttp-сессию с уже выполненным гостевым входом на Moodle.

    Алгоритм: создание сессии с CookieJar и таймаутом 60 с, вызов _guest_login(session),
    возврат сессии. Вызывающий код должен закрыть сессию (await session.close()).

    Returns:
        aiohttp.ClientSession с установленными cookies гостя.

    Raises:
        Исключения из _guest_login при неудачном входе.
    """
    jar = aiohttp.CookieJar()
    timeout = aiohttp.ClientTimeout(total=60)
    session = aiohttp.ClientSession(cookie_jar=jar, timeout=timeout)
    await _guest_login(session)
    return session


def _find_folder_ids(html: str) -> List[Tuple[str, str]]:
    """
    Находит в HTML страницы курса ссылки на ресурсы типа «папка» (mod/folder).

    Алгоритм: поиск по regex всех href на mod/folder/view.php?id=<digits>;
    относительные URL превращаются в абсолютные через BASE.

    Args:
        html: Исходный HTML страницы курса Moodle.

    Returns:
        Список пар (url, folder_id), где folder_id – строка с числовым id папки.
    """
    results = []
    for m in re.finditer(
            r'href="([^"]*mod/folder/view\.php\?id=(\d+)[^"]*)"',
            html,
            re.I,
    ):
        url = m.group(1)
        if not url.startswith("http"):
            url = urljoin(BASE + "/", url)
        results.append((url, m.group(2)))
    return results


def _find_pdf_links_in_html(html: str) -> List[Tuple[str, str]]:
    """
    Извлекает из HTML ссылки на PDF-файлы.

    Алгоритм: поиск href на pluginfile.php с .pdf и прямых ссылок на .pdf;
    имя файла берётся из последнего сегмента пути и URL-декодируется.

    Args:
        html: HTML страницы (например, содержимое папки курса).

    Returns:
        Список пар (url, decoded_filename); url – полный, filename – без пути.
    """
    results = []
    for m in re.finditer(r'href="([^"]*pluginfile\.php[^"]*\.pdf[^"]*)"', html, re.I):
        url = m.group(1)
        if not url.startswith("http"):
            url = urljoin(BASE + "/", url)
        # Декодируем URL-encoded имя файла
        parts = url.split("/")
        fn_encoded = parts[-1].split("?")[0] if parts else "schedule.pdf"
        fn = unquote(fn_encoded)
        results.append((url, fn))
    # Прямые .pdf ссылки (не pluginfile)
    for m in re.finditer(r'href="([^"]+\.pdf[^"]*)"', html, re.I):
        url = m.group(1)
        if "pluginfile" in url:
            continue  # уже обработано
        if not url.startswith("http"):
            url = urljoin(BASE + "/", url)
        parts = url.split("/")
        fn_encoded = parts[-1].split("?")[0] if parts else "schedule.pdf"
        fn = unquote(fn_encoded)
        results.append((url, fn))
    return results


async def download_schedule_pdf(
        group_code: str,
        course_id: int = None,
        save_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Скачивает PDF расписания для указанной группы из курса Moodle (гостевой доступ).

    Алгоритм:
    1. Гостевой вход через _get_guest_session.
    2. GET страницы курса course/view.php?id=course_id.
    3. Поиск всех папок _find_folder_ids, для каждой папки GET страницы папки.
    4. В каждой папке поиск PDF по _find_pdf_links_in_html; сравнение имени файла
       (без .pdf) с group_code без учёта регистра; при совпадении – скачивание через
       _download_pdf. Сессия закрывается в finally.

    Args:
        group_code: Код группы (например "ИДБ-24-10"); должен совпадать с именем файла без расширения.
        course_id: ID курса Moodle; если None, берётся MOODLE_COURSE_ID из конфига.
        save_dir: Директория для сохранения файла; если None, создаётся временный файл.

    Returns:
        Путь к сохранённому PDF-файлу или None при пустом group_code, отсутствии папок/PDF
        или ошибке загрузки.
    """
    if not group_code:
        return None
    cid = course_id or MOODLE_COURSE_ID
    code_lower = group_code.strip().lower()

    session = await _get_guest_session()
    try:
        # Загрузка страницы курса
        async with session.get(f"{BASE}/course/view.php?id={cid}") as resp:
            if resp.status != 200:
                return None
            course_html = await resp.text()

        # Все папки на странице курса
        folders = _find_folder_ids(course_html)
        if not folders:
            return None

        # Обходим папки, ищем нужный PDF
        for folder_url, _fid in folders:
            async with session.get(folder_url) as resp:
                if resp.status != 200:
                    continue
                folder_html = await resp.text()

            pdf_links = _find_pdf_links_in_html(folder_html)
            for pdf_url, pdf_filename in pdf_links:
                # Сравниваем имя файла (без .pdf) с кодом группы
                name_no_ext = pdf_filename.rsplit(".", 1)[0].lower()
                if name_no_ext == code_lower:
                    # Нашли – скачиваем
                    return await _download_pdf(session, pdf_url, pdf_filename, save_dir)

        return None
    finally:
        await session.close()


async def _download_pdf(
        session: aiohttp.ClientSession,
        url: str,
        filename: str,
        save_dir: Optional[str],
) -> Optional[str]:
    """
    Скачивает файл по URL и сохраняет как PDF.

    Алгоритм: GET url с редиректами; проверка, что тело начинается с %PDF;
    при save_dir – запись в save_dir/filename, иначе создание временного файла через mkstemp.

    Args:
        session: Открытая aiohttp-сессия.
        url: URL PDF-файла.
        filename: Имя файла для сохранения (при необходимости дополняется .pdf).
        save_dir: Директория для сохранения или None для временного файла.

    Returns:
        Абсолютный путь к сохранённому файлу или None при status != 200 или не-PDF содержимом.
    """
    async with session.get(url, allow_redirects=True) as resp:
        if resp.status != 200:
            return None
        data = await resp.read()
    if not data or data[:4] != b"%PDF":
        return None
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return path
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path


# Обратная совместимость
async def download_schedule_pdf_from_moodle(
        course_id: int,
        save_dir: Optional[str] = None,
        group_code: str = "",
) -> Optional[str]:
    """
    Обёртка для обратной совместимости; делегирует в download_schedule_pdf.

    Args:
        course_id: ID курса Moodle (передаётся в download_schedule_pdf).
        save_dir: Директория сохранения.
        group_code: Код группы для поиска PDF.

    Returns:
        Путь к PDF или None (см. download_schedule_pdf).
    """
    return await download_schedule_pdf(group_code, course_id=course_id, save_dir=save_dir)
